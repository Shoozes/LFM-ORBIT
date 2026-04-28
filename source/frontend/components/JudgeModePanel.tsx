import { useEffect, useMemo, useState } from "react";
import type { Mission } from "../types/mission";
import type { AlertItem, ApiMetricsSummary, RecentAlertsResponse } from "../types/telemetry";
import { formatReasonCode, formatSourceLabel } from "../utils/telemetry";

type DemoCase = "judge" | "payload" | "provenance" | "abstain" | "eclipse";

type GalleryItem = {
  context_thumb: string | null;
  context_thumb_source: string | null;
  timelapse_b64: string | null;
  timelapse_source: string | null;
  timelapse_analysis: string | null;
};

type VlmBoxResult = {
  label: string;
  bbox: number[];
};

type VlmGroundingResponse = {
  results?: VlmBoxResult[];
};

type VlmVqaResponse = {
  answer?: string;
};

type VlmCaptionResponse = {
  caption?: string;
};

type JudgeProof = {
  demo: string;
  replay_id: string;
  model: string;
  provider: string;
  bbox: number[];
  latency_ms: number;
  raw_payload_bytes: number;
  alert_payload_bytes: number;
  payload_reduction_ratio: number | null;
  confidence: number;
  abstained: boolean;
  result: string;
  mission: string;
  source_capture_time: string;
  prompt: string;
  output_json: Record<string, unknown>;
  artifacts: {
    screenshot: string;
    evidence_frame?: string;
    video: string;
    trace: string;
  };
};

type JudgeModePanelProps = {
  apiBaseUrl: string;
  demoCase: DemoCase;
  mission: Mission | null;
  alerts: AlertItem[];
  metricsSummary: ApiMetricsSummary | null;
  selectedCellId: string | null;
  onClose: () => void;
  onStepChange?: (stepIndex: number) => void;
};

const JUDGE_REPLAY_ID = "rondonia_frontier_judge";
const JUDGE_MODEL = "LFM2.5-VL-450M";
const JUDGE_BBOX = [-63.15, -10.15, -62.85, -9.85];
const RAW_FRAME_BYTES = 1_840_000;
const ALERT_JSON_BYTES = 1_240;
const SEEDED_LATENCY_MS = 842;
const FALLBACK_CAPTURE_TIME = "2025-01-15";
const JUDGE_PROMPT = "Find fresh clearing and road-edge canopy loss.";
const DEMO_TITLES: Record<DemoCase, string> = {
  judge: "Judge walkthrough proof",
  payload: "Pakistan flood payload reduction proof",
  provenance: "Atacama provenance proof",
  abstain: "Greenland abstain safety proof",
  eclipse: "Maritime orbital eclipse proof",
};

const DEMO_STORY_LINES: Record<DemoCase, string[]> = {
  judge: [
    "Satellite saw too much data.",
    "Edge triage ignored noise.",
    "Liquid VLM checked the important frame.",
    "Compact evidence JSON was downlinked.",
  ],
  payload: [
    "The Manchar Lake flood frame stayed local.",
    "Only the overflow bbox reached the VLM.",
    "The result became compact flood JSON.",
    "The downlink sent kilobytes, not megabytes.",
  ],
  provenance: [
    "Provider, capture time, mine bbox, and task stay attached.",
    "The prompt and model name are recorded.",
    "The output JSON is visible for audit.",
    "Judges can verify the chain without narration.",
  ],
  abstain: [
    "The ice mission bbox was selected.",
    "Imagery quality was insufficient.",
    "The VLM did not invent an answer.",
    "No alert packet was transmitted.",
  ],
  eclipse: [
    "The maritime mission continues during outage.",
    "Compact alert packets queue locally.",
    "Raw imagery is not pushed over a broken link.",
    "Restoring the link flushes JSON evidence.",
  ],
};

const DEMO_REASON_CODES: Record<DemoCase, string[]> = {
  judge: ["ndvi_drop", "nbr_drop", "soil_exposure_spike"],
  payload: ["flood_extent", "compact_json", "downlink_saved"],
  provenance: ["provider_bound", "capture_time", "bbox_bound"],
  abstain: ["quality_gate_failed", "low_confidence", "no_transmit"],
  eclipse: ["link_offline", "queue_local", "flush_on_restore"],
};

