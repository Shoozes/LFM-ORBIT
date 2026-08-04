export type BrowserModelCapabilityCore = {
  canFetch: boolean;
  code: "ready" | "secure-context-unavailable" | "wasm-unavailable" | "storage-unavailable" | "storage-low" | "device-memory-low";
  deviceMemoryGb: number | null;
  imageInput: false;
  message: string;
  mode: "browser-model" | "saved-packages-only";
  storageAvailable: boolean;
  storageRemainingBytes: number | null;
  textReasoning: true;
  wasmAvailable: boolean;
};

export type BrowserModelStatusCore = "idle" | "loading" | "ready" | "generating" | "error";

export function probeBrowserModelCapability(runtime?: unknown): Promise<BrowserModelCapabilityCore>;
export function statusAfterBrowserModelCancellation(status: BrowserModelStatusCore, hasLoadedInstance: boolean): BrowserModelStatusCore;
export function isBrowserModelAbortError(value: unknown): boolean;
export function responseText(value: unknown): string;
export function browserModelErrorMessage(value: unknown): string;
