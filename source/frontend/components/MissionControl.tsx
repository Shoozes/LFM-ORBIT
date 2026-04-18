/**
 * MissionControl — Operator command centre.
 *
 * - Natural-language task prompt → sent to agents as a mission
 * - DRAW AREA button → bbox rectangle selection on map
 * - Time range inputs (start/end date) → stored with mission for timelapse
 * - SEVER/RESTORE LINK toggle → simulates satellite blackout
 * - Mission status + history
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { getApiBaseUrl } from "../utils/telemetry";
import { Mission } from "../types/mission";




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
}: MissionControlProps) {
  const apiBase = getApiBaseUrl();
  const [task, setTask] = useState("");
  const [startDate, setStartDate] = useState("2024-06-01");
  const [endDate, setEndDate] = useState("2025-06-01");

  const [submitting, setSubmitting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const fetchStatus = useCallback(async () => {
    try {
      onRefresh();
    } catch { /* ignore */ }
  }, [apiBase, onRefresh]);

  useEffect(() => {
    if (!isOpen) return;
    fetchStatus();
    const id = window.setInterval(fetchStatus, 3000);
    return () => window.clearInterval(id);
  }, [isOpen, fetchStatus]);

  const handleSubmit = async () => {
    if (!task.trim()) return;
    setSubmitting(true);
    try {
      await fetch(`${apiBase}/api/mission/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_text: task.trim(),
          bbox: drawnBbox ?? null,
          start_date: startDate || null,
          end_date: endDate || null,
        }),
      });
      await onRefresh();
      setTask("");
    } catch { /* ignore */ } finally {
      setSubmitting(false);
    }
  };

  const handleStop = async () => {
    await fetch(`${apiBase}/api/mission/stop`, { method: "POST" });
    await onRefresh();
  };


  if (!isOpen) return null;

  const severityColor = (s: string) => {
    if (s === "active") return "text-emerald-700 bg-emerald-50 border-emerald-200";
    if (s === "complete") return "text-zinc-600 bg-zinc-100 border-zinc-200";
    return "text-zinc-500 bg-zinc-50 border-zinc-200";
  };

  return (
    <div className="flex flex-col w-full h-full text-left bg-white">
      <div className="w-full flex-1">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="text-xs uppercase tracking-widest font-semibold text-zinc-900">
              New Mission
            </span>
            {mission && (
              <span className={`rounded-full border px-2.5 py-0.5 text-[10px] uppercase tracking-wider ${severityColor(mission.status)}`}>
                {mission.status}
              </span>
            )}
          </div>
        </div>

        <div className="max-h-[80vh] overflow-y-auto px-6 py-5 space-y-5">

          {/* Active mission status */}
          {mission && (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 px-4 py-3 space-y-1">
              <p className="text-[10px] uppercase tracking-wider text-emerald-700 font-semibold">Active Mission #{mission.id}</p>
              <p className="text-sm text-zinc-900 font-medium leading-snug">{mission.task_text}</p>
              <div className="flex gap-4 text-xs text-zinc-600 mt-2">
                <span>{mission.cells_scanned} cells scanned</span>
                <span>{mission.flags_found} flags found</span>
                {mission.bbox && <span className="font-semibold text-emerald-700">AREA MAPPED</span>}
              </div>
              <button
                type="button"
                onClick={handleStop}
                className="mt-3 rounded border border-red-200 bg-white px-3 py-1.5 text-[10px] uppercase tracking-wider text-red-600 hover:bg-red-50 transition font-medium"
              >
                Stop Mission
              </button>
            </div>
          )}

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


        </div>
      </div>
    </div>
  );
}
