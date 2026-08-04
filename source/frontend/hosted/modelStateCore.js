const MIN_BROWSER_STORAGE_BYTES = 320 * 1024 * 1024;
const MIN_DEVICE_MEMORY_GB = 2;
const WASM_PROBE_BYTES = Uint8Array.from([0, 97, 115, 109, 1, 0, 0, 0]);

function savedPackagesOnly(code, message, details = {}) {
  return {
    canFetch: false,
    code,
    deviceMemoryGb: details.deviceMemoryGb ?? null,
    imageInput: false,
    message,
    mode: "saved-packages-only",
    storageAvailable: details.storageAvailable ?? false,
    storageRemainingBytes: details.storageRemainingBytes ?? null,
    textReasoning: true,
    wasmAvailable: details.wasmAvailable ?? false,
  };
}

function hasWorkingWebAssembly(runtime) {
  try {
    return typeof runtime?.WebAssembly?.validate === "function"
      && runtime.WebAssembly.validate(WASM_PROBE_BYTES);
  } catch {
    return false;
  }
}

export async function probeBrowserModelCapability(runtime = globalThis) {
  if (runtime?.isSecureContext === false) {
    return savedPackagesOnly(
      "secure-context-unavailable",
      "Secure HTTPS context is required for reliable local model loading. Saved evidence packages remain available.",
    );
  }
  const wasmAvailable = hasWorkingWebAssembly(runtime);
  if (!wasmAvailable) {
    return savedPackagesOnly(
      "wasm-unavailable",
      "WebAssembly is unavailable here. Saved evidence packages remain available without local model inference.",
    );
  }

  const browserStorage = runtime?.navigator?.storage;
  if (!browserStorage || typeof browserStorage.estimate !== "function") {
    return savedPackagesOnly(
      "storage-unavailable",
      "Browser storage is unavailable here, so the local model is disabled. Saved evidence packages remain available.",
      { wasmAvailable, storageAvailable: false },
    );
  }

  let estimate;
  try {
    estimate = await browserStorage.estimate();
  } catch {
    return savedPackagesOnly(
      "storage-unavailable",
      "Browser storage could not be checked safely, so the local model is disabled. Saved evidence packages remain available.",
      { wasmAvailable, storageAvailable: true },
    );
  }

  const quota = Number(estimate?.quota);
  const usage = Number(estimate?.usage);
  if (!Number.isFinite(quota) || !Number.isFinite(usage) || quota < 0 || usage < 0) {
    return savedPackagesOnly(
      "storage-unavailable",
      "Browser storage returned an incomplete estimate, so the local model is disabled. Saved evidence packages remain available.",
      { wasmAvailable, storageAvailable: true },
    );
  }
  const storageRemainingBytes = Number.isFinite(quota) && Number.isFinite(usage)
    ? Math.max(0, quota - usage)
    : null;
  if (storageRemainingBytes !== null && storageRemainingBytes < MIN_BROWSER_STORAGE_BYTES) {
    return savedPackagesOnly(
      "storage-low",
      "Browser storage is too full for a reliable local model download. Saved evidence packages remain available.",
      { wasmAvailable, storageAvailable: true, storageRemainingBytes },
    );
  }

  const rawDeviceMemory = Number(runtime?.navigator?.deviceMemory);
  const deviceMemoryGb = Number.isFinite(rawDeviceMemory) && rawDeviceMemory > 0 ? rawDeviceMemory : null;
  if (deviceMemoryGb !== null && deviceMemoryGb < MIN_DEVICE_MEMORY_GB) {
    return savedPackagesOnly(
      "device-memory-low",
      "This browser reports limited device memory for a 219 MB local model. Saved evidence packages remain available.",
      { wasmAvailable, storageAvailable: true, storageRemainingBytes, deviceMemoryGb },
    );
  }

  return {
    canFetch: true,
    code: "ready",
    deviceMemoryGb,
    imageInput: false,
    message: "WebAssembly and browser storage are available for local text reasoning.",
    mode: "browser-model",
    storageAvailable: true,
    storageRemainingBytes,
    textReasoning: true,
    wasmAvailable: true,
  };
}

export function statusAfterBrowserModelCancellation(status, hasLoadedInstance) {
  if (status === "loading") return "idle";
  if (status === "generating") return hasLoadedInstance ? "ready" : "idle";
  return status;
}

export function isBrowserModelAbortError(value) {
  return Boolean(value && typeof value === "object" && value.name === "AbortError");
}

export function responseText(value) {
  if (typeof value === "string") return value.trim();
  if (Array.isArray(value)) {
    return value
      .map((part) => {
        if (typeof part === "string") return part;
        if (part && typeof part === "object" && "text" in part) return String(part.text || "");
        return "";
      })
      .join("")
      .trim();
  }
  return "";
}

export function browserModelErrorMessage(value) {
  if (isBrowserModelAbortError(value)) {
    return "Model fetch was cancelled. Saved evidence packages remain available; retry when ready.";
  }
  const detail = value && typeof value === "object" && typeof value.message === "string"
    ? value.message.trim()
    : "";
  return detail
    ? `The browser model could not load: ${detail} Saved evidence packages remain available.`
    : "The browser model could not load. Saved evidence packages remain available; retry when ready.";
}
