from typing import Literal, TypedDict

try:
    from typing import NotRequired
except ImportError:  # Python 3.10 compatibility
    from typing_extensions import NotRequired


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
    blue: NotRequired[float]
    green: NotRequired[float]
    nir: float
    red: float
    swir: float
    swir1: NotRequired[float]
    swir2: NotRequired[float]
    scl_cloud_ratio: NotRequired[float]
    cloud_probability: NotRequired[float]
    valid_pixel_ratio: NotRequired[float]
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
    acquisition_key: NotRequired[str]
    acquisition_id: NotRequired[str]
    source_asset_id: NotRequired[str]
    before_frame_hash: NotRequired[str]
    after_frame_hash: NotRequired[str]


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


class ObjectTarget(TypedDict):
    label: str
    prompt: str
    class_key: str
    enabled: bool


class TargetPack(TypedDict):
    id: str
    name: str
    description: str
    targets: list[ObjectTarget]


class DetectionBox(TypedDict):
    id: str
    label: str
    bbox: list[float]
    bbox_format: Literal["unit_xyxy"]
    confidence: float
    color_key: str
    source_model: str
    prompt: str
    runtime_truth_mode: str
    imagery_origin: str
    scoring_basis: str
    frame_ref: NotRequired[str]
    timestamp: NotRequired[str]
    count_quality: NotRequired[str]


class DetectionSummary(TypedDict):
    target_pack_id: str | None
    total_boxes: int
    counts_by_label: dict[str, int]
    top_boxes: list[DetectionBox]
    provenance: dict[str, str | bool]


class ObjectDelta(TypedDict):
    label: str
    baseline_count: int
    current_count: int
    delta_count: int
    delta_percent: float
    action_hint: Literal["discard", "defer", "downlink_now"]


class ObjectEvidencePayload(TypedDict):
    target_pack_id: str | None
    object_targets: list[ObjectTarget]
    detection_summary: DetectionSummary
    object_deltas: NotRequired[list[ObjectDelta]]


class VisualModelReview(TypedDict):
    enabled: bool
    image_conditioned: bool
    runtime_backend: str
    runtime_inference_mode: str
    response: str
    reason: str
    visual_model: NotRequired[str]
    image_source: NotRequired[str]
    frame_id: NotRequired[str]
    bbox: NotRequired[list[float]]
    reviewed_at: NotRequired[str]


class WildfireSmokeAssessment(TypedDict):
    smoke_likelihood: float
    cloud_likelihood: float
    burn_likelihood: float
    hotspot_support: float
    confidence_delta: float
    final_confidence: float
    target_action: Literal["prune", "defer", "review", "downlink_now"]
    reason_codes: list[str]
    provenance: dict[str, str | float | bool]


class AlertRecord(TypedDict):
    event_id: str
    region_id: str
    cell_id: str
    mission_id: NotRequired[int | None]
    use_case_id: NotRequired[str | None]
    target_pack_id: NotRequired[str | None]
    change_score: float
    confidence: float
    priority: Literal["low", "medium", "high", "critical"]
    reason_codes: list[str]
    payload_bytes: int
    timestamp: NotRequired[str]
    downlinked: NotRequired[bool]
    observation_source: NotRequired[str]
    runtime_truth_mode: NotRequired[str]
    imagery_origin: NotRequired[str]
    scoring_basis: NotRequired[str]
    before_window: NotRequired[WindowObservation]
    after_window: NotRequired[WindowObservation]
    demo_forced_anomaly: NotRequired[bool]
    boundary_context: NotRequired[list[BoundaryContext]]
    detection_summary: NotRequired[DetectionSummary]
    object_deltas: NotRequired[list[ObjectDelta]]
    visual_model_review: NotRequired[VisualModelReview]
    wildfire_assessment: NotRequired[WildfireSmokeAssessment]


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
    imagery_origin: NotRequired[str]
    scoring_basis: NotRequired[str]
    boundary_context: NotRequired[list[BoundaryContext]]


class MetricsSummary(TypedDict):
    region_id: str
    demo_mode_enabled: bool
    demo_mode_loop_scan: bool
    runtime_truth_mode: str
    imagery_origin: str
    scoring_basis: str
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
    imagery_origin: str
    scoring_basis: str
    before_window: WindowObservation
    after_window: WindowObservation
    heartbeat: ScanHeartbeat
    cycle_index: int
    demo_forced_anomaly: bool
    boundary_context: NotRequired[list[BoundaryContext]]
    detection_summary: NotRequired[DetectionSummary]
    object_deltas: NotRequired[list[ObjectDelta]]
    wildfire_assessment: NotRequired[WildfireSmokeAssessment]


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
    imagery_origin: str
    scoring_basis: str
    confirmation_policy: str
    confirmation_required_acquisitions: int
    resource_limits: dict[str, dict[str, int | float]]


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
    model_runtime: NotRequired[str]
    deterministic_model: NotRequired[str]


class AnalysisModelInfo(TypedDict):
    available: bool
    description: str
    requires: str


class AnalysisStatusResponse(TypedDict):
    default_model: str
    optional_model: str | None
    models: dict[str, AnalysisModelInfo]
    note: str
