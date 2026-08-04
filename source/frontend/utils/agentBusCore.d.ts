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

export type AgentBusEnvelope = {
  type: "history" | "messages";
  messages: AgentMessage[];
};

export function normalizeAgentMessage(value: unknown): AgentMessage | null;
export function parseAgentBusEnvelope(raw: unknown): AgentBusEnvelope | null;
export function mergeAgentMessages(
  existing: AgentMessage[],
  incoming: AgentMessage[],
  limit?: number,
): AgentMessage[];
