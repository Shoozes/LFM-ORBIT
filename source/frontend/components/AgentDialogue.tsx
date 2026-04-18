import { useEffect, useRef, useState } from "react";
import { getApiBaseUrl } from "../utils/telemetry";
import { useAgentBus } from "../hooks/useAgentBus";

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
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return ts.slice(11, 19);
  }
}

type AgentDialogueProps = {
  isOpen: boolean;
  onClose: () => void;
};

export default function AgentDialogue({ isOpen }: AgentDialogueProps) {
  const [operatorInput, setOperatorInput] = useState("");
  const [stats, setStats] = useState<Record<string, number> | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const apiBase = getApiBaseUrl();
  const { messages, wsStatus } = useAgentBus();

  useEffect(() => {
    if (isOpen && endRef.current) {
      endRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isOpen]);

  // Fetch bus stats periodically
  useEffect(() => {
    if (!isOpen) return;
    const fetchStats = async () => {
      try {
        const r = await fetch(`${apiBase}/api/agent/bus/stats`);
        if (r.ok) setStats(await r.json() as Record<string, number>);
      } catch { /* ignore */ }
    };
    fetchStats();
    const id = window.setInterval(fetchStats, 5000);
    return () => window.clearInterval(id);
  }, [isOpen, apiBase]);

  const sendOperatorMessage = async () => {
    const msg = operatorInput.trim();
    if (!msg) return;
    setOperatorInput("");
    try {
      await fetch(`${apiBase}/api/agent/bus/inject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg }),
      });
    } catch { /* ignore */ }
  };

  // Filter: hide dense heartbeats by default for readability
  const displayMessages = messages.filter(
    (m) => m.msg_type !== "heartbeat" || m.payload.status === "booted" || m.payload.status === "online"
  );

  if (!isOpen) return null;

  return (
    <div className="flex flex-col h-full w-full overflow-hidden bg-white">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-4">
          <div className="flex items-center gap-3">
            <div className={`h-2 w-2 rounded-full ${wsStatus === "open" ? "bg-emerald-500 animate-pulse" : "bg-zinc-300"}`} />
            <span className="text-xs uppercase tracking-widest text-zinc-500 font-semibold">Agent Dialogue Bus</span>
            <span className={`rounded border px-2 py-0.5 text-[10px] uppercase tracking-wider font-semibold ${
              wsStatus === "open"
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-zinc-200 bg-zinc-50 text-zinc-500"
            }`}>
              {wsStatus}
            </span>
          </div>

          <div className="flex items-center gap-4">
            {stats && (
              <div className="flex gap-3 text-xs text-zinc-500 font-medium">
                <span>{stats.from_satellite} sat</span>
                <span>{stats.from_ground} gnd</span>
                <span>{stats.total_messages} total</span>
              </div>
            )}
            <div className="flex items-center gap-2 text-xs text-zinc-400 uppercase font-semibold hidden sm:flex">
              <span>SAT</span>
              <span>⇌</span>
              <span>GND</span>
            </div>
          </div>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 border-b border-zinc-100 px-5 py-2 text-[10px] font-semibold uppercase tracking-wider">
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
        <div className="flex-1 overflow-y-auto px-4 py-3 font-mono text-sm space-y-2">
          {displayMessages.length === 0 && (
            <div className="flex items-center justify-center h-full text-zinc-400 text-sm">
              Waiting for agent messages…
            </div>
          )}

          {displayMessages.map((msg) => {
            const note = msg.payload.note || "";
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
                      {msg.payload.severity && (
                        <span className={`uppercase tracking-wider text-[9px] font-bold px-1.5 py-0.5 rounded border ${
                          msg.payload.severity === "critical" ? "border-red-200 text-red-700 bg-red-50" :
                          msg.payload.severity === "high" ? "border-orange-200 text-orange-700 bg-orange-50" :
                          msg.payload.severity === "moderate" ? "border-amber-200 text-amber-700 bg-amber-50" :
                          "border-zinc-200 text-zinc-600 bg-zinc-50"
                        }`}>
                          {msg.payload.severity}
                        </span>
                      )}
                      <span className="ml-auto text-[10px] text-zinc-400 shrink-0">
                        {formatTimestamp(msg.timestamp)}
                      </span>
                    </div>
                    <p className="leading-relaxed text-xs break-words text-zinc-800">{note}</p>
                    {msg.payload.action && (
                      <p className="mt-1 text-[11px] text-zinc-500 italic border-l-2 border-zinc-200 pl-2">{msg.payload.action as string}</p>
                    )}
                    {msg.payload.change_score !== undefined && (
                      <div className="mt-2 flex gap-3 text-[10px] text-zinc-500 font-semibold uppercase tracking-wider">
                        <span>Score: <span className="text-zinc-800">{(msg.payload.change_score as number).toFixed(3)}</span></span>
                        {msg.payload.confidence !== undefined && (
                          <span>Conf: <span className="text-zinc-800">{(msg.payload.confidence as number).toFixed(3)}</span></span>
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
        <div className="border-t border-zinc-200 px-4 py-3 flex gap-2 items-center bg-zinc-50">
          <span className="text-[10px] uppercase tracking-wider font-semibold text-purple-600 shrink-0">User</span>
          <input
            type="text"
            value={operatorInput}
            onChange={(e) => setOperatorInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendOperatorMessage()}
            placeholder="Inject manual command into agent bus…"
            className="flex-1 rounded border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 placeholder-zinc-400 focus:border-zinc-400 focus:ring-1 focus:ring-zinc-400 outline-none"
          />
          <button
            onClick={sendOperatorMessage}
            className="rounded border border-purple-200 bg-purple-50 px-4 py-2 text-[11px] font-bold uppercase tracking-wider text-purple-700 hover:bg-purple-100 transition"
          >
            Inject
          </button>
      </div>
    </div>
  );
}
