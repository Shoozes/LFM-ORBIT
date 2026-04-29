import { useEffect, useMemo, useRef, useState } from "react";
import type { AlertAnalysis, AlertItem, CellImageryResponse, ScanWindow } from "../types/telemetry";
import { getApiBaseUrl, formatSourceLabel, formatReasonCode } from "../utils/telemetry";
import { useAgentBus } from "../hooks/useAgentBus";
import type { Mission } from "../types/mission";
type GalleryFull = {
  timelapse_b64: string | null;
  timelapse_source: string | null;
  timelapse_analysis: string | null;
  context_thumb: string | null;
  context_thumb_source: string | null;
  has_timelapse: number;
};

type ValidationPanelProps = {
  selectedCellId: string | null;
  alert: AlertItem | null;
  onOpenTimelapse?: () => void;
  mission?: Mission | null;
};

function getDelta(beforeValue: number, afterValue: number): string {
  const delta = afterValue - beforeValue;
  const sign = delta >= 0 ? "+" : "";
  return `${sign}${delta.toFixed(3)}`;
}

function buildSummary(alert: AlertItem | null): string[] {
  if (!alert) {
    return ["No alert is selected. Choose a flagged cell to inspect the temporal evidence."];
  }

  if (!alert.before_window || !alert.after_window) {
    return ["This alert has no attached temporal windows yet."];
  }

  const notes: string[] = [];

  if (
    alert.observation_source === "seeded_sentinelhub_replay" ||
    alert.observation_source === "seeded_replay" ||
    alert.observation_source === "replay"
  ) {
    notes.push("✓ Replay evidence restored from cached real API imagery and historical agent outputs.");
  }

  // Spectral evidence
  if (alert.reason_codes.includes("multi_index_consensus")) {
    notes.push("✓ Strong multi-index consensus indicating structural canopy loss.");
  } else if (alert.reason_codes.includes("ndvi_drop") && alert.reason_codes.includes("nbr_drop")) {
    notes.push("✓ Combined vegetation (NDVI) and burn-ratio (NBR) signals decreased.");
  }

  if (alert.reason_codes.includes("soil_exposure_spike")) {
    notes.push("✓ Significant emergence of exposed bare soil / structural dryness.");
  }

  if (alert.reason_codes.includes("observation_pattern_match")) {
    notes.push("✓ Pattern matches the cached disturbance signature.");
  }

  // Quality checks
  if (alert.reason_codes.includes("low_quality_window")) {
    notes.push("⚠ Warning: Detection limited by low-quality observation imagery.");
  }

  // Context checks
  if (alert.reason_codes.includes("regional_phenology_shift")) {
    notes.push("⚠ Downgrade: Drought context detected; local region similarly stressed.");
  } else if (alert.reason_codes.includes("suspected_canopy_loss")) {
    notes.push("✓ Targeted focal anomaly stands out from surrounding region.");
  }

  if (notes.length > 0) {
    return notes;
  }

  return ["Temporal signals shifted enough to trigger a triage alert, but evidence remains ambiguous."];
}

