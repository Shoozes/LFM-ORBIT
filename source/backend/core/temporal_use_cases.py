"""Temporal remote-sensing use-case catalog and autoprep helpers."""

from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any


GENERIC_USE_CASE_ID = "temporal_change_generic"


_TEMPORAL_USE_CASES: list[dict[str, Any]] = [
    {
        "id": "deforestation",
        "display_name": "Deforestation and canopy degradation",
        "target_task": "deforestation_detection",
        "target_category": "deforestation",
        "default_target_action": "alert",
        "temporal_methods": [
            "seasonal baseline comparison",
            "before-after vegetation index delta",
            "multi-index consensus across NDVI, EVI2, NBR, NDMI, and soil exposure",
            "ground timelapse validation",
        ],
        "signals": [
            "ndvi_drop",
            "evi2_drop",
            "nbr_drop",
            "ndmi_drop",
            "soil_exposure_spike",
            "suspected_canopy_loss",
            "multi_index_consensus",
        ],
        "keywords": [
            "deforestation",
            "forest",
            "canopy",
            "logging",
            "clear cut",
            "clearcut",
            "vegetation loss",
            "tree cover",
            "forest degradation",
            "bare soil",
        ],
        "examples": [
            {
                "name": "Amazon frontier clearing",
                "task_text": "Scan an Amazon frontier bbox for new canopy loss against the same-season baseline.",
                "bbox": [-62.1, -9.8, -61.4, -9.1],
                "start_date": "2024-06",
                "end_date": "2025-06",
                "expected_signal": "NDVI, EVI2, NBR, and NDMI drop while SWIR/NIR soil exposure rises.",
                "training_label": {"target_action": "alert", "target_category": "deforestation"},
            },
            {
                "name": "Seasonal drought control",
                "task_text": "Reject a broad regional vegetation dip when neighboring cells show the same phenology shift.",
                "bbox": [-61.8, -4.2, -60.9, -3.4],
                "start_date": "2023-08",
                "end_date": "2025-08",
                "expected_signal": "Regional phenology shift lowers confidence instead of escalating a single-cell alert.",
                "training_label": {"target_action": "prune", "target_category": "none"},
            },
        ],
    },
    {
        "id": "wildfire",
        "display_name": "Wildfire burn, active-fire, and recovery monitoring",
        "target_task": "wildfire_temporal_detection",
        "target_category": "wildfire",
        "default_target_action": "alert",
        "temporal_methods": [
            "pre-fire to post-fire burn severity comparison",
            "NBR and NDMI change detection",
            "thermal or hotspot cue fusion when available",
            "post-event recovery trend tracking",
        ],
        "signals": [
            "nbr_drop",
            "ndmi_drop",
            "burn_scar",
            "thermal_anomaly",
            "hotspot",
            "smoke_plume",
            "fire_recovery",
        ],
        "keywords": [
            "wildfire",
            "fire",
            "burn",
            "burn scar",
            "char",
            "smoke",
            "hotspot",
            "thermal",
            "active fire",
            "fireline",
            "burn severity",
        ],
        "examples": [
            {
                "name": "Post-fire burn scar",
                "task_text": "Detect a new wildfire burn scar by comparing pre-fire and post-fire Sentinel windows.",
                "bbox": [-121.8, 38.4, -121.0, 39.0],
                "start_date": "2024-07",
                "end_date": "2024-10",
                "expected_signal": "NBR and NDMI drop sharply with darkened spatial context and reduced vegetation response.",
                "training_label": {"target_action": "alert", "target_category": "wildfire"},
            },
            {
                "name": "Regrowth after burn",
                "task_text": "Track vegetation recovery over repeated post-fire timelapse frames.",
                "bbox": [-120.9, 37.1, -120.2, 37.8],
                "start_date": "2023-09",
                "end_date": "2026-03",
                "expected_signal": "Burn severity stabilizes and NDVI recovery increases frame-over-frame.",
                "training_label": {"target_action": "review", "target_category": "wildfire"},
            },
        ],
    },
    {
        "id": "maritime_activity",
        "display_name": "Maritime vessel, port, wake, and slick monitoring",
        "target_task": "maritime_temporal_monitoring",
        "target_category": "maritime",
        "default_target_action": "review",
        "temporal_methods": [
            "multi-date vessel and wake persistence checks",
            "port activity change detection",
            "coastal and offshore anomaly tracking",
            "cardinal-direction investigation around a detected maritime anomaly",
            "Element84 Sentinel-2 STAC date deduplication for consistent temporal scenes",
            "SAR or optical cue fusion when available",
        ],
        "signals": [
            "vessel_presence",
            "ship_wake",
            "ais_mismatch",
            "port_activity_change",
            "oil_slick",
            "channel_blockage",
            "traffic_congestion",
            "grounded_vessel",
            "maritime_anomaly",
        ],
        "keywords": [
            "maritime",
            "ship",
            "vessel",
            "boat",
            "wake",
            "port",
            "harbor",
            "oil slick",
            "slick",
            "ais",
            "canal",
            "anchorage",
            "blockage",
            "congestion",
            "queue",
            "queueing",
            "grounding",
            "grounded",
            "illegal fishing",
            "shipping lane",
            "offshore",
        ],
        "examples": [
            {
                "name": "AIS-dark vessel candidate",
                "task_text": "Scan a shipping lane for repeated vessel-sized bright targets without matching AIS context.",
                "bbox": [103.4, 1.0, 104.2, 1.7],
                "start_date": "2025-01",
                "end_date": "2025-03",
                "expected_signal": "A moving point target and wake appear across frames while static coastal context remains stable.",
                "training_label": {"target_action": "review", "target_category": "maritime"},
            },
            {
                "name": "Oil slick spread",
                "task_text": "Track a suspected oil slick shape as it expands and drifts between maritime frames.",
                "bbox": [-91.8, 28.3, -90.8, 29.1],
                "start_date": "2024-04",
                "end_date": "2024-05",
                "expected_signal": "Low-texture slick geometry changes over water while coastline and clouds are rejected as controls.",
                "training_label": {"target_action": "alert", "target_category": "maritime"},
            },
            {
                "name": "Canal blockage investigation",
                "task_text": "Review vessel queueing around a canal choke point and explore N/E/S/W context for a likely blockage cause.",
                "bbox": [32.25, 29.72, 32.75, 30.12],
                "start_date": "2025-03",
                "end_date": "2025-04",
                "expected_signal": "Vessel clusters or queues persist across distinct dates near a narrow maritime corridor.",
                "training_label": {"target_action": "review", "target_category": "maritime"},
            },
        ],
    },
    {
        "id": "civilian_lifeline_disruption",
        "display_name": "Civilian lifeline before/after disruption monitoring",
        "target_task": "civilian_lifeline_temporal_monitoring",
        "target_category": "civilian_lifeline",
        "default_target_action": "review",
        "temporal_methods": [
            "baseline-to-current frame comparison",
            "strict candidate schema validation before downlink escalation",
            "localized bbox review for obstruction, facility disruption, or surface change",
            "civilian-impact triage across mobility, logistics, aid, trade, and water service",
        ],
        "signals": [
            "probable_large_scale_disruption",
            "probable_surface_change",
            "probable_access_obstruction",
            "shipping_or_aid_disruption",
            "logistics_delay",
            "trade_disruption",
            "civilian_facility_disruption",
            "public_mobility_disruption",
            "water_service_disruption",
        ],
        "keywords": [
            "lifeline",
            "civilian infrastructure",
            "before after",
            "before/after",
            "baseline frame",
            "current frame",
            "bridge",
            "road access",
            "access obstruction",
            "facility disruption",
            "public mobility",
            "water service",
            "aid route",
            "logistics delay",
            "trade disruption",
            "downlink now",
        ],
        "examples": [
            {
                "name": "Bridge access obstruction",
                "task_text": "Compare baseline and current frames for a bridge approach obstruction affecting public mobility.",
                "bbox": [-118.32, 33.99, -118.16, 34.11],
                "start_date": "2025-01",
                "end_date": "2025-02",
                "expected_signal": "A localized obstruction appears in the current frame while the baseline route is clear.",
                "training_label": {
                    "target_action": "review",
                    "target_category": "civilian_lifeline",
                },
            },
            {
                "name": "Water service facility control",
                "task_text": "Reject a no-event candidate when before and after frames show no material facility or access change.",
                "bbox": [-105.08, 39.69, -104.90, 39.79],
                "start_date": "2025-04",
                "end_date": "2025-05",
                "expected_signal": "Facility footprint and access routes remain stable, so the candidate action is discard.",
                "training_label": {
                    "target_action": "prune",
                    "target_category": "none",
                },
            },
        ],
    },
    {
        "id": "ice_cap_growth",
        "display_name": "Ice cap, glacier, and sea-ice growth or retreat",
        "target_task": "ice_cap_temporal_monitoring",
        "target_category": "ice_cap_growth",
        "default_target_action": "review",
        "temporal_methods": [
            "seasonally aligned snow and ice extent comparison",
            "albedo and visible-brightness trend analysis",
            "terminus or ice-edge displacement tracking",
            "multi-year growth versus retreat labeling",
        ],
        "signals": [
            "ice_extent_growth",
            "ice_extent_retreat",
            "snowline_shift",
            "albedo_change",
            "glacier_terminus_shift",
            "sea_ice_edge_change",
        ],
        "keywords": [
            "ice cap",
            "icecap",
            "glacier",
            "ice sheet",
            "sea ice",
            "snowline",
            "snow line",
            "albedo",
            "calving",
            "ice growth",
            "ice retreat",
            "terminus",
        ],
        "examples": [
            {
                "name": "Ice cap growth season control",
                "task_text": "Compare same-season frames to identify true ice cap growth rather than winter snow cover.",
                "bbox": [-47.0, 65.4, -45.7, 66.2],
                "start_date": "2022-08",
                "end_date": "2025-08",
                "expected_signal": "High-albedo ice extent expands in comparable late-summer windows across multiple years.",
                "training_label": {"target_action": "review", "target_category": "ice_cap_growth"},
            },
            {
                "name": "Glacier terminus retreat negative",
                "task_text": "Reject an ice-growth label when the terminus edge recedes over the temporal sequence.",
                "bbox": [-50.6, 69.0, -49.5, 69.8],
                "start_date": "2021-07",
                "end_date": "2025-07",
                "expected_signal": "Ice edge retreats and exposed rock/water increases, producing an ice-loss label instead.",
                "training_label": {"target_action": "review", "target_category": "ice_retreat"},
            },
        ],
    },
    {
        "id": "flood_extent",
        "display_name": "Flood extent and water persistence",
        "target_task": "flood_temporal_detection",
        "target_category": "flood",
        "default_target_action": "alert",
        "temporal_methods": [
            "pre-event to post-event water extent comparison",
            "temporary water persistence tracking",
            "cloud and shadow rejection",
        ],
        "signals": [
            "water_extent_growth",
            "surface_water_persistence",
            "river_overbank",
            "floodplain_expansion",
        ],
        "keywords": [
            "flood",
            "inundation",
            "water extent",
            "river overbank",
            "floodplain",
            "standing water",
            "surface water",
        ],
        "examples": [
            {
                "name": "River overbank flood",
                "task_text": "Find new surface water outside the normal channel after a storm sequence.",
                "bbox": [90.1, 23.2, 91.0, 24.0],
                "start_date": "2025-05",
                "end_date": "2025-08",
                "expected_signal": "Water-like pixels expand into floodplain cells and persist across multiple frames.",
                "training_label": {"target_action": "alert", "target_category": "flood"},
            }
        ],
    },
    {
        "id": "crop_phenology",
        "display_name": "Crop phenology, harvest, and irrigation change",
        "target_task": "crop_temporal_monitoring",
        "target_category": "agriculture",
        "default_target_action": "review",
        "temporal_methods": [
            "seasonal vegetation curve comparison",
            "planting and harvest phase detection",
            "irrigation-driven moisture trend checks",
        ],
        "signals": [
            "phenology_shift",
            "harvest_signal",
            "irrigation_change",
            "crop_stress",
        ],
        "keywords": [
            "crop",
            "agriculture",
            "harvest",
            "irrigation",
            "farm",
            "phenology",
            "planting",
            "crop stress",
        ],
        "examples": [
            {
                "name": "Harvest cycle",
                "task_text": "Separate normal harvest from structural land-cover loss using same-field seasonal history.",
                "bbox": [-96.8, 39.0, -96.0, 39.8],
                "start_date": "2024-04",
                "end_date": "2025-11",
                "expected_signal": "Vegetation declines after harvest but recovers on the next crop cycle.",
                "training_label": {"target_action": "prune", "target_category": "none"},
            }
        ],
    },
    {
        "id": "urban_expansion",
        "display_name": "Urban expansion and construction progression",
        "target_task": "urban_expansion_temporal_detection",
        "target_category": "urban_expansion",
        "default_target_action": "review",
        "temporal_methods": [
            "built-surface expansion comparison",
            "bare-ground to structure transition tracking",
            "road-grid and construction footprint persistence checks",
        ],
        "signals": [
            "built_surface_growth",
            "construction_progression",
            "road_expansion",
            "bare_ground_persistence",
        ],
        "keywords": [
            "urban",
            "construction",
            "building",
            "road",
            "subdivision",
            "built surface",
            "settlement",
        ],
        "examples": [
            {
                "name": "Construction footprint",
                "task_text": "Track a bare-ground construction footprint becoming persistent built surface.",
                "bbox": [77.3, 28.3, 77.9, 28.9],
                "start_date": "2023-01",
                "end_date": "2026-01",
                "expected_signal": "Temporary bare soil transitions into stable high-reflectance structures and roads.",
                "training_label": {"target_action": "review", "target_category": "urban_expansion"},
            }
        ],
    },
    {
        "id": "mining_expansion",
        "display_name": "Mining expansion and tailings disturbance",
        "target_task": "mining_temporal_detection",
        "target_category": "mining",
        "default_target_action": "alert",
        "temporal_methods": [
            "bare-earth expansion comparison",
            "tailings pond shape tracking",
            "vegetation-to-exposed-ground transition detection",
        ],
        "signals": [
            "bare_ground_expansion",
            "tailings_change",
            "excavation_growth",
            "soil_exposure_spike",
        ],
        "keywords": [
            "mine",
            "mining",
            "tailings",
            "pit",
            "excavation",
            "quarry",
            "bare ground expansion",
        ],
        "examples": [
            {
                "name": "Open-pit expansion",
                "task_text": "Detect an expanding open-pit mine and separate it from seasonal vegetation loss.",
                "bbox": [-70.6, -23.8, -69.8, -23.1],
                "start_date": "2023-01",
                "end_date": "2026-01",
                "expected_signal": "Persistent bare-earth footprint expands across consecutive same-season frames.",
                "training_label": {"target_action": "alert", "target_category": "mining"},
            }
        ],
    },
    {
        "id": GENERIC_USE_CASE_ID,
        "display_name": "Generic temporal change review",
        "target_task": "temporal_change_review",
        "target_category": "temporal_change",
        "default_target_action": "review",
        "temporal_methods": [
            "multi-frame contextual comparison",
            "same-season before-after review",
            "static-image color-shift rejection",
        ],
        "signals": [
            "temporal_change",
            "contextual_frame_sequence",
            "needs_operator_review",
        ],
        "keywords": [
            "temporal",
            "timelapse",
            "change over time",
            "before after",
            "multi date",
            "sequence",
        ],
        "examples": [
            {
                "name": "Unknown change candidate",
                "task_text": "Review a multi-frame satellite sequence for real contextual change before labeling.",
                "bbox": [-60.5, -3.5, -60.0, -3.0],
                "start_date": "2024-01",
                "end_date": "2025-01",
                "expected_signal": "At least two distinct contextual imagery slices are needed before any temporal label is trusted.",
                "training_label": {"target_action": "review", "target_category": "temporal_change"},
            }
        ],
    },
]


