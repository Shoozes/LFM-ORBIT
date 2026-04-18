import { useEffect, useRef, useState } from "react";
import { getApiBaseUrl } from "../utils/telemetry";

export type AgentMessage = {
  id: number;
  sender: "satellite" | "ground" | "operator" | "broadcast";
  recipient: string;
  msg_type: "flag" | "confirmation" | "reject" | "heartbeat" | "status" | "query" | "error";
  cell_id: string | null;
  payload: {
    note?: string;
    change_score?: number;
    confidence?: number;
    severity?: string;
    action?: string;
    analysis_summary?: string;
    findings?: string[];
    status?: string;
    cycle?: number;
    cells_scanned?: number;
    flags_sent?: number;
    discard_ratio?: number;
    [key: string]: unknown;
  };
  timestamp: string;
};

export function useAgentBus() {
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [wsStatus, setWsStatus] = useState<"connecting" | "open" | "closed">("closed");
  const wsRef = useRef<WebSocket | null>(null);
  const apiBase = getApiBaseUrl();

  useEffect(() => {
    let reconnectTimer: number;
    let isActive = true;

    const connect = () => {
      if (!isActive) return;
      const wsBase = apiBase.replace(/^http/, "ws");
      const ws = new WebSocket(`${wsBase}/ws/agent-dialogue`);
      wsRef.current = ws;
      setWsStatus("connecting");

      ws.onopen = () => {
        if (!isActive) return;
        setWsStatus("open");
      };

      ws.onclose = () => {
        if (!isActive) return;
        setWsStatus("closed");
        reconnectTimer = window.setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        // Will trigger onclose subsequently
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data as string) as {
            type: string;
            messages: AgentMessage[];
          };
          if (data.type === "history") {
            setMessages(data.messages);
          } else if (data.type === "messages") {
            setMessages((prev) => {
              const existingIds = new Set(prev.map((m) => m.id));
              const fresh = data.messages.filter((m) => !existingIds.has(m.id));
              return [...prev, ...fresh];
            });
          }
        } catch {
          // ignore parse errors
        }
      };
    };

    connect();

    return () => {
      isActive = false;
      clearTimeout(reconnectTimer);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [apiBase]);

  return { messages, wsStatus };
}
