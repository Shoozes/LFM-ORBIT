"""Ground Station knowledge base and local action controller."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any

from core.ground_agent_semantics import match_ground_agent_semantics
from core.location_resolver import resolve_location_candidates


MISSION_PACKS: dict[str, dict[str, Any]] = {
    "deforestation_amazon": {
        "label": "Amazon frontier deforestation",
        "aliases": ["amazon", "deforestation", "forest", "rondonia", "canopy"],
        "use_case_id": "deforestation",
        "target_pack_id": "deforestation",
        "task_text": "Run a Deforestation / Land-Use Change Watch over the Rondonia western frontier. Compare same-season replay frames for persistent canopy loss, clearing candidate regions, road expansion corridors, exposed soil, and canopy-loss boundaries without claiming legal status or exact land-use attribution from imagery alone.",
        "bbox": [-63.15, -10.15, -62.85, -9.85],
        "start_date": "2023-01-15",
        "end_date": "2025-01-15",
    },
    "maritime_suez": {
        "label": "Suez maritime queue",
        "aliases": ["maritime", "suez", "vessel", "ship", "queue", "dark vessel"],
        "use_case_id": "maritime_activity",
        "target_pack_id": "port",
        "task_text": "Review maritime vessel queueing near the Suez channel.",
        "bbox": [32.5, 29.88, 32.58, 29.96],
        "start_date": "2025-03-01",
        "end_date": "2025-12-15",
    },
    "flood_manchar": {
        "label": "Manchar Lake flood",
        "aliases": ["flood", "manchar", "pakistan", "surface water", "overflow"],
        "use_case_id": "flood_extent",
        "task_text": "Find new surface water and overflow around Pakistan's Manchar Lake during the 2022 flood sequence.",
        "bbox": [67.63, 26.31, 67.87, 26.55],
        "start_date": "2022-06-15",
        "end_date": "2022-09-15",
    },
    "mining_atacama": {
        "label": "Critical Minerals Expansion Watch",
        "aliases": [
            "critical minerals",
            "mining",
            "mine",
            "atacama",
            "salar",
            "escondida",
            "open pit",
            "evaporation pond",
            "tailings",
            "bare earth",
        ],
        "use_case_id": "mining_expansion",
        "target_pack_id": "critical_minerals",
        "task_text": "Run Critical Minerals Expansion Watch over the Salar de Atacama / Escondida / Atacama mining corridor. Compare historical and current satellite imagery for evaporation pond regions, tailings regions, open-pit expansion, industrial roads, facility clusters, exposed soil, and surface color change without claiming illegal mining, pollution confirmation, or production output.",
        "bbox": [-69.115, -24.29, -69.035, -24.21],
        "start_date": "2024-01-15",
        "end_date": "2025-12-15",
    },
    "ice_greenland": {
        "label": "Greenland ice and snow extent",
        "aliases": ["ice", "snow", "greenland", "cryosphere", "ndsi"],
        "use_case_id": "ice_snow_extent",
        "task_text": "Review Greenland edge snow and ice extent using NDSI, SCL cloud rejection, and multi-frame persistence before any extent-change label.",
        "bbox": [-51.13, 69.1, -50.97, 69.26],
        "start_date": "2024-01-15",
        "end_date": "2025-12-15",
    },
    "wildfire_highway82": {
        "label": "Highway 82 wildfire",
        "aliases": ["wildfire", "fire", "smoke", "burn scar", "georgia", "highway 82"],
        "use_case_id": "wildfire",
        "target_pack_id": "fireline",
        "task_text": "Review the Highway 82 wildfire near Atkinson and Waynesville, Georgia for smoke, burn scar, and vegetation stress.",
        "bbox": [-81.916, 31.143, -81.756, 31.303],
        "start_date": "2026-04-01",
        "end_date": "2026-04-28",
    },
    "southeast_fireline_watch": {
        "label": "Southeast Fireline Watch",
        "aliases": ["southeast fireline", "fireline watch", "lifeline fire", "vehicle queue", "road obstruction"],
        "use_case_id": "wildfire",
        "target_pack_id": "fireline",
        "task_text": "Run Southeast Fireline Watch. Triage wildfire candidate evidence, drought-like vegetation stress controls, and civilian lifeline exposure. Downlink only compact proof packets for smoke, burn-scar, road-obstruction, or access-risk candidates.",
        "bbox": [-81.916, 31.143, -81.756, 31.303],
        "start_date": "2026-04-01",
        "end_date": "2026-04-28",
    },
    "florida_fire_drought_watch": {
        "label": "Florida Fire/Drought Readiness Watch",
        "aliases": [
            "florida",
            "florida fire",
            "florida wildfire",
            "florida wildfires",
            "wildfires in florida",
            "florida drought",
            "drought conditions",
            "recent drought conditions",
            "drought fire",
            "north florida",
            "fire drought",
        ],
        "use_case_id": "wildfire",
        "target_pack_id": "fireline",
        "task_text": "Run Florida Fire/Drought Readiness Watch over a North Florida corridor. Triage drought-stressed vegetation, smoke candidates, burn-scar candidates, road or trail access, firebreak context, water/vegetation boundaries, and civilian lifeline exposure. Treat this as candidate evidence until source-backed imagery confirms smoke, active fire, or burn scar.",
        "bbox": [-83.2, 29.0, -81.3, 30.7],
        "start_date": "2026-04-15",
        "end_date": "2026-04-25",
    },
    "florida_manatee_habitat_review": {
        "label": "Florida Manatee Habitat Review",
        "aliases": [
            "manatee",
            "manatees",
            "manatee population",
            "manatee populations",
            "manatee habitat",
            "manatees in water",
            "florida manatee",
            "seagrass",
            "warm water refuge",
            "crystal river",
            "clearwater",
            "banana river",
            "winter aggregation",
        ],
        "use_case_id": "temporal_change_generic",
        "target_pack_id": "waterline",
        "task_text": "Run Florida Manatee Habitat Review over a Gulf Coast spring/estuary context. Treat this as a hard protected-wildlife proxy mission: review water extent, water color/turbidity candidates, water/vegetation boundaries where visible, warm-water refuge context, shoreline or river access, boat-traffic corridor context, and conservation-area boundaries. Do not count or locate individual animals, infer population size, or claim protected-species presence from orbital imagery.",
        "bbox": [-82.85, 28.75, -82.45, 29.15],
        "start_date": "2026-01-01",
        "end_date": "2026-02-28",
    },
}

REPLAY_ALIASES: dict[str, str] = {
    "rondonia": "rondonia_frontier_showcase",
    "amazon": "rondonia_frontier_showcase",
    "frontier": "rondonia_frontier_showcase",
    "deforestation": "rondonia_frontier_showcase",
    "flood": "manchar_flood_replay",
    "manchar": "manchar_flood_replay",
    "pakistan": "manchar_flood_replay",
    "mining": "atacama_mining_replay",
    "critical minerals": "atacama_mining_replay",
    "atacama": "atacama_mining_replay",
    "salar": "atacama_mining_replay",
    "escondida": "atacama_mining_replay",
    "ice": "greenland_ice_snow_extent_replay",
    "snow": "greenland_ice_snow_extent_replay",
    "greenland": "greenland_ice_snow_extent_replay",
    "wildfire": "georgia_wildfire_replay",
    "fire": "georgia_wildfire_replay",
    "georgia": "georgia_wildfire_replay",
    "southeast fireline": "southeast_fireline_object_replay",
    "fireline watch": "southeast_fireline_object_replay",
    "urban": "delhi_urban_replay",
    "delhi": "delhi_urban_replay",
    "maritime": "singapore_maritime_replay",
    "maritime traffic": "singapore_maritime_replay",
    "port": "singapore_maritime_replay",
    "singapore": "singapore_maritime_replay",
    "ship": "singapore_maritime_replay",
    "strait": "singapore_maritime_replay",
    "traffic": "singapore_maritime_replay",
    "vessel": "singapore_maritime_replay",
}

LOCATION_TARGETS: dict[str, dict[str, Any]] = {
    "bull_creek_fl": {
        "label": "Bull Creek, FL",
        "aliases": [
            "bull creek",
            "bull creek fl",
            "bull creek florida",
            "bull creek wma",
            "bull creek wildlife management area",
        ],
        "center": [-80.965, 28.095],
        "bbox": [-81.07, 28.02, -80.86, 28.18],
        "camera": {
            "zoom": 12.2,
            "pitch": 60,
            "bearing": -32,
            "duration_ms": 1200,
        },
        "location_type": "wetland / pine-flatwoods context",
        "terrain_context": "Low-relief Florida wetlands, pine flatwoods, trails, roads, canals, and managed conservation land. Terrain may look subtle even when 3D relief boost is enabled.",
        "mission_context": "Use as a camera and bbox context target for land-cover, road/trail access, water/vegetation boundary, and review-area setup. Do not treat the no-auth 3D layer as acquisition-time evidence.",
        "semantic_tags": [
            "wetland_context",
            "pine_flatwoods",
            "low_relief_terrain",
            "road_trail_access",
            "water_vegetation_boundary",
            "camera_target",
        ],
        "suggested_targets": [
            "water/vegetation boundary",
            "road or trail corridor",
            "managed-land boundary",
            "canal or drainage line",
            "surface moisture context",
        ],
        "evidence_guidance": "Prefer region-level labels and temporal/source-backed imagery for claims. Use the map view as spatial context only.",
        "summary": "Wetland and pine-flatwoods context target for camera navigation, bbox selection, and cautious land-cover review.",
    },
    "giza_pyramid_complex": {
        "label": "Giza Pyramid Complex",
        "aliases": [
            "giza",
            "giza pyramid",
            "giza pyramids",
            "pyramids of giza",
            "great pyramid",
            "great pyramid of giza",
        ],
        "center": [31.1342, 29.9792],
        "bbox": [31.118, 29.965, 31.152, 29.993],
        "camera": {
            "zoom": 14.4,
            "pitch": 56,
            "bearing": -28,
            "duration_ms": 1200,
        },
        "location_type": "archaeological heritage site context",
        "terrain_context": "Desert plateau, monument footprints, access roads, tourist/service areas, and surrounding urban edge. Use the map as spatial context only.",
        "mission_context": "Use as a camera and bbox context target for navigation, heritage-site context, access-corridor review, or visual orientation. Do not treat the basemap or 3D layer as acquisition-time mission evidence.",
        "semantic_tags": [
            "heritage_site_context",
            "desert_plateau",
            "access_corridor",
            "urban_edge",
            "camera_target",
        ],
        "suggested_targets": [
            "monument footprint context",
            "access road corridor",
            "visitor/service area",
            "urban edge",
            "sand/stone surface context",
        ],
        "evidence_guidance": "Use this as navigation and context unless a dated mission/replay source is launched for evidence. Avoid heritage-condition claims from the basemap alone.",
        "summary": "Heritage-site context target for map navigation, bbox selection, and cautious visual orientation.",
    },
    "bronx_ny": {
        "label": "Bronx, NY",
        "aliases": [
            "bronx",
            "the bronx",
            "bronx ny",
            "bronx new york",
            "the bronx ny",
            "the bronx new york",
        ],
        "center": [-73.8648, 40.8448],
        "bbox": [-73.9339, 40.7857, -73.7654, 40.9153],
        "camera": {
            "zoom": 11.6,
            "pitch": 58,
            "bearing": -24,
            "duration_ms": 1200,
        },
        "location_type": "urban borough context",
        "terrain_context": "Dense urban grid, river and shoreline edges, parks, rail corridors, highways, bridges, and waterfront/industrial zones. Use this map view as spatial context only.",
        "mission_context": "Use as a camera and bbox context target for urban orientation, infrastructure corridor review, shoreline/water-boundary context, park/open-space review, or follow-on mission setup. Do not treat the basemap as dated mission evidence.",
        "semantic_tags": [
            "urban_borough_context",
            "dense_urban_grid",
            "shoreline_boundary",
            "transport_corridor",
            "park_open_space",
            "camera_target",
        ],
        "suggested_targets": [
            "shoreline or river boundary",
            "transport corridor",
            "park or open-space context",
            "dense urban block",
            "waterfront or industrial corridor",
        ],
        "evidence_guidance": "Use this as navigation and review context unless a dated mission/replay source is launched. Avoid asserting current conditions, incidents, or infrastructure status from the basemap alone.",
        "summary": "Urban borough context target for map navigation, bbox selection, and cautious infrastructure or shoreline review.",
    },
    "davenport_fl": {
        "label": "Davenport, FL",
        "aliases": [
            "davenport",
            "davenport fl",
            "davenport florida",
            "davenport polk county",
            "davenport polk county florida",
            "polk county construction",
        ],
        "center": [-81.6017, 28.1614],
        "bbox": [-81.7, 28.08, -81.48, 28.28],
        "camera": {
            "zoom": 11.4,
            "pitch": 56,
            "bearing": -18,
            "duration_ms": 1200,
        },
        "location_type": "suburban growth / construction context",
        "terrain_context": "Low-relief Central Florida suburban growth area with roads, subdivisions, cleared parcels, retention ponds, and mixed wetland or open-land boundaries.",
        "mission_context": "Use as a bbox context target for long-window construction progression, new subdivision footprint review, road expansion, cleared-parcel persistence, and built-surface growth. Static map imagery is only context until a dated timelapse or replay is generated.",
        "semantic_tags": [
            "suburban_growth_context",
            "construction_progression",
            "built_surface_growth",
            "road_expansion",
            "cleared_parcel_persistence",
            "camera_target",
        ],
        "suggested_targets": [
            "construction footprint",
            "new subdivision region",
            "road expansion corridor",
            "cleared parcel",
            "retention pond / drainage context",
        ],
        "evidence_guidance": "Use dated multi-frame imagery before claiming new construction. Keep outputs at region or footprint level and avoid parcel ownership, legal, or occupancy claims.",
        "summary": "Central Florida suburban-growth context target for construction timelapse planning and cautious built-surface change review.",
    },
    "lake_okeechobee_fl": {
        "label": "Lake Okeechobee, FL",
        "aliases": [
            "lake okeechobee",
            "okeechobee",
            "lake okeechobee fl",
            "lake okeechobee florida",
            "okeechobee algae",
            "okeechobee bloom",
            "okeechobee cyanobacteria",
        ],
        "center": [-80.82, 26.94],
        "bbox": [-81.16, 26.64, -80.55, 27.24],
        "camera": {
            "zoom": 8.9,
            "pitch": 42,
            "bearing": -12,
            "duration_ms": 1200,
        },
        "location_type": "large freshwater lake / water-quality context",
        "terrain_context": "Large shallow lake, canals, locks, agricultural runoff context, shorelines, and open-water areas where surface blooms can appear as broad swirls or patches.",
        "mission_context": "Use as a bbox context target for probable algal bloom, high chlorophyll, cyanobacteria-like signal, water-color boundary, turbidity, and cloud/glint control review. Satellite imagery alone does not confirm species or toxin level.",
        "semantic_tags": [
            "freshwater_lake_context",
            "harmful_algal_bloom_candidate",
            "cyanobacteria_like_signal",
            "high_chlorophyll_signal",
            "water_quality_context",
            "candidate_only",
            "camera_target",
        ],
        "suggested_targets": [
            "probable surface bloom",
            "high chlorophyll signal",
            "cyanobacteria-like signal",
            "surface scum candidate",
            "turbidity control area",
            "cloud/glint control",
        ],
        "evidence_guidance": "Use probable bloom wording only. Do not claim toxicity, species, microcystin, or red tide from Sentinel-2 or basemap imagery without NOAA/FDEP or field confirmation.",
        "summary": "Freshwater water-quality context target for Lake Okeechobee algal bloom candidate review.",
    },
    "north_pacific_debris_context": {
        "label": "North Pacific Debris Convergence Review Window",
        "aliases": [
            "great pacific garbage patch",
            "pacific garbage patch",
            "north pacific garbage patch",
            "garbage patch",
            "garbage patches",
            "biggest garbage patch",
            "biggest garbage patches",
            "largest garbage patch",
            "largest garbage patches",
            "ocean garbage patch",
            "ocean garbage patches",
            "pacific trash vortex",
            "north pacific gyre",
            "marine debris gyre",
        ],
        "center": [-145.5, 34.5],
        "bbox": [-146.0, 34.0, -145.0, 35.0],
        "review_bbox": [-145.6, 34.4, -145.4, 34.6],
        "camera": {
            "zoom": 6.4,
            "pitch": 40,
            "bearing": -15,
            "duration_ms": 1200,
        },
        "location_type": "open-ocean debris convergence context",
        "terrain_context": "Open-ocean gyre context with sparse visible structure. RGB basemaps may look nearly uniform, and floating plastics are often dispersed below visible pixel scale.",
        "mission_context": "Use as a cautious review window for slick, foam-line, windrow, or floating-debris candidates. Do not treat this as proof of Great Pacific Garbage Patch mass, material identity, or continuous monthly visibility.",
        "semantic_tags": [
            "open_ocean_context",
            "marine_debris_candidate",
            "debris_convergence",
            "slick_candidate",
            "candidate_only",
            "camera_target",
        ],
        "suggested_targets": [
            "slick candidate area",
            "foam line region",
            "floating debris candidate",
            "windrow candidate",
            "cloud/glint/algae control",
        ],
        "evidence_guidance": "Use candidate labels only. Do not claim Great Pacific Garbage Patch mass, material ID, or monthly visible growth from optical imagery; prefer coastal, river, storm, or field-survey context for confirmation.",
        "summary": "Open-ocean gyre context target for cautious marine debris and slick candidate review, not garbage-patch mass monitoring.",
    },
    "suez_canal": {
        "label": "Suez Canal",
        "aliases": [
            "suez",
            "suez canal",
            "suez channel",
            "the suez canal",
        ],
        "center": [32.54, 29.92],
        "bbox": [32.5, 29.88, 32.58, 29.96],
        "camera": {
            "zoom": 12.8,
            "pitch": 55,
            "bearing": -18,
            "duration_ms": 1200,
        },
        "location_type": "maritime canal context",
        "terrain_context": "Canal waterway, port approaches, desert edge, vessel lanes, anchorages, and service infrastructure. Use the basemap as context only.",
        "mission_context": "Use as a bbox context target for maritime orientation, vessel-queue review setup, channel access context, or follow-on mission planning. Navigation alone does not launch a maritime scan.",
        "semantic_tags": [
            "maritime_context",
            "canal_corridor",
            "vessel_lane",
            "port_approach",
            "camera_target",
        ],
        "suggested_targets": [
            "vessel lane context",
            "anchorage or queue area",
            "port approach",
            "canal shoreline",
            "service infrastructure",
        ],
        "evidence_guidance": "Use dated imagery or replay evidence before claiming vessel activity. Navigation alone should not infer traffic, blockage, or queue status.",
        "summary": "Maritime canal context target for map navigation, bbox selection, and cautious vessel/port workflow setup.",
    },
    "greenland_ice_edge": {
        "label": "Greenland Ice Edge",
        "aliases": [
            "greenland",
            "greenland ice",
            "greenland ice edge",
            "greenland ice sheet edge",
            "ice edge greenland",
        ],
        "center": [-51.05, 69.18],
        "bbox": [-51.13, 69.1, -50.97, 69.26],
        "camera": {
            "zoom": 10.6,
            "pitch": 54,
            "bearing": -20,
            "duration_ms": 1200,
        },
        "location_type": "cryosphere edge context",
        "terrain_context": "Snow/ice margin, exposed rock, open-water or meltwater context, and low-detail polar basemap areas. Cloud and seasonal controls matter for evidence.",
        "mission_context": "Use as a bbox context target for snow/ice extent review setup, NDSI/SCL-gated replay context, or cautious ice-edge orientation. Navigation is not proof of retreat or growth.",
        "semantic_tags": [
            "cryosphere_context",
            "ice_edge",
            "snow_ice_extent",
            "open_water_boundary",
            "camera_target",
        ],
        "suggested_targets": [
            "ice terminus or edge",
            "open water boundary",
            "exposed bedrock",
            "snow/ice extent context",
            "cloud/shadow control",
        ],
        "evidence_guidance": "Use multispectral/dateranged evidence before claiming ice change. Reject static single-image color shifts as timelapse proof.",
        "summary": "Greenland snow/ice edge context target for map navigation, bbox selection, and cautious cryosphere review setup.",
    },
    "manchar_lake": {
        "label": "Manchar Lake",
        "aliases": [
            "manchar",
            "manchar lake",
            "lake manchar",
            "manchar lake pakistan",
        ],
        "center": [67.75, 26.43],
        "bbox": [67.63, 26.31, 67.87, 26.55],
        "camera": {
            "zoom": 11.4,
            "pitch": 52,
            "bearing": -18,
            "duration_ms": 1200,
        },
        "location_type": "lake / floodplain context",
        "terrain_context": "Lake basin, floodplain, canals, shoreline edges, exposed basin, and settlement/agriculture context. Use dated imagery for flood or waterline claims.",
        "mission_context": "Use as a bbox context target for flood/waterline review setup or replay orientation. Navigation alone does not load the Manchar flood replay.",
        "semantic_tags": [
            "lake_context",
            "floodplain_context",
            "waterline_boundary",
            "shoreline_change",
            "camera_target",
        ],
        "suggested_targets": [
            "waterline boundary",
            "floodplain edge",
            "canal or drainage corridor",
            "exposed basin",
            "settlement/agriculture context",
        ],
        "evidence_guidance": "Use dated flood replay or generated timelapse evidence before claiming flood extent or shoreline change.",
        "summary": "Lake/floodplain context target for map navigation, bbox selection, and cautious waterline workflow setup.",
    },
}

ALLOWED_AGENT_ACTIONS = {
    "load_replay",
    "rescan_replay",
    "start_mission_pack",
    "start_custom_mission",
    "stop_mission",
    "navigate_map",
    "navigate_map_location",
    "set_link_state",
    "update_mission_targets",
    "set_target_pack",
    "save_target_pack",
    "clear_mission_targets",
}

TARGET_PACK_BY_USE_CASE = {
    "deforestation": "deforestation",
    "wildfire": "fireline",
    "maritime_activity": "port",
    "civilian_lifeline_disruption": "lifeline",
    "ice_snow_extent": "glacier",
    "ice_cap_growth": "glacier",
    "flood_extent": "waterline",
    "harmful_algal_bloom": "algae_bloom",
    "crop_phenology": "deforestation",
    "urban_expansion": "urban_expansion",
    "mining_expansion": "critical_minerals",
}

PLANNER_REGION_HINTS: list[dict[str, Any]] = [
    {
        "label": "North Florida fire/drought corridor",
        "aliases": ["north florida", "florida", "florida drought", "florida wildfire", "florida fire"],
        "bbox": [-83.2, 29.0, -81.3, 30.7],
    },
    {
        "label": "Davenport, FL construction growth context",
        "aliases": [
            "davenport",
            "davenport fl",
            "davenport florida",
            "davenport polk county",
            "polk county construction",
        ],
        "bbox": [-81.7, 28.08, -81.48, 28.28],
    },
    {
        "label": "Florida Gulf Coast spring/estuary context",
        "aliases": ["crystal river", "gulf coast florida", "florida gulf coast", "manatee habitat"],
        "bbox": [-82.85, 28.75, -82.45, 29.15],
    },
    {
        "label": "Rondonia frontier context",
        "aliases": ["rondonia", "amazon frontier"],
        "bbox": [-63.15, -10.15, -62.85, -9.85],
    },
    {
        "label": "Atacama mining corridor",
        "aliases": ["atacama", "salar de atacama", "escondida"],
        "bbox": [-69.115, -24.29, -69.035, -24.21],
    },
    {
        "label": "Greenland edge snow/ice context",
        "aliases": ["greenland"],
        "bbox": [-51.13, 69.1, -50.97, 69.26],
    },
    {
        "label": "Suez channel maritime context",
        "aliases": ["suez", "suez channel"],
        "bbox": [32.5, 29.88, 32.58, 29.96],
    },
    {
        "label": "Manchar Lake flood context",
        "aliases": ["manchar", "manchar lake", "pakistan flood"],
        "bbox": [67.63, 26.31, 67.87, 26.55],
    },
]

MANATEE_HABITAT_REGIONS: list[dict[str, Any]] = [
    {
        "label": "Banana River lagoon context",
        "aliases": ["banana river", "banana river fl", "banana river florida", "merritt island"],
        "bbox": [-80.78, 28.16, -80.55, 28.58],
    },
    {
        "label": "Clearwater / Tampa Bay coastal-water context",
        "aliases": ["clearwater", "clearwater fl", "clearwater florida", "tampa bay"],
        "bbox": [-82.92, 27.78, -82.58, 28.08],
    },
    {
        "label": "Crystal River / Kings Bay warm-water refuge context",
        "aliases": ["crystal river", "kings bay", "homosassa"],
        "bbox": [-82.85, 28.75, -82.45, 29.15],
    },
]


def _base_state() -> dict[str, Any]:
    from core.agent_bus import get_bus_stats
    from core.link_state import is_link_connected
    from core.mission import get_active_mission
    from core.queue import get_alert_counts

    return {
        "alerts": get_alert_counts(),
        "bus": get_bus_stats(),
        "mission": get_active_mission(),
        "link": "online" if is_link_connected() else "offline",
    }


def _action(name: str, status: str, result: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "status": status, "result": result}


def _proposal_subject(details: dict[str, Any]) -> str:
    if details.get("replay_id"):
        return str(details["replay_id"])
    if details.get("pack_id"):
        return str(details["pack_id"])
    if details.get("target_pack_id"):
        return str(details["target_pack_id"])
    if details.get("mission_id"):
        return f"mission_{details['mission_id']}"
    if details.get("location_id"):
        return str(details["location_id"])
    if "connected" in details:
        return "online" if bool(details["connected"]) else "offline"
    return "unknown"


def _proposal(
    *,
    kind: str,
    title: str,
    summary: str,
    details: dict[str, Any],
    confirm_label: str,
    risk_level: str,
    cancel_label: str = "Cancel",
) -> dict[str, Any]:
    return {
        "id": f"proposal_{kind}_{_proposal_subject(details)}",
        "kind": kind,
        "title": title,
        "summary": summary,
        "details": details,
        "confirm_label": confirm_label,
        "cancel_label": cancel_label,
        "risk_level": risk_level,
    }


def _with_request(proposal: dict[str, Any], user_msg: str) -> dict[str, Any]:
    proposal["details"]["request"] = user_msg.strip()
    return proposal


def _catalog_summary(limit: int = 8) -> list[dict[str, Any]]:
    from core.replay import list_seeded_replays

    return [
        {
            "replay_id": item.get("replay_id"),
            "title": item.get("title"),
            "use_case_id": item.get("use_case_id"),
            "alert_count": item.get("alert_count"),
            "cells_scanned": item.get("cells_scanned"),
        }
        for item in list_seeded_replays()[:limit]
    ]


def _replay_catalog_item(replay_id: str) -> dict[str, Any] | None:
    from core.replay import list_seeded_replays

    for item in list_seeded_replays():
        if item.get("replay_id") == replay_id:
            return item
    return None


def _replay_scoring_basis(replay_id: str, use_case_id: str | None) -> str:
    if replay_id == "greenland_ice_snow_extent_replay" or use_case_id == "ice_snow_extent":
        return "multispectral_bands"
    if replay_id == "rondonia_frontier_showcase" or use_case_id == "deforestation":
        return "proxy_bands"
    return "visual_only"


def _replay_proposal(kind: str, replay_id: str) -> dict[str, Any]:
    item = _replay_catalog_item(replay_id) or {"replay_id": replay_id, "title": replay_id}
    title = str(item.get("title") or replay_id)
    use_case_id = str(item.get("use_case_id") or "")
    scoring_basis = _replay_scoring_basis(replay_id, use_case_id or None)
    action_label = "Load replay" if kind == "load_replay" else "Rescan replay"
    details = {
        "replay_id": replay_id,
        "title": title,
        "use_case_id": use_case_id,
        "runtime_truth_mode": "replay" if kind == "load_replay" else "realtime",
        "imagery_origin": "cached_api" if kind == "load_replay" else "provider_chain",
        "scoring_basis": scoring_basis if kind == "load_replay" else "current_runtime",
        "start_date": item.get("start_date") or "",
        "end_date": item.get("end_date") or "",
        "alert_count": item.get("alert_count") or 0,
        "cells_scanned": item.get("cells_scanned") or 0,
        "expected_reset": kind == "load_replay",
        "state_impact": [
            "Runtime reset" if kind == "load_replay" else "Start active mission from replay bbox",
            "Load replay evidence" if kind == "load_replay" else "Use current provider/model stack",
            "Refresh Mission Control",
            "Refresh Logs, Inspect, Gallery, and Agent Dialogue",
        ],
    }
    return _proposal(
        kind=kind,
        title=f"{action_label}: {title}",
        summary=(
            "Load cached real API replay evidence into Mission, Logs, Inspect, Gallery, and Agent Dialogue."
            if kind == "load_replay"
            else "Start a live rescan from this replay's bbox and dates using the current runtime/model stack."
        ),
        details=details,
        confirm_label="Run Replay" if kind == "load_replay" else "Start Rescan",
        risk_level="medium",
    )


def _mission_pack_proposal(pack_id: str, pack: dict[str, Any]) -> dict[str, Any]:
    from core.object_targets import get_target_pack

    target_pack_id = pack.get("target_pack_id")
    target_pack = get_target_pack(str(target_pack_id)) if target_pack_id else None
    return _proposal(
        kind="start_mission_pack",
        title=f"Launch Mission Pack: {pack['label']}",
        summary="Start a new mission from this preset bbox, date range, task text, and object targets.",
        details={
            "pack_id": pack_id,
            "label": pack["label"],
            "use_case_id": pack["use_case_id"],
            "target_pack_id": target_pack["id"] if target_pack else None,
            "object_targets": target_pack["targets"] if target_pack else [],
            "bbox": pack["bbox"],
            "start_date": pack["start_date"],
            "end_date": pack["end_date"],
            "task_text": pack["task_text"],
            "expected_reset": False,
            "state_impact": [
                "Set active mission",
                "Apply object target pack" if target_pack else "Keep mission object targets empty",
                "Start satellite scan loop on preset bbox",
                "Refresh Mission Control",
                "Append Agent Dialogue mission note",
            ],
        },
        confirm_label="Launch Mission",
        risk_level="medium",
    )


def _clean_operator_request(user_msg: str, *, limit: int = 260) -> str:
    request = re.sub(r"\s+", " ", user_msg).strip(" .")
    if len(request) <= limit:
        return request
    return request[: limit - 3].rstrip() + "..."


def _default_planner_dates(text: str) -> tuple[str, str]:
    today = datetime.now(timezone.utc).date()
    year_window = re.search(r"\b(?:last|past|previous)\s+(\d{1,2})\s+years?\b", text)
    if year_window:
        years = max(1, min(int(year_window.group(1)), 40))
        try:
            start = today.replace(year=today.year - years)
        except ValueError:
            start = today.replace(month=2, day=28, year=today.year - years)
    elif "last decade" in text or "past decade" in text:
        try:
            start = today.replace(year=today.year - 10)
        except ValueError:
            start = today.replace(month=2, day=28, year=today.year - 10)
    elif since_match := re.search(r"\bsince\s+((?:19|20)\d{2})\b", text):
        year = max(1972, min(int(since_match.group(1)), today.year))
        start = today.replace(year=year, month=1, day=1)
    elif any(token in text for token in ("long-term", "multi year", "multiyear", "since", "trend")):
        start = today - timedelta(days=365)
    else:
        start = today - timedelta(days=30)
    return start.isoformat(), today.isoformat()


def _month_span(start_date: str, end_date: str) -> int | None:
    try:
        start = datetime.fromisoformat(start_date).date()
        end = datetime.fromisoformat(end_date).date()
    except ValueError:
        return None
    if end < start:
        return None
    return max(1, (end.year - start.year) * 12 + end.month - start.month + 1)


def _infer_temporal_cadence(text: str, start_date: str, end_date: str) -> tuple[str, int | None, str]:
    if any(token in text for token in ("every month", "each month", "per month", "monthly")):
        return (
            "monthly",
            _month_span(start_date, end_date),
            "Requested monthly cadence; accepted frames still depend on provider availability, clouds, no-data, and quality gates.",
        )
    if any(token in text for token in ("every quarter", "each quarter", "quarterly")):
        month_count = _month_span(start_date, end_date)
        return (
            "quarterly",
            max(1, round(month_count / 3)) if month_count else None,
            "Requested quarterly cadence; accepted frames still depend on provider availability, clouds, no-data, and quality gates.",
        )
    if any(token in text for token in ("every year", "each year", "annual", "yearly")):
        month_count = _month_span(start_date, end_date)
        return (
            "yearly",
            max(1, round(month_count / 12)) if month_count else None,
            "Requested yearly cadence; accepted frames still depend on provider availability, clouds, no-data, and quality gates.",
        )
    return (
        "mission default",
        None,
        "No explicit frame cadence requested; use the mission runtime default for the selected provider and quality gates.",
    )


def _planner_safety_guidance(target_pack_id: str | None, use_case_id: str) -> str:
    if target_pack_id == "fireline" or use_case_id == "wildfire":
        return (
            "Treat smoke, burn scar, vegetation stress, access, and lifeline exposure as candidate evidence "
            "until source-backed imagery confirms the event."
        )
    if target_pack_id == "waterline" or use_case_id == "flood_extent":
        return (
            "Review water extent, shoreline, exposed basin, and color-boundary changes as region-level evidence; "
            "do not infer protected wildlife presence or population counts."
        )
    if target_pack_id == "algae_bloom" or use_case_id == "harmful_algal_bloom":
        return (
            "Review high chlorophyll, cyanobacteria-like, surface-scum, and water-color signals as probable bloom "
            "candidates only; do not claim toxicity, species, microcystin, or red tide without NOAA/FDEP or field confirmation."
        )
    if target_pack_id == "critical_minerals":
        return (
            "Review extraction-site regions, tailings, ponds, roads, facilities, exposed soil, and color change "
            "without claiming legality, pollution, or production output."
        )
    if target_pack_id == "port" or use_case_id == "maritime_activity":
        return (
            "Review port, vessel-queue, wake, container, crane, and access context as activity evidence; "
            "do not infer illegal activity from imagery alone."
        )
    if target_pack_id == "lifeline":
        return (
            "Review public mobility and service-continuity context as candidate civilian lifeline evidence; "
            "avoid casualty, intent, or sensitive-person claims."
        )
    if target_pack_id == "plastic":
        return (
            "Review slick, foam-line, windrow, and floating-debris candidates only where features aggregate above "
            "visible pixel scale; do not claim open-ocean garbage-patch mass, material identity, or continuous "
            "monthly visibility from optical bands."
        )
    if target_pack_id == "urban_expansion" or use_case_id == "urban_expansion":
        return (
            "Review construction footprints, road expansion, cleared parcels, and built-surface persistence as "
            "region-level temporal evidence; avoid parcel ownership, legal, occupancy, or permit claims."
        )
    if target_pack_id == "glacier":
        return (
            "Review snow/ice extent, terminus, open-water, bedrock, and retreat-boundary changes with cloud and "
            "seasonal-window controls."
        )
    return "Keep the mission result as candidate temporal evidence until source provenance and operator review support it."


def _infer_target_pack_id(text: str, use_case_id: str) -> str | None:
    if any(token in text for token in ("algae", "algal", "bloom", "cyanobacteria", "chlorophyll", "red tide", "water quality", "ndci", "fai")):
        return "algae_bloom"
    if any(token in text for token in ("construction", "new construction", "subdivision", "built surface", "building footprint", "urban expansion")):
        return "urban_expansion"
    if any(token in text for token in ("critical minerals", "mining", "mine", "tailings", "open pit", "evaporation pond")):
        return "critical_minerals"
    if any(token in text for token in ("deforestation", "forest", "canopy", "clear cut", "clearcut", "tree cover")):
        return "deforestation"
    if any(token in text for token in ("wildfire", "fire", "fireline", "smoke", "burn scar", "burn", "dry fuels")):
        return "fireline"
    if any(token in text for token in ("maritime", "port", "ship", "vessel", "boat", "harbor", "queue", "container")):
        return "port"
    if any(token in text for token in ("shelter", "tent", "camp", "clinic roof", "water tank")):
        return "camp"
    if any(token in text for token in ("bridge", "road", "lifeline", "traffic", "aid route", "water service")):
        return "lifeline"
    if any(
        token in text
        for token in (
            "plastic",
            "debris",
            "slick",
            "foam line",
            "storm debris",
            "garbage",
            "trash",
            "marine litter",
            "litter patch",
            "garbage patch",
            "trash vortex",
            "north pacific gyre",
            "ocean gyre",
        )
    ):
        return "plastic"
    if any(token in text for token in ("glacier", "ice", "snow", "cryosphere", "terminus")):
        return "glacier"
    if any(token in text for token in ("flood", "waterline", "shoreline", "lake", "water extent", "drought", "seagrass")):
        return "waterline"
    return TARGET_PACK_BY_USE_CASE.get(use_case_id)


def _infer_planner_region(text: str, target_pack_id: str | None) -> dict[str, Any] | None:
    location_match = _match_location_target(text)
    if location_match:
        _, target, candidate = location_match
        bbox = target.get("review_bbox") or target["bbox"]
        return {
            "label": target["label"],
            "bbox": bbox,
            "location_context_bbox": target.get("bbox") if target.get("bbox") != bbox else None,
            "location_candidate": candidate,
            "semantic_tags": target.get("semantic_tags") or [],
            "suggested_targets": target.get("suggested_targets") or [],
            "evidence_guidance": target.get("evidence_guidance") or "",
            "source": "known_location",
        }

    if "florida" in text and target_pack_id == "waterline":
        gulf_hint = next((hint for hint in PLANNER_REGION_HINTS if "Gulf Coast" in hint["label"]), None)
        if gulf_hint:
            return {**gulf_hint, "source": "region_hint"}

    for hint in PLANNER_REGION_HINTS:
        if any(alias in text for alias in hint["aliases"]):
            return {**hint, "source": "region_hint"}
    return None


def _planner_reply(plan: dict[str, Any]) -> str:
    attempts = plan["planner_attempts"]
    return (
        "Planning pass complete. "
        f"Attempted workflow: {attempts[0]} {attempts[1]} {attempts[2]} "
        f"Final result: {plan['planner_result']}. Review the proposal before launch."
    )


def _custom_mission_proposal(plan: dict[str, Any]) -> dict[str, Any]:
    from core.object_targets import get_target_pack

    target_pack_id = plan.get("target_pack_id")
    target_pack = get_target_pack(str(target_pack_id)) if target_pack_id else None
    target_pack_id = target_pack["id"] if target_pack else None
    region_label = plan.get("region_label") or "default scan region"
    return _proposal(
        kind="start_custom_mission",
        title=f"Launch Custom Mission Plan: {plan['display_name']}",
        summary=f"Start a custom Ground Agent mission plan over {region_label}.",
        details={
            "planner_result": plan["planner_result"],
            "workflow_mode": "agentic_prompt_workflow",
            "use_case_id": plan["use_case_id"],
            "target_pack_id": target_pack_id,
            "object_targets": target_pack["targets"] if target_pack else [],
            "object_target_labels": [str(target["label"]) for target in target_pack["targets"]] if target_pack else [],
            "bbox": plan.get("bbox"),
            "location_context_bbox": plan.get("location_context_bbox"),
            "region_label": region_label,
            "region_source": plan.get("region_source"),
            "semantic_tags": plan.get("semantic_tags") or [],
            "suggested_targets": plan.get("suggested_targets") or [],
            "evidence_guidance": plan.get("evidence_guidance"),
            "location_provider": plan.get("location_provider"),
            "location_confidence": plan.get("location_confidence"),
            "start_date": plan["start_date"],
            "end_date": plan["end_date"],
            "temporal_cadence": plan.get("temporal_cadence"),
            "requested_frame_count": plan.get("requested_frame_count"),
            "cadence_note": plan.get("cadence_note"),
            "task_text": plan["task_text"],
            "planner_attempts": plan["planner_attempts"],
            "tool_plan": plan["tool_plan"],
            "evidence_limits": plan["evidence_limits"],
            "confidence": plan["confidence"],
            "expected_reset": False,
            "state_impact": [
                "Set active mission from planner output",
                "Apply inferred object target pack" if target_pack else "Keep mission object targets empty",
                "Move map to inferred bbox and select review area" if plan.get("bbox") else "Use default scan region until the operator selects a bbox",
                "Start satellite scan loop",
                "Append Agent Dialogue mission note",
            ],
        },
        confirm_label="Launch Plan",
        risk_level="medium",
    )


def _mission_pack_plan_proposal(pack_id: str, pack: dict[str, Any]) -> dict[str, Any]:
    proposal = _mission_pack_proposal(pack_id, pack)
    proposal["summary"] = "Agentic planner matched this request to a curated mission pack."
    proposal["details"]["planner_result"] = "curated_mission_pack_ready"
    proposal["details"]["workflow_mode"] = "agentic_prompt_workflow"
    proposal["details"]["planner_attempts"] = [
        "Parsed operator request into a mission intent",
        f"Matched curated pack `{pack_id}`",
        f"Selected use case `{pack['use_case_id']}` and target pack `{pack.get('target_pack_id') or 'none'}`",
    ]
    proposal["details"]["tool_plan"] = [
        "Launch preset mission only after operator confirmation",
        "Satellite Pruner scans the pack bbox and emits compact candidate packets",
        "Ground Validator reviews retained evidence, replay context, and object targets",
    ]
    proposal["details"]["evidence_limits"] = [
        "Candidate evidence only until imagery provenance and operator review support it",
        "No protected wildlife counts, person-level claims, or legal-status claims from imagery alone",
    ]
    return proposal


def _build_agentic_mission_plan(user_msg: str, text: str) -> dict[str, Any] | None:
    skip_curated_pack = any(
        token in text
        for token in ("construction", "new construction", "subdivision", "built surface", "building footprint", "urban expansion")
    )
    match = None if skip_curated_pack else _match_mission_pack(text)
    if match:
        pack_id, pack = match
        plan = {
            "planner_result": f"curated mission pack `{pack_id}` is ready",
            "planner_attempts": [
                "Parsed operator request into a mission intent.",
                f"Matched curated pack `{pack_id}`.",
                f"Selected `{pack.get('target_pack_id') or 'no'}` target pack for `{pack['use_case_id']}`.",
            ],
        }
        return {
            "reply": _planner_reply(plan),
            "actions": [],
            "proposals": [_with_request(_mission_pack_plan_proposal(pack_id, pack), user_msg)],
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    from core.temporal_use_cases import classify_temporal_use_case

    decision = classify_temporal_use_case({"task_text": user_msg})
    use_case_id = str(decision.get("id") or "temporal_change_generic")
    target_pack_id = _infer_target_pack_id(text, use_case_id)
    region = _infer_planner_region(text, target_pack_id)
    start_date, end_date = _default_planner_dates(text)
    temporal_cadence, requested_frame_count, cadence_note = _infer_temporal_cadence(text, start_date, end_date)
    clean_request = _clean_operator_request(user_msg)
    region_label = region.get("label") if region else None
    location_candidate = region.get("location_candidate") if region and isinstance(region.get("location_candidate"), dict) else {}
    safety = _planner_safety_guidance(target_pack_id, use_case_id)
    display_name = str(decision.get("display_name") or "Temporal Change Review")
    if target_pack_id == "plastic" and use_case_id == "temporal_change_generic":
        display_name = "Coastal Debris / Slick Candidate Watch"
    task_text = (
        f"Attempt Ground Agent mission plan for: {clean_request}. "
        f"Review {region_label or 'the active/default scan region'} with SimSat-first runtime and compact evidence packets. "
        f"Requested temporal cadence: {temporal_cadence}. "
        f"{safety}"
    )
    planner_attempts = [
        "Parsed operator request into mission intent and temporal keywords.",
        f"Classified use case `{use_case_id}` with confidence {float(decision.get('confidence') or 0.0):.2f}.",
        (
            f"Inferred target pack `{target_pack_id}` and region `{region_label}` from {region.get('source') or 'planner hints'}."
            if region_label
            else f"Inferred target pack `{target_pack_id or 'none'}`; no named bbox was found."
        ),
    ]
    plan = {
        "planner_result": "custom mission plan ready" if (target_pack_id or region_label) else "custom mission plan needs review",
        "display_name": display_name,
        "use_case_id": use_case_id,
        "target_pack_id": target_pack_id,
        "bbox": region.get("bbox") if region else None,
        "location_context_bbox": region.get("location_context_bbox") if region else None,
        "region_label": region_label,
        "region_source": region.get("source") if region else None,
        "semantic_tags": region.get("semantic_tags") if region else [],
        "suggested_targets": region.get("suggested_targets") if region else [],
        "evidence_guidance": region.get("evidence_guidance") if region else None,
        "location_provider": location_candidate.get("provider"),
        "location_confidence": location_candidate.get("confidence"),
        "start_date": start_date,
        "end_date": end_date,
        "temporal_cadence": temporal_cadence,
        "requested_frame_count": requested_frame_count,
        "cadence_note": cadence_note,
        "task_text": task_text,
        "planner_attempts": planner_attempts,
        "tool_plan": [
            "Use DPhi SimSat first for live evidence during the hackathon run",
            f"Request {temporal_cadence} frame sampling when the runtime supports it",
            "Use sh.txt/Sentinel paths only as development or replay support when configured",
            "Emit compact candidate packets for Ground Validator review before proof packaging",
        ],
        "evidence_limits": [
            safety,
            cadence_note,
            "Do not make legal, casualty, protected-species, or person-level claims from orbital imagery alone.",
        ],
        "confidence": float(decision.get("confidence") or 0.0),
    }
    return {
        "reply": _planner_reply(plan),
        "actions": [],
        "proposals": [_with_request(_custom_mission_proposal(plan), user_msg)],
        "state": _base_state(),
        "suggestions": _suggestions(),
    }


def _wants_agentic_mission_plan(text: str) -> bool:
    if (
        any(token in text for token in ("cv", "visual evidence", "grounding", "bbox"))
        and "mission" not in text
        and not any(token in text for token in ("try", "plan", "attempt", "search", "investigate", "monitor", "review"))
    ):
        return False
    if not any(
        token in text
        for token in (
            "try looking",
            "check",
            "look for",
            "looking for",
            "find",
            "search",
            "investigate",
            "assess",
            "review",
            "monitor",
            "mission plan",
            "plan a mission",
            "attempt",
            "task the satellite",
        )
    ):
        return False
    return not any(
        token in text
        for token in (
            "status",
            "what can",
            "capabilities",
            "help",
            "list replay",
            "show replays",
            "available replay",
        )
    )


def _wants_temporal_area_review(text: str) -> bool:
    temporal_terms = (
        "timelapse",
        "time lapse",
        "last ",
        "past ",
        "previous ",
        "since ",
        "over time",
        "changed",
        "change",
        "new construction",
        "construction",
        "urban expansion",
        "built surface",
        "subdivision",
        "algae",
        "algal bloom",
        "algae bloom",
        "cyanobacteria",
        "chlorophyll",
        "red tide",
        "water quality",
        "ndci",
        "fai",
    )
    request_terms = (
        "show me",
        "check",
        "find",
        "search",
        "look for",
        "looking for",
        "review",
        "monitor",
        "investigate",
        "assess",
    )
    return any(term in text for term in temporal_terms) and any(term in text for term in request_terms)


def _link_state_proposal(connected: bool) -> dict[str, Any]:
    return _proposal(
        kind="set_link_state",
        title="Restore SAT/GND Link" if connected else "Set SAT/GND Link Offline",
        summary=(
            "Restore downlink so queued compact alerts can flush."
            if connected
            else "Set the link offline so satellite alerts queue locally until restore."
        ),
        details={
            "connected": connected,
            "target_state": "online" if connected else "offline",
            "expected_reset": False,
            "state_impact": [
                "Update link state",
                "Write Agent Dialogue status note",
                "Affect queued alert flush behavior",
            ],
        },
        confirm_label="Restore Link" if connected else "Set Offline",
        risk_level="medium",
    )


def _match_location_query(query: str) -> tuple[str, dict[str, Any], dict[str, Any]] | None:
    candidates = resolve_location_candidates(query, LOCATION_TARGETS, limit=1)
    if not candidates or float(candidates[0].get("confidence", 0.0)) < 0.55:
        return None
    candidate = candidates[0]
    location_id = str(candidate["location_id"])
    target = LOCATION_TARGETS[location_id]
    return location_id, target, candidate


def _match_location_target(text: str) -> tuple[str, dict[str, Any], dict[str, Any]] | None:
    return _match_location_query(text)


def _known_location_labels() -> str:
    return ", ".join(target["label"] for target in LOCATION_TARGETS.values())


def _location_semantics(target: dict[str, Any]) -> dict[str, Any]:
    return {
        "location_type": target.get("location_type") or "map context",
        "terrain_context": target.get("terrain_context") or "",
        "mission_context": target.get("mission_context") or target.get("summary") or "",
        "semantic_tags": target.get("semantic_tags") or [],
        "suggested_targets": target.get("suggested_targets") or [],
        "evidence_guidance": target.get("evidence_guidance") or "",
    }


def _wants_stop_mission(text: str) -> bool:
    return any(
        token in text
        for token in (
            "cancel current mission",
            "cancel the current mission",
            "cancel mission",
            "stop current mission",
            "stop the current mission",
            "stop mission",
            "stop the mission",
            "end mission",
            "halt mission",
            "clear current mission",
            "exit replay",
            "leave replay",
        )
    )


def _wants_camera_move(text: str) -> bool:
    return any(
        token in text
        for token in (
            "take me to",
            "tke me to",
            "take us to",
            "fly to",
            "go to",
            "move map",
            "map to",
            "zoom to",
            "camera",
            "coords",
            "coordinates",
            "show me",
        )
    )


def _wants_destination_redirect(text: str) -> bool:
    return any(
        token in text
        for token in (
            "take me to",
            "tke me to",
            "take us to",
            "fly to",
            "go to",
            "map to",
            "zoom to",
        )
    )


def _is_app_panel_redirect(text: str) -> bool:
    return any(
        token in text
        for token in (
            "settings",
            "mission control",
            "logs",
            "inspect",
            "proof",
            "object evidence",
            "agent tab",
            "agents tab",
        )
    )


def _stop_mission_proposal() -> dict[str, Any]:
    mission = _active_mission_or_none()
    return _proposal(
        kind="stop_mission",
        title="Stop Active Mission" if mission else "Confirm Mission Idle",
        summary=(
            "Stop the active mission and pause the visible scan animation until another live mission starts."
            if mission
            else "No active mission is running; confirm the app should remain in idle navigation mode."
        ),
        details={
            "mission_id": mission["id"] if mission else None,
            "expected_reset": False,
            "state_impact": [
                "Mark active mission complete" if mission else "Leave mission state idle",
                "Pause map scan animation",
                "Keep the current map context available for review",
                "Append Agent Dialogue mission note",
            ],
        },
        confirm_label="Stop Mission" if mission else "Keep Idle",
        risk_level="medium" if mission else "low",
    )


def _location_proposal(
    location_id: str,
    target: dict[str, Any],
    stop_first: bool,
    candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mission = _active_mission_or_none()
    label = str(target["label"])
    semantics = _location_semantics(target)
    candidate = candidate or {}
    return _proposal(
        kind="navigate_map_location",
        title=("Stop Mission and Fly Camera: " if stop_first else "Fly Camera: ") + label,
        summary=(
            "Stop the active mission, pause scan animation, and fly the map camera to this location context."
            if stop_first
            else "Fly the map camera to this location context and set a reusable bbox."
        ),
        details={
            "query": candidate.get("query") or label,
            "location_id": location_id,
            "label": label,
            "provider": candidate.get("provider") or "local_registry",
            "feature_type": candidate.get("feature_type") or target.get("location_type") or "map context",
            "confidence": candidate.get("confidence", 0.9),
            "center": candidate.get("center") or target["center"],
            "bbox": candidate.get("bbox") or target["bbox"],
            "preview_tiles": candidate.get("preview_tiles") or [],
            "camera": target["camera"],
            "reason": candidate.get("reason") or target["summary"],
            **semantics,
            "stop_active_mission": stop_first,
            "active_mission_id": mission["id"] if stop_first and mission else None,
            "active_mission_task": mission.get("task_text") if stop_first and mission else None,
            "expected_reset": False,
            "state_impact": [
                "Stop active mission first" if stop_first else "Keep mission state unchanged",
                "Move map camera to target coordinates",
                "Set bbox around target area for Mission Control and visual tools",
                "Show semantic context and suggested evidence targets",
                "Pause scan animation unless a new live mission starts",
            ],
        },
        confirm_label="Stop & Fly Map" if stop_first else "Fly Map",
        risk_level="medium" if stop_first else "low",
    )


def _active_mission_or_none() -> dict[str, Any] | None:
    from core.mission import get_active_mission

    return get_active_mission()


def _split_object_labels(fragment: str) -> list[str]:
    cleanup = fragment.lower()
    cleanup = cleanup.replace("object targets", "")
    cleanup = cleanup.replace("object target", "")
    cleanup = cleanup.replace("objects", "")
    cleanup = cleanup.replace("object", "")
    cleanup = cleanup.replace("current mission", "")
    cleanup = cleanup.replace("this mission", "")
    cleanup = cleanup.replace("mission", "")
    cleanup = cleanup.replace("look for", "")
    cleanup = cleanup.replace("looking for", "")
    cleanup = cleanup.replace("to scan for", "")
    cleanup = cleanup.replace("scan for", "")
    cleanup = cleanup.replace(".", "")
    cleanup = cleanup.replace(";", ",")
    parts = [part.strip(" ,") for part in cleanup.replace(" and ", ",").split(",")]
    return [part for part in parts if part]


def _extract_after_keyword(text: str, keyword: str) -> str | None:
    marker = f"{keyword} "
    if marker not in text:
        return None
    fragment = text.split(marker, 1)[1]
    for stop in (" to ", " from ", " in ", " on "):
        if stop in fragment:
            fragment = fragment.split(stop, 1)[0]
    return fragment.strip()


def _match_add_targets(text: str) -> list[str]:
    if "add " not in text:
        return []
    fragment = _extract_after_keyword(text, "add")
    return _split_object_labels(fragment or "")


def _match_remove_targets(text: str) -> list[str]:
    for keyword in ("remove", "delete", "disable"):
        fragment = _extract_after_keyword(text, keyword)
        if fragment:
            return _split_object_labels(fragment)
    return []


def _match_target_pack(text: str) -> str | None:
    if not any(token in text for token in ("target pack", "object pack", "switch", "set pack")):
        return None
    from core.object_targets import list_target_packs

    best: tuple[int, str] | None = None
    for pack in list_target_packs():
        aliases = {pack["id"], pack["name"].lower(), *pack["id"].replace("_", " ").split()}
        score = sum(1 for alias in aliases if alias and alias in text)
        if score and (best is None or score > best[0]):
            best = (score, pack["id"])
    return best[1] if best else None


def _match_save_pack_name(text: str) -> str | None:
    if "save" not in text or "pack" not in text:
        return None
    for marker in (" called ", " named ", " as "):
        if marker in text:
            name = text.split(marker, 1)[1].strip(" .\"'")
            return name.title() if name else None
    return "Custom Mission Pack"


def _target_update_proposal(add: list[str], remove: list[str]) -> dict[str, Any] | None:
    mission = _active_mission_or_none()
    if not mission:
        return None
    summary_parts = []
    if add:
        summary_parts.append(f"add {', '.join(add)}")
    if remove:
        summary_parts.append(f"remove {', '.join(remove)}")
    summary = " and ".join(summary_parts)
    return _proposal(
        kind="update_mission_targets",
        title="Update Objects to Look For",
        summary=f"Update the active mission object targets: {summary}.",
        details={
            "mission_id": mission["id"],
            "add": add,
            "remove": remove,
            "state_impact": [
                "Update active mission object targets",
                "Refresh visual evidence controls",
                "Use the revised targets for future retained-cell grounding",
                "Attach matching boxes to future proof packets when available",
            ],
        },
        confirm_label="Apply Objects",
        risk_level="low",
    )


def _target_pack_proposal(target_pack_id: str) -> dict[str, Any] | None:
    from core.object_targets import get_target_pack

    mission = _active_mission_or_none()
    pack = get_target_pack(target_pack_id)
    if not mission or not pack:
        return None
    return _proposal(
        kind="set_target_pack",
        title=f"Set Target Pack: {pack['name']}",
        summary=f"Replace the active mission objects with the {pack['name']} target pack.",
        details={
            "mission_id": mission["id"],
            "target_pack_id": pack["id"],
            "object_targets": pack["targets"],
            "state_impact": [
                "Replace active mission object targets",
                "Refresh visual evidence controls",
                "Use this pack for future object evidence scans",
            ],
        },
        confirm_label="Apply Pack",
        risk_level="low",
    )


def _save_target_pack_proposal(name: str) -> dict[str, Any] | None:
    mission = _active_mission_or_none()
    if not mission:
        return None
    object_targets = mission.get("object_targets") or []
    return _proposal(
        kind="save_target_pack",
        title=f"Save Target Pack: {name}",
        summary="Save the active mission object list as a reusable runtime custom pack.",
        details={
            "mission_id": mission["id"],
            "name": name,
            "pack_id": name.lower().replace(" ", "_"),
            "object_targets": object_targets,
            "state_impact": [
                "Write runtime custom target pack",
                "Keep versioned default packs unchanged",
                "Expose the pack through the target pack registry",
            ],
        },
        confirm_label="Save Pack",
        risk_level="low",
    )


def _clear_targets_proposal() -> dict[str, Any] | None:
    mission = _active_mission_or_none()
    if not mission:
        return None
    return _proposal(
        kind="clear_mission_targets",
        title="Clear Mission Object Targets",
        summary="Clear the active mission object targets and target pack id.",
        details={
            "mission_id": mission["id"],
            "state_impact": [
                "Clear active mission object targets",
                "Keep mission bbox and task text unchanged",
                "Future object grounding will require new targets",
            ],
        },
        confirm_label="Clear Objects",
        risk_level="low",
    )


def _match_replay_id(text: str) -> str | None:
    from core.replay import list_seeded_replays

    for alias, replay_id in REPLAY_ALIASES.items():
        if alias in text:
            return replay_id

    catalog = list_seeded_replays()
    best: tuple[int, str] | None = None
    words = {word for word in text.replace("_", " ").replace("-", " ").split() if len(word) >= 3}
    for item in catalog:
        replay_id = str(item.get("replay_id") or "")
        haystack = " ".join(
            str(item.get(key) or "")
            for key in ("replay_id", "title", "description", "summary", "use_case_id")
        ).lower()
        score = sum(1 for word in words if word in haystack)
        if score and (best is None or score > best[0]):
            best = (score, replay_id)
    return best[1] if best else None


def _match_mission_pack(text: str) -> tuple[str, dict[str, Any]] | None:
    best: tuple[int, str, dict[str, Any]] | None = None
    for pack_id, pack in MISSION_PACKS.items():
        aliases = [pack_id, str(pack["label"]).lower(), *pack["aliases"]]
        score = sum(1 for alias in aliases if alias in text)
        if score and (best is None or score > best[0]):
            best = (score, pack_id, pack)
    if not best:
        return None
    return best[1], best[2]


def _match_mission_pack_from_context() -> tuple[str, dict[str, Any]] | None:
    from core.mission import get_active_mission

    mission = get_active_mission()
    if not mission:
        return None

    use_case_id = str(mission.get("use_case_id") or "")
    for pack_id, pack in MISSION_PACKS.items():
        if use_case_id and pack.get("use_case_id") == use_case_id:
            return pack_id, pack

    context_text = " ".join(
        str(mission.get(key) or "")
        for key in ("task_text", "summary", "replay_id")
    ).lower()
    return _match_mission_pack(context_text)


def _is_protected_wildlife_request(text: str) -> bool:
    return any(term in text for term in ("manatee", "manatees"))


def _is_population_or_detection_request(text: str) -> bool:
    population_terms = ("population", "populations", "count", "counts", "census", "survey", "surveys")
    detection_terms = ("find", "look for", "looking for", "locate", "spot", "detect", "search")
    return any(term in text for term in population_terms) or any(term in text for term in detection_terms)


def _match_manatee_habitat_region(text: str) -> dict[str, Any] | None:
    for region in MANATEE_HABITAT_REGIONS:
        if any(alias in text for alias in region["aliases"]):
            return region
    return None


def _manatee_habitat_dates(text: str) -> tuple[str, str]:
    if any(term in text for term in ("winter", "cold", "warm water", "aggregation", "bunch", "bunch up")):
        return "2026-01-01", "2026-02-28"
    return "2026-01-01", "2026-02-28"


def _protected_wildlife_reply(region_label: str | None, *, detection_request: bool) -> str:
    region_text = f" around {region_label}" if region_label else ""
    leading = (
        "I cannot count or locate manatee populations from orbital imagery. This is a hard protected-wildlife mission. "
        if detection_request
        else "Manatee review from orbital imagery is a hard protected-wildlife mission. "
    )
    return (
        f"{leading}"
        "A safer workflow is a habitat/access proxy review, not animal detection: use winter warm-water refuge context, "
        f"seagrass and shallow-water visibility, water clarity/turbidity, shoreline or river access, boat-traffic corridor context, "
        f"and conservation-area boundaries{region_text}. "
        "Use official wildlife survey, telemetry, stranding, or field-observation sources for population or presence claims. "
        "Orbit should return candidate habitat/refuge/access evidence only; do not box individual animals or infer population size from the map."
    )


def _protected_wildlife_pack_proposal(pack_id: str, pack: dict[str, Any]) -> dict[str, Any]:
    proposal = _mission_pack_proposal(pack_id, pack)
    proposal["summary"] = "Hard protected-wildlife request reframed as habitat/access proxy evidence, not animal detection."
    proposal["details"]["planner_result"] = "protected wildlife habitat proxy ready"
    proposal["details"]["workflow_mode"] = "protected_wildlife_proxy_workflow"
    proposal["details"]["difficulty"] = (
        "Manatees are small, often submerged, and protected; current Orbit evidence should review habitat context instead of detecting animals."
    )
    proposal["details"]["planner_attempts"] = [
        "Recognized protected-wildlife request.",
        "Rejected population count, presence, and individual-animal detection claims.",
        "Selected winter habitat/access proxy review with the waterline target pack.",
    ]
    proposal["details"]["evidence_limits"] = [
        "No animal counts, locations, population estimates, or presence claims from orbital imagery.",
        "Use official field survey, telemetry, stranding, or observation sources for wildlife claims.",
        "Keep Orbit output to candidate habitat/refuge/access context.",
    ]
    return proposal


def _protected_wildlife_custom_proposal(user_msg: str, text: str, region: dict[str, Any]) -> dict[str, Any]:
    start_date, end_date = _manatee_habitat_dates(text)
    region_label = str(region["label"])
    task_text = (
        f"Attempt protected-wildlife-safe Florida Manatee Habitat Review around {region_label}. "
        "Treat this as a hard habitat/access proxy mission, not animal detection. Review water extent, water color/turbidity candidates, "
        "water/vegetation boundaries where visible, warm-water refuge context, seagrass/shallow-water visibility, shoreline or river access, "
        "boat-traffic corridor context, and conservation-area boundaries. Do not count or locate individual animals, infer population size, "
        "or claim protected-species presence from orbital imagery."
    )
    plan = {
        "planner_result": "protected wildlife habitat proxy ready",
        "display_name": "Florida Manatee Habitat Proxy Review",
        "use_case_id": "temporal_change_generic",
        "target_pack_id": "waterline",
        "bbox": region["bbox"],
        "region_label": region_label,
        "start_date": start_date,
        "end_date": end_date,
        "task_text": task_text,
        "planner_attempts": [
            "Recognized protected-wildlife request.",
            f"Selected operator-named habitat context `{region_label}`.",
            "Selected winter habitat/access proxy review with the waterline target pack.",
        ],
        "tool_plan": [
            "Use DPhi SimSat first for live map/tasking during the hackathon run",
            "Review waterline, water color, shoreline, and access-context candidates",
            "Package final output as candidate habitat/refuge/access context only",
        ],
        "evidence_limits": [
            "No animal counts, locations, population estimates, or presence claims from orbital imagery.",
            "Use official field survey, telemetry, stranding, or observation sources for wildlife claims.",
            "Keep boxes and summaries at habitat/access-region level.",
        ],
        "confidence": 0.35,
    }
    return _with_request(_custom_mission_proposal(plan), user_msg)


def execute_ground_agent_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    """Execute a whitelisted Ground Agent action after operator confirmation."""
    from core.agent_bus import post_message
    from core.link_state import is_link_connected, set_link_state
    from core.mission import (
        add_mission_targets,
        clear_mission_targets,
        get_active_mission,
        remove_mission_targets,
        set_mission_target_pack,
        start_mission,
        stop_mission,
    )
    from core.object_targets import save_custom_target_pack
    from core.replay import load_seeded_replay, rescan_seeded_replay

    kind = str(proposal.get("kind") or "").strip()
    details = proposal.get("details") if isinstance(proposal.get("details"), dict) else {}
    actions: list[dict[str, Any]] = []

    if kind not in ALLOWED_AGENT_ACTIONS:
        actions.append(_action("confirm_proposal", "error", {"error": "Unsupported Ground Agent action."}))
        return {
            "reply": "I cannot run that proposal. The action is not in the Ground Agent whitelist.",
            "actions": actions,
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if kind == "stop_mission":
        active = get_active_mission()
        stop_mission()
        post_message(
            sender="operator",
            recipient="broadcast",
            msg_type="mission",
            payload={
                "task": "IDLE",
                "mission_id": active.get("id") if active else None,
                "note": (
                    f"[MISSION #{active['id']}] Ground agent stopped the mission. Scan animation paused until a new live mission starts."
                    if active
                    else "[MISSION] Ground agent confirmed idle navigation mode. No active mission was running."
                ),
            },
        )
        actions.append(_action(
            "stop_mission",
            "ok",
            {
                "stopped_mission_id": active.get("id") if active else None,
                "had_active_mission": bool(active),
            },
        ))
        return {
            "reply": (
                "Stopped the active mission. The scan animation is paused until a new live mission starts."
                if active
                else "No active mission was running. The map remains in idle navigation mode."
            ),
            "actions": actions,
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if kind in {"navigate_map", "navigate_map_location"}:
        location_id = str(details.get("location_id") or "").strip()
        target = LOCATION_TARGETS.get(location_id)
        if not target:
            actions.append(_action("navigate_map", "error", {"location_id": location_id, "error": "Unknown location target."}))
            return {
                "reply": "Map navigation cancelled because the proposal did not match a known location target.",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        active = get_active_mission()
        stopped_mission_id = None
        if bool(details.get("stop_active_mission")):
            stopped_mission_id = active.get("id") if active else None
            stop_mission()
            actions.append(_action(
                "stop_mission",
                "ok",
                {
                    "stopped_mission_id": stopped_mission_id,
                    "had_active_mission": bool(active),
                },
            ))
        post_message(
            sender="operator",
            recipient="broadcast",
            msg_type="mission",
            payload={
                "task": "MAP_CAMERA",
                "location_id": location_id,
                "location_type": target.get("location_type"),
                "semantic_tags": target.get("semantic_tags") or [],
                "suggested_targets": target.get("suggested_targets") or [],
                "bbox": target["bbox"],
                "note": f"[MAP] Ground agent camera target set to {target['label']} ({target.get('location_type', 'map context')}).",
            },
        )
        semantics = _location_semantics(target)
        result = {
            "location_id": location_id,
            "label": target["label"],
            "center": target["center"],
            "bbox": target["bbox"],
            "camera": target["camera"],
            "reason": target["summary"],
            **semantics,
            "stopped_mission_id": stopped_mission_id,
        }
        actions.append(_action("navigate_map", "ok", result))
        return {
            "reply": (
                f"Stopped the active mission and moved the map camera to {target['label']}."
                if stopped_mission_id
                else f"Moved the map camera to {target['label']} and set the bbox for review."
            ),
            "actions": actions,
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if kind == "load_replay":
        replay_id = str(details.get("replay_id") or "").strip()
        if not replay_id:
            actions.append(_action("load_replay", "error", {"error": "Missing replay_id."}))
            return {
                "reply": "Replay load cancelled because the proposal did not include a replay id.",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        try:
            result = load_seeded_replay(replay_id)
        except Exception as exc:
            actions.append(_action("load_replay", "error", {"replay_id": replay_id, "error": str(exc)}))
            return {
                "reply": f"Replay load failed for `{replay_id}`: {exc}",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        actions.append(_action("load_replay", "ok", result))
        return {
            "reply": f"Loaded replay `{replay_id}` into Mission, Logs, Inspect, Gallery, and Agent Dialogue.",
            "actions": actions,
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if kind == "rescan_replay":
        replay_id = str(details.get("replay_id") or "").strip()
        if not replay_id:
            actions.append(_action("rescan_replay", "error", {"error": "Missing replay_id."}))
            return {
                "reply": "Replay rescan cancelled because the proposal did not include a replay id.",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        try:
            result = rescan_seeded_replay(replay_id)
        except Exception as exc:
            actions.append(_action("rescan_replay", "error", {"replay_id": replay_id, "error": str(exc)}))
            return {
                "reply": f"Replay rescan failed for `{replay_id}`: {exc}",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        actions.append(_action("rescan_replay", "ok", result))
        return {
            "reply": f"Started live rescan from replay `{replay_id}` using the current runtime and model stack.",
            "actions": actions,
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if kind == "start_custom_mission":
        task_text = str(details.get("task_text") or "").strip()
        if not task_text:
            actions.append(_action("start_custom_mission", "error", {"error": "Missing task_text."}))
            return {
                "reply": "Custom mission launch cancelled because the proposal did not include task text.",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        bbox_value = details.get("bbox")
        bbox = bbox_value if isinstance(bbox_value, list) else None
        start_date = str(details.get("start_date") or "").strip() or None
        end_date = str(details.get("end_date") or "").strip() or None
        use_case_id = str(details.get("use_case_id") or "").strip() or None
        target_pack_id = str(details.get("target_pack_id") or "").strip() or None
        try:
            mission = start_mission(
                task_text=task_text,
                bbox=bbox,
                start_date=start_date,
                end_date=end_date,
                summary=str(details.get("planner_result") or "Ground Agent custom mission plan"),
                use_case_id=use_case_id,
                target_pack_id=target_pack_id,
            )
        except Exception as exc:
            actions.append(_action("start_custom_mission", "error", {"error": str(exc)}))
            return {
                "reply": f"Custom mission plan failed: {exc}",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        post_message(
            sender="operator",
            recipient="broadcast",
            msg_type="mission",
            payload={
                "mission_id": mission["id"],
                "task": mission["task_text"],
                "bbox": mission["bbox"],
                "target_pack_id": mission.get("target_pack_id"),
                "object_targets": mission.get("object_targets") or [],
                "note": f"[MISSION #{mission['id']}] Ground agent launched custom mission plan.",
            },
        )
        actions.append(_action("start_custom_mission", "ok", {"mission": mission, "planner_result": details.get("planner_result")}))
        return {
            "reply": "Launched the custom mission plan. The satellite pruner will attempt the plan and the Ground Validator will review retained evidence at the end.",
            "actions": actions,
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if kind == "start_mission_pack":
        pack_id = str(details.get("pack_id") or "").strip()
        pack = MISSION_PACKS.get(pack_id)
        if not pack:
            actions.append(_action("start_mission_pack", "error", {"pack_id": pack_id, "error": "Unknown pack."}))
            return {
                "reply": "Mission pack launch cancelled because the proposal did not match a known pack.",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        try:
            mission = start_mission(
                task_text=pack["task_text"],
                bbox=pack["bbox"],
                start_date=pack["start_date"],
                end_date=pack["end_date"],
                use_case_id=pack["use_case_id"],
                target_pack_id=pack.get("target_pack_id"),
            )
        except Exception as exc:
            actions.append(_action("start_mission_pack", "error", {"pack_id": pack_id, "error": str(exc)}))
            return {
                "reply": f"Mission pack `{pack_id}` failed: {exc}",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        post_message(
            sender="operator",
            recipient="broadcast",
            msg_type="mission",
            payload={
                "mission_id": mission["id"],
                "task": mission["task_text"],
                "bbox": mission["bbox"],
                "target_pack_id": mission.get("target_pack_id"),
                "object_targets": mission.get("object_targets") or [],
                "note": f"[MISSION #{mission['id']}] Ground agent launched pack: {pack['label']}",
            },
        )
        actions.append(_action("start_mission_pack", "ok", {"pack_id": pack_id, "mission": mission}))
        return {
            "reply": f"Launched mission pack `{pack_id}`. The satellite pruner will scan the pack bbox and downlink compact alerts only.",
            "actions": actions,
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if kind == "update_mission_targets":
        mission_id = details.get("mission_id")
        if not isinstance(mission_id, int):
            actions.append(_action("update_mission_targets", "error", {"error": "Missing mission_id."}))
            return {
                "reply": "Object target update cancelled because the proposal did not include a mission id.",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        add_labels = [str(label).strip() for label in details.get("add", []) if str(label).strip()]
        remove_labels = [str(label).strip() for label in details.get("remove", []) if str(label).strip()]
        try:
            mission = add_mission_targets(mission_id, add_labels) if add_labels else _base_state()["mission"]
            if remove_labels:
                mission = remove_mission_targets(mission_id, remove_labels)
        except Exception as exc:
            actions.append(_action("update_mission_targets", "error", {"mission_id": mission_id, "error": str(exc)}))
            return {
                "reply": f"Mission object target update failed: {exc}",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        post_message(
            sender="operator",
            recipient="broadcast",
            msg_type="mission",
            payload={
                "mission_id": mission_id,
                "target_pack_id": mission.get("target_pack_id") if isinstance(mission, dict) else None,
                "object_targets": mission.get("object_targets", []) if isinstance(mission, dict) else [],
                "note": f"[MISSION #{mission_id}] Ground agent updated object targets.",
            },
        )
        actions.append(_action("update_mission_targets", "ok", {"mission": mission, "add": add_labels, "remove": remove_labels}))
        return {
            "reply": "Updated the active mission object targets.",
            "actions": actions,
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if kind == "set_target_pack":
        mission_id = details.get("mission_id")
        target_pack_id = str(details.get("target_pack_id") or "").strip()
        if not isinstance(mission_id, int) or not target_pack_id:
            actions.append(_action("set_target_pack", "error", {"error": "Missing mission_id or target_pack_id."}))
            return {
                "reply": "Target pack update cancelled because the proposal is missing required details.",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        try:
            mission = set_mission_target_pack(mission_id, target_pack_id)
        except Exception as exc:
            actions.append(_action("set_target_pack", "error", {"mission_id": mission_id, "target_pack_id": target_pack_id, "error": str(exc)}))
            return {
                "reply": f"Target pack update failed: {exc}",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        actions.append(_action("set_target_pack", "ok", {"mission": mission, "target_pack_id": target_pack_id}))
        return {
            "reply": f"Applied target pack `{target_pack_id}` to the active mission.",
            "actions": actions,
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if kind == "save_target_pack":
        mission_id = details.get("mission_id")
        name = str(details.get("name") or "Custom Mission Pack").strip()
        pack_id = str(details.get("pack_id") or name.lower().replace(" ", "_")).strip()
        object_targets = details.get("object_targets")
        if not isinstance(mission_id, int) or not isinstance(object_targets, list) or not object_targets:
            actions.append(_action("save_target_pack", "error", {"error": "No mission object targets to save."}))
            return {
                "reply": "Custom pack save cancelled because the active mission has no object targets.",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        try:
            pack = save_custom_target_pack(
                {
                    "id": pack_id,
                    "name": name,
                    "description": "Runtime custom object target pack saved by Ground Agent.",
                    "targets": object_targets,
                }
            )
        except Exception as exc:
            actions.append(_action("save_target_pack", "error", {"pack_id": pack_id, "error": str(exc)}))
            return {
                "reply": f"Custom target pack save failed: {exc}",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        actions.append(_action("save_target_pack", "ok", {"pack": pack, "mission_id": mission_id}))
        return {
            "reply": f"Saved `{pack['name']}` as a runtime custom target pack.",
            "actions": actions,
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if kind == "clear_mission_targets":
        mission_id = details.get("mission_id")
        if not isinstance(mission_id, int):
            actions.append(_action("clear_mission_targets", "error", {"error": "Missing mission_id."}))
            return {
                "reply": "Object target clear cancelled because the proposal did not include a mission id.",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        try:
            mission = clear_mission_targets(mission_id)
        except Exception as exc:
            actions.append(_action("clear_mission_targets", "error", {"mission_id": mission_id, "error": str(exc)}))
            return {
                "reply": f"Object target clear failed: {exc}",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        actions.append(_action("clear_mission_targets", "ok", {"mission": mission}))
        return {
            "reply": "Cleared active mission object targets.",
            "actions": actions,
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if kind == "set_link_state":
        if not isinstance(details.get("connected"), bool):
            actions.append(_action("set_link_state", "error", {"error": "Missing boolean connected state."}))
            return {
                "reply": "Link-state change cancelled because the proposal did not include a boolean connected value.",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }

        connected = details["connected"]
        was_connected = is_link_connected()
        set_link_state(connected)
        post_message(
            sender="operator",
            recipient="broadcast",
            msg_type="status",
            payload={
                "connected": connected,
                "note": (
                    "Ground agent restored the SAT/GND downlink."
                    if connected
                    else "Ground agent set the SAT/GND downlink offline."
                ),
            },
        )
        actions.append(_action("set_link_state", "ok", {"connected": connected, "was_connected": was_connected}))
        return {
            "reply": (
                "SAT/GND link restored. Queued compact alerts can now flush through the ground validator."
                if connected
                else "SAT/GND link is offline. Satellite flags will remain unread in the agent bus until restore."
            ),
            "actions": actions,
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    # Defensive guard for future whitelist edits without a dispatch branch.
    actions.append(_action("confirm_proposal", "error", {"error": "Unsupported Ground Agent action."}))
    return {
        "reply": "I cannot run that proposal. The action is not in the Ground Agent dispatcher.",
        "actions": actions,
        "state": _base_state(),
        "suggestions": _suggestions(),
    }


def execute_ground_agent_chat(user_msg: str) -> dict[str, Any]:
    """Answer the operator and execute a small set of local ground-agent tools."""
    text = user_msg.lower().strip()
    actions: list[dict[str, Any]] = []

    if not text:
        return {
            "reply": "No message received.",
            "actions": actions,
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if _is_protected_wildlife_request(text):
        pack_id = "florida_manatee_habitat_review"
        pack = MISSION_PACKS[pack_id]
        region = _match_manatee_habitat_region(text)
        detection_request = _is_population_or_detection_request(text)
        proposal = (
            _protected_wildlife_custom_proposal(user_msg, text, region)
            if region
            else _with_request(_protected_wildlife_pack_proposal(pack_id, pack), user_msg)
        )
        return {
            "reply": _protected_wildlife_reply(str(region["label"]) if region else None, detection_request=detection_request),
            "actions": actions,
            "proposals": [proposal],
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if "replay" in text and any(k in text for k in ("list", "show", "available", "catalog")):
        catalog = _catalog_summary()
        actions.append(_action("list_replays", "ok", {"replays": catalog}))
        return {
            "reply": f"{len(catalog)} replay entries are available. Ask me to load or rescan one by name.",
            "actions": actions,
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if any(k in text for k in ("restore link", "restore downlink", "restore the downlink", "link online", "reconnect", "downlink online")):
        return {
            "reply": "I can restore the SAT/GND link. Review the state change before I apply it.",
            "actions": [],
            "proposals": [_with_request(_link_state_proposal(True), user_msg)],
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if any(k in text for k in ("link offline", "sever link", "drop link", "blackout", "eclipse")):
        return {
            "reply": "I can set the SAT/GND link offline for queue proof. Review the state change before I apply it.",
            "actions": [],
            "proposals": [_with_request(_link_state_proposal(False), user_msg)],
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    semantics = match_ground_agent_semantics(user_msg)
    if semantics and semantics.get("intent") == "ambiguous_location":
        query = str((semantics.get("arguments") or {}).get("query") or "that place")
        actions.append(_action("resolve_location", "error", {"error": "Ambiguous location.", "query": query}))
        return {
            "reply": (
                f"`{query}` is ambiguous for map navigation. Please clarify the country, state, or a vetted target. "
                f"Known destinations: {_known_location_labels()}."
            ),
            "actions": actions,
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if semantics and semantics.get("tool") == "resolve_location" and not _wants_temporal_area_review(text):
        query = str((semantics.get("arguments") or {}).get("query") or "").strip()
        location_match = _match_location_query(query) if query else None
        if location_match:
            location_id, target, candidate = location_match
            active_mission = _active_mission_or_none()
            stop_first = _wants_stop_mission(text) or (active_mission is not None and _wants_destination_redirect(text))
            return {
                "reply": (
                    f"You have an active mission. I can stop it and fly the camera to {target['label']} for this new destination. Review before I apply it."
                    if stop_first
                    else f"I can resolve `{query}` to {target['label']}, preview the bbox, and move the map only after confirmation."
                ),
                "actions": [],
                "proposals": [_with_request(_location_proposal(location_id, target, stop_first, candidate), user_msg)],
                "state": _base_state(),
                "suggestions": _suggestions(),
            }

    if _wants_temporal_area_review(text):
        plan_response = _build_agentic_mission_plan(user_msg, text)
        if plan_response:
            return plan_response

    location_match = _match_location_target(text)
    if location_match and _wants_camera_move(text):
        location_id, target, candidate = location_match
        active_mission = _active_mission_or_none()
        stop_first = _wants_stop_mission(text) or (active_mission is not None and _wants_destination_redirect(text))
        return {
            "reply": (
                f"You have an active mission. I can stop it and fly the camera to {target['label']} for this new destination. Review before I apply it."
                if stop_first
                else f"I can fly the map camera to {target['label']} and set the bbox for review."
            ),
            "actions": [],
            "proposals": [_with_request(_location_proposal(location_id, target, stop_first, candidate), user_msg)],
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if _wants_destination_redirect(text) and not _is_app_panel_redirect(text):
        actions.append(_action("navigate_map", "error", {"error": "No resolved map destination.", "known_destinations": list(LOCATION_TARGETS)}))
        return {
            "reply": f"I could not resolve that destination to a vetted map target yet. Known destinations: {_known_location_labels()}.",
            "actions": actions,
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if _wants_stop_mission(text):
        return {
            "reply": "I can stop the active mission and pause the visible scan animation. Review before I apply it.",
            "actions": [],
            "proposals": [_with_request(_stop_mission_proposal(), user_msg)],
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if any(token in text for token in ("clear objects", "clear object targets", "clear mission targets")):
        proposal = _clear_targets_proposal()
        if not proposal:
            actions.append(_action("clear_mission_targets", "error", {"error": "No active mission."}))
            return {
                "reply": "Start or load a mission before clearing object targets.",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        return {
            "reply": "I can clear the active mission object targets. Review before I apply it.",
            "actions": [],
            "proposals": [_with_request(proposal, user_msg)],
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    save_pack_name = _match_save_pack_name(text)
    if save_pack_name:
        proposal = _save_target_pack_proposal(save_pack_name)
        if not proposal:
            actions.append(_action("save_target_pack", "error", {"error": "No active mission."}))
            return {
                "reply": "Start or load a mission before saving a target pack.",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        return {
            "reply": "I can save the active object list as a reusable target pack. Review before I write it.",
            "actions": [],
            "proposals": [_with_request(proposal, user_msg)],
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    target_pack_id = _match_target_pack(text)
    if target_pack_id:
        proposal = _target_pack_proposal(target_pack_id)
        if not proposal:
            actions.append(_action("set_target_pack", "error", {"error": "No active mission or unknown target pack."}))
            return {
                "reply": "I could not apply that target pack. Start a mission first, then choose a known pack.",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        return {
            "reply": f"I found target pack `{target_pack_id}`. Review before I apply it.",
            "actions": [],
            "proposals": [_with_request(proposal, user_msg)],
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    add_targets = _match_add_targets(text)
    remove_targets = _match_remove_targets(text)
    if add_targets or remove_targets:
        proposal = _target_update_proposal(add_targets, remove_targets)
        if not proposal:
            actions.append(_action("update_mission_targets", "error", {"error": "No active mission."}))
            return {
                "reply": "Start or load a mission before editing object targets.",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        return {
            "reply": "I can update the active mission object targets. Review before I apply it.",
            "actions": [],
            "proposals": [_with_request(proposal, user_msg)],
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if "replay" in text and any(k in text for k in ("rescan", "rerun", "run live", "current runtime")):
        replay_id = _match_replay_id(text)
        if not replay_id:
            actions.append(_action("rescan_replay", "error", {"error": "No matching replay found."}))
            return {
                "reply": "I could not match that replay. Ask for 'list replays' or name Rondonia, Manchar, Atacama, Greenland, Georgia, Delhi, or Singapore.",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        return {
            "reply": f"I found replay `{replay_id}`. Review the rescan before starting a new runtime pass.",
            "actions": [],
            "proposals": [_with_request(_replay_proposal("rescan_replay", replay_id), user_msg)],
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if "replay" in text and (
        any(k in text for k in ("load", "open", "request", "hydrate", "switch", "run"))
        or _match_replay_id(text)
    ):
        replay_id = _match_replay_id(text)
        if not replay_id:
            actions.append(_action("load_replay", "error", {"error": "No matching replay found."}))
            return {
                "reply": "I could not match that replay. Ask for 'list replays' or name Rondonia, Manchar, Atacama, Greenland, Georgia, Delhi, or Singapore.",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        return {
            "reply": f"I found a replay candidate: `{replay_id}`. Review before loading it into the app.",
            "actions": [],
            "proposals": [_with_request(_replay_proposal("load_replay", replay_id), user_msg)],
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if _wants_agentic_mission_plan(text):
        plan_response = _build_agentic_mission_plan(user_msg, text)
        if plan_response:
            return plan_response

    wants_mission = (
        any(k in text for k in ("mission pack", "run mission", "start mission", "launch mission", "task satellite"))
        or ("mission" in text and _match_mission_pack(text) is not None)
    )
    if wants_mission:
        match = _match_mission_pack(text) or _match_mission_pack_from_context()
        if not match:
            packs = ", ".join(pack["label"] for pack in MISSION_PACKS.values())
            actions.append(_action("start_mission_pack", "error", {"available_packs": list(MISSION_PACKS)}))
            return {
                "reply": f"I could not match a mission pack. Available packs: {packs}.",
                "actions": actions,
                "state": _base_state(),
                "suggestions": _suggestions(),
            }
        pack_id, pack = match
        return {
            "reply": f"I matched mission pack `{pack_id}`. Review the mission before launch.",
            "actions": [],
            "proposals": [_with_request(_mission_pack_proposal(pack_id, pack), user_msg)],
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    return {
        "reply": get_ground_agent_reply(user_msg),
        "actions": actions,
        "state": _base_state(),
        "suggestions": _suggestions(),
    }


def _suggestions() -> list[str]:
    return [
        "Run Florida fire drought mission",
        "Run critical minerals mission",
        "Take me to the Bronx NY",
        "Stop mission and fly to Bull Creek FL",
        "List replays",
    ]


def get_ground_agent_reply(user_msg: str) -> str:
    """
    Local intent reply for the Ground Station operator.
    Reads live DB state and explains the visible UI without external services.
    """
    from core.agent_bus import get_bus_stats, list_pins
    from core.config import REGION
    from core.metrics import read_metrics_summary
    from core.queue import get_alert_counts

    counts = get_alert_counts()
    metrics = read_metrics_summary()
    msg = user_msg.lower().strip()

    if any(k in msg for k in ("operator playbook", "guide me", "walk me through", "what can you do", "capabilities")):
        return (
            "Operator playbook: start a mission pack or load a replay, tune the mission object targets, "
            "run visual evidence on the selected bbox, inspect retained alert packets, and open Proof Mode for compact JSON/downlink accounting. "
            "Mutating actions are proposal-based: I show state impact first, then wait for confirmation."
        )

    if any(k in msg for k in ("agent status", "satellite agent", "sat agent", "ground agent status", "satellite pruner", "ground validator")):
        from core.agent_bus import get_bus_stats
        from core.link_state import is_link_connected
        from core.mission import get_active_mission

        stats = get_bus_stats()
        mission = get_active_mission()
        mission_label = (
            f"mission #{mission['id']} ({mission.get('mission_mode', 'live')})"
            if mission
            else "no active mission"
        )
        return (
            f"Satellite Pruner: {metrics.get('total_cells_scanned', 0)} cell evaluations, "
            f"latest discard ratio {metrics.get('latest_discard_ratio', 0):.1%}. "
            f"Ground Validator: {counts['total_alerts']} alert packets, {stats['unread_messages']} unread bus messages. "
            f"Link: {'online' if is_link_connected() else 'offline'}. Active context: {mission_label}."
        )

    if any(k in msg for k in ("status", "overview", "summary", "how many", "report")):
        return (
            f"Ground Station nominal. Downlinked {counts['total_alerts']} alert packets "
            f"({counts.get('total_payload_bytes', 0)} bytes total payload). "
            f"Bandwidth saved vs raw imagery: {metrics.get('total_bandwidth_saved_mb', 0):.1f} MB. "
            f"Latest discard ratio: {metrics.get('latest_discard_ratio', 0):.1%}. "
            f"Completed scan cycles: {metrics.get('total_cycles_completed', 0)}."
        )

    if any(k in msg for k in ("bandwidth", "saving", "downlink", "payload", "bytes")):
        saved = metrics.get("total_bandwidth_saved_mb", 0)
        alerts = counts["total_alerts"]
        raw_mb = alerts * 5.0
        return (
            "Bandwidth triage active. Orbital agent filtered raw imagery down to "
            f"{counts.get('total_payload_bytes', 0)} bytes of alert packets. "
            f"Estimated {saved:.1f} MB saved vs raw downlink "
            f"({alerts} alerts x about 5 MB/frame = about {raw_mb:.0f} MB avoided). "
            "This is the onboard compression story: raw frame stays local, compact JSON moves."
        )

    if any(k in msg for k in ("discard", "ratio", "filter", "threw", "pruned", "ignored")):
        ratio = metrics.get("latest_discard_ratio", 0)
        total = metrics.get("total_cells_scanned", 0)
        alerts = counts["total_alerts"]
        return (
            f"Discard ratio: {ratio:.1%}. Of {total} cells evaluated by the orbital pruner, "
            f"{alerts} crossed the anomaly threshold and were downlinked. "
            "The rest were rejected onboard before consuming downlink."
        )

    if any(k in msg for k in ("alert", "anomal", "flagged", "deforest", "detection")):
        examples = metrics.get("flagged_examples", [])
        if examples:
            top = examples[0]
            return (
                f"{counts['total_alerts']} alert packets downlinked. "
                f"Latest flagged cell: {top.get('cell_id', 'N/A')} "
                f"(change score {top.get('change_score', 0):.3f}, "
                f"confidence {top.get('confidence', 0):.3f}). "
                "Select an alert to inspect temporal imagery and local evidence reasoning."
            )
        return f"{counts['total_alerts']} alerts in queue. Click a flagged cell on the map to inspect it."

    if any(k in msg for k in ("scan", "progress", "cycle", "grid", "h3", "hex", "cell")):
        return (
            "Grid scan active over the selected mission area. "
            f"Completed {metrics.get('total_cycles_completed', 0)} cycles and "
            f"{metrics.get('total_cells_scanned', 0)} cell evaluations. "
            "The satellite pruner scores cells first and only promotes retained evidence packets."
        )

    if any(k in msg for k in ("point out", "where are", "show me tools", "what parts of the app do")):
        from core.agent_bus import upsert_pin

        upsert_pin("ground", -1.5, -57.5, "Mission Control", "Operator tool located on the right mission rail.")
        upsert_pin("ground", -3.119, -63.5, "Evidence Gallery", "Logs and Inspect expose retained alert evidence.")
        upsert_pin("ground", -5.5, -60.025, "Agent Dialogue", "Agents tab shows the SAT/GND bus and action chat.")
        return "I placed Ground Agent pins for Mission Control, Evidence Gallery, and Agent Dialogue."

    if any(k in msg for k in ("map", "what am i", "looking at", "satellite imagery", "basemap", "esri")):
        return (
            "The map shows a satellite basemap for operator context, the active scan grid, and actor pins. "
            "Scoring comes from the configured observation provider and evidence packet fields, not from the basemap alone."
        )

    if any(k in msg for k in ("pin", "marker", "dot", "symbol", "icon", "drop a")):
        pins = list_pins()
        sat_pins = sum(1 for p in pins if p["pin_type"] == "satellite")
        gnd_pins = sum(1 for p in pins if p["pin_type"] == "ground")
        opr_pins = sum(1 for p in pins if p["pin_type"] == "operator")
        return (
            "Map pin system: satellite flags, ground confirmations, and operator markers. "
            f"Active pins: {sat_pins} satellite, {gnd_pins} ground, {opr_pins} operator. "
            "Shift-click the map to drop an operator marker."
        )

    if any(k in msg for k in ("validation", "inspect", "panel", "before", "after", "chip", "imagery")):
        return (
            "Inspect opens when you select a retained alert. It shows cell id, event signature, "
            "imagery references, band/proxy deltas, local evidence analysis, and export controls."
        )

    if any(k in msg for k in ("cv", "visual evidence", "grounding", "bbox", "boats", "homes", "flaring", "dark smoke")):
        return (
            "Visual evidence tools can search the selected bbox for mission targets or operator prompts such as homes, boats, "
            "possible flaring, and dark smoke. Target packs make those object prompts reusable. Treat those boxes as candidate evidence until they are backed "
            "by model provenance, replay context, or operator review; fallback vision never confirms a detection."
        )

    if any(k in msg for k in ("temporal", "ndvi", "nbr", "nir", "band", "spectral", "delta", "change score")):
        return (
            "Temporal evidence compares observation windows and records the scoring basis explicitly. "
            "SimSat runtime scoring is labeled proxy_bands; replay or direct Sentinel lanes can carry multispectral metadata."
        )

    if any(k in msg for k in ("agent dialogue", "dialogue", "bus", "message bus", "agents talking", "sat gnd")):
        stats = get_bus_stats()
        return (
            "The Agent Dialogue Bus is a SQLite-backed queue connecting Satellite Pruner, Ground Validator, and operator actions. "
            f"Current bus: {stats['total_messages']} total messages, {stats['unread_messages']} unread."
        )

    if any(k in msg for k in ("settings", "gear", "provider", "config", "credential", "sentinel hub")):
        return (
            "Settings shows provider status, SimSat readiness, credential state, trained model status, and depth adapter status. "
            "DPhi SimSat is the primary hackathon runtime lane."
        )

    if any(k in msg for k in ("architect", "how", "work", "pipeline", "lfm", "model")):
        return (
            "Pipeline: Satellite Pruner scans cells, rejects noise, and emits retained evidence packets. "
            "Ground Validator reviews bbox, source, temporal or proxy scores, confidence, and visual references. "
            "Liquid reasoning is applied to the retained evidence packet unless a manifest-resolved multimodal bundle is installed."
        )

    if any(k in msg for k in ("provider", "imagery", "simsat", "sentinel", "esri", "image")):
        return (
            f"Active observation mode: {REGION.observation_mode}. "
            "Provider fallback order: simsat_sentinel -> simsat_mapbox -> sentinelhub_direct -> nasa_api_direct -> cached proxy loader. "
            "SimSat evidence is labeled separately from cached replay and fallback paths."
        )

    if any(k in msg for k in ("help", "command", "what can", "capabilit", "list")):
        return (
            "Ground Agent can answer status, bandwidth, discard ratio, alerts, scan progress, map, pins, validation, "
            "temporal evidence, agent bus, settings, architecture, and provider questions. "
            "It can also list/load/rescan replays, launch mission packs, edit mission object targets, save target packs, "
            "toggle the SAT/GND link, stop missions, and fly the map camera to known targets such as Bull Creek, FL."
        )

    return (
        f"Ground Station online. {counts['total_alerts']} alerts downlinked, "
        f"{metrics.get('total_bandwidth_saved_mb', 0):.1f} MB saved. "
        "Ask for status, list replays, load a replay, run a mission pack, or toggle the link."
    )