_USE_CASE_BY_ID = {item["id"]: item for item in _TEMPORAL_USE_CASES}


def list_temporal_use_cases() -> list[dict[str, Any]]:
    """Return all supported temporal use cases with examples."""
    return deepcopy(_TEMPORAL_USE_CASES)


def get_temporal_use_case(use_case_id: str | None) -> dict[str, Any]:
    """Return a use-case definition, falling back to the generic temporal case."""
    return deepcopy(_USE_CASE_BY_ID.get(str(use_case_id or ""), _USE_CASE_BY_ID[GENERIC_USE_CASE_ID]))


def _normalize_text(value: str) -> str:
    normalized = value.lower().replace("_", " ").replace("-", " ")
    normalized = re.sub(r"[^a-z0-9.+/ ]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _contains_term(normalized_text: str, term: str) -> bool:
    if not term:
        return False
    if any(separator in term for separator in (" ", "/", "+", ".")):
        return term in normalized_text
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalized_text) is not None


def _collect_text(value: Any, *, depth: int = 0) -> list[str]:
    if depth > 4 or value is None:
        return []
    if isinstance(value, str):
        if value.startswith("data:") or len(value) > 5000:
            return []
        return [value]
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, dict):
        texts: list[str] = []
        for key, child in value.items():
            if str(key).lower() in {"assets", "context_thumb", "timelapse_b64", "video_b64"}:
                continue
            texts.append(str(key))
            texts.extend(_collect_text(child, depth=depth + 1))
        return texts
    if isinstance(value, (list, tuple, set)):
        texts = []
        for child in value:
            texts.extend(_collect_text(child, depth=depth + 1))
        return texts
    return []


