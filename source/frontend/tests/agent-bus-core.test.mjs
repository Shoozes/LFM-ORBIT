import assert from "node:assert/strict";
import test from "node:test";
import {
  mergeAgentMessages,
  normalizeAgentMessage,
  parseAgentBusEnvelope,
} from "../utils/agentBusCore.js";

function message(overrides = {}) {
  return {
    id: 1,
    sender: "satellite",
    recipient: "ground",
    msg_type: "flag",
    cell_id: "sq_1",
    payload: { note: "candidate", change_score: 0.42, confidence: 0.8 },
    timestamp: "2026-08-04T12:00:00Z",
    ...overrides,
  };
}

test("agent bus parser ignores malformed envelopes and messages", () => {
  assert.equal(parseAgentBusEnvelope("not json"), null);
  assert.equal(parseAgentBusEnvelope(JSON.stringify({ type: "messages", messages: {} })), null);

  const parsed = parseAgentBusEnvelope(JSON.stringify({
    type: "messages",
    messages: [
      message(),
      message({ id: 2, payload: { note: { unsafe: true }, change_score: "bad" } }),
      { id: "3", sender: "ground" },
    ],
  }));

  assert.equal(parsed?.messages.length, 2);
  assert.deepEqual(parsed?.messages[1].payload, {});
});

test("agent bus message normalization keeps display fields safe", () => {
  const normalized = normalizeAgentMessage(message({
    payload: {
      note: "safe",
      severity: "high",
      action: "review",
      findings: ["one"],
      confidence: Number.NaN,
    },
  }));

  assert.deepEqual(normalized?.payload, {
    note: "safe",
    severity: "high",
    action: "review",
    findings: ["one"],
  });
  assert.equal(normalizeAgentMessage(message({ sender: "unknown" })), null);
});

test("agent bus merge deduplicates updates and retains a bounded chronological tail", () => {
  const merged = mergeAgentMessages(
    [message({ id: 1 }), message({ id: 2, payload: { note: "old" } })],
    [message({ id: 2, payload: { note: "updated" } }), message({ id: 3 })],
    2,
  );

  assert.deepEqual(merged.map((item) => item.id), [2, 3]);
  assert.equal(merged[0].payload.note, "updated");
});
