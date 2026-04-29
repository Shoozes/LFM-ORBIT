/**
 * MissionControl — Operator command centre.
 *
 * - Natural-language task prompt → sent to agents as a mission
 * - DRAW AREA button → bbox rectangle selection on map
 * - Time range inputs (start/end date) → stored with mission for timelapse
 * - SEVER/RESTORE LINK toggle → simulates satellite blackout
 * - Mission status + history
 */
import { useEffect, useRef, useState } from "react";
import { getApiBaseUrl } from "../utils/telemetry";
import { Mission } from "../types/mission";

type ReplayCatalogItem = {
  replay_id: string;
  source_kind?: "curated_replay" | "seeded_cache" | string;
  title: string;
  description: string;
  summary: string;
  bbox?: number[] | null;
  use_case_id?: string | null;
  alert_count: number;
  cells_scanned: number;
  primary_cell_id: string;
};

type MonitorPreview = {
  kind: "lifeline" | "maritime";
  title: string;
  mode: string;
  primary: string;
  secondary: string[];
  status: string;
};

type MissionPresetTone =
  | "forest"
  | "traffic"
  | "water"
  | "ice"
  | "fire"
  | "flood"
  | "crop"
  | "urban"
  | "mining";

type MissionPreset = {
  id: string;
  label: string;
  place: string;
  useCaseId: string;
  taskText: string;
  bbox: number[];
  startDate: string;
  endDate: string;
  tone: MissionPresetTone;
};

type MaritimeMonitorResponse = {
  mode?: string;
  use_case?: { id?: string; display_name?: string };
  target?: { timestamp?: string };
  monitor?: { signals?: string[] };
  stac?: { disabled?: boolean; items?: unknown[] };
  investigation?: { directions?: unknown[] };
};

type LifelineMonitorResponse = {
  mode?: string;
  use_case?: { id?: string; display_name?: string };
  asset?: { display_name?: string; asset_id?: string };
  candidate?: { event_type?: string; civilian_impact?: string };
  decision?: { action?: string; priority?: string; downlink_now?: boolean };
  frames?: { pair_state?: { distinct_contextual_frames?: boolean; asset_pair_available?: boolean } };
};

type ApiErrorPayload = {
  detail?: string | { msg?: string; message?: string } | Array<{ msg?: string; message?: string } | string>;
  error?: string;
};

const MARITIME_PREVIEW_TARGET = {
  lat: 29.92,
  lon: 32.54,
  timestamp: "2025-12-15",
  bbox: [32.5, 29.88, 32.58, 29.96],
  taskText: "Review maritime vessel queueing near the Suez channel.",
};

