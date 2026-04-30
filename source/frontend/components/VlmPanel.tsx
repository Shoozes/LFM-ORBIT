import { useState } from "react";
import { getApiBaseUrl } from "../utils/telemetry";

export type VlmBox = { label: string; bbox: number[] };

type VlmPanelProps = {
  isOpen: boolean;
  onClose: () => void;
  activeBbox: number[] | null; // geographic bounds [west, south, east, north]
  onBoxesUpdate: (boxes: VlmBox[]) => void;
};

type GroundingResponse = {
  results?: unknown;
};

type VqaResponse = {
  answer?: unknown;
};

type CaptionResponse = {
  caption?: unknown;
};

function getErrorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}

async function readApiError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json() as { error?: unknown; detail?: unknown };
    if (typeof payload.error === "string" && payload.error.trim()) return payload.error;
    if (typeof payload.detail === "string" && payload.detail.trim()) return payload.detail;
  } catch {
    return fallback;
  }
  return fallback;
}

async function postJson<TResponse>(
  url: string,
  payload: unknown,
  fallbackError: string,
): Promise<TResponse> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, `${fallbackError} with HTTP ${response.status}.`));
  }
  return await response.json() as TResponse;
}

function isVlmBox(value: unknown): value is VlmBox {
  if (!value || typeof value !== "object") return false;
  const candidate = value as { label?: unknown; bbox?: unknown };
  return (
    typeof candidate.label === "string" &&
    Array.isArray(candidate.bbox) &&
    candidate.bbox.length === 4 &&
    candidate.bbox.every((entry) => typeof entry === "number" && Number.isFinite(entry))
  );
}

function normalizeBoxes(value: unknown): VlmBox[] {
  return Array.isArray(value) ? value.filter(isVlmBox) : [];
}

const TARGET_PRESETS = [
  "homes",
  "boats",
  "possible flaring",
  "dark smoke",
  "clearing",
  "road",
  "river",
];

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

  async function submitGrounding(rawPrompt: string) {
    const prompt = rawPrompt.trim();
    if (!activeBbox || !prompt) return;
    setLoadingGrounding(true);
    setGroundingError(null);
    try {
      const data = await postJson<GroundingResponse>(
        `${apiBaseUrl}/api/vlm/grounding`,
        { bbox: activeBbox, prompt },
        "Grounding failed",
      );
      const results = normalizeBoxes(data.results);
      setGroundingResults(results);
      onBoxesUpdate(results);
    } catch (err) {
      setGroundingError(getErrorMessage(err, "Grounding failed."));
    } finally {
      setLoadingGrounding(false);
    }
  }

  async function handleGrounding() {
    await submitGrounding(groundingPrompt);
  }

  async function runGroundingPrompt(prompt: string) {
    setGroundingPrompt(prompt);
    await submitGrounding(prompt);
  }

  async function handleVqa() {
    const question = vqaQuestion.trim();
    if (!activeBbox || !question) return;
    setLoadingVqa(true);
    setVqaError(null);
    try {
      const data = await postJson<VqaResponse>(
        `${apiBaseUrl}/api/vlm/vqa`,
        { bbox: activeBbox, question },
        "Visual Q&A failed",
      );
      setVqaAnswer(typeof data.answer === "string" ? data.answer : "No answer returned.");
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
      const data = await postJson<CaptionResponse>(
        `${apiBaseUrl}/api/vlm/caption`,
        { bbox: activeBbox },
        "Captioning failed",
      );
      setCaption(typeof data.caption === "string" ? data.caption : "No caption returned.");
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
          <span className="text-[10px] uppercase font-bold tracking-widest text-zinc-900">Visual Evidence Tools</span>
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
           Select an area on the map using the Draw Area tool to enable optional visual evidence checks.
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
                  placeholder="Find: homes, boats, possible flaring, dark smoke"
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
              <div className="flex flex-wrap gap-1.5">
                {TARGET_PRESETS.map((target) => (
                  <button
                    key={target}
                    type="button"
                    data-testid={`vlm-target-${target.replace(/\s+/g, "-")}`}
                    onClick={() => void runGroundingPrompt(`Find ${target}`)}
                    disabled={loadingGrounding}
                    className="rounded border border-zinc-200 bg-white px-2 py-1 text-[9px] font-semibold uppercase tracking-wider text-zinc-500 hover:border-zinc-300 hover:text-zinc-800 disabled:opacity-50"
                  >
                    {target}
                  </button>
                ))}
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
                           <div key={idx} data-testid="vlm-grounding-result" className="bg-white border border-zinc-200 rounded px-2 py-1 flex items-center gap-2">
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