type DemoProfile = {
  replayId: string;
  provider: string;
  bbox: number[];
  result: string;
  mission: string;
  captureTime: string;
  prompt: string;
  confidence: number;
  latencyMs: number;
  cellId: string;
  groundingLabel: string;
  groundingBox: number[];
  vqa: string;
  caption: string;
  visualAsset?: string;
};

const DEMO_PROFILES: Record<DemoCase, DemoProfile> = {
  judge: {
    replayId: JUDGE_REPLAY_ID,
    provider: "seeded replay",
    bbox: JUDGE_BBOX,
    result: "forest boundary disturbance detected",
    mission: "Rondonia frontier canopy-loss replay",
    captureTime: FALLBACK_CAPTURE_TIME,
    prompt: JUDGE_PROMPT,
    confidence: 0.82,
    latencyMs: SEEDED_LATENCY_MS,
    cellId: "sq_-10.0_-63.0",
    groundingLabel: "clearing",
    groundingBox: [0.24, 0.18, 0.74, 0.76],
    vqa: "Mixed vegetation, exposed clearing, and road context.",
    caption: "Deforested clearing beside intact canopy.",
  },
  payload: {
    replayId: "flood_extent",
    provider: "Sentinel Hub Sentinel-2 L2A",
    bbox: [67.63, 26.31, 67.87, 26.55],
    result: "Manchar Lake flood overflow candidate compressed to alert JSON",
    mission: "Find new surface water and overflow around Pakistan's Manchar Lake during the 2022 flood sequence.",
    captureTime: "2022-09-15",
    prompt: "Find floodwater outside the normal lake boundary and downlink compact alert JSON.",
    confidence: 0.79,
    latencyMs: 688,
    cellId: "pakistan_manchar_flood_candidate",
    groundingLabel: "flood overflow",
    groundingBox: [0.45, 0.34, 0.78, 0.74],
    vqa: "Expanded lake water and flood overflow are inside the evidence bbox.",
    caption: "Manchar Lake flood overflow candidate; raw frame stays local.",
    visualAsset: "/demo-assets/pakistan-manchar-flood.png",
  },
  provenance: {
    replayId: "mining_expansion",
    provider: "Sentinel Hub Sentinel-2 L2A",
    bbox: [-69.115, -24.29, -69.035, -24.21],
    result: "open-pit mining expansion review packet ready",
    mission: "Detect Atacama open-pit mining expansion and separate persistent bare earth from seasonal vegetation loss.",
    captureTime: "2025-12-15",
    prompt: "Track Atacama open-pit expansion with provider, capture time, bbox, prompt, and model attached.",
    confidence: 0.81,
    latencyMs: 731,
    cellId: "atacama_open_pit_candidate",
    groundingLabel: "mine expansion",
    groundingBox: [0.34, 0.24, 0.68, 0.68],
    vqa: "Open-pit benches, tailings, and access roads are visible inside the mine bbox.",
    caption: "Atacama mining footprint with provenance fields bound to the output JSON.",
    visualAsset: "/demo-assets/atacama-mining.png",
  },
  abstain: {
    replayId: "ice_cap_growth",
    provider: "Sentinel Hub Sentinel-2 L2A",
    bbox: [-51.13, 69.1, -50.97, 69.26],
    result: "no alert transmitted",
    mission: "Compare same-season Greenland ice cap and glacier edge frames for true growth or retreat.",
    captureTime: "2025-10-15",
    prompt: "Abstain if imagery is stale, cloudy, or insufficient.",
    confidence: 0.21,
    latencyMs: 219,
    cellId: "greenland_quality_gate",
    groundingLabel: "quality gate",
    groundingBox: [0.24, 0.18, 0.74, 0.76],
    vqa: "Unavailable",
    caption: "No caption transmitted",
    visualAsset: "/demo-assets/greenland-ice.png",
  },
  eclipse: {
    replayId: "maritime_activity",
    provider: "Sentinel Hub Sentinel-2 L2A",
    bbox: [32.5, 29.88, 32.58, 29.96],
    result: "maritime vessel-queue review packet ready",
    mission: "Review maritime vessel queueing near the Suez channel.",
    captureTime: "2025-12-15",
    prompt: "Review vessel queueing near a narrow channel and queue JSON during outage.",
    confidence: 0.76,
    latencyMs: 612,
    cellId: "maritime_suez_channel",
    groundingLabel: "vessel queue",
    groundingBox: [0.22, 0.28, 0.76, 0.64],
    vqa: "Vessel queue candidate near narrow channel context.",
    caption: "Maritime queue candidate held for compact downlink.",
    visualAsset: "/demo-assets/suez-maritime.png",
  },
};

