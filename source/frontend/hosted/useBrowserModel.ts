import { useCallback, useEffect, useRef, useState } from "react";
import type { Wllama } from "@wllama/wllama";
import wasmUrl from "@wllama/wllama/esm/wasm/wllama.wasm?url";
import { loadHostedModelManifest, verifyHostedModelArtifact } from "./hostedModel";
import type { HostedModelManifest } from "./hostedModel";
import { HOSTED_MODEL_ENABLED } from "./hostedConfig";
import {
  browserModelErrorMessage,
  probeBrowserModelCapability,
  responseText,
  statusAfterBrowserModelCancellation,
} from "./modelState";
import type { BrowserModelCapability, BrowserModelManifestStatus, BrowserModelStatus } from "./modelState";

export type ChatMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

export type BrowserModelController = {
  cancel: () => void;
  cancelDownload: () => void;
  cancelGeneration: () => void;
  chat: (messages: ChatMessage[]) => Promise<string>;
  capability: BrowserModelCapability | null;
  error: string | null;
  load: () => Promise<void>;
  manifestStatus: BrowserModelManifestStatus;
  model: HostedModelManifest | null;
  modelEnabled: boolean;
  progress: number;
  retryManifest: () => void;
  status: BrowserModelStatus;
};

export function useBrowserModel(): BrowserModelController {
  const instanceRef = useRef<Wllama | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [status, setStatus] = useState<BrowserModelStatus>("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [manifest, setManifest] = useState<HostedModelManifest | null>(null);
  const [manifestStatus, setManifestStatus] = useState<BrowserModelManifestStatus>(HOSTED_MODEL_ENABLED ? "loading" : "disabled");
  const [capability, setCapability] = useState<BrowserModelCapability | null>(null);
  const manifestRef = useRef<HostedModelManifest | null>(null);
  const manifestPromiseRef = useRef<Promise<HostedModelManifest> | null>(null);
  const statusRef = useRef<BrowserModelStatus>("idle");
  const generationAbortRef = useRef<AbortController | null>(null);

  const transition = useCallback((nextStatus: BrowserModelStatus) => {
    statusRef.current = nextStatus;
    setStatus(nextStatus);
  }, []);

  useEffect(() => {
    let active = true;
    void probeBrowserModelCapability()
      .then((result) => {
        if (active) setCapability(result);
      })
      .catch(() => {
        if (active) {
          setCapability({
            canFetch: false,
            code: "storage-unavailable",
            deviceMemoryGb: null,
            imageInput: false,
            message: "Browser capabilities could not be checked safely. Saved evidence packages remain available.",
            mode: "saved-packages-only",
            storageAvailable: false,
            storageRemainingBytes: null,
            textReasoning: true,
            wasmAvailable: false,
          });
        }
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  const fetchManifest = useCallback((signal?: AbortSignal): Promise<HostedModelManifest> => {
    if (!HOSTED_MODEL_ENABLED) {
      return Promise.reject(new Error("Browser inference is disabled for this hosted build; saved packages remain available."));
    }
    if (manifestRef.current) return Promise.resolve(manifestRef.current);
    if (manifestPromiseRef.current) return manifestPromiseRef.current;

    setManifestStatus("loading");
    const promise = loadHostedModelManifest(signal)
      .then((loadedManifest) => {
        if (signal?.aborted) return loadedManifest;
        manifestRef.current = loadedManifest;
        setManifest(loadedManifest);
        setManifestStatus("ready");
        return loadedManifest;
      })
      .catch((manifestError: unknown) => {
        if (!signal?.aborted) {
          setManifestStatus("error");
          setError(manifestError instanceof Error ? manifestError.message : String(manifestError));
        }
        throw manifestError;
    });
    manifestPromiseRef.current = promise;
    void promise.then(
      () => {
        if (manifestPromiseRef.current === promise) manifestPromiseRef.current = null;
      },
      () => {
        if (manifestPromiseRef.current === promise) manifestPromiseRef.current = null;
      },
    );
    return promise;
  }, []);

  useEffect(() => {
    if (!HOSTED_MODEL_ENABLED) return undefined;
    // The manifest is a small static identity file. Keep this shared request
    // independent from component cleanup so React StrictMode cannot abort the
    // first request and leave a second mount waiting on its rejected promise.
    void fetchManifest().catch(() => undefined);
    return undefined;
  }, [fetchManifest]);

  const retryManifest = useCallback(() => {
    if (!HOSTED_MODEL_ENABLED) return;
    setError(null);
    void fetchManifest().catch(() => undefined);
  }, [fetchManifest]);

  const load = useCallback(async () => {
    if (["loading", "ready", "generating"].includes(statusRef.current)) return;
    if (!HOSTED_MODEL_ENABLED) {
      setError("Browser inference is disabled for this hosted build; saved packages remain available.");
      return;
    }
    if (capability && !capability.canFetch) {
      setError(capability.message);
      return;
    }
    if (!manifestRef.current && manifestStatus !== "ready") {
      setError("The pinned browser model manifest is not ready yet. Retry the manifest check before fetching.");
      return;
    }
    transition("loading");
    setProgress(0);
    setError(null);
    const controller = new AbortController();
    abortRef.current = controller;
    let instance: Wllama | null = null;
    try {
      const loadedManifest = manifestRef.current ?? await fetchManifest(controller.signal);
      manifestRef.current = loadedManifest;
      setManifest(loadedManifest);
      await verifyHostedModelArtifact(loadedManifest, controller.signal);
      const { Wllama } = await import("@wllama/wllama");
      instance = new Wllama({ default: wasmUrl });
      await instance.loadModelFromUrl(
        loadedManifest.url,
        {
          n_ctx: 2048,
          n_batch: 128,
          // GitHub Pages does not provide cross-origin isolation by default.
          // Wllama will otherwise probe SharedArrayBuffer and can select a
          // thread mode that is fragile on iOS Safari; single-thread mode is
          // the safer public fallback while isolated local builds may scale.
          n_threads: globalThis.crossOriginIsolated ? undefined : 1,
          signal: controller.signal,
          progressCallback: ({ loaded, total }) => {
            setProgress(total > 0 ? Math.max(0, Math.min(1, loaded / total)) : 0);
          },
        },
      );
      if (controller.signal.aborted) return;
      instanceRef.current = instance;
      setProgress(1);
      transition("ready");
    } catch (loadError) {
      if (controller.signal.aborted) return;
      setError(browserModelErrorMessage(loadError));
      transition("error");
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      if (instance && instanceRef.current !== instance) {
        void instance.exit().catch(() => undefined);
      }
    }
  }, [capability, fetchManifest, manifestStatus, transition]);

  const chat = useCallback(async (messages: ChatMessage[]): Promise<string> => {
    const instance = instanceRef.current;
    if (!instance) throw new Error("Load the browser model before chatting.");
    transition("generating");
    setError(null);
    const controller = new AbortController();
    generationAbortRef.current = controller;
    try {
      const result = await instance.createChatCompletion({
        messages,
        max_tokens: 160,
        temperature: 0.25,
        top_p: 0.9,
        abortSignal: controller.signal,
      });
      const text = responseText(result.choices?.[0]?.message?.content);
      if (!text) throw new Error("The browser model returned an empty response.");
      transition("ready");
      return text;
    } catch (chatError) {
      if (controller.signal.aborted) throw new DOMException("Browser generation cancelled.", "AbortError");
      setError(chatError instanceof Error ? chatError.message : String(chatError));
      transition(instanceRef.current ? "ready" : "error");
      throw chatError;
    } finally {
      if (generationAbortRef.current === controller) generationAbortRef.current = null;
    }
  }, [transition]);

  const cancelDownload = useCallback(() => {
    const controller = abortRef.current;
    if (controller) {
      controller.abort();
      if (abortRef.current === controller) abortRef.current = null;
    }
    const currentStatus = statusRef.current;
    if (currentStatus !== "loading") return;
    const nextStatus = statusAfterBrowserModelCancellation(currentStatus, Boolean(instanceRef.current));
    if (nextStatus !== currentStatus) {
      transition(nextStatus);
    }
  }, [transition]);

  const cancelGeneration = useCallback(() => {
    const controller = generationAbortRef.current;
    if (!controller) return;
    controller.abort();
    const currentStatus = statusRef.current;
    const nextStatus = statusAfterBrowserModelCancellation(currentStatus, Boolean(instanceRef.current));
    if (nextStatus !== currentStatus) {
      transition(nextStatus);
    }
  }, [transition]);

  const cancel = useCallback(() => {
    cancelDownload();
    cancelGeneration();
  }, [cancelDownload, cancelGeneration]);

  useEffect(() => () => {
    abortRef.current?.abort();
    generationAbortRef.current?.abort();
    void instanceRef.current?.exit().catch(() => undefined);
  }, []);

  return {
    cancel,
    cancelDownload,
    cancelGeneration,
    chat,
    capability,
    error,
    load,
    manifestStatus,
    model: manifest,
    modelEnabled: HOSTED_MODEL_ENABLED,
    progress,
    retryManifest,
    status,
  };
}