function renderWindowCard(title: string, window: ScanWindow) {
  return (
    <div className="rounded border border-zinc-200 bg-zinc-50 p-3">
      <p className="text-[10px] text-zinc-500 uppercase font-semibold tracking-wider mb-2">{title}</p>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-zinc-500 font-semibold">Label:</span> <span className="text-zinc-900 font-medium">{window.label}</span>
        </div>
        <div>
          <span className="text-zinc-500 font-semibold">Quality:</span> <span className="text-zinc-900 font-medium">{window.quality.toFixed(3)}</span>
        </div>
        <div>
          <span className="text-zinc-500 font-semibold">NIR:</span> <span className="text-zinc-900 font-medium">{window.nir !== undefined ? window.nir.toFixed(3) : "—"}</span>
        </div>
        <div>
          <span className="text-zinc-500 font-semibold">RED:</span> <span className="text-zinc-900 font-medium">{window.red !== undefined ? window.red.toFixed(3) : "—"}</span>
        </div>
        <div>
          <span className="text-zinc-500 font-semibold">SWIR:</span> <span className="text-zinc-900 font-medium">{window.swir !== undefined ? window.swir.toFixed(3) : "—"}</span>
        </div>
        <div>
          <span className="text-zinc-500 font-semibold">NDVI:</span> <span className="text-zinc-900 font-medium">{window.ndvi !== undefined ? window.ndvi.toFixed(3) : "—"}</span>
        </div>
        <div>
          <span className="text-zinc-500 font-semibold">NBR:</span> <span className="text-zinc-900 font-medium">{window.nbr !== undefined ? window.nbr.toFixed(3) : "—"}</span>
        </div>
        <div>
          <span className="text-zinc-500 font-semibold">EVI2:</span> <span className="text-zinc-900 font-medium">{window.evi2 !== undefined ? window.evi2.toFixed(3) : "—"}</span>
        </div>
        <div>
          <span className="text-zinc-500 font-semibold">NDMI:</span> <span className="text-zinc-900 font-medium">{window.ndmi !== undefined ? window.ndmi.toFixed(3) : "—"}</span>
        </div>
        <div>
          <span className="text-zinc-500 font-semibold">Soil Ratio:</span> <span className="text-zinc-900 font-medium">{window.soil_ratio !== undefined ? window.soil_ratio.toFixed(3) : "—"}</span>
        </div>
        <div>
          <span className="text-zinc-500 font-semibold">Flags:</span>{" "}
          <span className="text-zinc-900 font-medium">{window.flags.length > 0 ? window.flags.join(", ") : "none"}</span>
        </div>
      </div>
    </div>
  );
}

function getDataUrlExtension(dataUrl: string): string {
  if (dataUrl.startsWith("data:image/jpeg")) return "jpg";
  if (dataUrl.startsWith("data:image/png")) return "png";
  if (dataUrl.startsWith("data:image/svg+xml")) return "svg";
  if (dataUrl.startsWith("data:video/webm")) return "webm";
  if (dataUrl.startsWith("data:video/mp4")) return "mp4";
  return "bin";
}

function downloadDataUrl(dataUrl: string, filenameStem: string) {
  const a = document.createElement("a");
  a.href = dataUrl;
  a.download = `${filenameStem}.${getDataUrlExtension(dataUrl)}`;
  a.click();
}