const MISSION_LOCATION_PRESETS: MissionPreset[] = [
  {
    id: "deforestation_amazon",
    label: "Deforestation",
    place: "Amazon frontier",
    useCaseId: "deforestation",
    taskText: "Scan the Amazon frontier near Rondonia for new canopy loss against the same-season baseline.",
    bbox: [-62.1, -9.8, -61.4, -9.1],
    startDate: "2024-06-01",
    endDate: "2025-06-01",
    tone: "forest",
  },
  {
    id: "traffic_i4_disney",
    label: "Transport",
    place: "I-4 interchange",
    useCaseId: "civilian_lifeline_disruption",
    taskText: "Run a close transportation mix scan over the Florida I-4 and SR-536 interchange near Walt Disney World for road access, public mobility, and corridor bottleneck changes.",
    bbox: [-81.535, 28.36, -81.505, 28.39],
    startDate: "2025-03-01",
    endDate: "2025-03-15",
    tone: "traffic",
  },
  {
    id: "maritime_suez",
    label: "Maritime",
    place: "Suez channel",
    useCaseId: "maritime_activity",
    taskText: MARITIME_PREVIEW_TARGET.taskText,
    bbox: MARITIME_PREVIEW_TARGET.bbox,
    startDate: "2025-03-01",
    endDate: MARITIME_PREVIEW_TARGET.timestamp,
    tone: "water",
  },
  {
    id: "ice_greenland",
    label: "Ice/Snow",
    place: "Greenland coast",
    useCaseId: "ice_snow_extent",
    taskText: "Review Greenland edge snow and ice extent using NDSI, SCL cloud rejection, and multi-frame persistence before any extent-change label.",
    bbox: [-51.13, 69.1, -50.97, 69.26],
    startDate: "2024-01-15",
    endDate: "2025-12-15",
    tone: "ice",
  },
  {
    id: "wildfire_highway82",
    label: "Wildfire",
    place: "Highway 82 fire",
    useCaseId: "wildfire",
    taskText: "Review the Highway 82 wildfire near Atkinson and Waynesville, Georgia for smoke, burn scar, and vegetation stress.",
    bbox: [-81.916, 31.143, -81.756, 31.303],
    startDate: "2026-04-01",
    endDate: "2026-04-28",
    tone: "fire",
  },
  {
    id: "wildfire_future_spc_high_plains",
    label: "Fire Watch",
    place: "SPC D2 High Plains",
    useCaseId: "wildfire",
    taskText: "Watch the SPC Day 2 critical fire-weather corridor across eastern New Mexico and western Texas for new smoke plume, active-fire, or burn-scar evidence after the valid window.",
    bbox: [-104.9, 31.0, -101.1, 35.5],
    startDate: "2026-04-28",
    endDate: "2026-04-29",
    tone: "fire",
  },
  {
    id: "flood_manchar",
    label: "Flood",
    place: "Manchar Lake flood",
    useCaseId: "flood_extent",
    taskText: "Find new surface water and overflow around Pakistan's Manchar Lake during the 2022 flood sequence.",
    bbox: [67.63, 26.31, 67.87, 26.55],
    startDate: "2022-06-15",
    endDate: "2022-09-15",
    tone: "flood",
  },
  {
    id: "crop_kansas",
    label: "Crop",
    place: "Kansas fields",
    useCaseId: "crop_phenology",
    taskText: "Separate normal Kansas harvest cycles from structural land-cover loss using seasonal field history.",
    bbox: [-96.8, 39.0, -96.0, 39.8],
    startDate: "2024-04-01",
    endDate: "2025-11-01",
    tone: "crop",
  },
  {
    id: "urban_delhi",
    label: "Urban",
    place: "Delhi NCR",
    useCaseId: "urban_expansion",
    taskText: "Track Delhi NCR construction footprints becoming persistent built surface and road grid.",
    bbox: [77.3, 28.3, 77.9, 28.9],
    startDate: "2023-01-01",
    endDate: "2026-01-01",
    tone: "urban",
  },
  {
    id: "mining_atacama",
    label: "Mining",
    place: "Atacama open pit",
    useCaseId: "mining_expansion",
    taskText: "Detect Atacama open-pit mining expansion and separate persistent bare earth from seasonal vegetation loss.",
    bbox: [-69.115, -24.29, -69.035, -24.21],
    startDate: "2024-01-15",
    endDate: "2025-12-15",
    tone: "mining",
  },
];

const PRESET_TONE_CLASSES: Record<MissionPresetTone, string> = {
  forest: "border-emerald-200 bg-emerald-50 text-emerald-900 hover:bg-emerald-100",
  traffic: "border-amber-200 bg-amber-50 text-amber-900 hover:bg-amber-100",
  water: "border-blue-200 bg-blue-50 text-blue-900 hover:bg-blue-100",
  ice: "border-cyan-200 bg-cyan-50 text-cyan-900 hover:bg-cyan-100",
  fire: "border-red-200 bg-red-50 text-red-900 hover:bg-red-100",
  flood: "border-sky-200 bg-sky-50 text-sky-900 hover:bg-sky-100",
  crop: "border-lime-200 bg-lime-50 text-lime-900 hover:bg-lime-100",
  urban: "border-violet-200 bg-violet-50 text-violet-900 hover:bg-violet-100",
  mining: "border-stone-300 bg-stone-100 text-stone-900 hover:bg-stone-200",
};

