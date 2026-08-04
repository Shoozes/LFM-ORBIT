/**
 * useMapPins — polls /api/map/pins and provides CRUD utilities.
 *
 * Returns the live pin list, a drop function (for operator pins via shift-click),
 * a remove function, a refetch function, and a visible error string.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { getApiBaseUrl } from "../utils/telemetry";
import { createRequestGate } from "../utils/requestGateCore.js";
import type { RequestGate } from "../utils/requestGateCore.js";

export type MapPin = {
  id: number;
  pin_type: "satellite" | "ground" | "operator";
  cell_id: string | null;
  lat: number;
  lng: number;
  label: string;
  note: string;
  severity: string | null;
  timestamp: string;
};

const POLL_MS = 3000;
const FETCH_TIMEOUT_MS = 5000;

async function fetchWithTimeout(input: RequestInfo | URL, init: RequestInit = {}) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  const abortRequest = () => controller.abort();
  init.signal?.addEventListener("abort", abortRequest, { once: true });
  try {
    if (init.signal?.aborted) controller.abort();
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    window.clearTimeout(timeoutId);
    init.signal?.removeEventListener("abort", abortRequest);
  }
}

function errorMessage(error: unknown, fallback: string) {
  if (error instanceof DOMException && error.name === "AbortError") {
    return `${fallback}: request timed out`;
  }
  if (error instanceof Error && error.message) {
    return `${fallback}: ${error.message}`;
  }
  return fallback;
}

export function useMapPins() {
  const [pins, setPins] = useState<MapPin[]>([]);
  const [error, setError] = useState<string | null>(null);
  const apiBase = getApiBaseUrl();
  const mountedRef = useRef(true);
  const refreshGateRef = useRef<RequestGate | null>(null);

  const fetchPins = useCallback(async (): Promise<boolean> => {
    const gate = refreshGateRef.current ?? createRequestGate();
    refreshGateRef.current = gate;
    const request = gate.begin();
    try {
      const r = await fetchWithTimeout(`${apiBase}/api/map/pins`, {
        signal: request.controller.signal,
      });
      if (!r.ok) {
        throw new Error(`HTTP ${r.status}`);
      }
      const data = (await r.json()) as { pins: MapPin[] };
      if (mountedRef.current && gate.isCurrent(request)) {
        setPins(Array.isArray(data.pins) ? data.pins : []);
        setError(null);
        return true;
      }
      return false;
    } catch (exc) {
      if (mountedRef.current && gate.isLatest(request)) {
        setError(errorMessage(exc, "Map pins unavailable"));
      }
      return false;
    } finally {
      if (gate.isLatest(request)) {
        gate.finish(request);
      }
    }
  }, [apiBase]);

  useEffect(() => {
    mountedRef.current = true;
    fetchPins();
    const id = window.setInterval(fetchPins, POLL_MS);
    return () => {
      mountedRef.current = false;
      window.clearInterval(id);
      refreshGateRef.current?.abort();
      refreshGateRef.current = null;
    };
  }, [fetchPins]);

  const dropPin = useCallback(
    async (lat: number, lng: number, note?: string) => {
      try {
        refreshGateRef.current?.abort();
        const response = await fetchWithTimeout(`${apiBase}/api/map/pins`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lat, lng, note: note ?? "Operator marker.", label: "" }),
        });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const refreshed = await fetchPins();
        if (mountedRef.current && refreshed) setError(null);
        return true;
      } catch (exc) {
        if (mountedRef.current) setError(errorMessage(exc, "Operator pin was not saved"));
        return false;
      }
    },
    [apiBase, fetchPins]
  );

  const removePin = useCallback(
    async (pinId: number) => {
      try {
        refreshGateRef.current?.abort();
        const response = await fetchWithTimeout(`${apiBase}/api/map/pins/${pinId}`, { method: "DELETE" });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        if (mountedRef.current) {
          setPins((prev) => prev.filter((p) => p.id !== pinId));
          setError(null);
        }
        await fetchPins();
        return true;
      } catch (exc) {
        if (mountedRef.current) setError(errorMessage(exc, "Operator pin was not removed"));
        return false;
      }
    },
    [apiBase, fetchPins]
  );

  return { pins, dropPin, removePin, refetch: fetchPins, error };
}
