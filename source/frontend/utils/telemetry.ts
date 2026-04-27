import type {
  AlertItem,
  BoundaryContext,
  GridInitMessage,
  OrbitalScanEventDetail,
  ScanResultMessage,
  ScanWindow,
  TelemetryMessage,
} from "../types/telemetry";

export function formatSourceLabel(source: string | undefined): string {
  if (!source) return "Unknown Source";
  switch (source) {
    case "simsat_sentinel":
    case "simsat_sentinel_imagery":
      return "SimSat Sentinel";
    case "simsat_mapbox":
    case "simsat_mapbox_imagery":
      return "SimSat Mapbox";
    case "sentinelhub_direct":
    case "sentinelhub_direct_imagery":
      return "Sentinel Hub (Live)";
    case "nasa_api_direct":
    case "nasa_api_direct_imagery":
      return "NASA Direct";
    case "nasa_gibs":
      return "NASA GIBS";
    case "semi_real_loader_v1":
      return "Semi-Real (Offline Demo)";
    case "seeded_sentinelhub_replay":
      return "Seeded Replay (Sentinel Hub Cache)";
    case "seeded_replay":
      return "Seeded Replay";
    case "seeded_cache":
      return "Seeded Local Cache";
    case "esri_arcgis":
      return "Esri World Imagery";
    case "offline_svg":
      return "Offline SVG Fallback";
    case "provided_asset":
      return "Provided Asset";
    case "generated_webm":
      return "Generated WebM";
    case "live_fetch":
      return "Live Provider Fetch";
    case "gee":
      return "GEE Sentinel-2";
    case "Seeded Orbital Video Cache":
      return "Seeded Orbital Cache";
    case "error_fallback":
      return "Fallback Observation";
    default: return source;
  }
}

export function formatReasonCode(code: string): string {
  const map: Record<string, string> = {
    ndvi_drop: "NDVI Drop",
    evi2_drop: "EVI2 Drop",
    nir_drop: "NIR Drop",
    nbr_drop: "NBR Drop",
    ndmi_drop: "Moisture Loss",
    soil_exposure_spike: "Soil Exposure Spike",
    multi_index_consensus: "Multi-Index Consensus",
    observation_pattern_match: "Disturbance Match",
    low_quality_window: "Low Quality Data",
    suspected_canopy_loss: "Canopy Loss",
    stable_vegetation: "Stable",
    regional_phenology_shift: "Regional Drought Signature",
  };
  return map[code] || code.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
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

function normalizeBoundaryContext(value: unknown): BoundaryContext[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }

  const normalized = value
    .map((entry) => {
      if (
        !isRecord(entry) ||
        !isString(entry.layer_type) ||
        !isString(entry.source_name) ||
        !(entry.feature_name === null || isString(entry.feature_name)) ||
        !isNumber(entry.overlap_area_m2) ||
        !isNumber(entry.overlap_ratio) ||
        !isNumber(entry.distance_to_boundary_m)
      ) {
        return null;
      }

      return {
        layer_type: entry.layer_type,
        source_name: entry.source_name,
        feature_name: entry.feature_name,
        overlap_area_m2: entry.overlap_area_m2,
        overlap_ratio: entry.overlap_ratio,
        distance_to_boundary_m: entry.distance_to_boundary_m,
      };
    })
    .filter((entry): entry is BoundaryContext => entry !== null);

  return normalized.length > 0 ? normalized : undefined;
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
    !isNumber(value.evi2) ||
    !isNumber(value.ndmi) ||
    !isNumber(value.soil_ratio) ||
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
    evi2: value.evi2,
    ndmi: value.ndmi,
    soil_ratio: value.soil_ratio,
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
    const boundaryContext = normalizeBoundaryContext(parsed.boundary_context);

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
      demo_forced_anomaly: parsed.demo_forced_anomaly === true,
      boundary_context: boundaryContext,
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
    demo_forced_anomaly: message.demo_forced_anomaly,
    boundary_context: message.boundary_context,
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
    const host = window.location.hostname === "localhost" ? "127.0.0.1" : window.location.hostname;
    return `${window.location.protocol}//${host}:8000`;
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