def _record_reason_codes(record: dict[str, Any]) -> set[str]:
    raw_codes = record.get("reason_codes")
    if not isinstance(raw_codes, list):
        return set()
    return {_normalize_text(str(code)) for code in raw_codes}


def classify_temporal_use_case(
    record: dict[str, Any],
    requested_use_case_id: str | None = None,
) -> dict[str, Any]:
    """Choose the most likely temporal use case for a record or mission payload."""
    if requested_use_case_id and requested_use_case_id in _USE_CASE_BY_ID:
        use_case = _USE_CASE_BY_ID[requested_use_case_id]
        return _decision_payload(use_case, confidence=1.0, matched_terms=["explicit_use_case_id"])

    text_blob = " ".join(_collect_text(record))
    normalized_text = _normalize_text(text_blob)
    reason_codes = _record_reason_codes(record)

    best_use_case = _USE_CASE_BY_ID[GENERIC_USE_CASE_ID]
    best_score = 0
    best_terms: list[str] = []

    for use_case in _TEMPORAL_USE_CASES:
        if use_case["id"] == GENERIC_USE_CASE_ID:
            continue

        score = 0
        matched_terms: list[str] = []
        candidates = [
            *use_case.get("keywords", []),
            *use_case.get("signals", []),
            use_case.get("target_task", ""),
            use_case.get("target_category", ""),
            use_case.get("id", ""),
        ]

        for candidate in candidates:
            term = _normalize_text(str(candidate))
            if not term:
                continue
            if _contains_term(normalized_text, term):
                matched_terms.append(term)
                score += 2

        for signal in use_case.get("signals", []):
            term = _normalize_text(str(signal))
            if term in reason_codes:
                matched_terms.append(term)
                score += 8

        target_category = _normalize_text(str(record.get("target_category", "")))
        if target_category and target_category == _normalize_text(str(use_case.get("target_category", ""))):
            matched_terms.append(f"target_category:{target_category}")
            score += 3

        if score > best_score:
            best_use_case = use_case
            best_score = score
            best_terms = sorted(set(matched_terms))

    if best_score <= 0:
        return _decision_payload(_USE_CASE_BY_ID[GENERIC_USE_CASE_ID], confidence=0.35, matched_terms=[])

    confidence = min(0.99, 0.45 + (best_score / (best_score + 8.0)) * 0.5)
    return _decision_payload(best_use_case, confidence=confidence, matched_terms=best_terms)


