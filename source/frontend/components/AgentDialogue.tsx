import { useEffect, useRef, useState } from "react";
import { getApiBaseUrl } from "../utils/telemetry";
import { createRequestGate } from "../utils/requestGateCore.js";
import { useAgentBus } from "../hooks/useAgentBus";
import type { Mission } from "../types/mission";

function getSenderLabel(sender: string): string {
  if (sender === "satellite") return "SAT";
  if (sender === "ground") return "GND";
  if (sender === "operator") return "OPR";
  return "SYS";
}

function getMsgTypeColor(msg_type: string): string {
  if (msg_type === "flag") return "text-amber-700 bg-amber-50 border-amber-200";
  if (msg_type === "confirmation") return "text-emerald-700 bg-emerald-50 border-emerald-200";
  if (msg_type === "reject") return "text-zinc-500 bg-zinc-50 border-zinc-200";
  if (msg_type === "heartbeat") return "text-slate-500 bg-transparent";
  if (msg_type === "status") return "text-indigo-700 bg-indigo-50 border-indigo-200";
  if (msg_type === "error") return "text-red-700 bg-red-50 border-red-200";
  return "text-zinc-500 border-zinc-200 bg-zinc-50";
}

function getMsgTypeIcon(msg_type: string): string {
  if (msg_type === "flag") return "⚑";
  if (msg_type === "confirmation") return "✓";
  if (msg_type === "reject") return "✗";
  if (msg_type === "heartbeat") return "♥";
  if (msg_type === "status") return "≡";
  if (msg_type === "error") return "!";
  return "·";
}

function formatTimestamp(ts: string): string {
  const d = new Date(ts);
  if (Number.isFinite(d.getTime())) {
    return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }
  return ts.length >= 19 ? ts.slice(11, 19) : "Unknown time";
}

function formatMetric(value: unknown): string | null {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(3) : null;
}

async function readBusError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json() as { error?: unknown; detail?: unknown };
    if (typeof payload.error === "string" && payload.error.trim()) {
      return payload.error;
    }
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail;
    }
  } catch {
    return fallback;
  }
  return fallback;
}

type AgentDialogueProps = {
  isOpen: boolean;
  onClose: () => void;
  mission?: Mission | null;
};

const BUS_INJECT_TIMEOUT_MS = 10_000;

function normalizeBusStats(value: unknown): Record<string, number> | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const entries = Object.entries(value).filter(([, entry]) => typeof entry === "number" && Number.isFinite(entry));
  return entries.length === 0 ? null : Object.fromEntries(entries);
}

