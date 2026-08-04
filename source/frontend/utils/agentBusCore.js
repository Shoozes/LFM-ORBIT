const VALID_SENDERS = new Set(["satellite", "ground", "operator", "broadcast"]);
const VALID_MESSAGE_TYPES = new Set([
  "flag",
  "confirmation",
  "reject",
  "heartbeat",
  "status",
  "query",
  "error",
]);
const PAYLOAD_STRING_FIELDS = ["note", "severity", "action", "analysis_summary", "status"];
const PAYLOAD_NUMBER_FIELDS = ["change_score", "confidence", "cycle", "cells_scanned", "flags_sent", "discard_ratio"];
const DEFAULT_MESSAGE_LIMIT = 200;

function isRecord(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function normalizePayload(value) {
  if (!isRecord(value)) return null;

  const payload = { ...value };
  for (const field of PAYLOAD_STRING_FIELDS) {
    if (field in payload && typeof payload[field] !== "string") {
      delete payload[field];
    }
  }
  for (const field of PAYLOAD_NUMBER_FIELDS) {
    if (field in payload && !isFiniteNumber(payload[field])) {
      delete payload[field];
    }
  }
  if ("findings" in payload && (!Array.isArray(payload.findings) || !payload.findings.every((item) => typeof item === "string"))) {
    delete payload.findings;
  }
  return payload;
}

export function normalizeAgentMessage(value) {
  if (!isRecord(value)) return null;
  if (!Number.isSafeInteger(value.id) || value.id <= 0) return null;
  if (!VALID_SENDERS.has(value.sender) || typeof value.recipient !== "string" || !value.recipient.trim()) return null;
  if (!VALID_MESSAGE_TYPES.has(value.msg_type)) return null;
  if (!(value.cell_id === null || typeof value.cell_id === "string")) return null;
  if (typeof value.timestamp !== "string" || !value.timestamp.trim()) return null;

  const payload = normalizePayload(value.payload);
  if (!payload) return null;

  return {
    id: value.id,
    sender: value.sender,
    recipient: value.recipient,
    msg_type: value.msg_type,
    cell_id: value.cell_id,
    payload,
    timestamp: value.timestamp,
  };
}

export function parseAgentBusEnvelope(raw) {
  let parsed = raw;
  if (typeof raw === "string") {
    try {
      parsed = JSON.parse(raw);
    } catch {
      return null;
    }
  }

  if (!isRecord(parsed) || (parsed.type !== "history" && parsed.type !== "messages") || !Array.isArray(parsed.messages)) {
    return null;
  }

  return {
    type: parsed.type,
    messages: parsed.messages.map(normalizeAgentMessage).filter(Boolean),
  };
}

export function mergeAgentMessages(existing, incoming, limit = DEFAULT_MESSAGE_LIMIT) {
  const safeLimit = Number.isSafeInteger(limit) && limit > 0 ? limit : DEFAULT_MESSAGE_LIMIT;
  const byId = new Map();

  for (const message of [...existing, ...incoming]) {
    const normalized = normalizeAgentMessage(message);
    if (normalized) byId.set(normalized.id, normalized);
  }

  return [...byId.values()]
    .sort((left, right) => left.id - right.id)
    .slice(-safeLimit);
}
