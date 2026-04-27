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
  title: string;
  description: string;
  summary: string;
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
        }),
      });
      if (!response.ok) {
        throw new Error(await readApiError(response, "Backend unreachable or request failed"));
      }
      await onRefresh();
      setTask("");
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
      setReplayNotice("Seeded replay loaded into Mission, Logs, Inspect, and Agent Dialogue.");
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : "Replay failed to load.");
    } finally {
      setReplayBusyId(null);
    }
  };

  const handleMaritimePreview = async () => {
    setMonitorBusy("maritime");
    setErrorMsg("");
    try {
      const response = await fetch(`${apiBase}/api/maritime/monitor`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lat: 29.92,
          lon: 32.54,
          timestamp: "2025-03-15",
          task_text: "Review maritime vessel queueing near a narrow channel.",
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
            <div className="space-y-2">
              <label className="block text-[10px] uppercase tracking-wider font-semibold text-zinc-500">
                Seeded Replay
              </label>
              <p className="text-xs text-zinc-600 leading-relaxed">
                Load a completed mission with bundled timelapses, persisted alerts, and agent reasoning so judges can inspect a finished Orbit run without waiting on live scan timing.
              </p>
              <div className="space-y-3">
                {replays.map((replay) => (
                  <div key={replay.replay_id} className="rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-zinc-900">{replay.title}</p>
                        <p className="mt-1 text-xs text-zinc-600 leading-snug">{replay.description}</p>
                      </div>
                      <button
                        type="button"
                        data-testid={`load-replay-${replay.replay_id}`}
                        onClick={() => void handleReplayLoad(replay.replay_id)}
                        disabled={submitting || replayBusyId !== null || hasBlockingLiveMission}
                        className="shrink-0 rounded border border-cyan-200 bg-white px-3 py-1.5 text-[10px] uppercase tracking-wider text-cyan-700 hover:bg-cyan-50 disabled:opacity-40 disabled:cursor-not-allowed transition font-semibold"
                      >
                        {replayBusyId === replay.replay_id ? "Loading..." : mission?.mission_mode === "replay" ? "Replace Replay" : "Load Replay"}
                      </button>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-3 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                      <span>{replay.cells_scanned} cells scanned</span>
                      <span>{replay.alert_count} alerts loaded</span>
                      <span>Primary: {replay.primary_cell_id}</span>
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
                onClick={() => setTask("Conduct a high-resolution sweep for active logging in the northern sector. Flag any significant NDVI drop.")}
                className="text-[10px] font-bold text-zinc-400 hover:text-zinc-600 transition"
              >
                Use Suggested Template
              </button>
            </div>
            <textarea
              ref={textareaRef}
              value={task}
              onChange={(e) => setTask(e.target.value)}
              rows={3}
              placeholder="Search for areas where deforestation seems to have occurred…"
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
              <div className="flex flex-col gap-2 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2.5">
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
