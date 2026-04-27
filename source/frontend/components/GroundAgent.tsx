import { useState, useRef, useEffect } from "react";
import { getApiBaseUrl } from "../utils/telemetry";

type Message = { role: "user" | "assistant"; content: string };

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

export default function GroundAgent() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "Ground Agent initialized. Reading telemetry. How can I assist you with operations?" }
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const sendMessage = async () => {
    const outbound = input.trim();
    if (!outbound || isLoading) return;

    const newMessages: Message[] = [...messages, { role: "user", content: outbound }];
    setMessages(newMessages);
    setInput("");
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
      const data = await response.json() as { reply?: unknown };
      const reply = typeof data.reply === "string" && data.reply.trim() ? data.reply : "[Error: Empty reply]";
      setMessages((prev) => [...prev, { role: "assistant", content: reply }]);
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
            <span className={`inline-block rounded-lg px-4 py-2 shadow-sm ${m.role === "user" ? "bg-zinc-900 text-white" : "bg-zinc-50 border border-zinc-200 text-zinc-900"}`}>
              {m.content}
            </span>
          </div>
        ))}
        {isLoading && <div className="text-sm text-zinc-500 animate-pulse">Computing...</div>}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-zinc-200 p-3 flex gap-2">
        <input 
          type="text" 
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          placeholder="Command agent..."
          disabled={isLoading}
          className="flex-1 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-2 text-sm text-zinc-900 placeholder-zinc-400 outline-none focus:border-zinc-400 focus:ring-1 focus:ring-zinc-400 disabled:opacity-60"
        />
        <button
          onClick={sendMessage}
          disabled={isLoading || !input.trim()}
          className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
