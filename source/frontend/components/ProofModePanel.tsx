import { type CSSProperties, useEffect, useMemo, useState } from "react";
import type { Mission } from "../types/mission";
import type { AlertItem, ApiMetricsSummary, RecentAlertsResponse } from "../types/telemetry";
import { formatReasonCode, formatSourceLabel } from "../utils/telemetry";
import {
  colorForVlmBox,
  displayObjectEvidenceCount,
  displayObjectEvidenceLabel,
  objectEvidenceScopeNote,
} from "../utils/objectEvidence";
import { filterAlertsForBbox } from "../utils/missionAlerts";

type DemoCase = "showcase" | "payload" | "provenance" | "abstain" | "eclipse" | "ice" | "forest";

type GalleryItem = {
  context_thumb: string | null;
  context_thumb_source: string | null;
  timelapse_b64: string | null;
  timelapse_source: string | null;
  timelapse_analysis: string | null;
};

type MissionTimelapse = {
  video_b64: string;
  frames_count: number;
  source?: string;
  provider?: string;
  runtime_truth_mode?: string;
  imagery_origin?: string;
  scoring_basis?: string;
  provenance?: {
    label?: string;
    provider?: string;
    kind?: string;
    cache_family?: string;
  };
};

type VlmBoxResult = {
  label: string;
  bbox: number[];
  bbox_format?: "unit_xyxy" | "unit_yxyx";
  confidence?: number;
  color_key?: string;
  source_model?: string;
  count_quality?: string;
  runtime_truth_mode?: string;
  imagery_origin?: string;
  scoring_basis?: string;
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

type ProofJson = {
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
  payload_accounting: {
    raw_payload_basis: string;
    alert_payload_basis: string;
    counted_alert_fields: string[];
    excluded_from_alert_payload_bytes: string[];
    note: string;
  };
  output_json: Record<string, unknown>;
  artifacts: {
    screenshot: string;
    evidence_frame?: string;
    video: string;
    trace: string;
  };
};

type ConfidenceContributor = {
  signal: string;
  weight: number;
  score: number;
  weighted: number;
  evidence: string;
};

type DtnProof = {
  link_state_before: string;
  link_state_after: string;
  queued_alerts_before_restore: number;
  queued_alerts_after_restore: number;
  flushed_alerts: number;
  queue_source: string;
  proof_message_ids?: number[];
};

type ProofModePanelProps = {
  apiBaseUrl: string;
  demoCase: DemoCase;
  demoMode?: boolean;
  mission: Mission | null;
  alerts: AlertItem[];
  metricsSummary: ApiMetricsSummary | null;
  selectedCellId: string | null;
  onClose: () => void;
  onStepChange?: (stepIndex: number) => void;
};

const SHOWCASE_REPLAY_ID = "atacama_mining_replay";
const SHOWCASE_MODEL = "Liquid evidence reviewer (LFM2.5-VL-450M handoff-ready)";
const SHOWCASE_BBOX = [-69.115, -24.29, -69.035, -24.21];
const RAW_FRAME_BYTES = 1_840_000;
const ALERT_JSON_BYTES = 1_240;
const SEEDED_LATENCY_MS = 842;
const SHOWCASE_PROMPT = "Find critical minerals expansion regions: evaporation ponds, tailings, open-pit growth, industrial roads, facility clusters, exposed soil, and surface color change.";
const COUNTED_ALERT_FIELDS = [
  "status",
  "result",
  "confidence",
  "action",
  "cell_id",
  "reason_codes",
  "use_case_id",
  "grounding",
  "vqa",
  "caption",
  "object_targets",
  "detections",
  "object_deltas",
];
const EXCLUDED_PAYLOAD_FIELDS = [
  "proof wrapper",
  "provider/source display fields",
  "bbox and prompt audit fields",
  "screenshot/video/trace artifact references",
  "payload_accounting metadata",
];
const DEMO_TITLES: Record<DemoCase, string> = {
  showcase: "Critical minerals expansion proof",
  payload: "Pakistan flood payload reduction proof",
  provenance: "Critical minerals provenance proof",
  abstain: "Greenland abstain safety proof",
  eclipse: "Maritime orbital eclipse proof",
  ice: "Greenland ice/snow extent proof",
  forest: "Rondonia land-use-change proof",
};

const DEMO_CONTEXT: Record<DemoCase, { what: string; where: string; when: string; why: string }> = {
  showcase: {
    what: "Critical Minerals Expansion Watch promotes one extraction-site evidence packet",
    where: "Salar de Atacama / Escondida / Atacama mining corridor, Chile",
    when: "2024-01-15 to 2025-12-15 replay window",
    why: "show long-term industrial land-change evidence becoming compact proof JSON and training tags",
  },
  payload: {
    what: "Flood-overflow bbox becomes a compact alert packet",
    where: "Manchar Lake, Pakistan",
    when: "2022-06-15 to 2022-09-15",
    why: "show raw flood imagery stays local while kilobytes downlink",
  },
  provenance: {
    what: "Critical Minerals proof keeps source, bbox, prompt, and model attached",
    where: "Salar de Atacama / Escondida / Atacama mining corridor, Chile",
    when: "2024-01-15 to 2025-12-15",
    why: "make the evidence chain auditable without narration",
  },
  abstain: {
    what: "Ice/snow quality gate blocks an unsupported answer",
    where: "Greenland coastal ice edge",
    when: "2024-01-15 to 2025-10-15",
    why: "show bad imagery does not become a confident downlink",
  },
  eclipse: {
    what: "Maritime vessel-queue alert survives a simulated link outage",
    where: "Suez channel",
    when: "2025-03-01 to 2025-12-15",
    why: "prove compact JSON queues locally and flushes on restore",
  },
  ice: {
    what: "Ground Agent validates a cached Sentinel Hub ice/snow replay",
    where: "Greenland Ilulissat ice edge",
    when: "2024-01-15 to 2025-12-15",
    why: "show NDSI, SCL cloud rejection, temporal persistence, and visual context combining into one confidence score",
  },
  forest: {
    what: "Deforestation / Land-Use Change Watch promotes one retained evidence packet",
    where: "Rondonia western frontier, Brazil",
    when: "2023-01-15 to 2025-01-15 replay window",
    why: "show selected-area workflow, temporal evidence, CV region boxes, compact proof JSON, and training tags",
  },
};

const DEMO_STORY_LINES: Record<DemoCase, string[]> = {
  showcase: [
    "The Atacama mining corridor is visually legible from orbit.",
    "Satellite Pruner keeps expansion-region evidence instead of raw frames.",
    "Ground Validator reviews ponds, tailings, pits, roads, and facility regions.",
    "Proof JSON and training tags preserve source, bbox, confidence, and safe labels.",
  ],
  payload: [
    "The Manchar Lake flood frame stayed local.",
    "Only the overflow bbox reached the evidence reviewer.",
    "The result became compact flood JSON.",
    "The downlink sent kilobytes, not megabytes.",
  ],
  provenance: [
    "Provider, capture time, corridor bbox, and task stay attached.",
    "The prompt and model name are recorded.",
    "The output JSON is visible for audit.",
    "Reviewers can verify the chain without narration.",
  ],
  abstain: [
    "The ice mission bbox was selected.",
    "Imagery quality was insufficient.",
    "The reviewer did not invent an answer.",
    "No alert packet was transmitted.",
  ],
  eclipse: [
    "The maritime mission continues during outage.",
    "Compact alert packets queue locally.",
    "Raw imagery is not pushed over a broken link.",
    "Restoring the link flushes JSON evidence.",
  ],
  ice: [
    "Satellite Pruner kept the ice-edge replay packet.",
    "Ground Validator checked NDSI, SWIR/NIR, and SCL support.",
    "Cloud windows were rejected before scoring.",
    "Proof Mode exposes the weighted confidence stack.",
  ],
  forest: [
    "The operator selects a Rondonia frontier mission bbox.",
    "Satellite Pruner keeps persistent canopy-loss evidence and discards lower-value cells.",
    "Ground Validator reviews dates, source, proxy bands, and CV region boxes.",
    "Proof JSON carries bbox, confidence, provenance, safe labels, and training tags.",
  ],
};

const DEMO_REASON_CODES: Record<DemoCase, string[]> = {
  showcase: ["bare_ground_expansion", "tailings_change", "excavation_growth", "provider_bound"],
  payload: ["flood_extent", "compact_json", "downlink_saved"],
  provenance: ["provider_bound", "capture_time", "bbox_bound"],
  abstain: ["quality_gate_failed", "low_confidence", "no_transmit"],
  eclipse: ["link_offline", "queue_local", "flush_on_restore"],
  ice: ["ndsi_increase", "multi_frame_persistence", "cloud_rejected"],
  forest: ["ndvi_drop", "nbr_drop", "soil_exposure_spike", "proxy_band_review"],
};

const MISSION_NO_IMAGE_TITLE = "Nothing interesting found.";
const MISSION_NO_IMAGE_BODY = "The mission finished without retained flags. Proof Mode still shows the mission bbox, date range, source path, and compact JSON summary.";
const MISSION_NO_IMAGE_NOTE = "This proof stays tied to the current search and never borrows another replay's imagery.";

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
  visualVideo?: string;
  visualVideoSource?: string;
};

