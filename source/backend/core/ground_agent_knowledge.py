"""Ground Station knowledge base and local action controller."""

from __future__ import annotations

from typing import Any


MISSION_PACKS: dict[str, dict[str, Any]] = {
    "deforestation_amazon": {
        "label": "Amazon frontier deforestation",
        "aliases": ["amazon", "deforestation", "forest", "rondonia", "canopy"],
        "use_case_id": "deforestation",
        "task_text": "Scan the Amazon frontier near Rondonia for new canopy loss against the same-season baseline.",
        "bbox": [-62.1, -9.8, -61.4, -9.1],
        "start_date": "2024-06-01",
        "end_date": "2025-06-01",
    },
    "maritime_suez": {
        "label": "Suez maritime queue",
        "aliases": ["maritime", "suez", "vessel", "ship", "queue", "dark vessel"],
        "use_case_id": "maritime_activity",
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
        "label": "Atacama mining expansion",
        "aliases": ["mining", "mine", "atacama", "open pit", "bare earth"],
        "use_case_id": "mining_expansion",
        "task_text": "Detect Atacama open-pit mining expansion and separate persistent bare earth from seasonal vegetation loss.",
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
        "task_text": "Review the Highway 82 wildfire near Atkinson and Waynesville, Georgia for smoke, burn scar, and vegetation stress.",
        "bbox": [-81.916, 31.143, -81.756, 31.303],
        "start_date": "2026-04-01",
        "end_date": "2026-04-28",
    },
}

REPLAY_ALIASES: dict[str, str] = {
    "rondonia": "rondonia_frontier_judge",
    "amazon": "rondonia_frontier_judge",
    "frontier": "rondonia_frontier_judge",
    "deforestation": "rondonia_frontier_judge",
    "flood": "manchar_flood_replay",
    "manchar": "manchar_flood_replay",
    "pakistan": "manchar_flood_replay",
    "mining": "atacama_mining_replay",
    "atacama": "atacama_mining_replay",
    "ice": "greenland_ice_snow_extent_replay",
    "snow": "greenland_ice_snow_extent_replay",
    "greenland": "greenland_ice_snow_extent_replay",
    "wildfire": "georgia_wildfire_replay",
    "fire": "georgia_wildfire_replay",
    "georgia": "georgia_wildfire_replay",
    "urban": "delhi_urban_replay",
    "delhi": "delhi_urban_replay",
    "maritime": "singapore_maritime_replay",
    "singapore": "singapore_maritime_replay",
    "vessel": "singapore_maritime_replay",
}


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


def execute_ground_agent_chat(user_msg: str) -> dict[str, Any]:
    """Answer the operator and execute a small set of local ground-agent tools."""
    from core.agent_bus import post_message
    from core.link_state import is_link_connected, set_link_state
    from core.mission import start_mission
    from core.replay import load_seeded_replay, rescan_seeded_replay

    text = user_msg.lower().strip()
    actions: list[dict[str, Any]] = []

    if not text:
        return {
            "reply": "No message received.",
            "actions": actions,
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

    if any(k in text for k in ("restore link", "link online", "reconnect", "downlink online")):
        was_connected = is_link_connected()
        set_link_state(True)
        post_message(
            sender="operator",
            recipient="broadcast",
            msg_type="status",
            payload={"connected": True, "note": "Ground agent restored the SAT/GND downlink."},
        )
        actions.append(_action("set_link_state", "ok", {"connected": True, "was_connected": was_connected}))
        return {
            "reply": "SAT/GND link restored. Queued compact alerts can now flush through the ground validator.",
            "actions": actions,
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    if any(k in text for k in ("link offline", "sever link", "drop link", "blackout", "eclipse")):
        was_connected = is_link_connected()
        set_link_state(False)
        post_message(
            sender="operator",
            recipient="broadcast",
            msg_type="status",
            payload={"connected": False, "note": "Ground agent set the SAT/GND downlink offline."},
        )
        actions.append(_action("set_link_state", "ok", {"connected": False, "was_connected": was_connected}))
        return {
            "reply": "SAT/GND link is offline. Satellite flags will remain unread in the agent bus until restore.",
            "actions": actions,
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

    if "replay" in text and any(k in text for k in ("load", "open", "request", "hydrate", "switch")):
        replay_id = _match_replay_id(text)
        if not replay_id:
            actions.append(_action("load_replay", "error", {"error": "No matching replay found."}))
            return {
                "reply": "I could not match that replay. Ask for 'list replays' or name Rondonia, Manchar, Atacama, Greenland, Georgia, Delhi, or Singapore.",
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
            "reply": f"Loaded replay `{replay_id}` into Mission, Logs, Inspect, and Agent Dialogue.",
            "actions": actions,
            "state": _base_state(),
            "suggestions": _suggestions(),
        }

    wants_mission = any(k in text for k in ("mission pack", "run mission", "start mission", "launch mission", "task satellite"))
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
        try:
            mission = start_mission(
                task_text=pack["task_text"],
                bbox=pack["bbox"],
                start_date=pack["start_date"],
                end_date=pack["end_date"],
                use_case_id=pack["use_case_id"],
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

    return {
        "reply": get_ground_agent_reply(user_msg),
        "actions": actions,
        "state": _base_state(),
        "suggestions": _suggestions(),
    }


def _suggestions() -> list[str]:
    return [
        "List replays",
        "Load Manchar flood replay",
        "Run maritime mission pack",
        "Set link offline",
        "Restore link",
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
            "Visual evidence tools can search the selected bbox for operator targets such as homes, boats, "
            "possible flaring, and dark smoke. Treat those boxes as candidate evidence until they are backed "
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
            "Settings shows provider status, SimSat readiness, credential state, optional model status, and depth adapter status. "
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
            "It can also list/load/rescan replays, launch mission packs, and toggle the SAT/GND link."
        )

    return (
        f"Ground Station online. {counts['total_alerts']} alerts downlinked, "
        f"{metrics.get('total_bandwidth_saved_mb', 0):.1f} MB saved. "
        "Ask for status, list replays, load a replay, run a mission pack, or toggle the link."
    )
