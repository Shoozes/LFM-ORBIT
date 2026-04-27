import { formatSourceLabel, formatReasonCode } from "../utils/telemetry";
import type { Mission } from "../types/mission";
import type { AlertItem, ApiHealth, ApiMetricsSummary, ScanHeartbeat } from "../types/telemetry";

type AlertsLogsProps = {
  isOpen: boolean;
  onClose: () => void;
  alerts: AlertItem[];
  metricsSummary: ApiMetricsSummary | null;
  apiHealth: ApiHealth | null;
  heartbeat: ScanHeartbeat | null;
  selectedCellId: string | null;
  onSelectCell: (cellId: string) => void;
  mission?: Mission | null;
};

function getPriorityTone(priority: string): string {
  if (priority === "critical") return "text-red-700 font-bold bg-red-50 border-red-200";
  if (priority === "high") return "text-orange-700 font-bold bg-orange-50 border-orange-200";
  if (priority === "medium") return "text-amber-700 font-bold bg-amber-50 border-amber-200";
  return "text-zinc-600 border-zinc-200 bg-zinc-50";
}

function formatMetricPercent(value: number | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "0.0%";
  return `${(value * 100).toFixed(1)}%`;
}

function formatMetricLabel(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export default function AlertsLogs({
  isOpen,
  onClose,
  alerts,
  metricsSummary,
  apiHealth,
  heartbeat,
  selectedCellId,
  onSelectCell,
  mission,
}: AlertsLogsProps) {
  if (!isOpen) return null;

  const isReplayMission = mission?.mission_mode === "replay";
  const recentAlertCount = isReplayMission
    ? alerts.length
    : (heartbeat?.alerts_emitted ?? apiHealth?.total_alerts ?? alerts.length);
  const rejectionEntries = Object.entries(metricsSummary?.runtime_rejections_by_reason ?? {})
    .sort((left, right) => right[1] - left[1])
    .slice(0, 3);

  return (
    <div className="flex flex-col h-full w-full bg-white">
      <div className="flex flex-1 flex-col overflow-hidden bg-transparent">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-5">
          <div>
            <h2 className="text-xs uppercase tracking-widest font-semibold text-zinc-900">Alerts & Logs</h2>
            <p className="text-xs text-zinc-500 mt-1">
              {isReplayMission
                ? "Seeded replay evidence restored into the standard alert surfaces."
                : "Historical downlinked evidence and recent organic alerts."}
            </p>
          </div>
        </div>

        {/* Content */}
        <div className="flex flex-col flex-1 min-h-0 overflow-y-auto">
          {isReplayMission && mission && (
            <div className="mx-6 mt-6 rounded-lg border border-cyan-200 bg-cyan-50 px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-cyan-700">
                Replay Bundle · {mission.replay_id || `#${mission.id}`}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-zinc-700">
                {mission.summary || "Bundled local evidence and historical agent reasoning are pinned for inspection."}
              </p>
            </div>
          )}

          {/* Pipeline Integrity */}
          <div className="mx-6 mt-6 rounded-lg border border-zinc-200 bg-white px-4 py-3">
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                Pipeline Integrity
              </p>
              <span className="rounded border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-zinc-500">
                QC
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="rounded border border-zinc-100 bg-zinc-50 px-3 py-2">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">Scene Rejects</p>
                <p className="mt-1 text-sm font-bold text-zinc-900">
                  {formatMetricPercent(metricsSummary?.pct_scenes_rejected)}
                </p>
              </div>
              <div className="rounded border border-zinc-100 bg-zinc-50 px-3 py-2">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">Low Coverage</p>
                <p className="mt-1 text-sm font-bold text-zinc-900">
                  {formatMetricPercent(metricsSummary?.pct_low_valid_coverage)}
                </p>
              </div>
            </div>
            <div className="mt-3 space-y-1.5">
              {rejectionEntries.length === 0 ? (
                <p className="rounded border border-dashed border-zinc-200 bg-zinc-50 px-3 py-2 text-xs font-semibold text-zinc-400">
                  No runtime rejects recorded.
                </p>
              ) : (
                rejectionEntries.map(([reason, count]) => (
                  <div key={reason} className="flex items-center justify-between rounded border border-zinc-100 bg-zinc-50 px-3 py-2 text-xs">
                    <span className="font-semibold text-zinc-600">{formatMetricLabel(reason)}</span>
                    <span className="font-bold text-zinc-900">{count}</span>
                  </div>
                ))
              )}
            </div>
          </div>
          
          {/* Flagged Examples  */}
          <div className="flex flex-col w-full p-6 border-b border-zinc-200">
            <div className="flex items-center justify-between mb-4">
              <p className="text-[10px] uppercase tracking-wider font-semibold text-zinc-500">Flagged Examples</p>
              <p className="text-[10px] text-zinc-500 font-bold bg-zinc-100 px-2 py-0.5 rounded">
                {metricsSummary?.flagged_examples.length ?? 0}
              </p>
            </div>
            
            <div className="flex-1 space-y-3 overflow-y-auto pr-2 custom-scrollbar">
              {(metricsSummary?.flagged_examples ?? []).length === 0 ? (
                <div className="rounded border border-dashed border-zinc-300 bg-zinc-50 p-5 text-center text-sm font-semibold text-zinc-400">
                  No flagged examples logged yet.
                </div>
              ) : (
                metricsSummary?.flagged_examples.map((example: any) => (
                  <div
                    key={`${example.event_id}-${example.cycle_index}`}
                    className="rounded border border-zinc-200 bg-white p-4 hover:border-zinc-300 transition shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <div>
                        <p className="text-sm text-zinc-900 break-all font-bold">{example.cell_id}</p>
                        <p className="text-zinc-400 mt-0.5 text-[10px] uppercase tracking-wider font-semibold">{example.event_id}</p>
                      </div>
                      <p className="text-[10px] uppercase font-bold text-zinc-500 bg-zinc-100 px-2 py-0.5 rounded">
                        cycle {example.cycle_index}
                      </p>
                    </div>
                    <div className="grid grid-cols-2 gap-2 mb-3 bg-zinc-50 border border-zinc-100 rounded p-2.5 text-xs">
                      <div>
                        <span className="text-zinc-500 font-semibold">Score:</span>{" "}
                        <span className="text-zinc-900 font-bold">{example.change_score.toFixed(3)}</span>
                      </div>
                      <div>
                        <span className="text-zinc-500 font-semibold">Payload:</span>{" "}
                        <span className="text-zinc-900 font-medium">{example.payload_bytes}b</span>
                      </div>
                    </div>
                    <p className="text-zinc-500 text-xs italic">
                      {isReplayMission ? "Seeded replay example." : "Organic anomaly log."}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Recent Alerts */}
          <div className="flex flex-col w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <p className="text-[10px] uppercase tracking-wider font-semibold text-zinc-500">Recent Alerts</p>
              <p className="text-[10px] text-zinc-500 font-bold bg-zinc-100 border border-zinc-200 px-2 py-0.5 rounded">
                {recentAlertCount}
              </p>
            </div>

            <div className="flex-1 space-y-3 overflow-y-auto pr-2 custom-scrollbar">
              {alerts.length === 0 ? (
                <div className="rounded border border-dashed border-zinc-300 bg-zinc-50 p-5 text-center text-sm font-semibold text-zinc-400">
                  No alerts downlinked yet.
                </div>
              ) : (
                alerts.map((alert: any) => (
                  <button
                    key={alert.event_id}
                    type="button"
                    data-testid="alert-button"
                    onClick={() => {
                      onSelectCell(alert.cell_id);
                      onClose(); // Optional: close drawer to show the map + ValidationPanel
                    }}
                    className={`w-full text-left rounded border p-4 transition shadow-sm ${
                      selectedCellId === alert.cell_id
                        ? "border-zinc-900 bg-zinc-100 ring-1 ring-zinc-900"
                        : `bg-white hover:bg-zinc-50 border-zinc-200`
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <div>
                        <p className="text-sm font-bold text-zinc-900 break-all">{alert.cell_id}</p>
                        <p className="text-[10px] uppercase tracking-wider font-semibold text-zinc-400 mt-0.5">{alert.event_id}</p>
                      </div>
                      <p className={`text-[10px] px-2 py-0.5 rounded bg-zinc-100 font-bold uppercase tracking-wider border ${getPriorityTone(alert.priority)}`}>
                        {alert.priority}
                      </p>
                    </div>

                    <div className="grid grid-cols-2 gap-y-2 gap-x-4 text-xs mb-3 bg-zinc-50 border border-zinc-100 p-3 rounded">
                      <div className="flex justify-between">
                        <span className="text-zinc-500 font-semibold">Change</span>
                        <span className="text-zinc-900 font-bold">{alert.change_score.toFixed(3)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-zinc-500 font-semibold">Conf</span>
                        <span className="text-zinc-900 font-medium">{alert.confidence.toFixed(3)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-zinc-500 font-semibold">Bytes</span>
                        <span className="text-zinc-900 font-medium">{alert.payload_bytes}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-zinc-500 font-semibold">Status</span>
                        <span className={`font-semibold ${alert.downlinked ? "text-emerald-600" : "text-amber-600"}`}>{alert.downlinked ? "logged" : "queued"}</span>
                      </div>
                      <div className="col-span-2 pt-2 mt-1 border-t border-zinc-200 flex justify-between">
                        <span className="text-zinc-500 font-semibold">Source</span>
                        <span className="text-zinc-700 font-bold text-[10px] uppercase tracking-wider">{formatSourceLabel(alert.observation_source)}</span>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      {isReplayMission && (
                        <span className="border border-cyan-200 bg-cyan-50 px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider text-cyan-700">
                          Seeded Replay
                        </span>
                      )}
                      {alert.reason_codes.map((code: string) => (
                        <span
                          key={code}
                          className="border border-zinc-200 bg-white px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider text-zinc-600"
                        >
                          {formatReasonCode(code)}
                        </span>
                      ))}
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
