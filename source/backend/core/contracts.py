from typing import Literal, NotRequired, TypedDict


class RegionInfo(TypedDict):
    region_id: str
    display_name: str
    grid_resolution: int
    ring_size: int
    bbox: list[float]
    center_lat: float
    center_lng: float
    map_zoom: float


class WindowObservation(TypedDict):
    """
    WIRE FORMAT — the flat observation window that appears in AlertRecord,
    ScanResultMessage, and all API responses.

    This is what the frontend receives and what tests should assert against.
    Field names are intentionally flat (no nested dict) for JSON ergonomics.
    """
    label: str
    quality: float
    nir: float
    red: float
    swir: float
    ndvi: float
    nbr: float
    evi2: float
    ndmi: float
    soil_ratio: float
    flags: list[str]


class ObservationWindow(TypedDict):
    """
    INTERNAL FORMAT — the intermediate window produced by loader.py and
    consumed by scorer.py.

    Band values live in a nested dict keyed by band name (e.g. 'nir', 'red').
    scorer.py converts this into WindowObservation (flat) before emitting alerts.
    Do not expose ObservationWindow directly in API responses.
    """
    label: str
    quality: float
    bands: dict[str, float]
    flags: list[str]


class ObservationPair(TypedDict):
    source: str
    cell_id: str
    centroid_lat: float
    centroid_lng: float
    before: ObservationWindow
    after: ObservationWindow


class ScanHeartbeat(TypedDict):
    last_cell: str
    cells_scanned: int
    alerts_emitted: int
    discard_ratio: float
    total_cells: int
    cycle_index: int


class BoundaryContext(TypedDict):
    layer_type: str
    source_name: str
    feature_name: str | None
    overlap_area_m2: float
    overlap_ratio: float
    distance_to_boundary_m: float


class AlertRecord(TypedDict):
    event_id: str
    region_id: str
    cell_id: str
    change_score: float
    confidence: float
    priority: Literal["low", "medium", "high", "critical"]
    reason_codes: list[str]
    payload_bytes: int
    timestamp: NotRequired[str]
    downlinked: NotRequired[bool]
    observation_source: NotRequired[str]
    runtime_truth_mode: NotRequired[str]
    before_window: NotRequired[WindowObservation]
    after_window: NotRequired[WindowObservation]
    demo_forced_anomaly: NotRequired[bool]
    boundary_context: NotRequired[list[BoundaryContext]]


class MetricsFlaggedExample(TypedDict):
    event_id: str
    cell_id: str
    cycle_index: int
    change_score: float
    confidence: float
    priority: Literal["low", "medium", "high", "critical"]
    reason_codes: list[str]
    payload_bytes: int
    timestamp: str
    demo_forced_anomaly: bool
    runtime_truth_mode: NotRequired[str]
    boundary_context: NotRequired[list[BoundaryContext]]


class MetricsSummary(TypedDict):
    region_id: str
    demo_mode_enabled: bool
    demo_mode_loop_scan: bool
    total_cycles_completed: int
    total_cells_scanned: int
    total_alerts_emitted: int
    total_payload_bytes: int
    total_bandwidth_saved_mb: float
    latest_discard_ratio: float
    latest_cycle_index: int
    latest_cycle_started_at: str
    latest_cycle_completed_at: str
    pct_scenes_rejected: float
    pct_low_valid_coverage: float
    average_inference_latency_ms: float
    peak_memory_mb: float
    runtime_failures_by_stage: dict[str, int]
    runtime_rejections_by_reason: dict[str, int]
    flagged_examples: list[MetricsFlaggedExample]


class GridInitMessage(TypedDict):
    type: Literal["grid_init"]
    data: dict
    region: RegionInfo


class ScanResultMessage(TypedDict):
    type: Literal["scan_result"]
    event_id: str
    region_id: str
    cell_id: str
    is_anomaly: bool
    change_score: float
    confidence: float
    priority: Literal["low", "medium", "high", "critical"]
    reason_codes: list[str]
    payload_bytes: int
    estimated_bandwidth_saved_mb: float
    observation_source: str
    runtime_truth_mode: str
    before_window: WindowObservation
    after_window: WindowObservation
    heartbeat: ScanHeartbeat
    cycle_index: int
    demo_forced_anomaly: bool
    boundary_context: NotRequired[list[BoundaryContext]]


class HealthResponse(TypedDict):
    status: str
    region_id: str
    display_name: str
    bbox: list[float]
    grid_resolution: int
    ring_size: int
    anomaly_threshold: float
    observation_mode: str
    before_label: str
    after_label: str
    total_alerts: int
    total_payload_bytes: int
    demo_mode_enabled: bool
    runtime_truth_mode: str


class RecentAlertsResponse(TypedDict):
    region_id: str
    alerts: list[AlertRecord]


class AlertAnalysisRequest(TypedDict):
    change_score: float
    confidence: float
    reason_codes: list[str]
    before_window: dict
    after_window: dict
    observation_source: str
    demo_forced_anomaly: NotRequired[bool]


class AlertAnalysisResponse(TypedDict):
    model: str
    severity: str
    summary: str
    findings: list[str]
    confidence_note: str
    source_note: str


class AnalysisModelInfo(TypedDict):
    available: bool
    description: str
    requires: str


class AnalysisStatusResponse(TypedDict):
    default_model: str
    optional_model: str | None
    models: dict[str, AnalysisModelInfo]
    note: str