def _decision_payload(use_case: dict[str, Any], *, confidence: float, matched_terms: list[str]) -> dict[str, Any]:
    return {
        "id": use_case["id"],
        "display_name": use_case["display_name"],
        "target_task": use_case["target_task"],
        "target_category": use_case["target_category"],
        "default_target_action": use_case["default_target_action"],
        "confidence": round(confidence, 3),
        "matched_terms": matched_terms[:12],
        "temporal_methods": list(use_case["temporal_methods"]),
        "signals": list(use_case["signals"]),
        "examples": deepcopy(use_case["examples"]),
    }


def build_api_prep_plan(record: dict[str, Any], use_case_decision: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic prep plan for API-derived temporal evidence."""
    source = str(
        record.get("observation_source")
        or record.get("source")
        or record.get("confirmation_source")
        or "unknown"
    )
    source_lower = source.lower()
    if "sentinel" in source_lower:
        provider_family = "sentinel"
    elif "nasa" in source_lower or "gibs" in source_lower or "modis" in source_lower:
        provider_family = "nasa"
    elif "simsat" in source_lower:
        provider_family = "simsat"
    elif "gee" in source_lower or "earth engine" in source_lower:
        provider_family = "gee"
    elif "seeded" in source_lower:
        provider_family = "seeded_cache"
    else:
        provider_family = "unknown"

    has_windows = isinstance(record.get("before_window"), dict) and isinstance(record.get("after_window"), dict)
    assets = record.get("assets") if isinstance(record.get("assets"), dict) else {}
    has_context = bool(assets.get("context_thumb"))
    has_timelapse = bool(assets.get("timelapse") or record.get("timelapse_analysis"))

    return {
        "auto_decide": True,
        "auto_build": True,
        "provider_family": provider_family,
        "source": source,
        "use_case_id": use_case_decision["id"],
        "required_inputs": [
            "bbox_or_cell_id",
            "start_date",
            "end_date",
            "at_least_two_contextual_frames",
        ],
        "available_inputs": {
            "before_after_windows": has_windows,
            "context_thumbnail": has_context,
            "timelapse": has_timelapse,
            "lat_lng": record.get("lat") is not None and record.get("lng") is not None,
        },
        "recommended_assets": [
            "context_thumb.png",
            "timelapse.webm",
            "sample.json",
            "training.jsonl row",
        ],
        "quality_gates": [
            "reject invalid bbox/date windows before provider calls",
            "require two or more contextual imagery slices for temporal supervision",
            "flag static single-image color-shift videos as invalid timelapse evidence",
            "keep weak negatives separate from operator-reviewed gold controls",
        ],
    }


def enrich_temporal_record(record: dict[str, Any]) -> dict[str, Any]:
    """Attach use-case and API prep metadata to a dataset record."""
    enriched = dict(record)
    decision = classify_temporal_use_case(enriched)

    enriched["temporal_use_case"] = decision
    enriched["target_task"] = decision["target_task"]

    if enriched.get("target_action") != "prune":
        enriched["target_category"] = decision["target_category"]

    enriched["api_prep"] = build_api_prep_plan(enriched, decision)
    return enriched


def build_training_jsonl_row(record: dict[str, Any]) -> dict[str, Any]:
    """Build a chat-style JSONL row from an enriched Orbit dataset record."""
    decision = record.get("temporal_use_case")
    if not isinstance(decision, dict):
        decision = classify_temporal_use_case(record)

    context = {
        "sample_id": record.get("sample_id", ""),
        "record_type": record.get("record_type", ""),
        "review_state": record.get("review_state", ""),
        "label_tier": record.get("label_tier", ""),
        "cell_id": record.get("cell_id", ""),
        "bbox": record.get("bbox"),
        "lat": record.get("lat"),
        "lng": record.get("lng"),
        "timestamp": record.get("timestamp", ""),
        "change_score": record.get("change_score", 0.0),
        "confidence": record.get("confidence", 0.0),
        "priority": record.get("priority", ""),
        "reason_codes": record.get("reason_codes", []),
        "observation_source": record.get("observation_source", ""),
        "before_window": record.get("before_window"),
        "after_window": record.get("after_window"),
        "timelapse_analysis": record.get("timelapse_analysis"),
        "rejection_reason": record.get("rejection_reason"),
        "assets": record.get("assets", {}),
        "api_prep": record.get("api_prep", {}),
    }
    expected = {
        "use_case_id": decision["id"],
        "target_task": record.get("target_task") or decision["target_task"],
        "target_action": record.get("target_action") or decision["default_target_action"],
        "target_category": record.get("target_category") or decision["target_category"],
        "temporal_methods": decision.get("temporal_methods", []),
        "signals": decision.get("signals", []),
        "confidence": record.get("confidence", 0.0),
        "review_state": record.get("review_state", ""),
        "label_tier": record.get("label_tier", ""),
    }

    return {
        "sample_id": record.get("sample_id", ""),
        "split": record.get("split", "train"),
        "format": "orbit_temporal_sft_v1",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are LFM Orbit's temporal remote-sensing data prep agent. "
                    "Classify the temporal use case, decide whether to alert, prune, or review, "
                    "and return compact JSON suitable for dataset refinement."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(context, sort_keys=True, separators=(",", ":")),
            },
            {
                "role": "assistant",
                "content": json.dumps(expected, sort_keys=True, separators=(",", ":")),
            },
        ],
        "metadata": {
            "use_case_id": decision["id"],
            "target_task": expected["target_task"],
            "target_category": expected["target_category"],
            "target_action": expected["target_action"],
            "label_tier": expected["label_tier"],
        },
    }