const DEMO_PROFILES: Record<DemoCase, DemoProfile> = {
  showcase: {
    replayId: SHOWCASE_REPLAY_ID,
    provider: "Replay (Cached API Imagery)",
    bbox: SHOWCASE_BBOX,
    result: "critical minerals expansion region packet ready",
    mission: "Critical Minerals Expansion Watch over the Salar de Atacama / Escondida / Atacama mining corridor.",
    captureTime: "2025-12-15",
    prompt: SHOWCASE_PROMPT,
    confidence: 0.86,
    latencyMs: SEEDED_LATENCY_MS,
    cellId: "mining_atacama_open_pit",
    groundingLabel: "mining expansion region",
    groundingBox: [0.28, 0.20, 0.72, 0.80],
    vqa: "Open-pit benches, tailings-like surfaces, industrial roads, and facility clusters are visible inside the retained bbox.",
    caption: "Atacama critical-minerals extraction region with expansion evidence and provenance attached.",
    visualAsset: "/demo-assets/atacama-mining.png",
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
    result: "critical minerals expansion review packet ready",
    mission: "Run Critical Minerals Expansion Watch over the Salar de Atacama / Escondida / Atacama mining corridor.",
    captureTime: "2025-12-15",
    prompt: "Track evaporation pond regions, tailings regions, open-pit expansion, industrial roads, facility clusters, exposed soil, and surface color change with provider, capture time, bbox, prompt, and model attached.",
    confidence: 0.81,
    latencyMs: 731,
    cellId: "atacama_open_pit_candidate",
    groundingLabel: "critical minerals region",
    groundingBox: [0.34, 0.24, 0.68, 0.68],
    vqa: "Open-pit benches, tailings-like regions, pond-like areas, roads, and facility clusters are visible inside the bbox.",
    caption: "Atacama critical-minerals footprint with provenance fields bound to the output JSON.",
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
  ice: {
    replayId: "greenland_ice_snow_extent_replay",
    provider: "Sentinel Hub Sentinel-2 L2A",
    bbox: [-51.13, 69.1, -50.97, 69.26],
    result: "NDSI-supported snow/ice extent increased across accepted frames",
    mission: "Review Greenland edge snow and ice extent using NDSI, SCL cloud rejection, and multi-frame persistence before any extent-change label.",
    captureTime: "2025 accepted-frame current",
    prompt: "Compare Greenland ice/snow extent with NDSI, SWIR/NIR, SCL cloud rejection, and persistence gates.",
    confidence: 0.78,
    latencyMs: 842,
    cellId: "greenland_ice_snow_extent",
    groundingLabel: "ice/snow extent area",
    groundingBox: [0.22, 0.18, 0.78, 0.74],
    vqa: "Accepted frames show persistent ice/snow signal; cloud and no-data windows are rejected before scoring.",
    caption: "Greenland ice/snow extent replay with spectral confidence stack.",
    visualAsset: "/demo-assets/greenland-ice.png",
    visualVideo: "/demo-assets/greenland-ice-timelapse.webm",
    visualVideoSource: "Sentinel Hub contextual timelapse",
  },
  forest: {
    replayId: "rondonia_frontier_showcase",
    provider: "Replay (Cached API Imagery)",
    bbox: [-63.15, -10.15, -62.85, -9.85],
    result: "persistent canopy-loss candidate retained for review and training",
    mission: "Run a Deforestation / Land-Use Change Watch over the Rondonia western frontier.",
    captureTime: "2025-01-15",
    prompt: "Find persistent canopy-loss change, clearing candidate regions, road expansion corridors, exposed soil, and canopy-loss boundaries.",
    confidence: 0.86,
    latencyMs: SEEDED_LATENCY_MS,
    cellId: "sq_-10.0_-63.0",
    groundingLabel: "clearing candidate region",
    groundingBox: [0.24, 0.22, 0.64, 0.72],
    vqa: "The retained cell shows a persistent clearing candidate with road-edge expansion and exposed soil after the baseline window.",
    caption: "Rondonia frontier land-use-change replay with region boxes, proxy-band deltas, and proof metadata attached.",
  },
};

function demoName(demoCase: DemoCase): string {
  if (demoCase === "payload") return "payload-reduction";
  if (demoCase === "provenance") return "provenance";
  if (demoCase === "abstain") return "abstain-safety";
  if (demoCase === "eclipse") return "orbital-eclipse";
  if (demoCase === "ice") return "ice-snow-extent";
  if (demoCase === "forest") return "deforestation-tutorial";
  return "showcase";
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

function buildPayloadAccounting(isAbstain: boolean): ProofJson["payload_accounting"] {
  if (isAbstain) {
    return {
      raw_payload_basis: "candidate satellite frame bytes before edge triage",
      alert_payload_basis: "no compact alert JSON was transmitted after the quality gate abstained",
      counted_alert_fields: [],
      excluded_from_alert_payload_bytes: EXCLUDED_PAYLOAD_FIELDS,
      note: "alert_payload_bytes is zero for abstain proofs because no downlink alert is sent.",
    };
  }

  return {
    raw_payload_basis: "representative encoded satellite frame retained locally",
    alert_payload_basis: "compact downlink alert JSON only",
    counted_alert_fields: COUNTED_ALERT_FIELDS,
    excluded_from_alert_payload_bytes: EXCLUDED_PAYLOAD_FIELDS,
    note: "alert_payload_bytes intentionally excludes the larger proof artifact envelope, screenshots, video, trace, and audit-only display metadata.",
  };
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

function buildFallbackProof(demoCase: DemoCase): ProofJson {
  const isAbstain = demoCase === "abstain";
  const profile = DEMO_PROFILES[demoCase];
  const ratio = isAbstain ? null : Number((RAW_FRAME_BYTES / ALERT_JSON_BYTES).toFixed(2));
  const result = profile.result;
  return {
    demo: demoName(demoCase),
    replay_id: profile.replayId,
    model: SHOWCASE_MODEL,
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
    payload_accounting: buildPayloadAccounting(isAbstain),
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

function buildMissionPayloadAccounting(hasRetainedAlert: boolean): ProofJson["payload_accounting"] {
  if (hasRetainedAlert) return buildPayloadAccounting(false);
  return {
    raw_payload_basis: "representative satellite frames evaluated inside the mission bbox",
    alert_payload_basis: "no compact alert JSON was transmitted because no mission cell retained alert evidence",
    counted_alert_fields: [],
    excluded_from_alert_payload_bytes: EXCLUDED_PAYLOAD_FIELDS,
    note: "Proof Mode records mission bbox, task, dates, target pack, source mode, and scan counts even when nothing interesting is found.",
  };
}

function buildMissionProof(mission: Mission | null, demoCase: DemoCase, evidenceAlert: AlertItem | null = null): ProofJson {
  const base = buildFallbackProof(demoCase);
  if (!mission) return base;
  const dateRange = [mission.start_date, mission.end_date].filter(Boolean).join(" to ") || "current mission window";
  const targets = mission.object_targets?.map((target) => target.label).filter(Boolean) ?? [];
  const hasRetainedAlert = Boolean(evidenceAlert) || Number(mission.flags_found ?? 0) > 0;
  const alertBytes = evidenceAlert?.payload_bytes ?? (hasRetainedAlert ? ALERT_JSON_BYTES : 0);
  const confidence = evidenceAlert?.confidence !== undefined
    ? Number(evidenceAlert.confidence.toFixed(2))
    : Math.max(0.35, Math.min(0.92, Number(mission.use_case_confidence ?? base.confidence ?? 0.62)));
  const result = evidenceAlert?.analysis_summary
    ?? evidenceAlert?.ground_action
    ?? (hasRetainedAlert
      ? "mission retained alert evidence for review"
      : mission.cells_scanned > 0
        ? "Nothing interesting found."
        : "mission evidence packet initializing");
  const status = hasRetainedAlert
    ? "alert_ready"
    : mission.cells_scanned > 0
      ? "no_flags_retained"
      : "mission_active";
  const reasonCodes = evidenceAlert?.reason_codes?.length
    ? evidenceAlert.reason_codes
    : missionReasonCodes(mission);
  return {
    ...base,
    demo: "mission",
    replay_id: mission.replay_id ?? `mission_${mission.id}`,
    provider: mission.replay_id
      ? "Replay (Cached API Imagery)"
      : evidenceAlert?.observation_source
        ? formatSourceLabel(evidenceAlert.observation_source)
        : "SimSat mission scan",
    bbox: mission.bbox ?? base.bbox,
    alert_payload_bytes: alertBytes,
    payload_reduction_ratio: alertBytes > 0 ? Number((RAW_FRAME_BYTES / alertBytes).toFixed(2)) : null,
    confidence,
    result,
    mission: mission.task_text,
    source_capture_time: dateRange,
    prompt: mission.task_text,
    payload_accounting: buildMissionPayloadAccounting(hasRetainedAlert),
    output_json: {
      status,
      mission_id: mission.id,
      result,
      confidence,
      action: hasRetainedAlert ? "review_retained_alert" : "review_mission_summary",
      cell_id: evidenceAlert?.cell_id ?? `mission_${mission.id}`,
      reason_codes: reasonCodes,
      use_case_id: mission.use_case_id ?? mission.target_pack_id ?? "mission_review",
      target_pack_id: mission.target_pack_id ?? null,
      bbox: mission.bbox ?? null,
      start_date: mission.start_date,
      end_date: mission.end_date,
      cells_scanned: mission.cells_scanned,
      flags_found: mission.flags_found,
      runtime_truth_mode: evidenceAlert?.runtime_truth_mode ?? "live",
      imagery_origin: evidenceAlert?.imagery_origin ?? "simsat",
      scoring_basis: evidenceAlert?.scoring_basis ?? "mission_metadata",
      object_targets: targets,
      grounding: [],
    },
  };
}

function missionReasonCodes(mission: Mission | null): string[] {
  if (!mission) return [];
  return [
    mission.target_pack_id,
    mission.use_case_id,
    mission.mission_mode === "replay" ? "replay_evidence" : "mission_scan",
  ].filter((value): value is string => Boolean(value));
}

function rounded(value: number): number {
  return Number(value.toFixed(3));
}

function weighted(signal: string, weight: number, score: number, evidence: string): ConfidenceContributor {
  return {
    signal,
    weight,
    score,
    weighted: rounded(weight * score),
    evidence,
  };
}

function buildConfidenceContributors(
  demoCase: DemoCase,
  evidenceAlert: AlertItem | null,
  hasObjectEvidence: boolean,
): ConfidenceContributor[] {
  const normalized = `${demoCase} ${evidenceAlert?.cell_id ?? ""} ${evidenceAlert?.reason_codes?.join(" ") ?? ""} ${evidenceAlert?.scoring_basis ?? ""}`.toLowerCase();
  if (normalized.includes("ice") || normalized.includes("ndsi") || evidenceAlert?.scoring_basis === "multispectral_bands") {
    return [
      weighted("spectral bands", 0.4, 0.9, "Green, NIR, SWIR1, and NDSI support the snow/ice signal."),
      weighted("SCL scene quality", 0.2, 0.82, "Cloud/no-data windows are rejected before scoring."),
      weighted("temporal persistence", 0.2, 0.78, "Accepted frames persist across the replay window."),
      weighted("visual context", 0.12, 0.66, "Context timelapse is used for review, not as the scoring basis."),
      weighted("CV/depth context", 0.08, 0.26, "No object-count or depth claim is used for this ice proof."),
    ];
  }

  if (normalized.includes("maritime") || normalized.includes("vessel") || normalized.includes("ship")) {
    return [
      weighted("temporal context", 0.3, 0.82, "Accepted maritime frames changed after cloudy windows were rejected."),
      weighted("scene quality", 0.2, 0.78, "Cloud-gated replay metadata stays attached."),
      weighted("area evidence", 0.22, hasObjectEvidence ? 0.72 : 0.6, "Vessel-like cues are treated as maritime activity areas."),
      weighted("source provenance", 0.18, 0.86, "Replay source, bbox, and provider metadata are bound to the alert."),
      weighted("CV/depth context", 0.1, hasObjectEvidence ? 0.48 : 0.22, "Visual boxes support review but do not become exact counts."),
    ];
  }

  if (
    normalized.includes("deforestation")
    || normalized.includes("canopy")
    || normalized.includes("clearing")
    || normalized.includes("ndvi_drop")
    || normalized.includes("soil_exposure")
  ) {
    return [
      weighted("temporal persistence", 0.28, 0.88, "The clearing signal persists from baseline to current replay windows."),
      weighted("proxy band signal", 0.24, 0.84, "NDVI, NBR, NDMI, and soil-ratio deltas support canopy-loss review."),
      weighted("scene quality", 0.16, 0.9, "Cached same-season frames are high quality and cloud/no-data flags are absent."),
      weighted("CV region evidence", 0.18, hasObjectEvidence ? 0.82 : 0.58, "Clearing, road, exposed-soil, and boundary boxes stay region-level."),
      weighted("Ground Agent review", 0.14, 0.76, "Ground Validator recommends defer/review and preserves source provenance."),
    ];
  }

  if (
    normalized.includes("mining")
    || normalized.includes("tailings")
    || normalized.includes("excavation")
    || normalized.includes("bare_ground")
    || normalized.includes("bare ground")
  ) {
    return [
      weighted("temporal expansion", 0.3, 0.86, "Open-pit and exposed-surface regions persist across the replay window."),
      weighted("industrial morphology", 0.22, hasObjectEvidence ? 0.82 : 0.72, "Pond/tailings/pit/road regions are treated as area evidence, not production estimates."),
      weighted("scene quality", 0.16, 0.9, "Arid same-season frames preserve clear visual structure."),
      weighted("source provenance", 0.18, 0.88, "Provider, capture dates, bbox, prompt, and replay id stay attached."),
      weighted("review safety", 0.14, 0.74, "The packet avoids illegal-mining, pollution, or resource-output claims without external validation."),
    ];
  }

  return [
    weighted("temporal signal", 0.34, 0.78, "Before/after windows support the retained packet."),
    weighted("scene quality", 0.18, 0.74, "Quality metadata stays with the replay."),
    weighted("visual grounding", 0.2, hasObjectEvidence ? 0.76 : 0.62, "Grounding is candidate evidence pending review."),
    weighted("source provenance", 0.18, 0.86, "Provider, bbox, task, and replay id are carried into proof JSON."),
    weighted("map/context", 0.1, 0.34, "Map context assists review but is not scored evidence."),
  ];
}

function buildNoFindingsContributors(mission: Mission | null): ConfidenceContributor[] {
  const cellsScanned = Number(mission?.cells_scanned ?? 0);
  return [
    weighted("scan completion", 0.34, cellsScanned > 0 ? 0.9 : 0.3, `${cellsScanned} mission cells were swept inside the selected bbox.`),
    weighted("no retained flags", 0.26, 0.88, "No cell passed the mission target retention threshold."),
    weighted("source provenance", 0.2, 0.84, "Task, bbox, dates, source mode, and target pack stay attached to the proof."),
    weighted("review safety", 0.2, 0.82, "Proof Mode reports the no-finding result without borrowing another replay's imagery."),
  ];
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

function proofString(value: unknown, fallback = "unknown"): string {
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number" && Number.isFinite(value)) return value.toLocaleString();
  return fallback;
}

function clampUnit(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

function proofOverlayStyle(box: VlmBoxResult): CSSProperties {
  const [a = 0, b = 0, c = 0, d = 0] = box.bbox;
  const [xminRaw, yminRaw, xmaxRaw, ymaxRaw] = box.bbox_format === "unit_yxyx"
    ? [b, a, d, c]
    : [a, b, c, d];
  const xmin = Math.min(clampUnit(xminRaw), clampUnit(xmaxRaw));
  const xmax = Math.max(clampUnit(xminRaw), clampUnit(xmaxRaw));
  const ymin = Math.min(clampUnit(yminRaw), clampUnit(ymaxRaw));
  const ymax = Math.max(clampUnit(yminRaw), clampUnit(ymaxRaw));
  const color = colorForVlmBox(box);
  return {
    left: `${xmin * 100}%`,
    top: `${ymin * 100}%`,
    width: `${Math.max(0.01, xmax - xmin) * 100}%`,
    height: `${Math.max(0.01, ymax - ymin) * 100}%`,
    borderColor: color,
    backgroundColor: `${color}1f`,
    boxShadow: `0 0 0 1px rgba(2,6,23,0.65), 0 0 18px ${color}99`,
  };
}

function proofOverlayLabel(box: VlmBoxResult): string {
  const confidence = typeof box.confidence === "number" ? ` ${box.confidence.toFixed(2)}` : "";
  return `${displayObjectEvidenceLabel(box)}${confidence}`;
}

function replayDisplayName(replayId: string): string {
  return replayId
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function isReplayOverride(demoCase: DemoCase, mission: Mission | null): boolean {
  return Boolean(mission?.replay_id && mission.replay_id !== DEMO_PROFILES[demoCase].replayId);
}

function missionReplayContext(
  mission: Mission | null,
  proof: ProofJson,
): { what: string; where: string; when: string; why: string } {
  const task = mission?.task_text?.trim() || proof.mission;
  const replayId = mission?.replay_id ?? proof.replay_id;
  const dateRange = [mission?.start_date, mission?.end_date].filter(Boolean).join(" to ") || proof.source_capture_time;
  const normalized = `${task} ${replayId} ${mission?.use_case_id ?? ""}`.toLowerCase();

  if (normalized.includes("fire") || normalized.includes("wildfire") || normalized.includes("burn") || normalized.includes("smoke")) {
    return {
      what: "Florida Fire/Drought readiness pass reviews candidate fireline context",
      where: normalized.includes("florida") ? "North Florida corridor" : "operator-selected firewatch bbox",
      when: dateRange,
      why: "keep smoke, active-fire, and burn-scar claims candidate-only until source-backed imagery supports them",
    };
  }

  if (normalized.includes("maritime") || normalized.includes("vessel") || normalized.includes("singapore")) {
    return {
      what: "Ground Agent loads short-term maritime traffic replay evidence",
      where: normalized.includes("singapore") ? "Singapore Strait anchorage" : "maritime focus area",
      when: dateRange,
      why: "review vessel and port activity with source metadata, rejected windows, and bbox context attached",
    };
  }

  return {
    what: task,
    where: "operator-selected mission bbox",
    when: dateRange,
    why: "keep the claim bound to its evidence, source, model output, and compact proof JSON",
  };
}

function missionReplayStoryLines(mission: Mission | null): string[] {
  const normalized = `${mission?.task_text ?? ""} ${mission?.replay_id ?? ""} ${mission?.use_case_id ?? ""}`.toLowerCase();
  if (normalized.includes("fire") || normalized.includes("wildfire") || normalized.includes("burn") || normalized.includes("smoke")) {
    return [
      "Operator selected a firewatch focus bbox.",
      "Satellite Pruner swept cells and filtered proxy-only vegetation changes.",
      "Ground Validator keeps fire claims candidate-only without source-backed smoke, active-fire, or burn-scar evidence.",
      "Proof Mode shows mission-bounded metadata and compact JSON before any stronger claim.",
    ];
  }

  if (normalized.includes("maritime") || normalized.includes("vessel") || normalized.includes("singapore")) {
    return [
      "Operator selected a maritime focus bbox.",
      "Ground Agent proposed the cached replay before changing state.",
      "Cloud rejects and source metadata stay attached.",
      "Proof Mode shows bbox-bound evidence and compact JSON.",
    ];
  }

  return [
    "Operator selected a mission focus bbox.",
    "Ground Agent kept the mission evidence bounded.",
    "The proof keeps task, source, model, and bbox attached.",
    "Compact JSON is reviewable without raw-frame downlink.",
  ];
}

function missionProofTitle(mission: Mission | null, proof: ProofJson): string {
  if (mission?.replay_id) {
    return `${replayDisplayName(mission.replay_id)} proof`;
  }
  const rawTitle = mission?.task_text?.trim() || proof.mission || "Current mission";
  const title = rawTitle.replace(/^Run\s+/i, "").replace(/\.$/, "");
  return `${title.length > 84 ? `${title.slice(0, 81)}...` : title} proof`;
}

export default function ProofModePanel({
  apiBaseUrl,
  demoCase,
  demoMode = true,
  mission,
  alerts,
  metricsSummary,
  selectedCellId,
  onClose,
  onStepChange,
}: ProofModePanelProps) {
  const [recentAlerts, setRecentAlerts] = useState<AlertItem[]>(alerts);
  const [metrics, setMetrics] = useState<ApiMetricsSummary | null>(metricsSummary);
  const [galleryItem, setGalleryItem] = useState<GalleryItem | null>(null);
  const [missionTimelapse, setMissionTimelapse] = useState<MissionTimelapse | null>(null);
  const [missionTimelapseError, setMissionTimelapseError] = useState<string | null>(null);
  const [groundingResults, setGroundingResults] = useState<VlmBoxResult[]>(() => {
    if (!demoMode) return [];
    const profile = DEMO_PROFILES[demoCase];
    return [{ label: profile.groundingLabel, bbox: profile.groundingBox }];
  });
  const [vqaAnswer, setVqaAnswer] = useState(
    demoMode ? DEMO_PROFILES[demoCase].vqa : "Mission evidence is bounded to the selected bbox and retained alert packets.",
  );
  const [caption, setCaption] = useState(
    demoMode ? DEMO_PROFILES[demoCase].caption : "Current mission proof uses mission metadata until retained imagery is selected.",
  );
  const [observedLatencyMs, setObservedLatencyMs] = useState<number | null>(null);
  const [proof, setProof] = useState<ProofJson>(() => (
    demoMode ? buildFallbackProof(demoCase) : buildMissionProof(mission, demoCase)
  ));
  const [linkOffline, setLinkOffline] = useState(false);
  const [queueCount, setQueueCount] = useState(0);
  const [flushedQueueCount, setFlushedQueueCount] = useState(0);
  const [linkStatus, setLinkStatus] = useState("LINK OPEN");
  const [dtnProof, setDtnProof] = useState<DtnProof | null>(null);

  useEffect(() => {
    setRecentAlerts(alerts);
  }, [alerts]);

  useEffect(() => {
    setMetrics(metricsSummary);
  }, [metricsSummary]);

  const missionScoped = !demoMode && Boolean(mission);
  const liveMissionScoped = missionScoped && !mission?.replay_id;
  const usesReplayEvidence = Boolean(mission?.replay_id) || (demoMode && demoCase === "showcase");
  const scopedAlerts = useMemo(() => (
    liveMissionScoped
      ? filterAlertsForBbox(recentAlerts, mission?.bbox)
      : recentAlerts
  ), [liveMissionScoped, mission, recentAlerts]);

  const activeAlert = useMemo(() => {
    if (selectedCellId) {
      const matching = scopedAlerts.find((alert) => alert.cell_id === selectedCellId);
      if (matching) return matching;
    }
    return scopedAlerts[0] ?? null;
  }, [scopedAlerts, selectedCellId]);
  const missionAlert = missionScoped ? activeAlert : null;

  useEffect(() => {
    if (!demoMode) {
      setProof(buildMissionProof(mission, demoCase, missionAlert));
      setGroundingResults([]);
    }
  }, [demoCase, demoMode, mission, missionAlert]);

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

      const resolvedScopedAlerts = liveMissionScoped
        ? filterAlertsForBbox(resolvedAlerts, mission?.bbox)
        : resolvedAlerts;
      const resolvedAlert = selectedCellId
        ? resolvedScopedAlerts.find((alert) => alert.cell_id === selectedCellId) ?? resolvedScopedAlerts[0] ?? null
        : resolvedScopedAlerts[0] ?? null;

      if (usesReplayEvidence && resolvedAlert?.cell_id) {
        const galleryPayload = await fetchJson<GalleryItem>(`${apiBaseUrl}/api/gallery/${resolvedAlert.cell_id}`);
        if (!cancelled) setGalleryItem(galleryPayload);
      }

      if (usesReplayEvidence) {
        await sleep(700);
        onStepChange?.(4);
        const bbox = mission?.bbox ?? SHOWCASE_BBOX;
        const replayPrompt = mission?.task_text ?? SHOWCASE_PROMPT;
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
        if (demoMode) {
          const profile = DEMO_PROFILES[demoCase];
          setGroundingResults([{ label: profile.groundingLabel, bbox: profile.groundingBox }]);
          setVqaAnswer(profile.vqa);
          setCaption(profile.caption);
        } else {
          setGroundingResults([]);
          const hasFindings = Boolean(resolvedAlert) || Number(mission?.flags_found ?? 0) > 0;
          setVqaAnswer(
            hasFindings
              ? "Retained mission evidence is bounded to the selected bbox and alert packets."
              : "Nothing interesting was retained in this mission pass.",
          );
          setCaption(
            hasFindings
              ? "Current mission proof uses retained alert metadata and mission context."
              : "Mission completed with no retained flags; the related timelapse is context only.",
          );
          setMissionTimelapse(null);
          setMissionTimelapseError(null);
          if (mission?.bbox) {
            const defaultStart = mission.start_date || "2025-05-05";
            const defaultEnd = mission.end_date || "2026-05-05";
            const timelapsePayload = await fetchJson<MissionTimelapse & { error?: string; format?: string }>(
              `${apiBaseUrl}/api/timelapse/generate`,
              {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  bbox: mission.bbox,
                  start_date: defaultStart,
                  end_date: defaultEnd,
                  steps: 12,
                }),
              },
            );
            if (!cancelled) {
              if (
                timelapsePayload?.video_b64
                && Number(timelapsePayload.frames_count ?? 0) >= 2
                && timelapsePayload.format !== "none"
              ) {
                setMissionTimelapse(timelapsePayload);
              } else {
                setMissionTimelapseError(timelapsePayload?.error || "Related timelapse unavailable for this mission window.");
              }
            }
          }
        }
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
  }, [apiBaseUrl, alerts, demoCase, demoMode, metricsSummary, mission, onStepChange, selectedCellId, usesReplayEvidence]);

  useEffect(() => {
    if (!demoMode && mission) {
      setProof(buildMissionProof(mission, demoCase, missionAlert));
      return;
    }
    const isAbstain = demoCase === "abstain";
    const profile = DEMO_PROFILES[demoCase];
    const bbox = usesReplayEvidence ? mission?.bbox ?? profile.bbox : profile.bbox;
    const evidenceAlert = usesReplayEvidence ? activeAlert : null;
    const alertBytes = isAbstain ? 0 : usesReplayEvidence ? evidenceAlert?.payload_bytes ?? ALERT_JSON_BYTES : ALERT_JSON_BYTES;
    const ratio = isAbstain || alertBytes <= 0 ? null : Number((RAW_FRAME_BYTES / alertBytes).toFixed(2));
    const missionObjectTargets = mission?.object_targets?.filter((target) => target.enabled).map((target) => target.label) ?? [];
    const compactDetectionSummary = evidenceAlert?.detection_summary
      ? {
          target_pack_id: evidenceAlert.detection_summary.target_pack_id ?? mission?.target_pack_id ?? null,
          total_boxes: evidenceAlert.detection_summary.total_boxes,
          counts_by_label: evidenceAlert.detection_summary.counts_by_label,
          top_boxes: evidenceAlert.detection_summary.top_boxes.slice(0, 8).map((box) => ({
            label: box.label,
            bbox: box.bbox,
            confidence: box.confidence,
            source_model: box.source_model,
            count_quality: box.count_quality,
            scoring_basis: box.scoring_basis,
            imagery_origin: box.imagery_origin,
          })),
          provenance: evidenceAlert.detection_summary.provenance ?? {},
        }
      : null;
    const compactObjectDeltas = evidenceAlert?.object_deltas?.length
      ? evidenceAlert.object_deltas.map((delta) => ({
          label: delta.label,
          baseline_count: delta.baseline_count,
          current_count: delta.current_count,
          delta_count: delta.delta_count,
          action_hint: delta.action_hint,
        }))
      : [];
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
    const confidenceStack = buildConfidenceContributors(demoCase, evidenceAlert, Boolean(compactDetectionSummary));
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
          confidence_stack: confidenceStack,
          grounding: groundingResults,
          visual_summary: vqaAnswer,
          evidence_note: caption,
          ...(missionObjectTargets.length > 0 ? { object_targets: missionObjectTargets } : {}),
          ...(compactDetectionSummary ? { detections: compactDetectionSummary } : {}),
          ...(compactObjectDeltas.length > 0 ? { object_deltas: compactObjectDeltas } : {}),
          ...(demoCase === "eclipse"
            ? {
                link_state_before: dtnProof?.link_state_before ?? (linkOffline ? "offline" : "online"),
                queued_alerts_before_restore: dtnProof?.queued_alerts_before_restore ?? queueCount,
                link_state_after: dtnProof?.link_state_after ?? linkStatus.toLowerCase().replace("link ", ""),
                queued_alerts_after_restore: dtnProof?.queued_alerts_after_restore ?? queueCount,
                flushed_alerts: dtnProof?.flushed_alerts ?? flushedQueueCount,
                queue_source: dtnProof?.queue_source ?? "agent_bus_unread_messages",
                action: "queue_compact_json_until_link_restored",
              }
            : {}),
        };

    setProof({
      demo: isReplayOverride(demoCase, mission)
        ? replayDisplayName(mission?.replay_id ?? "mission_replay")
        : demoName(demoCase),
      replay_id: usesReplayEvidence ? mission?.replay_id ?? mission?.use_case_id ?? profile.replayId : profile.replayId,
      model: SHOWCASE_MODEL,
      provider,
      bbox,
      latency_ms: usesReplayEvidence ? SEEDED_LATENCY_MS : profile.latencyMs,
      raw_payload_bytes: RAW_FRAME_BYTES,
      alert_payload_bytes: alertBytes,
      payload_reduction_ratio: ratio,
      confidence,
      abstained: isAbstain,
      result,
      mission: usesReplayEvidence ? mission?.task_text ?? profile.mission : profile.mission,
      source_capture_time: captureTime,
      prompt,
      payload_accounting: buildPayloadAccounting(isAbstain),
      output_json: outputJson,
      artifacts: {
        screenshot: "final-screen.png",
        evidence_frame: "evidence-frame.png",
        video: "Playwright report video",
        trace: "Playwright report trace.zip",
      },
    });
  }, [activeAlert, caption, demoCase, demoMode, dtnProof, flushedQueueCount, groundingResults, linkOffline, linkStatus, mission, missionAlert, queueCount, usesReplayEvidence, vqaAnswer]);

  const toggleOrbitalEclipse = async () => {
    if (!linkOffline) {
      const payload = await fetchJson<DtnProof>(`${apiBaseUrl}/api/link/dtn-proof`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phase: "offline", count: 4 }),
      });
      setDtnProof(payload);
      setLinkOffline(true);
      setLinkStatus("LINK OFFLINE");
      setQueueCount(payload?.queued_alerts_before_restore ?? 4);
      setFlushedQueueCount(0);
      return;
    }

    const payload = await fetchJson<DtnProof>(`${apiBaseUrl}/api/link/dtn-proof`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phase: "restore" }),
    });
    setDtnProof(payload);
    setFlushedQueueCount(payload?.flushed_alerts ?? queueCount);
    setQueueCount(payload?.queued_alerts_after_restore ?? 0);
    setLinkOffline(false);
    setLinkStatus("LINK RESTORED");
  };

  const proofJson = useMemo(() => JSON.stringify(proof, null, 2), [proof]);
  const sourceText = `${proof.provider} / ${proof.source_capture_time}`;
  const evidenceAlert = usesReplayEvidence || liveMissionScoped ? activeAlert : null;
  const activeObjectTargets = mission?.object_targets?.filter((target) => target.enabled).map((target) => target.label) ?? [];
  const detectionSummary = evidenceAlert?.detection_summary ?? null;
  const objectDeltas = evidenceAlert?.object_deltas ?? [];
  const detectionCounts = detectionSummary ? Object.entries(detectionSummary.counts_by_label) : [];
  const proofOverlayBoxes = detectionSummary?.top_boxes?.length
    ? detectionSummary.top_boxes.slice(0, 6)
    : groundingResults.slice(0, 6);
  const profile = DEMO_PROFILES[demoCase];
  const fallbackVideoSource = proof.abstained || liveMissionScoped ? null : profile.visualVideo ?? null;
  const imageSource = usesReplayEvidence
    ? galleryItem?.context_thumb ?? profile.visualAsset ?? null
    : liveMissionScoped
      ? null
      : profile.visualAsset ?? null;
  const timelapseSource = proof.abstained
    ? null
    : usesReplayEvidence
      ? galleryItem?.timelapse_b64 ?? fallbackVideoSource
      : liveMissionScoped
        ? missionTimelapse?.video_b64 ?? null
        : fallbackVideoSource;
  const usingFallbackVideo = Boolean(fallbackVideoSource && timelapseSource === fallbackVideoSource);
  const visualSourceLabel = timelapseSource
    ? usingFallbackVideo
      ? profile.visualVideoSource ?? "Context Timelapse"
      : liveMissionScoped
        ? missionTimelapse?.provenance?.label
          ?? formatSourceLabel(missionTimelapse?.source ?? missionTimelapse?.provider ?? "mission timelapse")
        : formatSourceLabel(galleryItem?.timelapse_source ?? "replay")
    : imageSource
      ? usesReplayEvidence
        ? formatSourceLabel(galleryItem?.context_thumb_source ?? evidenceAlert?.observation_source)
        : proof.abstained
          ? "Local Quality Preview"
          : "Local Mission Frame"
      : proof.abstained
        ? "No Imagery Downlink"
        : liveMissionScoped
          ? "Mission BBox + Results"
        : demoCase === "eclipse"
          ? "Mission BBox + Queue"
          : "Mission BBox";
  const reasonCodes = evidenceAlert?.reason_codes ?? (liveMissionScoped ? missionReasonCodes(mission) : DEMO_REASON_CODES[demoCase]);
  const cellsScanned = liveMissionScoped
    ? Number(mission?.cells_scanned ?? 0)
    : metrics?.total_cells_scanned ?? mission?.cells_scanned ?? 9;
  const alertsEmitted =
    liveMissionScoped
      ? Number(mission?.flags_found ?? 0)
      : demoCase === "eclipse"
      ? Math.max(
          queueCount,
          flushedQueueCount,
          dtnProof?.queued_alerts_before_restore ?? 0,
          dtnProof?.flushed_alerts ?? 0,
          metrics?.total_alerts_emitted ?? 0,
          mission?.flags_found ?? 0,
        )
      : metrics?.total_alerts_emitted ?? mission?.flags_found ?? 4;
  const alertMetricLabel = demoCase === "eclipse" ? "Packets" : "Alerts";
  const replayOverride = isReplayOverride(demoCase, mission);
  const context = replayOverride || missionScoped ? missionReplayContext(mission, proof) : DEMO_CONTEXT[demoCase];
  const storyLines = replayOverride || missionScoped ? missionReplayStoryLines(mission) : DEMO_STORY_LINES[demoCase];
  const proofTitle = replayOverride || missionScoped
    ? missionProofTitle(mission, proof)
    : DEMO_TITLES[demoCase];
  const liveMissionHasFindings = liveMissionScoped && (Boolean(evidenceAlert) || Number(mission?.flags_found ?? 0) > 0);
  const confidenceStack = Array.isArray(proof.output_json.confidence_stack)
    ? (proof.output_json.confidence_stack as ConfidenceContributor[])
    : liveMissionScoped && !liveMissionHasFindings
      ? buildNoFindingsContributors(mission)
      : buildConfidenceContributors(demoCase, evidenceAlert, Boolean(detectionSummary));
  const proofStatusLabel = proof.abstained
    ? "ABSTAINED"
    : liveMissionScoped
      ? (liveMissionHasFindings ? "MISSION PROOF" : "NO FLAGS")
      : "ALERT READY";
  const proofDeliveryStatus = proof.abstained
    ? "status: abstained"
    : liveMissionScoped && !liveMissionHasFindings
      ? "status: no flags retained"
      : "status: transmitted";
  const showFrameOverlays = Boolean((timelapseSource || imageSource) && (!liveMissionScoped || liveMissionHasFindings));

  return (
    <div data-testid="proof-mode-panel" className="absolute inset-0 z-40 flex flex-col bg-zinc-950 text-zinc-100">
      <header className="flex shrink-0 items-center justify-between border-b border-zinc-800 bg-zinc-950 px-5 py-3">
        <div className="min-w-0 pr-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-cyan-300">Proof Mode</p>
          <h1 data-testid="demo-title" className="text-xl font-semibold text-white">
            {proofTitle}
          </h1>
          <p
            data-testid="demo-context-caption"
            className="mt-1 max-w-[980px] text-[11px] font-medium leading-snug text-zinc-300"
          >
            What: {context.what}. Where: {context.where}. When: {context.when}. Why: {context.why}.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="rounded border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-200">
            {proofStatusLabel}
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
              {usesReplayEvidence ? mission?.replay_id ?? SHOWCASE_REPLAY_ID : mission?.use_case_id ?? DEMO_PROFILES[demoCase].replayId}
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
              <p className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">{alertMetricLabel}</p>
              <p className="mt-1 text-lg font-semibold text-white">{alertsEmitted}</p>
            </div>
          </div>
          <div className="space-y-2 rounded border border-zinc-800 bg-zinc-950 p-3 text-xs text-zinc-300">
            {storyLines.map((line) => (
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
              <h2 className="text-sm font-semibold text-white">
                {liveMissionScoped && !liveMissionHasFindings ? "Mission result timelapse" : "BBox evidence overlay"}
              </h2>
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
                  void video.play().catch(() => undefined);
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
                  {proof.abstained ? "Quality Gate" : liveMissionScoped ? "Mission Summary" : "Delay-Tolerant Link"}
                </p>
                <p className="max-w-md text-lg font-semibold text-white">
                  {proof.abstained
                    ? "No imagery was trusted enough to transmit."
                    : liveMissionScoped
                      ? liveMissionHasFindings ? "Mission proof is ready." : MISSION_NO_IMAGE_TITLE
                    : "No raw frame was pushed while the link was offline."}
                </p>
                <p className="max-w-md text-xs leading-relaxed text-zinc-400">
                  {proof.abstained
                    ? "The proof records an abstain decision, low confidence, and a blocked alert packet."
                    : liveMissionScoped
                      ? liveMissionHasFindings
                        ? "A retained alert packet exists, but no related timelapse frame is available for this cell yet."
                        : `${MISSION_NO_IMAGE_BODY}${missionTimelapseError ? ` ${missionTimelapseError}` : ""}`
                    : "The mission keeps only compact JSON alerts in the local queue until the downlink is restored."}
                </p>
                {liveMissionScoped && (
                  <p className="max-w-md text-[11px] font-medium leading-relaxed text-cyan-200">
                    {MISSION_NO_IMAGE_NOTE}
                  </p>
                )}
              </div>
            )}
            {liveMissionScoped && !liveMissionHasFindings && (
              <div
                data-testid="proof-mission-result-overlay"
                className="absolute left-4 top-4 max-w-[360px] rounded border border-emerald-300/40 bg-zinc-950/88 px-3 py-2 text-zinc-100 shadow-lg backdrop-blur"
              >
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-emerald-200">Nothing interesting found</p>
                <p className="mt-1 text-xs font-medium leading-relaxed text-zinc-300">
                  {mission?.cells_scanned ?? 0} cells scanned, 0 flags retained. Related timelapse is context only.
                </p>
              </div>
            )}
            {showFrameOverlays && (
              <>
                <div className="absolute inset-[18%] border-2 border-cyan-300 shadow-[0_0_0_9999px_rgba(2,6,23,0.24)]" />
                <div className="absolute left-[24%] top-[28%] h-[38%] w-[45%] border-2 border-red-400 bg-red-500/10" />
                <div className="absolute left-[24%] top-[calc(28%-28px)] rounded bg-red-500 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-white">
                  evidence bbox
                </div>
              </>
            )}
            {showFrameOverlays && !proof.abstained && proofOverlayBoxes.map((box, index) => (
              <div
                key={`${box.label}-${index}`}
                data-testid="proof-cv-box"
                className="pointer-events-none absolute border-2"
                style={proofOverlayStyle(box)}
              >
                <span
                  className="absolute left-0 top-0 max-w-[190px] -translate-y-full rounded-t px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-zinc-950 shadow"
                  style={{ backgroundColor: colorForVlmBox(box) }}
                >
                  {proofOverlayLabel(box)}
                </span>
              </div>
            ))}
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
                ? liveMissionScoped
                  ? "Related mission timelapse: context only"
                  : usingFallbackVideo
                  ? "Context timelapse: spectral metadata is scoring basis"
                  : "Replay WebM evidence: contextual frames"
                : proof.abstained
                  ? "Static local frame: no alert transmitted"
                  : liveMissionScoped
                    ? "Mission proof: compact JSON and bbox metadata"
                  : demoCase === "eclipse"
                    ? "Static local frame: compact JSON queue only"
                    : "Static satellite frame: raw image stays local"}
            </div>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-3">
            <div className="rounded border border-zinc-800 bg-zinc-950 p-3">
              <p className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Evidence result</p>
              <p className="mt-1 text-xs font-semibold text-white">{proof.result}</p>
            </div>
            <div className="rounded border border-zinc-800 bg-zinc-950 p-3">
              <p className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Visual summary</p>
              <p className="mt-1 text-xs font-semibold text-white">{proof.abstained ? "Unavailable" : vqaAnswer}</p>
            </div>
            <div className="rounded border border-zinc-800 bg-zinc-950 p-3">
              <p className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Evidence note</p>
              <p className="mt-1 text-xs font-semibold text-white">{proof.abstained ? "No note transmitted" : caption}</p>
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
            <ProofRow label="Payload basis" value={proof.payload_accounting.alert_payload_basis} testId="proof-payload-accounting" />
            <ProofRow label="Reduction ratio" value={formatRatio(proof.payload_reduction_ratio)} testId="proof-reduction-ratio" />
            <ProofRow label="Abstain status" value={proofDeliveryStatus} />
          </div>

          <div
            data-testid="proof-confidence-stack"
            className="mt-3 rounded border border-emerald-500/25 bg-emerald-500/10 p-3 text-xs text-emerald-50"
          >
            <div className="mb-2 flex items-center justify-between gap-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-200">
                Confidence Stack
              </p>
              <span className="rounded border border-emerald-300/30 bg-zinc-950/60 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-emerald-100">
                total {proof.abstained ? "low" : proof.confidence.toFixed(2)}
              </span>
            </div>
            <div className="space-y-1.5">
              {confidenceStack.map((item) => (
                <div key={item.signal} className="rounded border border-emerald-300/20 bg-zinc-950/45 px-2 py-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-[10px] font-semibold uppercase tracking-[0.1em] text-emerald-100">
                      {item.signal}
                    </span>
                    <span className="shrink-0 text-[10px] font-semibold text-white">
                      {(item.weight * 100).toFixed(0)}% x {item.score.toFixed(2)} = {item.weighted.toFixed(2)}
                    </span>
                  </div>
                  <p className="mt-0.5 truncate text-[10px] text-emerald-200/70">{item.evidence}</p>
                </div>
              ))}
            </div>
          </div>

          {(activeObjectTargets.length > 0 || detectionSummary || objectDeltas.length > 0) && (
            <div
              data-testid="proof-object-evidence"
              className="mt-3 space-y-3 rounded border border-cyan-500/30 bg-cyan-500/10 p-3 text-xs text-cyan-50"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-200">
                    Object Evidence
                  </p>
                  {detectionSummary?.target_pack_id && (
                    <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-cyan-300/80">
                      Pack: {detectionSummary.target_pack_id}
                    </p>
                  )}
                </div>
                {detectionSummary && (
                  <span className="rounded border border-cyan-300/30 bg-zinc-950/60 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-cyan-100">
                    {detectionSummary.total_boxes} boxes
                  </span>
                )}
              </div>

              {activeObjectTargets.length > 0 && (
                <div>
                  <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-cyan-300/80">
                    Searched
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {activeObjectTargets.map((target) => (
                      <span key={target} className="rounded border border-cyan-300/25 bg-zinc-950/50 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.1em]">
                        {target}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {detectionCounts.length > 0 && (
                <div>
                  <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-cyan-300/80">
                    Found
                  </p>
                  <div className="grid grid-cols-2 gap-1.5">
                    {detectionCounts.map(([label, count]) => {
                      const sampleBox = detectionSummary?.top_boxes?.find((box) => box.label === label);
                      return (
                        <div key={label} className="rounded border border-cyan-300/20 bg-zinc-950/45 px-2 py-1">
                          <p className="truncate text-[10px] font-semibold uppercase tracking-[0.1em] text-cyan-100">
                            {displayObjectEvidenceLabel(sampleBox ?? label)}
                          </p>
                          <p className="text-sm font-bold text-white">{displayObjectEvidenceCount(label, count, sampleBox)}</p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {detectionSummary?.top_boxes?.length ? (
                <div>
                  <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-cyan-300/80">
                    Top Boxes
                  </p>
                  <div className="space-y-1.5">
                    {detectionSummary.top_boxes.slice(0, 4).map((box, index) => (
                      <div key={box.id ?? `${box.label}-${index}`} className="rounded border border-cyan-300/20 bg-zinc-950/45 px-2 py-1">
                        <p className="truncate text-[10px] font-semibold uppercase tracking-[0.1em] text-cyan-100">
                          {displayObjectEvidenceLabel(box)} · {box.confidence !== undefined ? box.confidence.toFixed(2) : "n/a"}
                        </p>
                        <p className="truncate text-[10px] text-cyan-200/70">
                          {box.source_model ?? "unknown source"} · [{box.bbox.map((value) => value.toFixed(2)).join(", ")}]
                        </p>
                        <p className="truncate text-[10px] text-cyan-200/80">{objectEvidenceScopeNote(box)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {objectDeltas.length > 0 && (
                <div>
                  <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-cyan-300/80">
                    Count Delta
                  </p>
                  <div className="space-y-1.5">
                    {objectDeltas.slice(0, 4).map((delta) => (
                      <div key={delta.label} className="flex items-center justify-between gap-2 rounded border border-cyan-300/20 bg-zinc-950/45 px-2 py-1">
                        <span className="truncate text-[10px] font-semibold uppercase tracking-[0.1em]">{delta.label}</span>
                        <span className="shrink-0 text-[10px] font-semibold text-cyan-100">
                          {delta.baseline_count} to {delta.current_count} ({delta.delta_count >= 0 ? "+" : ""}{delta.delta_count}) · {delta.action_hint}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {demoCase === "payload" && (
            <div className="mt-3 rounded border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm font-semibold text-emerald-100">
              <p>Raw frame: {formatBytes(RAW_FRAME_BYTES)}</p>
              <p>Alert JSON: {formatBytes(ALERT_JSON_BYTES)}</p>
              <p>Downlink reduction: {formatRatio(proof.payload_reduction_ratio)}</p>
            </div>
          )}

          {demoCase === "eclipse" && (
            <div
              data-testid="dtn-proof-summary"
              className="mt-3 rounded border border-amber-500/30 bg-amber-500/10 p-3 text-xs font-semibold text-amber-100"
            >
              <p>queue_source: {proofString(proof.output_json.queue_source)}</p>
              <p>link_state_before: {proofString(proof.output_json.link_state_before)}</p>
              <p>queued_alerts_before_restore: {proofString(proof.output_json.queued_alerts_before_restore)}</p>
              <p>link_state_after: {proofString(proof.output_json.link_state_after)}</p>
              <p>flushed_alerts: {proofString(proof.output_json.flushed_alerts)}</p>
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
