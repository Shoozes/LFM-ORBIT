import assert from "node:assert/strict";
import test from "node:test";
import {
  browserModelErrorMessage,
  isBrowserModelAbortError,
  probeBrowserModelCapability,
  responseText,
  statusAfterBrowserModelCancellation,
} from "../hosted/modelStateCore.js";

const enoughStorage = { quota: 1024 * 1024 * 1024, usage: 64 * 1024 * 1024 };

function runtime({ wasm = true, storage = enoughStorage, deviceMemory } = {}) {
  return {
    WebAssembly: { validate: () => wasm },
    navigator: {
      ...(deviceMemory === undefined ? {} : { deviceMemory }),
      storage: storage === null ? undefined : { estimate: async () => storage },
    },
  };
}

test("browser model cancellation preserves a loaded instance and resets a download", () => {
  assert.equal(statusAfterBrowserModelCancellation("generating", true), "ready");
  assert.equal(statusAfterBrowserModelCancellation("generating", false), "idle");
  assert.equal(statusAfterBrowserModelCancellation("loading", false), "idle");
  assert.equal(statusAfterBrowserModelCancellation("ready", true), "ready");
});

test("browser model abort detection accepts DOM-style errors without weakening ordinary errors", () => {
  assert.equal(isBrowserModelAbortError({ name: "AbortError" }), true);
  assert.equal(isBrowserModelAbortError(new DOMException("cancelled", "AbortError")), true);
  assert.equal(isBrowserModelAbortError(new Error("failed")), false);
  assert.equal(isBrowserModelAbortError({ name: "NetworkError" }), false);
});

test("browser model response parsing handles text, structured parts, and empty output", () => {
  assert.equal(responseText("  hello  "), "hello");
  assert.equal(responseText([" hello", { text: " world " }, { ignored: true }]), "hello world");
  assert.equal(responseText([]), "");
  assert.equal(responseText(null), "");
});

test("browser capability probe disables fetch when WebAssembly is unavailable", async () => {
  const result = await probeBrowserModelCapability(runtime({ wasm: false }));
  assert.equal(result.canFetch, false);
  assert.equal(result.code, "wasm-unavailable");
  assert.equal(result.mode, "saved-packages-only");
});

test("browser capability probe requires a secure context for model loading", async () => {
  const result = await probeBrowserModelCapability({
    ...runtime(),
    isSecureContext: false,
  });
  assert.equal(result.canFetch, false);
  assert.equal(result.code, "secure-context-unavailable");
  assert.match(result.message, /HTTPS/i);
});

test("browser capability probe disables fetch when storage is unavailable or too full", async () => {
  const unavailable = await probeBrowserModelCapability(runtime({ storage: null }));
  assert.equal(unavailable.code, "storage-unavailable");
  assert.equal(unavailable.wasmAvailable, true);

  const low = await probeBrowserModelCapability(runtime({ storage: { quota: 350 * 1024 * 1024, usage: 40 * 1024 * 1024 } }));
  assert.equal(low.code, "storage-low");
  assert.equal(low.storageRemainingBytes, 310 * 1024 * 1024);

  const malformed = await probeBrowserModelCapability(runtime({ storage: { quota: 512 * 1024 * 1024 } }));
  assert.equal(malformed.code, "storage-unavailable");
});

test("browser capability probe keeps low-memory devices on saved packages", async () => {
  const result = await probeBrowserModelCapability(runtime({ deviceMemory: 1 }));
  assert.equal(result.canFetch, false);
  assert.equal(result.code, "device-memory-low");
  assert.equal(result.deviceMemoryGb, 1);
});

test("browser capability probe permits the pinned text-only model when signals are healthy", async () => {
  const result = await probeBrowserModelCapability(runtime({ deviceMemory: 8 }));
  assert.equal(result.canFetch, true);
  assert.equal(result.code, "ready");
  assert.equal(result.mode, "browser-model");
  assert.equal(result.imageInput, false);
  assert.equal(result.textReasoning, true);
});

test("browser model errors keep cancellation and retry copy actionable", () => {
  assert.match(browserModelErrorMessage({ name: "AbortError" }), /cancelled/i);
  assert.match(browserModelErrorMessage(new Error("network failed")), /network failed/i);
  assert.match(browserModelErrorMessage({ message: "cross-realm failure" }), /cross-realm failure/i);
  assert.match(browserModelErrorMessage(null), /Saved evidence packages remain available/i);
});
