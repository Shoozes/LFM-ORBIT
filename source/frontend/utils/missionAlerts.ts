import type { AlertItem } from "../types/telemetry";

export function parseSquareCellCenter(cellId: string | undefined): [number, number] | null {
  if (!cellId?.startsWith("sq_")) return null;
  const parts = cellId.split("_");
  if (parts.length !== 3) return null;
  const lat = Number(parts[1]);
  const lng = Number(parts[2]);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  return [lat, lng];
}

export function cellIdMatchesBbox(cellId: string | undefined, bbox: number[] | null | undefined, tolerance = 0.11): boolean {
  if (!bbox) return true;
  const center = parseSquareCellCenter(cellId);
  if (!center) return false;
  const [lat, lng] = center;
  const [west, south, east, north] = bbox;
  return (
    lng >= west - tolerance
    && lng <= east + tolerance
    && lat >= south - tolerance
    && lat <= north + tolerance
  );
}

export function alertMatchesBbox(alert: AlertItem, bbox: number[] | null | undefined, tolerance = 0.11): boolean {
  return cellIdMatchesBbox(alert.cell_id, bbox, tolerance);
}

export function filterAlertsForBbox(alerts: AlertItem[], bbox: number[] | null | undefined): AlertItem[] {
  return alerts.filter((alert) => alertMatchesBbox(alert, bbox));
}
