import { useState } from "react";
import { getApiBaseUrl } from "../utils/telemetry";

export type VlmBox = { label: string; bbox: number[] };

type VlmPanelProps = {
  isOpen: boolean;
  onClose: () => void;
  activeBbox: number[] | null; // geographic bounds [west, south, east, north]
  onBoxesUpdate: (boxes: VlmBox[]) => void;
};

function getErrorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}

export default function VlmPanel({ isOpen, onClose, activeBbox, onBoxesUpdate }: VlmPanelProps) {
  const [groundingPrompt, setGroundingPrompt] = useState("");
  const [vqaQuestion, setVqaQuestion] = useState("");
  
  const [groundingResults, setGroundingResults] = useState<VlmBox[] | null>(null);
  const [vqaAnswer, setVqaAnswer] = useState<string | null>(null);
  const [caption, setCaption] = useState<string | null>(null);
  const [groundingError, setGroundingError] = useState<string | null>(null);
  const [vqaError, setVqaError] = useState<string | null>(null);
  const [captionError, setCaptionError] = useState<string | null>(null);
  
  const [loadingGrounding, setLoadingGrounding] = useState(false);
  const [loadingVqa, setLoadingVqa] = useState(false);
  const [loadingCaption, setLoadingCaption] = useState(false);

  const apiBaseUrl = getApiBaseUrl();

  if (!isOpen) return null;

  async function handleGrounding() {
    if (!activeBbox || !groundingPrompt) return;
    setLoadingGrounding(true);
    setGroundingError(null);
    try {
      const res = await fetch(`${apiBaseUrl}/api/vlm/grounding`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bbox: activeBbox, prompt: groundingPrompt })
      });
      if (!res.ok) throw new Error(`Grounding failed with HTTP ${res.status}.`);
      const data = await res.json();
      setGroundingResults(data.results);
      onBoxesUpdate(data.results);
    } catch (err) {
      setGroundingError(getErrorMessage(err, "Grounding failed."));
    } finally {
      setLoadingGrounding(false);
    }
  }

  async function handleVqa() {
    if (!activeBbox || !vqaQuestion) return;
    setLoadingVqa(true);
    setVqaError(null);
    try {
      const res = await fetch(`${apiBaseUrl}/api/vlm/vqa`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bbox: activeBbox, question: vqaQuestion })
      });
      if (!res.ok) throw new Error(`Visual Q&A failed with HTTP ${res.status}.`);
      const data = await res.json();
      setVqaAnswer(data.answer);
    } catch (err) {
      setVqaError(getErrorMessage(err, "Visual Q&A failed."));
    } finally {
      setLoadingVqa(false);
    }
  }

  async function handleCaption() {
    if (!activeBbox) return;
    setLoadingCaption(true);
    setCaptionError(null);
    try {
      const res = await fetch(`${apiBaseUrl}/api/vlm/caption`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bbox: activeBbox })
      });
      if (!res.ok) throw new Error(`Captioning failed with HTTP ${res.status}.`);
      const data = await res.json();
      setCaption(data.caption);
    } catch (err) {
      setCaptionError(getErrorMessage(err, "Captioning failed."));
    } finally {
      setLoadingCaption(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 text-sm p-4 bg-white">
      {/* Header */}
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase font-bold tracking-widest text-zinc-900">VLM Vision</span>
        </div>
        <button 
           onClick={() => {
              onBoxesUpdate([]); // Clear boxes on close
              onClose();
           }} 
           className="text-[10px] uppercase tracking-wider text-zinc-400 hover:text-zinc-600 font-semibold"
        >✕</button>
      </div>

      {!activeBbox ? (
         <div className="rounded border border-zinc-200 bg-zinc-50 p-4 text-xs text-zinc-500 font-medium text-center">
           Select an area on the map using the Draw Area tool to enable Vision Language Models.
         </div>
      ) : (
        <>
          {/* GROUNDING CARD */}
          <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4">
            <div className="mb-3 text-[10px] uppercase tracking-wider font-semibold text-zinc-500">
              Grounding
            </div>
            <div className="flex flex-col gap-2">
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Find: clearing, road, river"
                  value={groundingPrompt}
                  onChange={e => setGroundingPrompt(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleGrounding()}
                  className="min-w-0 flex-1 rounded border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900 outline-none focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500 placeholder-zinc-400 transition"
                />
                <button
                  type="button"
                  onClick={handleGrounding}
                  disabled={!groundingPrompt.trim() || loadingGrounding}
                  className="rounded border border-zinc-300 bg-white px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 disabled:cursor-not-allowed transition"
                >
                  Find
                </button>
              </div>
              {loadingGrounding ? (
                 <p className="text-[10px] animate-pulse text-zinc-400 mt-1 uppercase font-semibold">Searching region...</p>
              ) : groundingError ? (
                 <p className="text-xs font-medium text-red-600">{groundingError}</p>
              ) : groundingResults && (
                 <div className="mt-3 space-y-2">
                    {groundingResults.length === 0 ? (
                      <p className="text-xs text-zinc-400 italic">No matches found.</p>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        {groundingResults.map((r, idx) => (
                           <div key={idx} className="bg-white border border-zinc-200 rounded px-2 py-1 flex items-center gap-2">
                              <span className="text-[10px] font-bold text-zinc-900">{r.label}</span>
                              <span className="text-[9px] text-zinc-400">[{r.bbox.map(b => b.toFixed(2)).join(", ")}]</span>
                           </div>
                        ))}
                      </div>
                    )}
                 </div>
              )}
            </div>
          </div>

          {/* VQA CARD */}
          <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4">
            <div className="mb-3 text-[10px] uppercase tracking-wider font-semibold text-zinc-500">
              Visual Q&A
            </div>
            <div className="flex flex-col gap-2">
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="What land cover is visible?"
                  value={vqaQuestion}
                  onChange={e => setVqaQuestion(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleVqa()}
                  className="min-w-0 flex-1 rounded border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900 outline-none focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500 placeholder-zinc-400 transition"
                />
                <button
                  type="button"
                  onClick={handleVqa}
                  disabled={!vqaQuestion.trim() || loadingVqa}
                  className="rounded border border-zinc-300 bg-white px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 disabled:cursor-not-allowed transition"
                >
                  Ask
                </button>
              </div>
              {loadingVqa ? (
                 <p className="text-[10px] animate-pulse text-zinc-400 mt-1 uppercase font-semibold">Processing question...</p>
              ) : vqaError ? (
                 <p className="text-xs font-medium text-red-600">{vqaError}</p>
              ) : vqaAnswer && (
                 <p className="mt-2 text-xs text-zinc-800 font-medium">{vqaAnswer}</p>
              )}
            </div>
          </div>

          {/* CAPTIONING CARD */}
          <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4">
            <div className="mb-3 flex items-center justify-between">
              <div className="text-[10px] uppercase tracking-wider font-semibold text-zinc-500">
                Captioning
              </div>
              <button 
                onClick={handleCaption}
                className="rounded border border-zinc-300 bg-white px-3 py-1.5 text-[10px] uppercase tracking-wider font-semibold text-zinc-700 hover:bg-zinc-100 transition disabled:opacity-50"
                disabled={loadingCaption}
              >
                Generate
              </button>
            </div>
            <div className="flex flex-col gap-2">
              {loadingCaption ? (
                 <p className="text-[10px] animate-pulse text-zinc-400 uppercase font-semibold">Describing scene...</p>
              ) : captionError ? (
                 <p className="text-xs font-medium text-red-600">{captionError}</p>
              ) : caption ? (
                 <p className="mt-1 text-xs text-zinc-800 font-medium leading-relaxed">{caption}</p>
              ) : (
                 <p className="text-[10px] text-zinc-400 uppercase font-semibold">Describe the scene within the selected bounds.</p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