function demoName(demoCase: DemoCase): string {
  if (demoCase === "payload") return "payload-reduction";
  if (demoCase === "provenance") return "provenance";
  if (demoCase === "abstain") return "abstain-safety";
  if (demoCase === "eclipse") return "orbital-eclipse";
  return "judge-mode";
}

function formatBytes(bytes: number): string {
  if (bytes >= 1_000_000) return `${(bytes / 1_000_000).toFixed(2)} MB`;
  if (bytes >= 1_000) return `${(bytes / 1_000).toFixed(2)} KB`;
  return `${bytes} B`;
}

function formatRatio(ratio: number | null): string {
  if (ratio === null) return "No downlink";
  return `${Math.floor(ratio).toLocaleString()}x`;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T | null> {
  try {
    const response = await fetch(url, init);
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function buildFallbackProof(demoCase: DemoCase): JudgeProof {
  const isAbstain = demoCase === "abstain";
  const profile = DEMO_PROFILES[demoCase];
  const ratio = isAbstain ? null : Number((RAW_FRAME_BYTES / ALERT_JSON_BYTES).toFixed(2));
  const result = profile.result;
  return {
    demo: demoName(demoCase),
    replay_id: profile.replayId,
    model: JUDGE_MODEL,
    provider: profile.provider,
    bbox: profile.bbox,
    latency_ms: profile.latencyMs,
    raw_payload_bytes: RAW_FRAME_BYTES,
    alert_payload_bytes: isAbstain ? 0 : ALERT_JSON_BYTES,
    payload_reduction_ratio: ratio,
    confidence: profile.confidence,
    abstained: isAbstain,
    result,
    mission: profile.mission,
    source_capture_time: profile.captureTime,
    prompt: profile.prompt,
    output_json: isAbstain
      ? {
          status: "abstained",
          reason: "imagery stale/cloudy/insufficient",
          confidence: "low",
          transmitted: false,
        }
      : {
          status: "alert_ready",
          result,
          confidence: 0.82,
          action: "downlink_compact_json",
        },
    artifacts: {
      screenshot: "final-screen.png",
      evidence_frame: "evidence-frame.png",
      video: "Playwright report video",
      trace: "Playwright report trace.zip",
    },
  };
}

function ProofRow({
  label,
  value,
  testId,
}: {
  label: string;
  value: string;
  testId?: string;
}) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-zinc-800 py-2 last:border-b-0">
      <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-zinc-500">
        {label}
      </span>
      <span data-testid={testId} className="max-w-[240px] text-right text-xs font-semibold text-zinc-100">
        {value}
      </span>
    </div>
  );
}

export default function JudgeModePanel({
  apiBaseUrl,
  demoCase,
  mission,
  alerts,
  metricsSummary,
  selectedCellId,
  onClose,
  onStepChange,
}: JudgeModePanelProps) {
  const [recentAlerts, setRecentAlerts] = useState<AlertItem[]>(alerts);
  const [metrics, setMetrics] = useState<ApiMetricsSummary | null>(metricsSummary);
  const [galleryItem, setGalleryItem] = useState<GalleryItem | null>(null);
  const [groundingResults, setGroundingResults] = useState<VlmBoxResult[]>(() => {
    const profile = DEMO_PROFILES[demoCase];
    return [{ label: profile.groundingLabel, bbox: profile.groundingBox }];
  });
  const [vqaAnswer, setVqaAnswer] = useState(DEMO_PROFILES[demoCase].vqa);
  const [caption, setCaption] = useState(DEMO_PROFILES[demoCase].caption);
  const [observedLatencyMs, setObservedLatencyMs] = useState<number | null>(null);
  const [proof, setProof] = useState<JudgeProof>(() => buildFallbackProof(demoCase));
  const [linkOffline, setLinkOffline] = useState(false);
  const [queueCount, setQueueCount] = useState(0);
  const [flushedQueueCount, setFlushedQueueCount] = useState(0);
  const [linkStatus, setLinkStatus] = useState("LINK OPEN");

  useEffect(() => {
    setRecentAlerts(alerts);
  }, [alerts]);

  useEffect(() => {
    setMetrics(metricsSummary);
  }, [metricsSummary]);

  const usesReplayEvidence = Boolean(mission?.replay_id) || demoCase === "judge";

  const activeAlert = useMemo(() => {
    if (selectedCellId) {
      const matching = recentAlerts.find((alert) => alert.cell_id === selectedCellId);
      if (matching) return matching;
    }
    return recentAlerts[0] ?? null;
  }, [demoCase, recentAlerts, selectedCellId]);

  useEffect(() => {
    let cancelled = false;

    async function hydrateProof() {
      onStepChange?.(3);
      const [recentPayload, metricsPayload] = await Promise.all([
        fetchJson<RecentAlertsResponse>(`${apiBaseUrl}/api/alerts/recent?limit=10`),
        fetchJson<ApiMetricsSummary>(`${apiBaseUrl}/api/metrics/summary`),
      ]);

      if (cancelled) return;
      const resolvedAlerts = recentPayload?.alerts ?? alerts;
      setRecentAlerts(resolvedAlerts);
      setMetrics(metricsPayload ?? metricsSummary);

      const resolvedAlert = selectedCellId
        ? resolvedAlerts.find((alert) => alert.cell_id === selectedCellId) ?? resolvedAlerts[0] ?? null
        : resolvedAlerts[0] ?? null;

      if (usesReplayEvidence && resolvedAlert?.cell_id) {
        const galleryPayload = await fetchJson<GalleryItem>(`${apiBaseUrl}/api/gallery/${resolvedAlert.cell_id}`);
        if (!cancelled) setGalleryItem(galleryPayload);
      }

      if (usesReplayEvidence) {
        await sleep(700);
        onStepChange?.(4);
        const bbox = mission?.bbox ?? JUDGE_BBOX;
        const replayPrompt = mission?.task_text ?? JUDGE_PROMPT;
        const startedAt = performance.now();
        const [groundingPayload, vqaPayload, captionPayload] = await Promise.all([
          fetchJson<VlmGroundingResponse>(`${apiBaseUrl}/api/vlm/grounding`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ bbox, prompt: replayPrompt }),
          }),
          fetchJson<VlmVqaResponse>(`${apiBaseUrl}/api/vlm/vqa`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ bbox, question: "What changed inside the selected evidence box?" }),
          }),
          fetchJson<VlmCaptionResponse>(`${apiBaseUrl}/api/vlm/caption`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ bbox }),
          }),
        ]);
        const elapsedMs = Math.max(1, Math.round(performance.now() - startedAt));

        if (cancelled) return;
        if (groundingPayload?.results?.length) setGroundingResults(groundingPayload.results);
        if (vqaPayload?.answer) setVqaAnswer(vqaPayload.answer);
        if (captionPayload?.caption) setCaption(captionPayload.caption);
        setObservedLatencyMs(elapsedMs);
      } else {
        await sleep(500);
        onStepChange?.(4);
        const profile = DEMO_PROFILES[demoCase];
        setGroundingResults([{ label: profile.groundingLabel, bbox: profile.groundingBox }]);
        setVqaAnswer(profile.vqa);
        setCaption(profile.caption);
      }

      await sleep(700);
      onStepChange?.(5);
      await sleep(900);
      onStepChange?.(6);
    }

    void hydrateProof();
    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, alerts, demoCase, metricsSummary, mission?.bbox, onStepChange, selectedCellId, usesReplayEvidence]);

  useEffect(() => {
    const isAbstain = demoCase === "abstain";
    const profile = DEMO_PROFILES[demoCase];
    const ratio = isAbstain ? null : Number((RAW_FRAME_BYTES / ALERT_JSON_BYTES).toFixed(2));
    const bbox = usesReplayEvidence ? mission?.bbox ?? profile.bbox : profile.bbox;
    const evidenceAlert = usesReplayEvidence ? activeAlert : null;
    const provider = isAbstain
      ? profile.provider
      : demoCase === "eclipse"
        ? profile.provider
        : usesReplayEvidence
          ? evidenceAlert?.observation_source
            ? formatSourceLabel(evidenceAlert.observation_source)
            : profile.provider
          : profile.provider;
    const captureTime = usesReplayEvidence
      ? evidenceAlert?.after_window?.label ?? mission?.end_date ?? profile.captureTime
      : profile.captureTime;
    const confidence = isAbstain
      ? profile.confidence
      : usesReplayEvidence
        ? Number((evidenceAlert?.confidence ?? profile.confidence).toFixed(2))
        : profile.confidence;
    const result = usesReplayEvidence
      ? evidenceAlert?.analysis_summary ?? evidenceAlert?.ground_action ?? profile.result
      : profile.result;
    const prompt = usesReplayEvidence ? mission?.task_text ?? profile.prompt : profile.prompt;
    const outputJson = isAbstain
      ? {
          status: "abstained",
          reason: "imagery stale/cloudy/insufficient",
          confidence: "low",
          transmitted: false,
        }
      : {
          status: "alert_ready",
          result,
          confidence,
          action: "downlink_compact_json",
          cell_id: usesReplayEvidence ? evidenceAlert?.cell_id ?? profile.cellId : profile.cellId,
          reason_codes: evidenceAlert?.reason_codes ?? DEMO_REASON_CODES[demoCase],
          use_case_id: usesReplayEvidence ? mission?.use_case_id ?? null : profile.replayId,
          grounding: groundingResults,
          vqa: vqaAnswer,
          caption,
          ...(demoCase === "eclipse"
            ? {
                link_status: linkStatus,
                queued_alerts: queueCount,
                flushed_alerts: flushedQueueCount,
                action: "queue_compact_json_until_link_restored",
              }
            : {}),
        };

    setProof({
      demo: demoName(demoCase),
      replay_id: usesReplayEvidence ? mission?.replay_id ?? mission?.use_case_id ?? profile.replayId : profile.replayId,
      model: JUDGE_MODEL,
      provider,
      bbox,
      latency_ms: usesReplayEvidence ? SEEDED_LATENCY_MS : profile.latencyMs,
      raw_payload_bytes: RAW_FRAME_BYTES,
      alert_payload_bytes: isAbstain ? 0 : ALERT_JSON_BYTES,
      payload_reduction_ratio: ratio,
      confidence,
      abstained: isAbstain,
      result,
      mission: usesReplayEvidence ? mission?.task_text ?? profile.mission : profile.mission,
      source_capture_time: captureTime,
      prompt,
      output_json: outputJson,
      artifacts: {
        screenshot: "final-screen.png",
        evidence_frame: "evidence-frame.png",
        video: "Playwright report video",
        trace: "Playwright report trace.zip",
      },
    });
  }, [activeAlert, caption, demoCase, flushedQueueCount, groundingResults, linkStatus, mission, queueCount, usesReplayEvidence, vqaAnswer]);

  useEffect(() => {
    if (!linkOffline) return;
    const timer = window.setInterval(() => {
      setQueueCount((current) => Math.min(current + 1, 4));
    }, 450);
    return () => window.clearInterval(timer);
  }, [linkOffline]);

  const toggleOrbitalEclipse = async () => {
    if (!linkOffline) {
      setLinkOffline(true);
      setLinkStatus("LINK OFFLINE");
      setQueueCount(0);
      await fetchJson(`${apiBaseUrl}/api/link/state`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ connected: false }),
      });
      return;
    }

    const flushed = queueCount;
    setFlushedQueueCount(flushed);
    setQueueCount(0);
    setLinkOffline(false);
    setLinkStatus("LINK RESTORED");
    await fetchJson(`${apiBaseUrl}/api/link/state`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ connected: true }),
    });
  };

  const proofJson = useMemo(() => JSON.stringify(proof, null, 2), [proof]);
  const sourceText = `${proof.provider} / ${proof.source_capture_time}`;
  const evidenceAlert = usesReplayEvidence ? activeAlert : null;
  const imageSource = usesReplayEvidence ? galleryItem?.context_thumb : DEMO_PROFILES[demoCase].visualAsset ?? null;
  const timelapseSource = proof.abstained || !usesReplayEvidence ? null : galleryItem?.timelapse_b64;
  const visualSourceLabel = timelapseSource
    ? formatSourceLabel(galleryItem?.timelapse_source ?? "seeded_replay")
    : imageSource
      ? usesReplayEvidence
        ? formatSourceLabel(galleryItem?.context_thumb_source ?? evidenceAlert?.observation_source)
        : proof.abstained
          ? "Local Quality Preview"
          : "Local Mission Frame"
      : proof.abstained
        ? "No Imagery Downlink"
        : demoCase === "eclipse"
          ? "Mission BBox + Queue"
          : "Mission BBox";
  const reasonCodes = evidenceAlert?.reason_codes ?? DEMO_REASON_CODES[demoCase];
  const cellsScanned = metrics?.total_cells_scanned ?? mission?.cells_scanned ?? 9;
  const alertsEmitted = metrics?.total_alerts_emitted ?? mission?.flags_found ?? 4;

  return (
    <div data-testid="judge-mode-panel" className="absolute inset-0 z-40 flex flex-col bg-zinc-950 text-zinc-100">
      <header className="flex shrink-0 items-center justify-between border-b border-zinc-800 bg-zinc-950 px-5 py-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-cyan-300">Judge Mode</p>
          <h1 data-testid="demo-title" className="text-xl font-semibold text-white">
            {DEMO_TITLES[demoCase]}
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="rounded border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-200">
            {proof.abstained ? "ABSTAINED" : "ALERT READY"}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-zinc-700 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-zinc-300 hover:border-zinc-500 hover:text-white"
          >
            Close
          </button>
        </div>
      </header>

      <main className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-auto p-4 xl:grid-cols-[280px_minmax(0,1fr)_420px]">
        <section className="flex min-h-0 flex-col gap-3 rounded border border-zinc-800 bg-zinc-900/80 p-4">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-zinc-500">
              {usesReplayEvidence ? "Replay Position" : "Mission Position"}
            </p>
            <h2 className="mt-1 text-sm font-semibold text-white">
              {usesReplayEvidence ? mission?.replay_id ?? JUDGE_REPLAY_ID : mission?.use_case_id ?? DEMO_PROFILES[demoCase].replayId}
            </h2>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {Array.from({ length: 9 }).map((_, index) => {
              const active = index === 4;
              return (
                <div
                  key={index}
                  className={`aspect-square rounded border ${
                    active
                      ? "border-red-400 bg-red-500/30 shadow-[0_0_18px_rgba(248,113,113,0.35)]"
                      : index % 2 === 0
                        ? "border-emerald-500/40 bg-emerald-500/10"
                        : "border-zinc-700 bg-zinc-800"
                  }`}
                />
              );
            })}
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="rounded border border-zinc-800 bg-zinc-950 p-3">
              <p className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Cells</p>
              <p className="mt-1 text-lg font-semibold text-white">{cellsScanned}</p>
            </div>
            <div className="rounded border border-zinc-800 bg-zinc-950 p-3">
              <p className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Alerts</p>
              <p className="mt-1 text-lg font-semibold text-white">{alertsEmitted}</p>
            </div>
          </div>
          <div className="space-y-2 rounded border border-zinc-800 bg-zinc-950 p-3 text-xs text-zinc-300">
            {DEMO_STORY_LINES[demoCase].map((line) => (
              <p key={line}>{line}</p>
            ))}
          </div>
          {demoCase === "eclipse" && (
            <div className="mt-auto rounded border border-amber-500/30 bg-amber-500/10 p-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-200">Orbital Eclipse</p>
              <button
                data-testid="orbital-eclipse-toggle"
                type="button"
                onClick={() => void toggleOrbitalEclipse()}
                className="mt-2 w-full rounded border border-amber-300/40 bg-zinc-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-amber-100 hover:border-amber-200"
              >
                {linkOffline ? "Restore Link" : "Toggle Link Offline"}
              </button>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <div className="rounded border border-zinc-800 bg-zinc-950 p-2">
                  <p className="text-[10px] uppercase tracking-[0.14em] text-zinc-500">State</p>
                  <p className="mt-1 font-semibold text-amber-100">{linkStatus}</p>
                </div>
                <div className="rounded border border-zinc-800 bg-zinc-950 p-2">
                  <p className="text-[10px] uppercase tracking-[0.14em] text-zinc-500">Queue</p>
                  <p data-testid="dtn-queue-count" className="mt-1 font-semibold text-amber-100">
                    {queueCount} queued
                  </p>
                </div>
              </div>
              {linkStatus === "LINK RESTORED" && (
                <p className="mt-2 text-xs font-semibold text-emerald-200">
                  LINK RESTORED. Flushed {flushedQueueCount} JSON alerts.
                </p>
              )}
            </div>
          )}
        </section>

        <section className="flex min-h-0 flex-col rounded border border-zinc-800 bg-zinc-900/80 p-4">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-zinc-500">Satellite Frame</p>
              <h2 className="text-sm font-semibold text-white">BBox evidence overlay</h2>
            </div>
            <span className="rounded border border-cyan-500/30 bg-cyan-500/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-cyan-200">
              {visualSourceLabel}
            </span>
          </div>
          <div
            data-testid="satellite-frame"
            className="relative min-h-[360px] flex-1 overflow-hidden rounded border border-zinc-800 bg-zinc-950 xl:min-h-0"
          >
            {timelapseSource ? (
              <video
                data-testid="proof-timelapse-video"
                src={timelapseSource}
                poster={imageSource ?? undefined}
                muted
                loop
                autoPlay
                playsInline
                className="h-full w-full object-cover"
                onLoadedMetadata={(event) => {
                  const video = event.currentTarget;
                  if (Number.isFinite(video.duration) && video.duration > 10) {
                    video.currentTime = Math.min(4.2, video.duration * 0.28);
                    video.playbackRate = 0.5;
                  } else {
                    video.playbackRate = 1;
                  }
                  void video.play();
                }}
                onTimeUpdate={(event) => {
                  const video = event.currentTarget;
                  if (Number.isFinite(video.duration) && video.duration > 10) {
                    const clearWindowStart = Math.min(4.2, video.duration * 0.28);
                    const clearWindowEnd = Math.min(6.5, video.duration * 0.42);
                    if (video.currentTime > clearWindowEnd) {
                      video.currentTime = clearWindowStart;
                    }
                  }
                }}
              />
            ) : imageSource ? (
              <img
                src={imageSource}
                alt="Satellite mission frame"
                className="h-full w-full object-cover"
              />
            ) : null}
            {!timelapseSource && !imageSource && (
              <div
                data-testid="proof-no-imagery"
                className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-[radial-gradient(circle_at_center,rgba(8,145,178,0.14),transparent_45%),linear-gradient(135deg,#09090b,#18181b)] px-8 text-center"
              >
                <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-cyan-200">
                  {proof.abstained ? "Quality Gate" : "Delay-Tolerant Link"}
                </p>
                <p className="max-w-md text-lg font-semibold text-white">
                  {proof.abstained
                    ? "No imagery was trusted enough to transmit."
                    : "No raw frame was pushed while the link was offline."}
                </p>
                <p className="max-w-md text-xs leading-relaxed text-zinc-400">
                  {proof.abstained
                    ? "The proof records an abstain decision, low confidence, and a blocked alert packet."
                    : "The mission keeps only compact JSON alerts in the local queue until the downlink is restored."}
                </p>
              </div>
            )}
            <div className="absolute inset-[18%] border-2 border-cyan-300 shadow-[0_0_0_9999px_rgba(2,6,23,0.24)]" />
            <div className="absolute left-[24%] top-[28%] h-[38%] w-[45%] border-2 border-red-400 bg-red-500/10" />
            <div className="absolute left-[24%] top-[calc(28%-28px)] rounded bg-red-500 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-white">
              evidence bbox
            </div>
            <div className="absolute bottom-4 left-4 right-4 grid grid-cols-3 gap-2">
              {reasonCodes.slice(0, 3).map((code) => (
                <span
                  key={code}
                  className="rounded border border-zinc-900/40 bg-zinc-950/85 px-2 py-1 text-center text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-100"
                >
                  {formatReasonCode(code)}
                </span>
              ))}
            </div>
            <div
              data-testid="timelapse-integrity"
              className="absolute right-4 top-4 rounded border border-zinc-900/40 bg-zinc-950/85 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-100"
            >
              {timelapseSource
                ? "Seeded WebM evidence: 25 contextual frames"
                : proof.abstained
                  ? "Static local frame: no alert transmitted"
                  : demoCase === "eclipse"
                    ? "Static local frame: compact JSON queue only"
                    : "Static satellite frame: raw image stays local"}
            </div>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-3">
            <div className="rounded border border-zinc-800 bg-zinc-950 p-3">
              <p className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">VLM result</p>
              <p className="mt-1 text-xs font-semibold text-white">{proof.result}</p>
            </div>
            <div className="rounded border border-zinc-800 bg-zinc-950 p-3">
              <p className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">VQA</p>
              <p className="mt-1 text-xs font-semibold text-white">{proof.abstained ? "Unavailable" : vqaAnswer}</p>
            </div>
            <div className="rounded border border-zinc-800 bg-zinc-950 p-3">
              <p className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Caption</p>
              <p className="mt-1 text-xs font-semibold text-white">{proof.abstained ? "No caption transmitted" : caption}</p>
            </div>
          </div>
        </section>

        <aside className="flex min-h-0 flex-col rounded border border-zinc-800 bg-zinc-900/90 p-4">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-zinc-500">Proof Card</p>
              <h2 className="text-sm font-semibold text-white">{proof.demo}</h2>
            </div>
            {observedLatencyMs !== null && (
              <span className="rounded border border-zinc-700 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-300">
                observed {observedLatencyMs} ms
              </span>
            )}
          </div>

          <div className="rounded border border-zinc-800 bg-zinc-950 px-3">
            <ProofRow label="Mission" value={proof.mission} />
            <ProofRow label="Replay/source" value={sourceText} testId="proof-source" />
            <ProofRow label="Model" value={proof.model} testId="proof-model" />
            <ProofRow label="Latency" value={`${proof.latency_ms} ms`} testId="proof-latency" />
            <ProofRow label="Confidence" value={proof.abstained ? "low" : proof.confidence.toFixed(2)} />
            <ProofRow label="Raw payload" value={`Raw frame: ${formatBytes(proof.raw_payload_bytes)}`} testId="proof-raw-bytes" />
            <ProofRow label="Alert payload" value={`Alert JSON: ${formatBytes(proof.alert_payload_bytes)}`} testId="proof-alert-bytes" />
            <ProofRow label="Reduction ratio" value={formatRatio(proof.payload_reduction_ratio)} testId="proof-reduction-ratio" />
            <ProofRow label="Abstain status" value={proof.abstained ? "status: abstained" : "status: transmitted"} />
          </div>

          {demoCase === "payload" && (
            <div className="mt-3 rounded border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm font-semibold text-emerald-100">
              <p>Raw frame: {formatBytes(RAW_FRAME_BYTES)}</p>
              <p>Alert JSON: {formatBytes(ALERT_JSON_BYTES)}</p>
              <p>Downlink reduction: {formatRatio(proof.payload_reduction_ratio)}</p>
            </div>
          )}

          {demoCase === "abstain" && (
            <div className="mt-3 rounded border border-amber-500/30 bg-amber-500/10 p-3 text-sm font-semibold text-amber-100">
              <p>status: abstained</p>
              <p>reason: imagery stale/cloudy/insufficient</p>
              <p>confidence: low</p>
              <p>no alert transmitted</p>
            </div>
          )}

          {demoCase === "provenance" && (
            <div className="mt-3 rounded border border-cyan-500/30 bg-cyan-500/10 p-3 text-xs text-cyan-100">
              <p>provider: {proof.provider}</p>
              <p>replay id: {proof.replay_id}</p>
              <p>capture time: {proof.source_capture_time}</p>
              <p>bbox: [{proof.bbox.map((value) => value.toFixed(2)).join(", ")}]</p>
              <p>prompt: {proof.prompt}</p>
            </div>
          )}

          <pre
            data-testid="proof-json"
            className="mt-3 min-h-0 flex-1 overflow-auto rounded border border-zinc-800 bg-black p-3 text-[10px] leading-relaxed text-emerald-100"
          >
            {proofJson}
          </pre>
        </aside>
      </main>
    </div>
  );
}