export default function AgentDialogue({ isOpen, mission }: AgentDialogueProps) {
  const [operatorInput, setOperatorInput] = useState("");
  const [isInjecting, setIsInjecting] = useState(false);
  const [stats, setStats] = useState<Record<string, number> | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [injectError, setInjectError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const injectAbortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);
  const apiBase = getApiBaseUrl();
  const { messages, wsStatus } = useAgentBus();
  const isReplayMission = mission?.mission_mode === "replay";

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      injectAbortRef.current?.abort();
      injectAbortRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (isOpen && endRef.current) {
      endRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isOpen]);

  // Fetch bus stats periodically
  useEffect(() => {
    if (!isOpen) return;
    const gate = createRequestGate();
    const fetchStats = async () => {
      const request = gate.begin();
      try {
        const r = await fetch(`${apiBase}/api/agent/bus/stats`, { signal: request.controller.signal });
        if (!r.ok) {
          throw new Error(`HTTP ${r.status}`);
        }
        const nextStats = normalizeBusStats(await r.json());
        if (gate.isCurrent(request)) {
          if (nextStats) {
            setStats(nextStats);
            setStatsError(null);
          } else {
            setStats(null);
            setStatsError("Bus stats unavailable");
          }
        }
      } catch {
        if (gate.isCurrent(request)) {
          setStats(null);
          setStatsError("Bus stats unavailable");
        }
      } finally {
        gate.finish(request);
      }
    };
    void fetchStats();
    const id = window.setInterval(fetchStats, 5000);
    return () => {
      gate.abort();
      window.clearInterval(id);
    };
  }, [isOpen, apiBase]);

  const sendOperatorMessage = async () => {
    const msg = operatorInput.trim();
    if (!msg || isInjecting) return;
    setIsInjecting(true);
    setInjectError(null);
    const controller = new AbortController();
    injectAbortRef.current = controller;
    const timeoutId = window.setTimeout(() => controller.abort(), BUS_INJECT_TIMEOUT_MS);
    try {
      const response = await fetch(`${apiBase}/api/agent/bus/inject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg }),
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error(await readBusError(response, `Bus injection failed with HTTP ${response.status}.`));
      }
      if (mountedRef.current) setOperatorInput("");
    } catch (error) {
      if (!mountedRef.current) return;
      setInjectError(
        error instanceof DOMException && error.name === "AbortError"
          ? "Bus injection timed out. Confirm the backend is still running."
          : error instanceof Error
            ? error.message
            : "Bus injection failed.",
      );
    } finally {
      window.clearTimeout(timeoutId);
      if (injectAbortRef.current === controller) injectAbortRef.current = null;
      if (mountedRef.current) setIsInjecting(false);
    }
  };

  // Filter: hide dense heartbeats by default for readability
  const displayMessages = messages.filter(
    (m) => m.msg_type !== "heartbeat" || m.payload.status === "booted" || m.payload.status === "online"
  );

  if (!isOpen) return null;

  return (
    <div className="flex flex-col h-full w-full overflow-hidden bg-white">
        {/* Header */}
        <div className="flex items-center justify-between gap-3 border-b border-zinc-200 px-3 py-2">
          <div className="flex min-w-0 items-center gap-2">
            <div className={`h-2 w-2 rounded-full ${wsStatus === "open" ? "bg-emerald-500 animate-pulse" : "bg-zinc-300"}`} />
            <span className="truncate text-[11px] uppercase tracking-widest text-zinc-500 font-semibold">Agent Bus</span>
            <span className={`rounded border px-2 py-0.5 text-[10px] uppercase tracking-wider font-semibold ${
              wsStatus === "open"
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-zinc-200 bg-zinc-50 text-zinc-500"
            }`} data-testid="agent-bus-status">
              {wsStatus}
            </span>
          </div>

          <div className="flex shrink-0 items-center gap-3">
            {stats && (
              <div className="flex gap-2 text-[10px] font-medium text-zinc-500">
                <span><span className="text-xs text-zinc-700">{stats.from_satellite}</span> sat</span>
                <span><span className="text-xs text-zinc-700">{stats.from_ground}</span> gnd</span>
                <span><span className="text-xs text-zinc-700">{stats.total_messages}</span> total</span>
              </div>
            )}
            {!stats && statsError && (
              <span className="rounded border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-amber-700">
                {statsError}
              </span>
            )}
            <div className="hidden items-center gap-2 text-xs text-zinc-400 uppercase font-semibold sm:flex">
              <span>SAT</span>
              <span>⇌</span>
              <span>GND</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 border-b border-zinc-100 bg-zinc-50 px-3 py-1.5" data-testid="agent-role-strip">
          <div className="rounded border border-cyan-100 bg-white px-2 py-1">
            <p className="truncate text-[10px] font-bold uppercase tracking-wider text-cyan-700">Satellite Pruner</p>
          </div>
          <div className="rounded border border-emerald-100 bg-white px-2 py-1">
            <p className="truncate text-[10px] font-bold uppercase tracking-wider text-emerald-700">Ground Validator</p>
          </div>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-3 overflow-x-auto border-b border-zinc-100 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider">
          {[
            { icon: "⚑", label: "flag", cls: "text-amber-600" },
            { icon: "✓", label: "confirm", cls: "text-emerald-600" },
            { icon: "✗", label: "reject", cls: "text-zinc-500" },
            { icon: "♥", label: "heartbeat", cls: "text-slate-400" },
            { icon: "≡", label: "status", cls: "text-indigo-600" },
          ].map(({ icon, label, cls }) => (
            <span key={label} className={`flex items-center gap-1.5 ${cls}`}>
              <span className="text-sm">{icon}</span>
              <span className="text-zinc-500">{label}</span>
            </span>
          ))}
        </div>

        {/* Message feed */}
        <div className="flex-1 overflow-y-auto px-3 py-2 font-mono text-sm space-y-2">
          {isReplayMission && (
            <div className="rounded border border-cyan-200 bg-cyan-50 px-4 py-3 text-xs leading-relaxed text-cyan-800">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-cyan-700">
                Historical replay trace loaded
              </p>
              <p className="mt-1">
                This dialogue bus is showing restored SAT/GND reasoning from replay
                {mission?.replay_id ? ` ${mission.replay_id}` : ""}. Operator inject is disabled until replay mode is exited.
              </p>
            </div>
          )}
          {displayMessages.length === 0 && (
            <div className="flex items-center justify-center h-full text-zinc-400 text-sm">
              Waiting for agent messages…
            </div>
          )}

          {displayMessages.map((msg) => {
            const note = typeof msg.payload.note === "string" ? msg.payload.note : "";
            const action = typeof msg.payload.action === "string" ? msg.payload.action : null;
            const severity = typeof msg.payload.severity === "string" ? msg.payload.severity : null;
            const changeScore = formatMetric(msg.payload.change_score);
            const confidence = formatMetric(msg.payload.confidence);
            const isHeartbeat = msg.msg_type === "heartbeat";

            if (isHeartbeat) {
              return (
                <div key={msg.id} className="flex items-center gap-2 py-0.5 text-[10px] text-zinc-400">
                  <span>{formatTimestamp(msg.timestamp)}</span>
                  <span className="text-slate-400">♥</span>
                  <span className={`font-bold text-zinc-500`}>
                    {getSenderLabel(msg.sender)}
                  </span>
                  <span className="truncate">{note}</span>
                </div>
              );
            }

            return (
              <div
                key={msg.id}
                className={`rounded border px-4 py-3 ${getMsgTypeColor(msg.msg_type)}`}
              >
                <div className="flex items-start gap-3">
                  {/* Icon + sender */}
                  <div className="flex items-center gap-1.5 shrink-0 pt-0.5 font-sans">
                    <span className="text-xs">{getMsgTypeIcon(msg.msg_type)}</span>
                    <span className={`font-bold text-[10px] uppercase text-zinc-800`}>
                      {getSenderLabel(msg.sender)}
                    </span>
                    <span className="text-zinc-400">→</span>
                    <span className={`text-[10px] uppercase text-zinc-500`}>
                      {getSenderLabel(msg.recipient)}
                    </span>
                  </div>

                  {/* Content */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1.5 font-sans">
                      <span className="uppercase tracking-wider text-[10px] font-semibold text-zinc-500">
                        {msg.msg_type}
                      </span>
                      {msg.cell_id && (
                        <span className="text-[10px] text-zinc-400 truncate">
                          {msg.cell_id}
                        </span>
                      )}
                      {severity && (
                        <span className={`uppercase tracking-wider text-[9px] font-bold px-1.5 py-0.5 rounded border ${
                          severity === "critical" ? "border-red-200 text-red-700 bg-red-50" :
                          severity === "high" ? "border-orange-200 text-orange-700 bg-orange-50" :
                          severity === "moderate" ? "border-amber-200 text-amber-700 bg-amber-50" :
                          "border-zinc-200 text-zinc-600 bg-zinc-50"
                        }`}>
                          {severity}
                        </span>
                      )}
                      <span className="ml-auto text-[10px] text-zinc-400 shrink-0">
                        {formatTimestamp(msg.timestamp)}
                      </span>
                    </div>
                    <p className="leading-relaxed text-xs break-words text-zinc-800">{note}</p>
                    {action && (
                      <p className="mt-1 text-[11px] text-zinc-500 italic border-l-2 border-zinc-200 pl-2">{action}</p>
                    )}
                    {changeScore !== null && (
                      <div className="mt-2 flex gap-3 text-[10px] text-zinc-500 font-semibold uppercase tracking-wider">
                        <span>Score: <span className="text-zinc-800">{changeScore}</span></span>
                        {confidence !== null && (
                          <span>Conf: <span className="text-zinc-800">{confidence}</span></span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
          <div ref={endRef} />
        </div>

        {/* Operator inject */}
        <div className="border-t border-zinc-200 bg-zinc-50 px-4 py-3">
          {injectError && (
            <p className="mb-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-700" role="status">
              {injectError}
            </p>
          )}
          <div className="flex gap-2 items-center">
            <span className="text-[10px] uppercase tracking-wider font-semibold text-purple-600 shrink-0">User</span>
            <input
              type="text"
              value={operatorInput}
              onChange={(e) => {
                setOperatorInput(e.target.value);
                if (injectError) setInjectError(null);
              }}
              onKeyDown={(e) => e.key === "Enter" && sendOperatorMessage()}
              placeholder="Inject manual command into agent bus…"
              disabled={isInjecting || isReplayMission}
              className="flex-1 rounded border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 placeholder-zinc-400 focus:border-zinc-400 focus:ring-1 focus:ring-zinc-400 outline-none disabled:opacity-50"
            />
            <button
              onClick={sendOperatorMessage}
              disabled={isInjecting || !operatorInput.trim() || isReplayMission}
              className="rounded border border-purple-200 bg-purple-50 px-4 py-2 text-[11px] font-bold uppercase tracking-wider text-purple-700 hover:bg-purple-100 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isInjecting ? "Injecting..." : "Inject"}
            </button>
          </div>
      </div>
    </div>
  );
}
