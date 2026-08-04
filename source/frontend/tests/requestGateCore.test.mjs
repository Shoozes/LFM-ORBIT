import assert from "node:assert/strict";
import test from "node:test";
import { createRequestGate } from "../utils/requestGateCore.js";

test("request gate aborts superseded work and accepts only the latest response", () => {
  const gate = createRequestGate();
  const first = gate.begin();
  const second = gate.begin();

  assert.equal(first.controller.signal.aborted, true);
  assert.equal(gate.isCurrent(first), false);
  assert.equal(gate.isCurrent(second), true);

  gate.finish(first);
  assert.equal(gate.isCurrent(second), true);

  gate.finish(second);
  assert.equal(gate.isCurrent(second), false);
});

test("request gate invalidates in-flight work during cleanup", () => {
  const gate = createRequestGate();
  const request = gate.begin();

  gate.abort();

  assert.equal(request.controller.signal.aborted, true);
  assert.equal(gate.isCurrent(request), false);
});
