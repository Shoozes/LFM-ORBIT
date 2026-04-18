import { useState, useRef, useEffect } from "react";
import { getApiBaseUrl } from "../utils/telemetry";

type Message = { role: "user" | "assistant"; content: string };

export default function GroundAgent() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "Ground Agent initialized. Reading telemetry. How can I assist you with operations?" }
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;
    
    const newMessages: Message[] = [...messages, { role: "user", content: input }];
    setMessages(newMessages);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch(`${getApiBaseUrl()}/api/agent/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: newMessages }),
      });
      const data = await response.json();
      setMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);
    } catch (e) {
      setMessages((prev) => [...prev, { role: "assistant", content: "[Link Error: Ground Agent unreachable]" }]);
    } finally {
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
          className="flex-1 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-2 text-sm text-zinc-900 placeholder-zinc-400 focus:border-zinc-400 focus:ring-1 focus:ring-zinc-400 outline-none"
        />
        <button onClick={sendMessage} className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white hover:bg-zinc-800 transition">
          Send
        </button>
      </div>
    </div>
  );
}
