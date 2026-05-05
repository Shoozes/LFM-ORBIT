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
  activeBbox: number[] | null;
  onBoxesUpdate: (boxes: VlmBox[]) => void;
  activeMissionTargets?: ObjectTarget[];
  targetPackId?: string | null;
};

type GroundingResponse = {
  results?: unknown;
  provenance?: unknown;
  summary?: { provenance?: unknown };
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

export default function VlmPanel({
  isOpen,
  onClose,
  activeBbox,
  onBoxesUpdate,
  activeMissionTargets = [],
  targetPackId = null,
}: VlmPanelProps) {
  const [groundingResults, setGroundingResults] = useState<VlmBox[] | null>(null);
  const [hoveredBoxIndex, setHoveredBoxIndex] = useState<number | null>(null);
  const [groundingError, setGroundingError] = useState<string | null>(null);
  const [loadingGrounding, setLoadingGrounding] = useState(false);

  const apiBaseUrl = getApiBaseUrl();
  const enabledMissionTargets = activeMissionTargets.filter((target) => target.enabled);

  if (!isOpen) return null;

  async function runMissionTargets(targets: ObjectTarget[] = enabledMissionTargets) {
    if (!activeBbox || targets.length === 0) return;
    setLoadingGrounding(true);
    setGroundingError(null);
    try {
      const data = await postJson<GroundingResponse>(
        `${apiBaseUrl}/api/vlm/grounding/batch`,
        {
          bbox: activeBbox,
          targets,
          target_pack_id: targetPackId,
          frame_ref: "current",
        },
        "Evidence target check failed",
      );
      const prompt = targets.length === 1 ? targets[0].prompt : "mission targets";
      const results = normalizeBoxes(data.results, data.provenance ?? data.summary?.provenance, prompt);
      setGroundingResults(results);
      setHoveredBoxIndex(null);
      onBoxesUpdate(results);
    } catch (err) {
      setGroundingError(getErrorMessage(err, "Evidence target check failed."));
    } finally {
      setLoadingGrounding(false);
    }
  }

  function renderBoxTooltip(box: VlmBox) {
    const rows = [
      ["Confidence", box.confidence !== undefined ? box.confidence.toFixed(2) : "candidate"],
      ["BBox", `[${box.bbox.map((entry) => entry.toFixed(2)).join(", ")}]`],
      ["Prompt", box.prompt ?? "mission target"],
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

  return (
    <div data-testid="mission-evidence-panel" className="flex flex-col gap-3 bg-white p-4 text-sm">
      <div className="mb-1 flex items-center justify-between">
        <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-900">Mission Evidence</span>
        <button
          type="button"
          aria-label="Close mission evidence"
          onClick={() => {
            onBoxesUpdate([]);
            onClose();
          }}
          className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400 transition hover:text-zinc-600"
        >
          x
        </button>
      </div>

      {!activeBbox ? (
        <div className="rounded border border-zinc-200 bg-zinc-50 p-4 text-center text-xs font-medium text-zinc-500">
          No active area selected.
        </div>
      ) : (
        <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
              Targets
            </span>
            <button
              type="button"
              data-testid="vlm-run-mission-targets"
              onClick={() => void runMissionTargets()}
              disabled={loadingGrounding || enabledMissionTargets.length === 0}
              className="rounded border border-cyan-200 bg-white px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-cyan-700 transition hover:bg-cyan-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Run Targets
            </button>
          </div>

          {enabledMissionTargets.length > 0 ? (
            <div data-testid="vlm-mission-targets" className="flex flex-wrap gap-1.5">
              {enabledMissionTargets.map((target) => (
                <button
                  key={target.label}
                  type="button"
                  data-testid="vlm-mission-target-chip"
                  onClick={() => void runMissionTargets([target])}
                  disabled={loadingGrounding}
                  className="rounded border border-cyan-200 bg-white px-2 py-1 text-[9px] font-semibold uppercase tracking-wider text-cyan-700 transition hover:bg-cyan-50 disabled:opacity-50"
                  title={`${target.prompt} - ${target.class_key}`}
                >
                  {target.label}
                </button>
              ))}
            </div>
          ) : (
            <p className="text-xs font-medium text-zinc-500">No mission targets configured.</p>
          )}

          {loadingGrounding ? (
            <p className="mt-3 text-[10px] font-semibold uppercase tracking-wider text-zinc-400">Checking targets...</p>
          ) : groundingError ? (
            <p className="mt-3 text-xs font-medium text-red-600">{groundingError}</p>
          ) : groundingResults && (
            <div className="mt-4 space-y-2">
              {groundingResults.length === 0 ? (
                <p className="text-xs italic text-zinc-400">No matches found.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {groundingResults.map((result, idx) => (
                    <div
                      key={`${result.label}-${idx}`}
                      data-testid="vlm-grounding-result"
                      title={formatBoxTooltip(result)}
                      tabIndex={0}
                      onMouseEnter={() => setHoveredBoxIndex(idx)}
                      onMouseLeave={() => setHoveredBoxIndex(null)}
                      onFocus={() => setHoveredBoxIndex(idx)}
                      onBlur={() => setHoveredBoxIndex(null)}
                      className="group relative flex items-center gap-2 rounded border border-emerald-200 bg-white px-2 py-1 shadow-[0_0_16px_rgba(16,185,129,0.16)] outline-none focus:ring-2 focus:ring-cyan-300"
                    >
                      <span className="text-[10px] font-bold text-zinc-900">{result.label}</span>
                      {result.confidence !== undefined && (
                        <span className="text-[9px] font-semibold text-emerald-700">{result.confidence.toFixed(2)}</span>
                      )}
                      <span className="text-[9px] text-zinc-400">[{result.bbox.map((entry) => entry.toFixed(2)).join(", ")}]</span>
                      {hoveredBoxIndex === idx && renderBoxTooltip(result)}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
