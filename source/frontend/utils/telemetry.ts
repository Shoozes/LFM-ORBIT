import type {
  AlertItem,
  GridInitMessage,
  OrbitalScanEventDetail,
  ScanResultMessage,
  ScanWindow,
  TelemetryMessage,
} from "../types/telemetry";

export function formatSourceLabel(source: string | undefined): string {
  if (!source) return "Unknown Source";
  switch (source) {
    case "simsat_sentinel": return "SimSat Sentinel";
    case "sentinelhub_direct": return "Sentinel Hub (Live)";
    case "semi_real_loader_v1": return "Semi-Real (Offline Demo)";
    default: return source;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function normalizeWindow(value: unknown): ScanWindow | null {
  if (!isRecord(value)) {
    return null;
  }

  if (
    !isString(value.label) ||
    !isNumber(value.quality) ||
    !isNumber(value.nir) ||
    !isNumber(value.red) ||
    !isNumber(value.swir) ||
    !isNumber(value.ndvi) ||
    !isNumber(value.nbr) ||
    !isStringArray(value.flags)
  ) {
    return null;
  }

  return {
    label: value.label,
    quality: value.quality,
    nir: value.nir,
    red: value.red,
    swir: value.swir,
    ndvi: value.ndvi,
    nbr: value.nbr,
    flags: value.flags,
  };
}

function normalizeCellId(value: Record<string, unknown>): string | null {
  if (isString(value.cell_id)) {
    return value.cell_id;
  }

  if (isString(value.hex_id)) {
    return value.hex_id;
  }

  return null;
}

export function parseTelemetryMessage(raw: string): TelemetryMessage | null {
  try {
    const parsed: unknown = JSON.parse(raw);

    if (!isRecord(parsed) || !isString(parsed.type)) {
      return null;
    }

    if (parsed.type === "grid_init") {
      if (!parsed.data || !parsed.region) {
        return null;
      }

      return parsed as GridInitMessage;
    }

    if (parsed.type !== "scan_result") {
      return null;
    }

    const cellId = normalizeCellId(parsed);
    const beforeWindow = normalizeWindow(parsed.before_window);
    const afterWindow = normalizeWindow(parsed.after_window);

    if (
      !cellId ||
      !isString(parsed.event_id) ||
      !isString(parsed.region_id) ||
      typeof parsed.is_anomaly !== "boolean" ||
      !isNumber(parsed.change_score) ||
      !isNumber(parsed.confidence) ||
      !isString(parsed.priority) ||
      !isStringArray(parsed.reason_codes) ||
      !isNumber(parsed.payload_bytes) ||
      !isNumber(parsed.estimated_bandwidth_saved_mb) ||
      !isString(parsed.observation_source) ||
      !beforeWindow ||
      !afterWindow ||
      !isRecord(parsed.heartbeat) ||
      !isString(parsed.heartbeat.last_cell) ||
      !isNumber(parsed.heartbeat.cells_scanned) ||
      !isNumber(parsed.heartbeat.alerts_emitted) ||
      !isNumber(parsed.heartbeat.discard_ratio) ||
      !isNumber(parsed.heartbeat.total_cells) ||
      !isNumber(parsed.heartbeat.cycle_index) ||
      !isNumber(parsed.cycle_index)
    ) {
      return null;
    }

    return {
      type: "scan_result",
      event_id: parsed.event_id,
      region_id: parsed.region_id,
      cell_id: cellId,
      is_anomaly: parsed.is_anomaly,
      change_score: parsed.change_score,
      confidence: parsed.confidence,
      priority: parsed.priority as ScanResultMessage["priority"],
      reason_codes: parsed.reason_codes,
      payload_bytes: parsed.payload_bytes,
      estimated_bandwidth_saved_mb: parsed.estimated_bandwidth_saved_mb,
      observation_source: parsed.observation_source,
      before_window: beforeWindow,
      after_window: afterWindow,
      heartbeat: {
        last_cell: parsed.heartbeat.last_cell,
        cells_scanned: parsed.heartbeat.cells_scanned,
        alerts_emitted: parsed.heartbeat.alerts_emitted,
        discard_ratio: parsed.heartbeat.discard_ratio,
        total_cells: parsed.heartbeat.total_cells,
        cycle_index: parsed.heartbeat.cycle_index,
      },
      cycle_index: parsed.cycle_index,
    };
  } catch {
    return null;
  }
}

export function toAlertItem(message: ScanResultMessage): AlertItem {
  return {
    event_id: message.event_id,
    region_id: message.region_id,
    cell_id: message.cell_id,
    change_score: message.change_score,
    confidence: message.confidence,
    priority: message.priority,
    reason_codes: message.reason_codes,
    payload_bytes: message.payload_bytes,
    observation_source: message.observation_source,
    before_window: message.before_window,
    after_window: message.after_window,
    timestamp: new Date().toISOString(),
    downlinked: true,
  };
}

export function mergeAlertLists(existing: AlertItem[], incoming: AlertItem[]): AlertItem[] {
  const byEventId = new Map<string, AlertItem>();

  for (const alert of existing) {
    byEventId.set(alert.event_id, alert);
  }

  for (const alert of incoming) {
    const previous = byEventId.get(alert.event_id);
    byEventId.set(alert.event_id, {
      ...previous,
      ...alert,
    });
  }

  const sorted = Array.from(byEventId.values()).sort((left, right) => {
    const leftTimestamp = left.timestamp ? Date.parse(left.timestamp) : 0;
    const rightTimestamp = right.timestamp ? Date.parse(right.timestamp) : 0;

    if (rightTimestamp !== leftTimestamp) {
      return rightTimestamp - leftTimestamp;
    }

    if (right.change_score !== left.change_score) {
      return right.change_score - left.change_score;
    }

    return right.event_id.localeCompare(left.event_id);
  });

  if (sorted.length > 200) {
    return sorted.slice(0, 200);
  }
  return sorted;
}

export function createOrbitalScanEvent(
  detail: OrbitalScanEventDetail,
): CustomEvent<OrbitalScanEventDetail> {
  return new CustomEvent<OrbitalScanEventDetail>("orbital-scan", { detail });
}

export function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim();
  if (configured && configured.length > 0) return configured.replace(/\/$/, "");
  
  // Fallback to current hostname but locked to port 8000
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://127.0.0.1:8000";
}

export function getWebSocketUrl(apiBaseUrl?: string): string {
  const base = apiBaseUrl || getApiBaseUrl();
  const wsBase = base.replace(/^http/, "ws");
  return `${wsBase}/ws/telemetry`;
}

export function generateGridForBbox(bbox: number[]): GeoJSON.FeatureCollection {
  const [west, south, east, north] = bbox;
  const STEP_SIZE = 0.1;

  const minLat = Math.floor(south / STEP_SIZE) * STEP_SIZE;
  const maxLat = Math.ceil(north / STEP_SIZE) * STEP_SIZE;
  const minLng = Math.floor(west / STEP_SIZE) * STEP_SIZE;
  const maxLng = Math.ceil(east / STEP_SIZE) * STEP_SIZE;

  const features: GeoJSON.Feature[] = [];

  // Safeguard
  if ((maxLat - minLat) / STEP_SIZE > 50 || (maxLng - minLng) / STEP_SIZE > 50) {
      return { type: "FeatureCollection", features: [] };
  }

  for (let lat = minLat; lat <= maxLat + 0.0001; lat += STEP_SIZE) {
    for (let lng = minLng; lng <= maxLng + 0.0001; lng += STEP_SIZE) {
        const c_lat = Number(lat.toFixed(4));
        const c_lng = Number(lng.toFixed(4));
        const cell_id = `sq_${c_lat}_${c_lng}`;

        const w = (lng - STEP_SIZE / 2);
        const e = (lng + STEP_SIZE / 2);
        const s = (lat - STEP_SIZE / 2);
        const n = (lat + STEP_SIZE / 2);

        features.push({
            type: "Feature",
            id: cell_id,
            geometry: {
                type: "Polygon",
                coordinates: [[
                    [w, n],
                    [e, n],
                    [e, s],
                    [w, s],
                    [w, n]
                ]]
            },
            properties: {
                cell_id
            }
        });
    }
  }

  return {
    type: "FeatureCollection",
    features
  };
}