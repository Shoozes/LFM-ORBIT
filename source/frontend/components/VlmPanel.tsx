import { useState } from "react";
import type { ObjectTarget } from "../types/mission";
import { getApiBaseUrl } from "../utils/telemetry";

export type VlmBox = {
  label: string;
  bbox: number[];
  bbox_format?: "unit_yxyx" | "unit_xyxy";
  confidence?: number;
  color_key?: string;
  source_model?: string;
  prompt?: string;
  runtime_truth_mode?: string;
  imagery_origin?: string;
  scoring_basis?: string;
};

type VlmPanelProps = {
  isOpen: boolean;
  onClose: () => void;
  activeBbox: number[] | null; // geographic bounds [west, south, east, north]
  onBoxesUpdate: (boxes: VlmBox[]) => void;
  activeMissionTargets?: ObjectTarget[];
  targetPackId?: string | null;
};

type GroundingResponse = {
  results?: unknown;
  provenance?: unknown;
  summary?: { provenance?: unknown };
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

function readOptionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function readOptionalNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function readProvenanceString(provenance: unknown, key: string): string | undefined {
  if (!provenance || typeof provenance !== "object") return undefined;
  return readOptionalString((provenance as Record<string, unknown>)[key]);
}

function normalizeBboxFormat(value: unknown): VlmBox["bbox_format"] | undefined {
  return value === "unit_xyxy" || value === "unit_yxyx" ? value : undefined;
}

function normalizeBoxes(value: unknown, provenance?: unknown, prompt?: string): VlmBox[] {
  if (!Array.isArray(value)) return [];
  return value.filter(isVlmBox).map((box) => ({
    label: box.label,
    bbox: box.bbox.map((entry) => Math.min(1, Math.max(0, entry))),
    bbox_format: normalizeBboxFormat(box.bbox_format),
    confidence: readOptionalNumber(box.confidence),
    color_key: readOptionalString(box.color_key),
    source_model: readOptionalString(box.source_model) ?? readProvenanceString(provenance, "model"),
    prompt: readOptionalString(box.prompt) ?? prompt,
    runtime_truth_mode: readOptionalString(box.runtime_truth_mode) ?? readProvenanceString(provenance, "runtime_truth_mode"),
    imagery_origin: readOptionalString(box.imagery_origin) ?? readProvenanceString(provenance, "imagery_origin"),
    scoring_basis: readOptionalString(box.scoring_basis) ?? readProvenanceString(provenance, "scoring_basis"),
  }));
}

function formatBoxTooltip(box: VlmBox): string {
  const lines = [
    `Object: ${box.label}`,
    box.confidence !== undefined ? `Confidence: ${box.confidence.toFixed(2)}` : "Confidence: candidate",
    `BBox: [${box.bbox.map((entry) => entry.toFixed(2)).join(", ")}]`,
    box.source_model ? `Source: ${box.source_model}` : null,
    box.runtime_truth_mode ? `Mode: ${box.runtime_truth_mode}` : null,
    box.imagery_origin ? `Imagery: ${box.imagery_origin}` : null,
    box.scoring_basis ? `Basis: ${box.scoring_basis}` : null,
  ];
  return lines.filter((line): line is string => Boolean(line)).join("\n");
}

const TARGET_PRESETS = [
  "structure cluster",
  "vessel group",
  "possible flaring region",
  "dark smoke plume",
  "clearing region",
  "road corridor",
  "river reach",
];

export default function VlmPanel({
  isOpen,
  onClose,
  activeBbox,
  onBoxesUpdate,
  activeMissionTargets = [],
  targetPackId = null,
}: VlmPanelProps) {
  const [groundingPrompt, setGroundingPrompt] = useState("");
  const [vqaQuestion, setVqaQuestion] = useState("");
  
  const [groundingResults, setGroundingResults] = useState<VlmBox[] | null>(null);
  const [hoveredBoxIndex, setHoveredBoxIndex] = useState<number | null>(null);
  const [vqaAnswer, setVqaAnswer] = useState<string | null>(null);
  const [caption, setCaption] = useState<string | null>(null);
  const [groundingError, setGroundingError] = useState<string | null>(null);
  const [vqaError, setVqaError] = useState<string | null>(null);
  const [captionError, setCaptionError] = useState<string | null>(null);
  
  const [loadingGrounding, setLoadingGrounding] = useState(false);
  const [loadingVqa, setLoadingVqa] = useState(false);
  const [loadingCaption, setLoadingCaption] = useState(false);

  const apiBaseUrl = getApiBaseUrl();
  const enabledMissionTargets = activeMissionTargets.filter((target) => target.enabled);

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
      const results = normalizeBoxes(data.results, data.provenance, prompt);
      setGroundingResults(results);
      setHoveredBoxIndex(null);
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

  async function runMissionTargets() {
    if (!activeBbox || enabledMissionTargets.length === 0) return;
    setLoadingGrounding(true);
    setGroundingError(null);
    try {
      const data = await postJson<GroundingResponse>(
        `${apiBaseUrl}/api/vlm/grounding/batch`,
        {
          bbox: activeBbox,
          targets: enabledMissionTargets,
          target_pack_id: targetPackId,
          frame_ref: "current",
        },
        "Mission target grounding failed",
      );
      const results = normalizeBoxes(data.results, data.provenance ?? data.summary?.provenance, "mission targets");
      setGroundingResults(results);
      setHoveredBoxIndex(null);
      onBoxesUpdate(results);
    } catch (err) {
      setGroundingError(getErrorMessage(err, "Mission target grounding failed."));
    } finally {
      setLoadingGrounding(false);
    }
  }

  function renderBoxTooltip(box: VlmBox) {
    const rows = [
      ["Confidence", box.confidence !== undefined ? box.confidence.toFixed(2) : "candidate"],
      ["BBox", `[${box.bbox.map((entry) => entry.toFixed(2)).join(", ")}]`],
      ["Prompt", box.prompt ?? "visual grounding"],
      ["Source", box.source_model ?? "candidate evidence"],
      ["Mode", box.runtime_truth_mode ?? "unknown"],
      ["Imagery", box.imagery_origin ?? "unknown"],
      ["Basis", box.scoring_basis ?? "visual_only"],
    ];
    return (
      <div
        data-testid="vlm-result-tooltip"
        className="absolute left-0 top-full z-30 mt-2 w-72 rounded border border-cyan-200 bg-zinc-950 p-3 text-[10px] text-zinc-100 shadow-[0_0_24px_rgba(34,211,238,0.32)]"
      >
        <p className="mb-2 text-[11px] font-extrabold uppercase tracking-wider text-cyan-100">{box.label}</p>
        <div className="space-y-1.5">
          {rows.map(([label, value]) => (
            <div key={label} className="flex justify-between gap-3 border-t border-zinc-800 pt-1">
              <span className="shrink-0 font-bold uppercase tracking-wider text-zinc-400">{label}</span>
              <span className="text-right font-semibold text-zinc-100">{value}</span>
            </div>
          ))}
        </div>
      </div>
    );
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
              {enabledMissionTargets.length > 0 && (
                <div data-testid="vlm-mission-targets" className="rounded border border-cyan-100 bg-cyan-50/60 px-3 py-2">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className="text-[9px] font-bold uppercase tracking-wider text-cyan-700">
                      Mission Targets
                    </span>
                    <button
                      type="button"
                      data-testid="vlm-run-mission-targets"
                      onClick={() => void runMissionTargets()}
                      disabled={loadingGrounding}
                      className="rounded border border-cyan-200 bg-white px-2 py-1 text-[9px] font-semibold uppercase tracking-wider text-cyan-700 hover:bg-cyan-50 disabled:opacity-50"
                    >
                      Run All
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {enabledMissionTargets.map((target) => (
                      <button
                        key={target.label}
                        type="button"
                        data-testid="vlm-mission-target-chip"
                        onClick={() => void runGroundingPrompt(target.prompt)}
                        disabled={loadingGrounding}
                        className="rounded border border-cyan-200 bg-white px-2 py-1 text-[9px] font-semibold uppercase tracking-wider text-cyan-700 hover:bg-cyan-50 disabled:opacity-50"
                        title={`${target.prompt} · ${target.class_key}`}
                      >
                        {target.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Find: structure cluster, vessel group, possible flaring region"
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
                           <div
                             key={idx}
                             data-testid="vlm-grounding-result"
                             title={formatBoxTooltip(r)}
                             tabIndex={0}
                             onMouseEnter={() => setHoveredBoxIndex(idx)}
                             onMouseLeave={() => setHoveredBoxIndex(null)}
                             onFocus={() => setHoveredBoxIndex(idx)}
                             onBlur={() => setHoveredBoxIndex(null)}
                             className="group relative bg-white border border-emerald-200 rounded px-2 py-1 flex items-center gap-2 shadow-[0_0_16px_rgba(16,185,129,0.16)] outline-none focus:ring-2 focus:ring-cyan-300"
                           >
                              <span className="text-[10px] font-bold text-zinc-900">{r.label}</span>
                              {r.confidence !== undefined && (
                                <span className="text-[9px] font-semibold text-emerald-700">{r.confidence.toFixed(2)}</span>
                              )}
                              <span className="text-[9px] text-zinc-400">[{r.bbox.map(b => b.toFixed(2)).join(", ")}]</span>
                              {hoveredBoxIndex === idx && renderBoxTooltip(r)}
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
                 <div
                   data-testid="vlm-vqa-answer"
                   className="mt-2 rounded border border-emerald-200 bg-emerald-50 px-3 py-2"
                 >
                   <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-700">Answer</p>
                   <p className="mt-1 text-xs font-medium leading-relaxed text-zinc-800">{vqaAnswer}</p>
                 </div>
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
                 <div
                   data-testid="vlm-caption-result"
                   className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2"
                 >
                   <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-700">Caption</p>
                   <p className="mt-1 text-xs font-medium leading-relaxed text-zinc-800">{caption}</p>
                 </div>
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
