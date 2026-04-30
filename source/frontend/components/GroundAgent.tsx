import { useState, useRef, useEffect } from "react";
import { getApiBaseUrl } from "../utils/telemetry";

type AgentAction = {
  name: string;
  status: "ok" | "error" | string;
  result?: Record<string, unknown>;
};

type Message = {
  role: "user" | "assistant";
  content: string;
  actions?: AgentAction[];
};

type ChatResponse = {
  reply?: unknown;
  actions?: AgentAction[];
  suggestions?: string[];
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
  onActionComplete?: () => void | Promise<void>;
};

const DEFAULT_COMMANDS = [
  "List replays",
  "Load Manchar flood replay",
  "Run maritime mission pack",
  "Set link offline",
  "Restore link",
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
  if (action.name === "set_link_state" && typeof result.connected === "boolean") {
    return result.connected ? "online" : "offline";
  }
  if (action.name === "list_replays" && Array.isArray(result.replays)) {
    return `${result.replays.length} available`;
  }
  if (typeof result.error === "string") {
    return result.error;
  }
  return action.status;
}

export default function GroundAgent({ onActionComplete }: GroundAgentProps) {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "Ground Agent initialized. Reading telemetry. Send an operations request." }
  ]);
  const [input, setInput] = useState("");
  const [quickCommands, setQuickCommands] = useState(DEFAULT_COMMANDS);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const sendMessage = async (override?: string) => {
    const outbound = (override ?? input).trim();
    if (!outbound || isLoading) return;

    const newMessages: Message[] = [...messages, { role: "user", content: outbound }];
    setMessages(newMessages);
    if (!override) setInput("");
    setIsLoading(true);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

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
      const reply = typeof data.reply === "string" && data.reply.trim() ? data.reply : "[Error: Empty reply]";
      const actions = Array.isArray(data.actions) ? data.actions : [];
      if (Array.isArray(data.suggestions) && data.suggestions.every((item) => typeof item === "string")) {
        setQuickCommands(data.suggestions.slice(0, 5));
      }
      setMessages((prev) => [...prev, { role: "assistant", content: reply, actions }]);
      if (actions.some((action) => action.status === "ok")) {
        await onActionComplete?.();
      }
    } catch (e) {
      const message = e instanceof DOMException && e.name === "AbortError"
        ? "Ground Agent timed out."
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

  return (
    <div className="flex h-full w-full flex-col bg-white">
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((m, i) => (
          <div key={i} className={`text-sm leading-relaxed ${m.role === "user" ? "text-right" : "text-left"}`}>
            <div className={`inline-block max-w-full rounded-lg px-4 py-2 shadow-sm ${m.role === "user" ? "bg-zinc-900 text-white" : "bg-zinc-50 border border-zinc-200 text-zinc-900"}`}>
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
            </div>
          </div>
        ))}
        {isLoading && <div className="text-sm text-zinc-500 animate-pulse">Computing...</div>}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-zinc-200 p-3">
        <div className="mb-2 flex flex-wrap gap-1.5">
          {quickCommands.map((command) => (
            <button
              key={command}
              type="button"
              onClick={() => void sendMessage(command)}
              disabled={isLoading}
              className="rounded border border-zinc-200 bg-white px-2 py-1 text-[10px] font-semibold text-zinc-600 transition hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {command}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void sendMessage()}
            placeholder="Request replay, mission pack, link action..."
            disabled={isLoading}
            className="flex-1 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-2 text-sm text-zinc-900 placeholder-zinc-400 outline-none focus:border-zinc-400 focus:ring-1 focus:ring-zinc-400 disabled:opacity-60"
          />
          <button
            onClick={() => void sendMessage()}
            disabled={isLoading || !input.trim()}
            className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