const cleanApiError = (message: string) => message.replace(/^Value error,\s*/i, "");

async function readApiError(response: Response, fallback: string) {
  try {
    const payload = (await response.json()) as ApiErrorPayload;
    if (typeof payload.error === "string" && payload.error.trim()) {
      return cleanApiError(payload.error.trim());
    }
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return cleanApiError(payload.detail.trim());
    }
    if (Array.isArray(payload.detail)) {
      const messages = payload.detail
        .map((item) => {
          if (typeof item === "string") return item;
          return item.msg || item.message || "";
        })
        .map((item) => cleanApiError(item.trim()))
        .filter(Boolean);
      if (messages.length > 0) {
        return messages.join(" ");
      }
    }
    if (payload.detail && typeof payload.detail === "object" && !Array.isArray(payload.detail)) {
      const message = payload.detail.msg || payload.detail.message || "";
      if (message.trim()) {
        return cleanApiError(message.trim());
      }
    }
  } catch {
    return fallback;
  }
  return fallback;
}




type MissionControlProps = {
  isOpen: boolean;
  onClose: () => void;
  /** Called when operator activates bbox draw mode */
  onDrawBbox: () => void;
  /** Current operator-drawn bbox [W,S,E,N] or null */
  drawnBbox: number[] | null;
  onClearBbox: () => void;
  onOpenTimelapse?: () => void;
  mission: Mission | null;
  onRefresh: () => void;
  isScanComplete?: boolean;
  onReplayLoaded?: (primaryCellId: string | null) => void | Promise<void>;
  onReplayRescanStarted?: (mission: Mission) => void | Promise<void>;
  onPreviewBbox?: (bbox: number[]) => void;
  initialPresetId?: string | null;
};

