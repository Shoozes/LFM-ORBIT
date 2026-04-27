export type ConnectionState = "connecting" | "open" | "closed" | "error" | "reconnecting";

export type RegionInfo = {
  region_id: string;
  display_name: string;
  grid_resolution: number;
  ring_size: number;
  bbox: [number, number, number, number];
  center_lat: number;
  center_lng: number;
  map_zoom: number;
};

export type GridInitMessage = {
  type: "grid_init";
  data: GeoJSON.FeatureCollection;
  region: RegionInfo;
};

export type ScanHeartbeat = {
  last_cell: string;
  cells_scanned: number;
  alerts_emitted: number;
  discard_ratio: number;
  total_cells: number;
  cycle_index: number;
};

export type ScanWindow = {
  label: string;
  quality: number;
  nir: number;
  red: number;
  swir: number;
  ndvi: number;
  nbr: number;
  evi2: number;
  ndmi: number;
  soil_ratio: number;
  flags: string[];
};

export type BoundaryContext = {
  layer_type: string;
  source_name: string;
  feature_name: string | null;
  overlap_area_m2: number;
  overlap_ratio: number;
  distance_to_boundary_m: number;
};

export type ScanResultMessage = {
  type: "scan_result";
  event_id: string;
  region_id: string;
  cell_id: string;
  is_anomaly: boolean;
  change_score: number;
  confidence: number;
  priority: "low" | "medium" | "high" | "critical";
  reason_codes: string[];
  payload_bytes: number;
  estimated_bandwidth_saved_mb: number;
  observation_source: string;
  before_window: ScanWindow;
  after_window: ScanWindow;
  heartbeat: ScanHeartbeat;
  cycle_index: number;
  demo_forced_anomaly?: boolean;
  boundary_context?: BoundaryContext[];
};

export type ScanCompleteMessage = {
  type: "scan_complete";
};

export type TelemetryMessage = GridInitMessage | ScanResultMessage | ScanCompleteMessage;

export type AlertItem = {
  event_id: string;
  region_id: string;
  cell_id: string;
  change_score: number;
  confidence: number;
  priority: "low" | "medium" | "high" | "critical";
  reason_codes: string[];
  payload_bytes: number;
  observation_source?: string;
  before_window?: ScanWindow;
  after_window?: ScanWindow;
  timestamp?: string;
  downlinked?: boolean;
  demo_forced_anomaly?: boolean;
  boundary_context?: BoundaryContext[];
};

export type ApiHealth = {
  status: string;
  region_id: string;
  display_name: string;
  bbox: [number, number, number, number];
  grid_resolution: number;
  ring_size: number;
  anomaly_threshold: number;
  observation_mode: string;
  before_label: string;
  after_label: string;
  total_alerts: number;
  total_payload_bytes: number;
  demo_mode_enabled: boolean;
};

export type MetricsFlaggedExample = {
  event_id: string;
  cell_id: string;
  cycle_index: number;
  change_score: number;
  confidence: number;
  priority: "low" | "medium" | "high" | "critical";
  reason_codes: string[];
  payload_bytes: number;
  timestamp: string;
  demo_forced_anomaly?: boolean;
  boundary_context?: BoundaryContext[];
};

export type ApiMetricsSummary = {
  region_id: string;
  demo_mode_enabled: boolean;
  demo_mode_loop_scan: boolean;
  total_cycles_completed: number;
  total_cells_scanned: number;
  total_alerts_emitted: number;
  total_payload_bytes: number;
  total_bandwidth_saved_mb: number;
  latest_discard_ratio: number;
  latest_cycle_index: number;
  latest_cycle_started_at: string;
  latest_cycle_completed_at: string;
  pct_scenes_rejected: number;
  pct_low_valid_coverage: number;
  average_inference_latency_ms: number;
  peak_memory_mb: number;
  runtime_failures_by_stage: Record<string, number>;
  runtime_rejections_by_reason: Record<string, number>;
  flagged_examples: MetricsFlaggedExample[];
};

export type RecentAlertsResponse = {
  region_id: string;
  alerts: AlertItem[];
};

export type AlertAnalysis = {
  model: string;
  severity: "low" | "moderate" | "high" | "critical";
  summary: string;
  findings: string[];
  confidence_note: string;
  source_note: string;
};

export type AnalysisModelInfo = {
  available: boolean;
  description: string;
  requires: string;
};

export type AnalysisStatus = {
  default_model: string;
  optional_model: string | null;
  satellite_inference_loaded: boolean;
  models: Record<string, AnalysisModelInfo>;
  note: string;
};

export type OrbitalScanEventDetail = ScanResultMessage;

export type CellImageryResponse = {
  cell_id: string;
  centroid_lat: number;
  centroid_lng: number;
  cell_bbox: [number, number, number, number];
  imagery_source: "esri_arcgis" | "simsat_sentinel" | "simsat_mapbox" | string;
  before_label: string;
  after_label: string;
  context_image: string | null;
  before_image: string | null;
  after_image: string | null;
};
