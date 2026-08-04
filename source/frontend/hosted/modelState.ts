import {
  browserModelErrorMessage,
  isBrowserModelAbortError,
  probeBrowserModelCapability,
  responseText,
  statusAfterBrowserModelCancellation,
} from "./modelStateCore.js";

export type BrowserModelStatus = "idle" | "loading" | "ready" | "generating" | "error";

export type BrowserModelCapability = {
  canFetch: boolean;
  code: "ready" | "wasm-unavailable" | "storage-unavailable" | "storage-low" | "device-memory-low";
  deviceMemoryGb: number | null;
  imageInput: false;
  message: string;
  mode: "browser-model" | "saved-packages-only";
  storageAvailable: boolean;
  storageRemainingBytes: number | null;
  textReasoning: true;
  wasmAvailable: boolean;
};

export {
  browserModelErrorMessage,
  isBrowserModelAbortError,
  probeBrowserModelCapability,
  responseText,
  statusAfterBrowserModelCancellation,
};
