/**
 * useMapPins — polls /api/map/pins and provides CRUD utilities.
 *
 * Returns the live pin list, a drop function (for operator pins via shift-click),
 * a remove function, a refetch function, and a visible error string.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { getApiBaseUrl } from "../utils/telemetry";

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
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    window.clearTimeout(timeoutId);
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
  const requestSeqRef = useRef(0);

  const fetchPins = useCallback(async () => {
    const requestSeq = ++requestSeqRef.current;
    try {
      const r = await fetchWithTimeout(`${apiBase}/api/map/pins`);
      if (!r.ok) {
        throw new Error(`HTTP ${r.status}`);
      }
      const data = (await r.json()) as { pins: MapPin[] };
      if (mountedRef.current && requestSeq === requestSeqRef.current) {
        setPins(Array.isArray(data.pins) ? data.pins : []);
        setError(null);
      }
    } catch (exc) {
      if (mountedRef.current && requestSeq === requestSeqRef.current) {
        setError(errorMessage(exc, "Map pins unavailable"));
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
    };
  }, [fetchPins]);

  const dropPin = useCallback(
    async (lat: number, lng: number, note?: string) => {
      try {
        const response = await fetchWithTimeout(`${apiBase}/api/map/pins`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lat, lng, note: note ?? "Operator marker.", label: "" }),
        });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        await fetchPins();
        if (mountedRef.current) setError(null);
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
        const response = await fetchWithTimeout(`${apiBase}/api/map/pins/${pinId}`, { method: "DELETE" });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        if (mountedRef.current) {
          setPins((prev) => prev.filter((p) => p.id !== pinId));
          setError(null);
        }
        return true;
      } catch (exc) {
        if (mountedRef.current) setError(errorMessage(exc, "Operator pin was not removed"));
        return false;
      }
    },
    [apiBase]
  );

  return { pins, dropPin, removePin, refetch: fetchPins, error };
}
