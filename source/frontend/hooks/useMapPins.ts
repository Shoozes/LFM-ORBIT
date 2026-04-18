/**
 * useMapPins — polls /api/map/pins and provides CRUD utilities.
 *
 * Returns the live pin list, a drop function (for operator pins via shift-click),
 * and a remove function.
 */
import { useCallback, useEffect, useState } from "react";
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

export function useMapPins() {
  const [pins, setPins] = useState<MapPin[]>([]);
  const apiBase = getApiBaseUrl();

  const fetchPins = useCallback(async () => {
    try {
      const r = await fetch(`${apiBase}/api/map/pins`);
      if (r.ok) {
        const data = (await r.json()) as { pins: MapPin[] };
        setPins(data.pins);
      }
    } catch {
      // silently ignore — no pins is fine
    }
  }, [apiBase]);

  useEffect(() => {
    fetchPins();
    const id = window.setInterval(fetchPins, POLL_MS);
    return () => window.clearInterval(id);
  }, [fetchPins]);

  const dropPin = useCallback(
    async (lat: number, lng: number, note?: string) => {
      try {
        await fetch(`${apiBase}/api/map/pins`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lat, lng, note: note ?? "Operator marker.", label: "" }),
        });
        await fetchPins();
      } catch {
        // ignore
      }
    },
    [apiBase, fetchPins]
  );

  const removePin = useCallback(
    async (pinId: number) => {
      try {
        await fetch(`${apiBase}/api/map/pins/${pinId}`, { method: "DELETE" });
        setPins((prev) => prev.filter((p) => p.id !== pinId));
      } catch {
        // ignore
      }
    },
    [apiBase]
  );

  return { pins, dropPin, removePin, refetch: fetchPins };
}
