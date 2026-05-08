import { useState, useRef, useEffect } from "react";
import { getApiBaseUrl } from "../utils/telemetry";
import GroundAgentActionCard, {
  type AgentAction,
  type ChatResponse,
  type GroundAgentProposal,
} from "./GroundAgentActionCard";
import type { Mission } from "../types/mission";

type Message = {
  role: "user" | "assistant";
  content: string;
  actions?: AgentAction[];
  proposals?: GroundAgentProposal[];
};

async function readAgentError(response: Response, fallback: string): Promise<string> {
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

type GroundAgentProps = {
  onActionComplete?: (response: ChatResponse) => void | Promise<void>;
  onNavigate?: (target: "mission" | "logs" | "settings" | "proof") => void | Promise<void>;
  mission?: Mission | null;
  proofAttentionActive?: boolean;
};

const DEFAULT_COMMANDS = [
  "Load Spain Larouco wildfire proof replay",
  "Load Pineland Road wildfire proof replay",
  "Load Florida SR-26 wildfire proof replay",
  "Load critical minerals proof replay",
  "List real seeded proof replays",
];

const AGENT_REQUEST_TIMEOUT_MS = 30_000;

const NAV_SHORTCUTS: Array<{
  id: "mission" | "logs" | "settings" | "proof";
  label: string;
  target: "mission" | "logs" | "settings" | "proof";
  requiresMission?: boolean;
}> = [
  { id: "mission", label: "Mission Control", target: "mission" },
  { id: "logs", label: "Logs", target: "logs" },
  { id: "proof", label: "Proof Mode", target: "proof", requiresMission: true },
  { id: "settings", label: "Settings", target: "settings" },
];

function summarizeAction(action: AgentAction): string {
  const result = action.result ?? {};
  if (action.name === "load_replay" && typeof result.replay_id === "string") {
    return result.replay_id;
  }
  if (action.name === "rescan_replay" && typeof result.source_replay_id === "string") {
    return result.source_replay_id;
  }
  if (action.name === "start_mission_pack" && typeof result.pack_id === "string") {
    return result.pack_id;
  }
  if (action.name === "start_custom_mission") {
    const mission = result.mission;
    if (mission && typeof mission === "object" && "id" in mission) {
      return `mission #${String((mission as { id?: unknown }).id)}`;
    }
    return "custom plan";
  }
  if (action.name === "set_link_state" && typeof result.connected === "boolean") {
    return result.connected ? "online" : "offline";
  }
  if (action.name === "stop_mission") {
    return typeof result.stopped_mission_id === "number" ? `#${result.stopped_mission_id}` : "no active mission";
  }
  if (action.name === "navigate_map" && typeof result.label === "string") {
    return result.label;
  }
  if (action.name === "list_replays" && Array.isArray(result.replays)) {
    return `${result.replays.length} available`;
  }
  if (typeof result.error === "string") {
    return result.error;
  }
  return action.status;
}

export default function GroundAgent({ onActionComplete, onNavigate, mission, proofAttentionActive = false }: GroundAgentProps) {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "Ground Agent initialized. Reading telemetry. Send an operations request." }
  ]);
  const [input, setInput] = useState("");
  const [quickCommands, setQuickCommands] = useState(DEFAULT_COMMANDS);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const appendAgentResponse = async (data: ChatResponse) => {
    const reply = typeof data.reply === "string" && data.reply.trim() ? data.reply : "[Error: Empty reply]";
    const actions = Array.isArray(data.actions) ? data.actions : [];
    const proposals = Array.isArray(data.proposals) ? data.proposals : [];
    if (Array.isArray(data.suggestions) && data.suggestions.every((item) => typeof item === "string")) {
      setQuickCommands(data.suggestions.slice(0, 5));
    }
    setMessages((prev) => [...prev, { role: "assistant", content: reply, actions, proposals }]);
    if (actions.some((action) => action.status === "ok")) {
      try {
        await onActionComplete?.(data);
      } catch (err) {
        const message = err instanceof Error ? err.message : "UI refresh failed.";
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `Action completed, but the UI refresh did not finish: ${message}` },
        ]);
      }
    }
  };

  const handleProposalCancelled = (proposal: GroundAgentProposal) => {
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: `Cancelled proposal: ${proposal.title}. No app state changed.` },
    ]);
  };

  const sendMessage = async (override?: string) => {
    const outbound = (override ?? input).trim();
    if (!outbound || isLoading) return;

    const newMessages: Message[] = [...messages, { role: "user", content: outbound }];
    setMessages(newMessages);
    if (!override) setInput("");
    setIsLoading(true);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), AGENT_REQUEST_TIMEOUT_MS);

    try {
      const response = await fetch(`${getApiBaseUrl()}/api/agent/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: newMessages }),
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error(await readAgentError(response, `Ground Agent failed with HTTP ${response.status}.`));
      }
      const data = await response.json() as ChatResponse;
      await appendAgentResponse(data);
    } catch (e) {
      const message = e instanceof DOMException && e.name === "AbortError"
        ? "Ground Agent timed out after 30 seconds. Confirm the backend is still running on port 8000."
        : e instanceof Error
          ? e.message
          : "Ground Agent unreachable.";
      setMessages((prev) => [...prev, { role: "assistant", content: `[Link Error: ${message}]` }]);
    } finally {
      clearTimeout(timeoutId);
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  useEffect(() => {
    const element = inputRef.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 160)}px`;
  }, [input]);

  return (
    <div className="ground-agent-shell flex h-full min-h-0 w-full flex-col bg-white">
      <div
        className="ground-agent-playbook border-b border-zinc-200 bg-zinc-50 px-3 py-1.5"
        data-testid="ground-agent-operator-playbook"
      >
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-zinc-500">Operator Playbook</p>
              <p className="text-xs leading-tight text-zinc-600">Task, replay, inspect.</p>
            </div>
          </div>
          <span className={`shrink-0 rounded border px-2 py-1 text-[10px] font-bold uppercase tracking-wider ${
            mission?.status === "active"
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border-zinc-200 bg-white text-zinc-500"
          }`}>
            {mission?.status === "active" ? "Mission Active" : "No Mission"}
          </span>
        </div>
        <div className="ground-agent-shortcuts mt-2 flex gap-1.5 overflow-x-auto pb-0.5">
          {NAV_SHORTCUTS.map((shortcut) => {
            const disabled = shortcut.requiresMission && !mission;
            const disabledReason = disabled ? "Start or load a mission first." : "";
            const proofReady = shortcut.id === "proof" && proofAttentionActive && !disabled;
            return (
              <span
                key={shortcut.id}
                data-testid={`ground-agent-nav-${shortcut.id}-tip`}
                data-ui-tip={disabled ? disabledReason : proofReady ? "Proof is ready. Open results." : `Open ${shortcut.label}`}
                className="shrink-0"
              >
                <button
                  type="button"
                  data-testid={`ground-agent-nav-${shortcut.id}`}
                  data-proof-ready={proofReady ? "true" : "false"}
                  onClick={() => void onNavigate?.(shortcut.target)}
                  disabled={disabled || !onNavigate}
                  aria-label={disabled ? `${shortcut.label}. ${disabledReason}` : proofReady ? `${shortcut.label}. Proof is ready.` : shortcut.label}
                  className={`rounded border border-zinc-200 bg-white px-2 py-1 text-[10px] font-semibold text-zinc-700 transition hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-45 ${proofReady ? "proof-action-glow border-cyan-300 text-cyan-800" : ""}`}
                >
                  {shortcut.label}
                </button>
              </span>
            );
          })}
        </div>
      </div>

      <div className="ground-agent-thread min-h-0 flex-1 overflow-y-auto p-2 sm:p-3 space-y-2 sm:space-y-3" data-testid="ground-agent-thread">
        {messages.map((m, i) => (
          <div key={i} className={`text-sm leading-relaxed ${m.role === "user" ? "text-right" : "text-left"}`}>
            <div
              data-testid={`ground-agent-message-${m.role}`}
              className={`inline-block max-w-full rounded-lg px-4 py-2 shadow-sm ${m.role === "user" ? "bg-zinc-900 text-white" : "bg-zinc-50 border border-zinc-200 text-zinc-900"}`}
            >
              <p className="whitespace-pre-wrap break-words">{m.content}</p>
              {m.actions && m.actions.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {m.actions.map((action, index) => (
                    <span
                      key={`${action.name}-${index}`}
                      className={`rounded border px-2 py-1 text-[10px] font-semibold uppercase tracking-wider ${
                        action.status === "ok"
                          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                          : "border-red-200 bg-red-50 text-red-700"
                      }`}
                    >
                      {action.name.replace(/_/g, " ")} - {summarizeAction(action)}
                    </span>
                  ))}
                </div>
              )}
              {m.proposals && m.proposals.length > 0 && (
                <div className="space-y-2">
                  {m.proposals.map((proposal) => (
                    <GroundAgentActionCard
                      key={proposal.id}
                      proposal={proposal}
                      onConfirmed={appendAgentResponse}
                      onCancelled={handleProposalCancelled}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {isLoading && <div className="text-sm text-zinc-500 animate-pulse">Computing...</div>}
        <div ref={messagesEndRef} />
      </div>

      <div className="ground-agent-composer border-t border-zinc-200 p-2 sm:p-3">
        <div
          id="ground-agent-suggestions-label"
          data-testid="ground-agent-suggestions-label"
          className="mb-1.5 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-zinc-500"
        >
          <span>Suggested Prompts</span>
          <span className="ground-agent-suggestion-note normal-case tracking-normal text-zinc-400">Ask only. Confirm before app changes.</span>
        </div>
        <div className="mb-1.5 flex gap-1.5 overflow-x-auto pb-0.5 sm:mb-2">
          {quickCommands.map((command) => (
            <span
              key={command}
              data-ui-tip="Suggestion: sends this prompt to Ground Agent."
              className="shrink-0"
            >
              <button
                type="button"
                onClick={() => void sendMessage(command)}
                disabled={isLoading}
                aria-describedby="ground-agent-suggestions-label"
                className="rounded border border-zinc-200 bg-white px-2 py-1 text-[10px] font-semibold text-zinc-600 transition hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {command}
              </button>
            </span>
          ))}
        </div>
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            data-testid="ground-agent-chat-input"
            aria-label="Ground Agent operations request"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                void sendMessage();
              }
            }}
            placeholder="Request replay, mission pack, link action..."
            disabled={isLoading}
            rows={2}
            className="max-h-32 min-h-12 flex-1 resize-none rounded-lg border-2 border-zinc-300 bg-white px-3 py-2 text-sm leading-relaxed text-zinc-900 shadow-inner outline-none placeholder-zinc-400 focus:border-zinc-700 focus:ring-2 focus:ring-zinc-200 disabled:opacity-60 sm:min-h-14 sm:py-2.5"
          />
          <button
            onClick={() => void sendMessage()}
            disabled={isLoading || !input.trim()}
            className="min-h-11 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
