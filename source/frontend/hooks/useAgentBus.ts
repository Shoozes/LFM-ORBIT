import { useEffect, useRef, useState } from "react";
import { mergeAgentMessages, parseAgentBusEnvelope } from "../utils/agentBusCore.js";
import type { AgentMessage } from "../utils/agentBusCore.js";
import { getApiBaseUrl, getWebSocketUrl } from "../utils/telemetry";

export type { AgentMessage } from "../utils/agentBusCore.js";

export function useAgentBus() {
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [wsStatus, setWsStatus] = useState<"connecting" | "open" | "closed">("closed");
  const wsRef = useRef<WebSocket | null>(null);
  const apiBase = getApiBaseUrl();

  useEffect(() => {
    let reconnectTimer: number | undefined;
    let initialConnectTimer: number | undefined;
    let isActive = true;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 8;
    const baseReconnectDelayMs = 1000;

    const scheduleReconnect = () => {
      if (!isActive || reconnectTimer !== undefined || reconnectAttempts >= maxReconnectAttempts) {
        if (isActive && reconnectAttempts >= maxReconnectAttempts) {
          setWsStatus("closed");
        }
        return;
      }
      const delay = Math.min(baseReconnectDelayMs * 2 ** reconnectAttempts, 30_000);
      reconnectAttempts += 1;
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = undefined;
        connect();
      }, delay);
    };

    const connect = () => {
      if (!isActive) return;
      let ws: WebSocket;
      try {
        ws = new WebSocket(getWebSocketUrl(apiBase, "/ws/agent-dialogue"));
      } catch {
        setWsStatus("closed");
        scheduleReconnect();
        return;
      }
      wsRef.current = ws;
      setWsStatus("connecting");

      ws.onopen = () => {
        if (!isActive || wsRef.current !== ws) return;
        reconnectAttempts = 0;
        setWsStatus("open");
      };

      ws.onclose = () => {
        if (!isActive || wsRef.current !== ws) return;
        wsRef.current = null;
        setWsStatus("closed");
        scheduleReconnect();
      };

      ws.onerror = () => {
        // Will trigger onclose subsequently
      };

      ws.onmessage = (event) => {
        if (!isActive || wsRef.current !== ws) return;
        const data = parseAgentBusEnvelope(event.data);
        if (!data) return;
        if (data.type === "history") {
          setMessages(mergeAgentMessages([], data.messages));
        } else {
          setMessages((prev) => mergeAgentMessages(prev, data.messages));
        }
      };
    };

    initialConnectTimer = window.setTimeout(connect, 0);

    return () => {
      isActive = false;
      if (initialConnectTimer !== undefined) {
        window.clearTimeout(initialConnectTimer);
      }
      if (reconnectTimer !== undefined) {
        window.clearTimeout(reconnectTimer);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [apiBase]);

  return { messages, wsStatus };
}