export default function MissionControl({
  isOpen,
  onClose,
  onDrawBbox,
  drawnBbox,
  onClearBbox,
  onOpenTimelapse,
  mission,
  onRefresh,
  isScanComplete,
  onReplayLoaded,
  onReplayRescanStarted,
  onPreviewBbox,
  initialPresetId = null,
}: MissionControlProps) {
  const apiBase = getApiBaseUrl();
  const [task, setTask] = useState("");
  const [startDate, setStartDate] = useState("2024-06-01");
  const [endDate, setEndDate] = useState("2025-06-01");
  const [replays, setReplays] = useState<ReplayCatalogItem[]>([]);
  const [replayBusyId, setReplayBusyId] = useState<string | null>(null);
  const [replayNotice, setReplayNotice] = useState("");
  const [monitorBusy, setMonitorBusy] = useState<MonitorPreview["kind"] | null>(null);
  const [monitorPreview, setMonitorPreview] = useState<MonitorPreview | null>(null);
  const [selectedPresetId, setSelectedPresetId] = useState<string | null>(null);
  const [selectedUseCaseId, setSelectedUseCaseId] = useState<string | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (isOpen) {
      void onRefresh();
      void (async () => {
        try {
          const response = await fetch(`${apiBase}/api/replay/catalog`);
          if (!response.ok) {
            setReplays([]);
            return;
          }
          const payload = (await response.json()) as { replays?: ReplayCatalogItem[] };
          setReplays(payload.replays ?? []);
        } catch {
          setReplays([]);
        }
      })();
    }
  }, [apiBase, isOpen, onRefresh]);

  const [errorMsg, setErrorMsg] = useState("");

  const applyMissionPreset = (preset: MissionPreset) => {
    setSelectedPresetId(preset.id);
    setSelectedUseCaseId(preset.useCaseId);
    setMonitorPreview(null);
    setErrorMsg("");
    setTask(preset.taskText);
    setStartDate(preset.startDate);
    setEndDate(preset.endDate);
    onPreviewBbox?.([...preset.bbox]);
  };

  useEffect(() => {
    if (!isOpen || !initialPresetId || selectedPresetId === initialPresetId) {
      return;
    }
    const preset = MISSION_LOCATION_PRESETS.find((item) => item.id === initialPresetId);
    if (!preset) {
      return;
    }
    setSelectedPresetId(preset.id);
    setSelectedUseCaseId(preset.useCaseId);
    setMonitorPreview(null);
    setErrorMsg("");
    setTask(preset.taskText);
    setStartDate(preset.startDate);
    setEndDate(preset.endDate);
    onPreviewBbox?.([...preset.bbox]);
  }, [initialPresetId, isOpen, onPreviewBbox, selectedPresetId]);

  const handleSubmit = async () => {
    if (!task.trim()) return;
    if (startDate && endDate && startDate > endDate) {
      setErrorMsg("Start date must be on or before end date.");
      return;
    }
    setSubmitting(true);
    setErrorMsg("");
    try {
      const response = await fetch(`${apiBase}/api/mission/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_text: task.trim(),
          bbox: drawnBbox ?? null,
          start_date: startDate || null,
          end_date: endDate || null,
          use_case_id: selectedUseCaseId,
        }),
      });
      if (!response.ok) {
        throw new Error(await readApiError(response, "Backend unreachable or request failed"));
      }
      await onRefresh();
      setTask("");
      setSelectedPresetId(null);
      setSelectedUseCaseId(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Backend unreachable";
      setErrorMsg(`Mission failed to deploy: ${message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleStop = async () => {
    await fetch(`${apiBase}/api/mission/stop`, { method: "POST" });
    await onRefresh();
  };

  const formatMonitorLabel = (value: string) => value.replace(/_/g, " ");

  const handleReplayLoad = async (replayId: string) => {
    setReplayBusyId(replayId);
    setReplayNotice("");
    setErrorMsg("");
    try {
      const response = await fetch(`${apiBase}/api/replay/load/${replayId}`, { method: "POST" });
      const payload = (await response.json()) as { error?: string; primary_cell_id?: string | null };
      if (!response.ok) {
        throw new Error(payload.error || "Replay load failed");
      }
      if (onReplayLoaded) {
        await onReplayLoaded(payload.primary_cell_id ?? null);
      } else {
        await onRefresh();
      }
      setReplayNotice("Cached API replay loaded into Mission, Logs, Inspect, and Agent Dialogue.");
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : "Replay failed to load.");
    } finally {
      setReplayBusyId(null);
    }
  };

  const handleReplayRescan = async (replay: ReplayCatalogItem) => {
    setReplayBusyId(replay.replay_id);
    setReplayNotice("");
    setErrorMsg("");
    try {
      const response = await fetch(`${apiBase}/api/replay/rescan/${replay.replay_id}`, { method: "POST" });
      const payload = (await response.json()) as { error?: string; mission?: Mission };
      if (!response.ok || !payload.mission) {
        throw new Error(payload.error || "Replay rescan failed");
      }
      if (onReplayRescanStarted) {
        await onReplayRescanStarted(payload.mission);
      } else {
        await onRefresh();
      }
      if (payload.mission.bbox) {
        onPreviewBbox?.([...payload.mission.bbox]);
      } else if (replay.bbox) {
        onPreviewBbox?.([...replay.bbox]);
      }
      setReplayNotice("Live rescan started from replay metadata with the current model/runtime stack.");
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : "Replay rescan failed.");
    } finally {
      setReplayBusyId(null);
    }
  };

  const handleMaritimePreview = async () => {
    setMonitorBusy("maritime");
    setErrorMsg("");
    setSelectedPresetId("maritime_suez");
    setSelectedUseCaseId("maritime_activity");
    setTask(MARITIME_PREVIEW_TARGET.taskText);
    setStartDate("2025-03-01");
    setEndDate(MARITIME_PREVIEW_TARGET.timestamp);
    onPreviewBbox?.(MARITIME_PREVIEW_TARGET.bbox);
    try {
      const response = await fetch(`${apiBase}/api/maritime/monitor`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lat: MARITIME_PREVIEW_TARGET.lat,
          lon: MARITIME_PREVIEW_TARGET.lon,
          timestamp: MARITIME_PREVIEW_TARGET.timestamp,
          task_text: MARITIME_PREVIEW_TARGET.taskText,
          anomaly_description: "dense vessel queue near a narrow channel",
          include_stac: false,
        }),
      });
      if (!response.ok) {
        throw new Error(await readApiError(response, "Maritime monitor preview failed."));
      }
      const payload = (await response.json()) as MaritimeMonitorResponse;
      setMonitorPreview({
        kind: "maritime",
        title: "Maritime Monitor",
        mode: payload.mode || "orbit_maritime_monitoring_v1",
        primary: payload.use_case?.display_name || payload.use_case?.id || "maritime_activity",
        secondary: [
          `${payload.investigation?.directions?.length ?? 0} directions`,
          `${payload.monitor?.signals?.length ?? 0} signals`,
          `STAC ${payload.stac?.disabled ? "optional" : `${payload.stac?.items?.length ?? 0} scenes`}`,
        ],
        status: payload.target?.timestamp || "ready",
      });
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : "Maritime monitor preview failed.");
    } finally {
      setMonitorBusy(null);
    }
  };

  const handleLifelinePreview = async () => {
    setMonitorBusy("lifeline");
    setErrorMsg("");
    setSelectedPresetId(null);
    setSelectedUseCaseId("civilian_lifeline_disruption");
    try {
      const response = await fetch(`${apiBase}/api/lifelines/monitor`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          asset_id: "orbit_bridge_corridor",
          baseline_frame: {
            label: "before",
            date: "2025-01-01",
            source: "seeded_fixture",
            asset_ref: "before.png",
          },
          current_frame: {
            label: "after",
            date: "2025-01-15",
            source: "seeded_fixture",
            asset_ref: "after.png",
          },
          candidate: {
            event_type: "probable_access_obstruction",
            severity: "high",
            confidence: 0.88,
            bbox: [0.2, 0.25, 0.65, 0.75],
            civilian_impact: "public_mobility_disruption",
            why: "The current frame shows a bridge approach obstruction.",
            action: "downlink_now",
          },
          task_text: "Before/after lifeline bridge disruption review.",
        }),
      });
      if (!response.ok) {
        throw new Error(await readApiError(response, "Lifeline monitor preview failed."));
      }
      const payload = (await response.json()) as LifelineMonitorResponse;
      setMonitorPreview({
        kind: "lifeline",
        title: "Lifeline Monitor",
        mode: payload.mode || "orbit_lifeline_monitoring_v1",
        primary: `${formatMonitorLabel(payload.decision?.action || "review")} · ${formatMonitorLabel(payload.decision?.priority || "watch")}`,
        secondary: [
          payload.asset?.display_name || payload.asset?.asset_id || "lifeline asset",
          formatMonitorLabel(payload.candidate?.civilian_impact || "civilian_lifeline"),
          payload.frames?.pair_state?.distinct_contextual_frames ? "distinct frames" : "needs context",
        ],
        status: payload.use_case?.id || "civilian_lifeline_disruption",
      });
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : "Lifeline monitor preview failed.");
    } finally {
      setMonitorBusy(null);
    }
  };


  if (!isOpen) return null;

  const hasBlockingLiveMission = mission?.status === "active" && mission.mission_mode !== "replay";

  const severityColor = (s: string) => {
    if (s === "active") return "text-emerald-700 bg-emerald-50 border-emerald-200";
    if (s === "complete") return "text-zinc-600 bg-zinc-100 border-zinc-200";
    return "text-zinc-500 bg-zinc-50 border-zinc-200";
  };

  return (
    <div className="flex flex-col w-full h-full overflow-hidden text-left bg-white">
        {/* Header */}
        <div className="shrink-0 flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="text-xs uppercase tracking-widest font-semibold text-zinc-900">
              New Mission
            </span>
            {mission && (
              <span className={`rounded-full border px-2.5 py-0.5 text-[10px] uppercase tracking-wider ${severityColor(mission.status)}`}>
                {mission.mission_mode === "replay" ? `replay ${mission.status}` : mission.status}
              </span>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4 custom-scrollbar">

          {/* Active mission status */}
          {mission && (
            <div className={`rounded-lg px-4 py-3 space-y-1 ${
              mission.mission_mode === "replay"
                ? "border border-cyan-200 bg-cyan-50/60"
                : "border border-emerald-200 bg-emerald-50/50"
            }`}>
              <p className={`text-[10px] uppercase tracking-wider font-semibold ${
                mission.mission_mode === "replay" ? "text-cyan-700" : "text-emerald-700"
              }`}>
                {mission.mission_mode === "replay"
                  ? `Replay Mission · ${mission.replay_id || `#${mission.id}`}`
                  : `Active Mission #${mission.id}`}
              </p>
              <p className="text-sm text-zinc-900 font-medium leading-snug">{mission.task_text}</p>
              {mission.summary && (
                <p className="text-xs text-zinc-600 leading-snug">{mission.summary}</p>
              )}
              <div className="flex gap-4 text-xs text-zinc-600 mt-2">
                <span>{mission.cells_scanned} cells scanned</span>
                <span>{mission.flags_found} flags found</span>
                {mission.bbox && (
                  <span className={`font-semibold ${mission.mission_mode === "replay" ? "text-cyan-700" : "text-emerald-700"}`}>
                    AREA MAPPED
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={handleStop}
                className="mt-3 rounded border border-red-200 bg-white px-3 py-1.5 text-[10px] uppercase tracking-wider text-red-600 hover:bg-red-50 transition font-medium"
              >
                {mission.mission_mode === "replay" ? "Exit Replay" : "Stop Mission"}
              </button>
            </div>
          )}

          {replays.length > 0 && (
            <div className="space-y-2" data-testid="fast-replay-panel">
              <div className="flex items-center justify-between gap-3">
                <label className="block text-[10px] uppercase tracking-wider font-semibold text-zinc-500">
                  Fast Replay
                </label>
                <span className="text-[10px] uppercase tracking-wider text-zinc-400 font-semibold">
                  {replays.length} saved
                </span>
              </div>
              <p className="text-xs text-zinc-600 leading-relaxed">
                Load a completed mission instantly, or rescan the same bbox/date window with the current model after runtime updates.
              </p>
              <div className="space-y-3">
                {replays.map((replay) => (
                  <div key={replay.replay_id} className="rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-semibold text-zinc-900">{replay.title}</p>
                          <span className={`rounded border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider ${
                            replay.source_kind === "seeded_cache"
                              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                              : "border-cyan-200 bg-cyan-50 text-cyan-700"
                          }`}>
                            {replay.source_kind === "seeded_cache" ? "Replay Cache" : "Curated Replay"}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-zinc-600 leading-snug">{replay.description}</p>
                      </div>
                      <div className="flex shrink-0 flex-col gap-1.5">
                        <button
                          type="button"
                          data-testid={`load-replay-${replay.replay_id}`}
                          onClick={() => void handleReplayLoad(replay.replay_id)}
                          disabled={submitting || replayBusyId !== null || hasBlockingLiveMission}
                          className="rounded border border-cyan-200 bg-white px-3 py-1.5 text-[10px] uppercase tracking-wider text-cyan-700 hover:bg-cyan-50 disabled:opacity-40 disabled:cursor-not-allowed transition font-semibold"
                        >
                          {replayBusyId === replay.replay_id ? "Loading..." : mission?.mission_mode === "replay" ? "Replace Replay" : "Load Replay"}
                        </button>
                        <button
                          type="button"
                          data-testid={`rescan-replay-${replay.replay_id}`}
                          onClick={() => void handleReplayRescan(replay)}
                          disabled={submitting || replayBusyId !== null || hasBlockingLiveMission}
                          className="rounded border border-zinc-300 bg-white px-3 py-1.5 text-[10px] uppercase tracking-wider text-zinc-700 hover:bg-zinc-100 disabled:opacity-40 disabled:cursor-not-allowed transition font-semibold"
                        >
                          Rescan
                        </button>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-3 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                      <span>{replay.cells_scanned} cells scanned</span>
                      <span>{replay.alert_count} alerts loaded</span>
                      <span>Primary: {replay.primary_cell_id}</span>
                      {replay.use_case_id && <span>{replay.use_case_id.replace(/_/g, " ")}</span>}
                    </div>
                    {replay.summary && (
                      <p className="mt-2 text-xs text-zinc-600 leading-snug">{replay.summary}</p>
                    )}
                  </div>
                ))}
              </div>
              {replayNotice && (
                <div className="rounded border border-cyan-200 bg-cyan-50 px-3 py-2 text-xs font-medium text-cyan-700">
                  {replayNotice}
                </div>
              )}
            </div>
          )}

          <div data-testid="mission-preset-panel" className="space-y-3 rounded-lg border border-zinc-200 bg-white px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <label className="block text-[10px] uppercase tracking-wider font-semibold text-zinc-500">
                Mission Location Presets
              </label>
              <span className="text-[10px] uppercase tracking-wider text-zinc-400 font-semibold">
                Known Places
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {MISSION_LOCATION_PRESETS.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  data-testid={`mission-preset-${preset.id}`}
                  onClick={() => applyMissionPreset(preset)}
                  className={`rounded border px-2 py-2 text-left transition ${PRESET_TONE_CLASSES[preset.tone]} ${
                    selectedPresetId === preset.id ? "ring-2 ring-zinc-900/20" : ""
                  }`}
                  title={`${preset.label}: ${preset.place}`}
                >
                  <span className="block text-[11px] font-semibold leading-tight text-current">{preset.label}</span>
                  <span className="mt-0.5 block text-[10px] leading-tight text-current opacity-70">{preset.place}</span>
                </button>
              ))}
            </div>
            {selectedPresetId && (
              <div data-testid="selected-mission-preset" className="rounded border border-zinc-200 bg-zinc-50 px-3 py-2 text-[11px] font-medium text-zinc-700">
                {MISSION_LOCATION_PRESETS.find((preset) => preset.id === selectedPresetId)?.place}
                <span className="text-zinc-400"> · </span>
                {selectedUseCaseId?.replace(/_/g, " ")}
              </div>
            )}
          </div>

          <div data-testid="monitor-template-panel" className="space-y-3 rounded-lg border border-zinc-200 bg-white px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <label className="block text-[10px] uppercase tracking-wider font-semibold text-zinc-500">
                Monitor Templates
              </label>
              <span className="text-[10px] uppercase tracking-wider text-zinc-400 font-semibold">
                API Ready
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                data-testid="maritime-monitor-button"
                onClick={() => void handleMaritimePreview()}
                disabled={monitorBusy !== null}
                className="rounded border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-800 hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed transition"
              >
                {monitorBusy === "maritime" ? "Loading..." : "Maritime"}
              </button>
              <button
                type="button"
                data-testid="lifeline-monitor-button"
                onClick={() => void handleLifelinePreview()}
                disabled={monitorBusy !== null}
                className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800 hover:bg-amber-100 disabled:opacity-50 disabled:cursor-not-allowed transition"
              >
                {monitorBusy === "lifeline" ? "Loading..." : "Lifeline"}
              </button>
            </div>
            {monitorPreview && (
              <div
                data-testid="monitor-proof-card"
                className={`rounded border px-3 py-3 ${
                  monitorPreview.kind === "maritime"
                    ? "border-blue-200 bg-blue-50/70"
                    : "border-amber-200 bg-amber-50/70"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-zinc-900">{monitorPreview.title}</p>
                    <p className="mt-0.5 truncate text-[11px] font-mono text-zinc-500">{monitorPreview.mode}</p>
                  </div>
                  <span className="shrink-0 rounded bg-white px-2 py-1 text-[10px] uppercase tracking-wider font-semibold text-zinc-600 border border-white/80">
                    {monitorPreview.status}
                  </span>
                </div>
                <p className="mt-2 text-sm font-medium text-zinc-800">{monitorPreview.primary}</p>
                <div className="mt-3 grid grid-cols-3 gap-2">
                  {monitorPreview.secondary.map((item) => (
                    <span
                      key={item}
                      className="min-w-0 rounded border border-white/80 bg-white px-2 py-1 text-center text-[10px] font-semibold leading-tight text-zinc-600 break-words"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Task prompt */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="block text-[10px] uppercase tracking-wider font-semibold text-zinc-500">
                Instruction
              </label>
              <button
                onClick={() => {
                  setSelectedPresetId(null);
                  setSelectedUseCaseId("deforestation");
                  setTask("Conduct a high-resolution sweep for active logging in the northern sector. Flag any significant NDVI drop.");
                }}
                className="text-[10px] font-bold text-zinc-400 hover:text-zinc-600 transition"
              >
                Use Forest Template
              </button>
            </div>
            <textarea
              data-testid="mission-task-input"
              ref={textareaRef}
              value={task}
              onChange={(e) => {
                setTask(e.target.value);
                setSelectedPresetId(null);
                setSelectedUseCaseId(null);
              }}
              rows={3}
              placeholder="Describe the satellite mission, target signal, and review outcome..."
              className="w-full resize-none rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 placeholder-zinc-400 focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500 outline-none"
            />
          </div>

          {/* Area + time */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="block text-[10px] uppercase tracking-wider font-semibold text-zinc-500">Start Date</label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500 outline-none"
              />
            </div>
            <div className="space-y-1.5">
              <label className="block text-[10px] uppercase tracking-wider font-semibold text-zinc-500">End Date</label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500 outline-none"
              />
            </div>
          </div>

          {/* Bbox draw */}
          <div className="space-y-1.5">
            <label className="block text-[10px] uppercase tracking-wider font-semibold text-zinc-500">
              Focus Area
            </label>
            {drawnBbox ? (
              <div data-testid="bbox-badge" className="flex flex-col gap-2 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2.5">
                <span className="text-[10px] uppercase tracking-wider font-semibold text-zinc-500">
                  Active Area
                </span>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-zinc-900 flex-1">
                    [{drawnBbox.map((v) => v.toFixed(2)).join(", ")}]
                  </span>
                  <button
                    type="button"
                    onClick={onClearBbox}
                    className="text-[10px] uppercase tracking-wider text-zinc-500 hover:text-red-500 transition font-semibold"
                  >
                    Clear
                  </button>
                </div>
                {onOpenTimelapse && (
                  <button
                    type="button"
                    onClick={onOpenTimelapse}
                    className="w-full mt-1 rounded border border-zinc-200 bg-white px-3 py-1.5 text-[10px] uppercase tracking-wider text-zinc-700 hover:bg-zinc-100 transition font-semibold"
                  >
                    View Timelapse Preview
                  </button>
                )}
              </div>
            ) : (
              <button
                type="button"
                onClick={() => { onDrawBbox(); onClose(); }}
                className="w-full rounded-lg border border-dashed border-zinc-300 bg-zinc-50 px-4 py-3 text-xs font-semibold text-zinc-500 hover:border-zinc-400 hover:text-zinc-700 transition"
              >
                Draw Area on Map
              </button>
            )}
          </div>

          {/* Submit */}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting || !task.trim() || mission?.status === "active"}
            className="w-full rounded-lg bg-zinc-900 py-3 text-sm font-semibold text-white hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            {submitting ? "Deploying..." : (isScanComplete ? "Mission Complete" : (mission?.status === "active" ? "Mission In Progress" : "Launch Mission"))}
          </button>

          {errorMsg && (
            <div className="text-xs text-red-600 font-semibold p-2 bg-red-50 border border-red-200 rounded text-center">
              {errorMsg}
            </div>
          )}


        </div>
    </div>
  );
}