function ImageryChip({
  src,
  label,
  sublabel,
  loading = false,
  onClick,
}: {
  src: string | null;
  label: string;
  sublabel?: string;
  loading?: boolean;
  onClick?: () => void;
}) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    setLoaded(false);
    setError(false);
  }, [src]);

  return (
    <div
      className={`overflow-hidden rounded border border-zinc-200 bg-zinc-50 ${onClick ? 'cursor-pointer hover:border-zinc-400 transition-colors' : ''}`}
      onClick={onClick}
    >
      <div className="relative w-full" style={{ paddingBottom: "100%" }}>
        {loading ? (
          <div className="absolute inset-0 bg-zinc-200/60 animate-pulse flex items-center justify-center">
            <span className="text-zinc-400 text-[10px] font-semibold uppercase tracking-wider drop-shadow-sm">Fetching...</span>
          </div>
        ) : src && !error ? (
          <>
            {!loaded && (
              <div className="absolute inset-0 bg-zinc-200/60 animate-pulse flex items-center justify-center">
                <span className="text-zinc-400 text-[10px] font-semibold uppercase tracking-wider drop-shadow-sm">Decoding...</span>
              </div>
            )}
            <img
              src={src}
              alt={label}
              className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-300 ${loaded ? "opacity-100" : "opacity-0"}`}
              onLoad={() => setLoaded(true)}
              onError={() => setError(true)}
            />
          </>
        ) : (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-zinc-400 text-[10px] font-semibold uppercase tracking-wider">
              {src === null ? "Unavailable" : "Load Error"}
            </span>
          </div>
        )}
      </div>
      <div className="px-3 py-2 border-t border-zinc-200 bg-white">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-700">{label}</p>
        {sublabel && <p className="text-[10px] text-zinc-500 mt-0.5">{sublabel}</p>}
      </div>
    </div>
  );
}

function AnalysisCard({ analysis, label }: { analysis: AlertAnalysis; label: string }) {
  return (
    <div className="rounded border border-zinc-200 bg-white p-3 text-xs shadow-sm">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-zinc-500 font-semibold uppercase tracking-wider text-[10px]">{label}</span>
        <span className="text-zinc-700 font-medium">{analysis.model}</span>
        <span
          className={`border px-1.5 py-0.5 text-[9px] uppercase font-bold tracking-wider rounded ml-auto ${
            analysis.severity === "critical"
              ? "border-red-200 bg-red-50 text-red-700"
              : analysis.severity === "high"
                ? "border-orange-200 bg-orange-50 text-orange-700"
                : analysis.severity === "moderate"
                  ? "border-amber-200 bg-amber-50 text-amber-700"
                  : "border-zinc-200 bg-zinc-50 text-zinc-600"
          }`}
        >
          {analysis.severity}
        </span>
      </div>
      <p className="text-zinc-800 leading-relaxed whitespace-pre-line mb-3">{analysis.summary}</p>
      <p className="text-zinc-400 text-[10px] italic">{analysis.source_note}</p>
    </div>
  );
}

export default function ValidationPanel({ selectedCellId, alert, onOpenTimelapse, mission }: ValidationPanelProps) {
  const summary = useMemo(() => buildSummary(alert), [alert]);
  const { messages } = useAgentBus();
  const cellMessages = useMemo(() => {
    return messages.filter(m => m.cell_id === selectedCellId && m.msg_type !== "heartbeat");
  }, [messages, selectedCellId]);

  const [analysis, setAnalysis] = useState<AlertAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [imagery, setImagery] = useState<CellImageryResponse | null>(null);
  const [imageryLoading, setImageryLoading] = useState(false);
  const [galleryItem, setGalleryItem] = useState<GalleryFull | null>(null);
  const [galleryLoading, setGalleryLoading] = useState(false);
  const apiBaseUrl = getApiBaseUrl();
  const videoRef = useRef<HTMLVideoElement>(null);

  // Reset analysis, imagery, and gallery data when the selected alert changes
  const alertKey = alert?.event_id ?? null;
  useEffect(() => {
    setAnalysis(null);
    setAnalyzeError(null);
    setGalleryItem(null);
  }, [alertKey]);

  // Fetch gallery item (timelapse + analysis) for confirmed alerts
  useEffect(() => {
    if (!selectedCellId || !alert) {
      setGalleryItem(null);
      return;
    }
    setGalleryLoading(true);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    void fetch(`${apiBaseUrl}/api/gallery/${selectedCellId}`, { signal: controller.signal })
      .then((r) => {
        clearTimeout(timeoutId);
        return r.ok ? r.json() : null;
      })
      .then((data) => setGalleryItem(data as GalleryFull | null))
      .catch(() => {
        clearTimeout(timeoutId);
        setGalleryItem(null);
      })
      .finally(() => setGalleryLoading(false));

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, [selectedCellId, alert, apiBaseUrl]);

  // Fetch cell imagery whenever the selected cell changes
  useEffect(() => {
    if (!selectedCellId) {
      setImagery(null);
      return;
    }

    setImagery(null);
    setImageryLoading(true);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    void fetch(`${apiBaseUrl}/api/imagery/cell/${selectedCellId}`, { signal: controller.signal })
      .then((r) => {
        clearTimeout(timeoutId);
        return r.ok ? r.json() : null;
      })
      .then((data) => {
        setImagery(data as CellImageryResponse | null);
      })
      .catch(() => {
        clearTimeout(timeoutId);
        setImagery(null);
      })
      .finally(() => setImageryLoading(false));

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, [selectedCellId, apiBaseUrl]);

  const canAnalyze = !!alert?.before_window && !!alert?.after_window;

  async function fetchAnalysis(): Promise<AlertAnalysis | null> {
    if (!alert?.before_window || !alert?.after_window) return null;
    const response = await fetch(`${apiBaseUrl}/api/analysis/alert`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        change_score: alert.change_score,
        confidence: alert.confidence,
        reason_codes: alert.reason_codes,
        before_window: alert.before_window,
        after_window: alert.after_window,
        observation_source: alert.observation_source ?? "unknown",
      }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return (await response.json()) as AlertAnalysis;
  }

  async function handleAnalyze() {
    setAnalyzing(true);
    setAnalyzeError(null);
    setAnalysis(null);

    try {
      const result = await fetchAnalysis();
      setAnalysis(result);
    } catch (err) {
      setAnalyzeError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  }

  if (!selectedCellId) {
      return (
        <div>
          <p className="text-[10px] uppercase font-semibold tracking-wider text-zinc-500 mb-2">Temporal Evidence</p>
          <div className="rounded border border-zinc-200 bg-zinc-50 p-4 text-sm text-zinc-600 font-medium">
            No cell is selected.
          </div>
        </div>
    );
  }

  if (!alert) {
      return (
        <div>
          <p className="text-[10px] uppercase font-semibold tracking-wider text-zinc-500 mb-2">Temporal Evidence</p>
          <div className="rounded border border-zinc-200 bg-zinc-50 p-4 text-sm text-zinc-600 font-medium">
            Cell <span className="text-zinc-900 font-bold break-all">{selectedCellId}</span> has no downlinked alert. The scanner discarded it or it has not crossed threshold yet.
          </div>
          {/* Still show satellite context imagery for non-alert cells */}
          {(imageryLoading || imagery?.context_image) && (
            <div className="mt-4">
              <p className="text-[10px] uppercase font-semibold tracking-wider text-zinc-500 mb-2">Satellite Context</p>
              <div className="w-32">
                <ImageryChip
                  src={imagery?.context_image ?? null}
                  label="CURRENT"
                  sublabel="Esri World Imagery"
                  loading={imageryLoading}
                  onClick={onOpenTimelapse}
                />
              </div>
            </div>
        )}
      </div>
    );
  }

  const hasResults = analysis !== null;
  const isReplayMission = mission?.mission_mode === "replay";

  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider font-semibold text-zinc-500 mb-2">Temporal Evidence</p>

      <div className="mb-4 rounded border border-zinc-200 bg-white p-4 shadow-sm">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <p className="text-sm font-bold text-zinc-900 break-all">{alert.cell_id}</p>
            <p className="text-[10px] uppercase tracking-wider font-semibold text-zinc-400">{alert.event_id}</p>
          </div>
          <div className="flex flex-col items-end gap-1.5">
            <p className="text-[10px] py-0.5 px-2 rounded bg-zinc-100 uppercase tracking-widest font-bold text-zinc-600">
              {alert.priority}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs mb-4 bg-zinc-50 border border-zinc-100 p-3 rounded">
          <div>
            <span className="text-zinc-500 font-semibold">Score:</span> <span className="text-zinc-900 font-bold">{alert.change_score.toFixed(3)}</span>
          </div>
          <div>
            <span className="text-zinc-500 font-semibold">Confidence:</span> <span className="text-zinc-900 font-medium">{alert.confidence.toFixed(3)}</span>
          </div>
          <div>
            <span className="text-zinc-500 font-semibold">Payload:</span> <span className="text-zinc-900 font-medium">{alert.payload_bytes} bytes</span>
          </div>
          <div>
            <span className="text-zinc-500 font-semibold">Source:</span> <span className="text-zinc-900 font-medium">{formatSourceLabel(alert.observation_source)}</span>
          </div>
        </div>

        {isReplayMission && (
          <div className="mb-3 rounded border border-cyan-200 bg-cyan-50 p-3 text-xs text-cyan-800 font-medium">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-cyan-700 mb-1">Cached API Replay Evidence</p>
            <p>
              Historical downlinks, timelapse evidence, and agent reasoning were restored from replay
              {mission?.replay_id ? ` ${mission.replay_id}` : ""} so this cell can be inspected without waiting on a realtime pass.
            </p>
          </div>
        )}

        <div className="mb-3 rounded border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 font-medium">
          This panel shows temporal evidence only. It identifies suspected logging activity and does not claim final ground truth.
        </div>

        <div className="text-sm text-zinc-700 leading-relaxed space-y-1">
          {summary.map((note, idx) => (
            <p key={idx} className={note.startsWith("⚠") ? "text-amber-700 font-medium" : note.startsWith("✓") ? "text-slate-800 font-medium" : ""}>
              {note}
            </p>
          ))}
        </div>
      </div>

      {/* Governance & Concession Overlays */}
      {alert?.boundary_context && alert.boundary_context.length > 0 && (
        <div className="mb-4">
          <p className="text-[10px] uppercase font-semibold tracking-wider text-teal-600 mb-2">Governance Overlays</p>
          <div className="space-y-2">
            {alert.boundary_context.map((bc, idx) => (
              <div key={idx} className="rounded border border-teal-200 bg-teal-50 p-2 text-xs flex justify-between items-center shadow-sm">
                <div>
                  <p className="font-semibold text-teal-900">{bc.feature_name || bc.source_name}</p>
                  <p className="text-teal-700 text-[9px] uppercase tracking-wider font-semibold">{bc.layer_type}</p>
                </div>
                <div className="text-right">
                  {bc.overlap_ratio > 0 ? (
                    <p className="font-bold text-teal-800">{(bc.overlap_ratio * 100).toFixed(1)}% OVERLAP</p>
                  ) : (
                    <p className="font-medium text-teal-600">{bc.distance_to_boundary_m.toFixed(0)}m AWAY</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Ground-agent timelapse (from gallery) */}
      {(galleryLoading || galleryItem) && (
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-[10px] uppercase tracking-wider font-semibold text-purple-600">Timelapse Evidence</p>
            {galleryItem?.timelapse_b64 && (
              <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
                {galleryItem.timelapse_source ? formatSourceLabel(galleryItem.timelapse_source) : "Ground Agent"}
              </p>
            )}
          </div>
          {galleryLoading && !galleryItem && (
            <div className="rounded border border-zinc-200 bg-zinc-50 p-4 text-center">
              <span className="text-xs text-zinc-500 font-medium animate-pulse">Requesting from ground station…</span>
            </div>
          )}
          {galleryItem?.timelapse_b64 ? (
            <div className="space-y-3">
              <video
                ref={videoRef}
                src={galleryItem.timelapse_b64}
                autoPlay
                loop
                controls
                muted
                className="w-full rounded border border-zinc-200 bg-black"
                style={{ maxHeight: "220px" }}
              />
              {galleryItem.timelapse_analysis && (
                <div className="rounded border border-zinc-200 bg-zinc-50 p-3 text-xs">
                  <p className="text-zinc-500 font-semibold tracking-wider uppercase text-[10px] mb-1">Temporal Signal Analysis</p>
                  <p className="text-zinc-800 leading-relaxed">{galleryItem.timelapse_analysis}</p>
                </div>
              )}
              {galleryItem.context_thumb_source && (
                <p className="text-[10px] text-zinc-500 font-semibold uppercase tracking-wider">
                  Context thumbnail: {formatSourceLabel(galleryItem.context_thumb_source)}
                </p>
              )}
            </div>
          ) : galleryItem && !galleryItem.timelapse_b64 ? (
            <div className="rounded border border-zinc-200 bg-zinc-50 p-3 text-center">
              <span className="text-xs text-zinc-500 font-medium">Timelapse pending or unavailable.</span>
            </div>
          ) : null}
        </div>
      )}

      {/* Satellite imagery chips */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <p className="text-[10px] uppercase font-semibold tracking-wider text-zinc-500">Satellite Imagery</p>
          <p className="text-[10px] uppercase font-semibold tracking-wider text-zinc-400">
            {imageryLoading
              ? "fetching…"
              : imagery?.imagery_source === "simsat_sentinel"
                ? "SimSat Sentinel"
                : imagery?.imagery_source === "simsat_mapbox"
                  ? "SimSat Mapbox"
                  : imagery?.context_image
                    ? "Esri World Imagery"
                    : "unavailable"}
          </p>
        </div>

        {imagery?.before_image || imagery?.after_image ? (
          <div className="grid grid-cols-2 gap-3">
            <ImageryChip
              src={imagery.before_image}
              label="BEFORE"
              sublabel={imagery.before_label}
              loading={imageryLoading}
              onClick={onOpenTimelapse}
            />
            <ImageryChip
              src={imagery.after_image}
              label="AFTER"
              sublabel={imagery.after_label}
              loading={imageryLoading}
              onClick={onOpenTimelapse}
            />
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            <ImageryChip
              src={imagery?.context_image ?? null}
              label="CURRENT"
              sublabel={imageryLoading ? "loading…" : "Esri World Imagery"}
              loading={imageryLoading}
              onClick={onOpenTimelapse}
            />
            <div className="overflow-hidden rounded border border-zinc-200 bg-zinc-50">
              <div className="relative w-full" style={{ paddingBottom: "100%" }}>
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 px-3 text-center">
                  <span className="text-zinc-400 text-[10px] font-bold tracking-wider uppercase">Missing</span>
                  <span className="text-zinc-500 text-[10px] font-medium leading-tight">
                    Before/after unavailable.
                  </span>
                </div>
              </div>
              <div className="px-3 py-2 border-t border-zinc-200 bg-white">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">BEFORE / AFTER</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {alert.before_window && alert.after_window ? (
        <>
          <div className="grid grid-cols-2 gap-3 mb-4">
            {renderWindowCard("Before Window", alert.before_window)}
            {renderWindowCard("After Window", alert.after_window)}
          </div>

          <div className="rounded border border-zinc-200 bg-white p-4 text-xs shadow-sm mb-4">
            <p className="text-zinc-500 font-semibold tracking-wider uppercase text-[10px] mb-3">Signal Deltas</p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <span className="text-zinc-500 font-semibold">NIR delta:</span>{" "}
                <span className="text-zinc-900 font-medium">{alert.before_window.nir !== undefined ? getDelta(alert.before_window.nir, alert.after_window.nir) : "—"}</span>
              </div>
              <div>
                <span className="text-zinc-500 font-semibold">RED delta:</span>{" "}
                <span className="text-zinc-900 font-medium">{alert.before_window.red !== undefined ? getDelta(alert.before_window.red, alert.after_window.red) : "—"}</span>
              </div>
              <div>
                <span className="text-zinc-500 font-semibold">SWIR delta:</span>{" "}
                <span className="text-zinc-900 font-medium">{alert.before_window.swir !== undefined ? getDelta(alert.before_window.swir, alert.after_window.swir) : "—"}</span>
              </div>
              <div>
                <span className="text-zinc-500 font-semibold">NDVI delta:</span>{" "}
                <span className="text-zinc-900 font-medium">{alert.before_window.ndvi !== undefined ? getDelta(alert.before_window.ndvi, alert.after_window.ndvi) : "—"}</span>
              </div>
              <div>
                <span className="text-zinc-500 font-semibold">NBR delta:</span>{" "}
                <span className="text-zinc-900 font-medium">{alert.before_window.nbr !== undefined ? getDelta(alert.before_window.nbr, alert.after_window.nbr) : "—"}</span>
              </div>
              <div>
                <span className="text-zinc-500 font-semibold">EVI2 delta:</span>{" "}
                <span className="text-zinc-900 font-medium">{alert.before_window.evi2 !== undefined ? getDelta(alert.before_window.evi2, alert.after_window.evi2) : "—"}</span>
              </div>
              <div>
                <span className="text-zinc-500 font-semibold">NDMI delta:</span>{" "}
                <span className="text-zinc-900 font-medium">{alert.before_window.ndmi !== undefined ? getDelta(alert.before_window.ndmi, alert.after_window.ndmi) : "—"}</span>
              </div>
              <div>
                <span className="text-zinc-500 font-semibold">Soil Ratio delta:</span>{" "}
                <span className="text-zinc-900 font-medium">{alert.before_window.soil_ratio !== undefined ? getDelta(alert.before_window.soil_ratio, alert.after_window.soil_ratio) : "—"}</span>
              </div>
              <div className="col-span-2 mt-1">
                <span className="text-zinc-500 font-semibold">Reason codes:</span>{" "}
                <div className="inline-flex flex-wrap gap-1 mt-1">
                  {alert.reason_codes.map(c => (
                    <span key={c} className="bg-zinc-100 border border-zinc-200 text-zinc-600 px-1.5 py-0.5 rounded text-[10px] tracking-wider uppercase">{formatReasonCode(c)}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* LFM AI Analysis */}
          <div className="rounded border border-zinc-200 bg-white p-4 text-xs shadow-sm mb-4">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-[10px] uppercase font-semibold tracking-wider text-zinc-500">AI Analysis</p>
                <p className="text-zinc-400 font-medium text-[10px] mt-0.5">LFM Model</p>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  data-testid="analyze-button"
                  onClick={handleAnalyze}
                  disabled={!canAnalyze || analyzing}
                  className="rounded border border-emerald-200 bg-emerald-50 hover:bg-emerald-100 disabled:opacity-50 text-emerald-700 px-4 py-1.5 text-[10px] font-bold uppercase tracking-wider transition"
                >
                  {analyzing ? "Running…" : "Analyze"}
                </button>
              </div>
            </div>

            {analyzeError && (
              <div className="mb-3 p-2 bg-red-50 text-red-600 rounded text-xs font-medium border border-red-200">Error: {analyzeError}</div>
            )}

            {hasResults ? (
              <div className="space-y-3">
                <AnalysisCard analysis={analysis!} label="LFM" />
              </div>
            ) : (
              !analyzing && (
                <p className="text-zinc-500 text-center py-2 bg-zinc-50 rounded border border-zinc-200">
                  Click <span className="text-emerald-600 font-bold">Analyze</span> to run inference on this cell.
                </p>
              )
            )}
          </div>

          {/* Internal Agent Logs */}
          {cellMessages.length > 0 && (
            <div className="rounded border border-zinc-200 bg-white p-4 text-xs shadow-sm">
              <p className="text-zinc-500 font-semibold tracking-wider uppercase text-[10px] mb-3">Agent Decision Log</p>
              <div className="space-y-3">
                {cellMessages.map(msg => (
                  <div key={msg.id} className={`p-3 rounded border ${msg.sender === "satellite" ? "border-blue-200 bg-blue-50" : "border-emerald-200 bg-emerald-50"}`}>
                    <div className="flex items-center justify-between mb-2">
                      <span className={`font-bold text-[10px] uppercase tracking-wider ${msg.sender === "satellite" ? "text-blue-700" : "text-emerald-700"}`}>
                        {msg.sender.replace("_", " ")}
                      </span>
                      <span className="text-zinc-400 font-bold text-[9px] uppercase tracking-widest">{msg.msg_type}</span>
                    </div>

                    <p className="text-zinc-800 leading-relaxed text-xs whitespace-pre-wrap font-sans">{msg.payload.note || "No textual note provided by agent."}</p>

                    {msg.payload.analysis_summary && (
                      <div className="mt-3 text-[10px] bg-white p-2 rounded text-zinc-700 border border-zinc-200 font-medium">
                        <span className="text-zinc-400 font-bold uppercase tracking-wider block mb-1">Rank Justification</span>
                        {msg.payload.analysis_summary}
                      </div>
                    )}

                    {msg.payload.action && (
                      <p className="mt-3 text-[11px] text-amber-700 font-bold italic border-l-2 border-amber-300 pl-2">{msg.payload.action as string}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          {/* Dataset Export Section for Model Training */}
          <div className="rounded border border-zinc-200 bg-white p-4 text-xs shadow-sm mt-4">
               <p className="text-zinc-500 font-semibold tracking-wider uppercase text-[10px] mb-3">Model Training Export</p>
               <p className="text-zinc-600 mb-4 leading-relaxed">
                 Export the metadata, temporal visual sequences, and VLM rankings as a standardized dataset tuple for downstream model fine-tuning.
               </p>
               <div className="flex gap-2">
                 <button
                   onClick={() => {
                     const data = JSON.stringify(alert, null, 2);
                     const blob = new Blob([data], { type: "application/json" });
                     const url = URL.createObjectURL(blob);
                     const a = document.createElement("a");
                     a.href = url;
                     a.download = `alert_${alert.cell_id}.json`;
                     a.click();
                     URL.revokeObjectURL(url);
                   }}
                 className="flex-1 bg-zinc-900 text-white font-bold text-[10px] uppercase tracking-wider py-2 rounded hover:bg-zinc-800 transition"
                 >
                   {isReplayMission ? "Download Record" : "Download JSON"}
                 </button>
                <button
                  onClick={() => {
                    if (imagery?.context_image) downloadDataUrl(imagery.context_image, `alert_${alert.cell_id}_context`);
                    if (imagery?.before_image) downloadDataUrl(imagery.before_image, `alert_${alert.cell_id}_before`);
                    if (imagery?.after_image) downloadDataUrl(imagery.after_image, `alert_${alert.cell_id}_after`);
                    if (galleryItem?.timelapse_b64) {
                      downloadDataUrl(galleryItem.timelapse_b64, `alert_${alert.cell_id}_timelapse`);
                    }
                  }}
                   disabled={!imagery?.context_image && !imagery?.before_image && !galleryItem?.timelapse_b64}
                   title={(!imagery?.context_image && !imagery?.before_image && !galleryItem?.timelapse_b64) ? "No assets available to export." : "Download available imagery and video assets."}
                   className="flex-1 border border-zinc-300 text-zinc-700 bg-white hover:bg-zinc-50 disabled:opacity-50 font-bold text-[10px] uppercase tracking-wider py-2 rounded transition"
                 >
                   Export Assets
                 </button>
               </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
