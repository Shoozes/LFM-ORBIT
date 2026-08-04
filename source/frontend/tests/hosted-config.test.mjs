import assert from "node:assert/strict";
import test from "node:test";
import { resolveHostedModelEnabled } from "../hosted/hostedConfigCore.js";

test("Pages model policy is disabled unless explicitly enabled", () => {
  assert.equal(resolveHostedModelEnabled("pages"), false);
  assert.equal(resolveHostedModelEnabled("pages", "false"), false);
  assert.equal(resolveHostedModelEnabled("pages", "true"), true);
});

test("local and hosted model policy stays enabled by default but accepts an explicit disable", () => {
  assert.equal(resolveHostedModelEnabled("development"), true);
  assert.equal(resolveHostedModelEnabled("hosted"), true);
  assert.equal(resolveHostedModelEnabled("hosted", "false"), false);
  assert.equal(resolveHostedModelEnabled("development", "true"), true);
});

test("invalid model policy values fail at the build boundary", () => {
  assert.throws(
    () => resolveHostedModelEnabled("pages", "yes"),
    /VITE_HOSTED_MODEL_ENABLED must be exactly true or false/i,
  );
  assert.throws(
    () => resolveHostedModelEnabled("hosted", "enabled"),
    /VITE_HOSTED_MODEL_ENABLED must be exactly true or false/i,
  );
});
