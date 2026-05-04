"""Product-specific Ground Agent semantic routing helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


SEMANTICS_EXAMPLE_PATH = Path(__file__).resolve().parents[1] / "data" / "ground_agent_tool_semantics.example.jsonl"
SEMANTICS_LOCAL_PATH = Path(__file__).resolve().parents[1] / "data" / "ground_agent_tool_semantics.local.jsonl"


def normalize_semantic_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def load_ground_agent_semantic_examples(*, include_local: bool = False) -> list[dict[str, Any]]:
    """Load local product routing examples for tests and optional guidance."""
    examples: list[dict[str, Any]] = []
    paths = [SEMANTICS_EXAMPLE_PATH]
    if include_local:
        paths.append(SEMANTICS_LOCAL_PATH)

    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
                if not isinstance(record, dict):
                    raise ValueError(f"Ground Agent semantics row must be an object at {path}:{line_number}.")
                examples.append(record)
    return examples


def _extract_location_query(text: str) -> str | None:
    patterns = (
        r"\b(?:take me to|tke me to|take us to|fly to|go to|move the map to|map to|zoom to|center on|open|show me|find|check)\s+(?P<query>.+)$",
        r"\bscan\s+(?P<query>.+?)\s+(?:for|over|with)\b",
        r"\brun\s+(?:a\s+)?mission\s+over\s+(?P<query>.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        query = match.group("query").strip(" ,.?")
        query = re.sub(r"^(?:the|a|an)\s+", "", query)
        query = re.split(r"\s+(?:for|with|using|in the last|over the last|during)\b", query, maxsplit=1)[0]
        query = query.strip(" ,.?")
        if query:
            return query
    return None


def match_ground_agent_semantics(user_msg: str) -> dict[str, Any] | None:
    """
    Classify product-specific operator language into an intent and normalized arguments.

    Deterministic rules are the runtime source of truth. The JSONL examples are
    guidance/eval fixtures and are not used as a geography database.
    """
    text = normalize_semantic_text(user_msg)
    if not text:
        return None

    if any(token in text for token in ("restore link", "restore downlink", "restore the downlink", "link online", "reconnect", "downlink online")):
        return {"intent": "set_link_state", "tool": "set_link_state", "arguments": {"connected": True}}
    if any(token in text for token in ("link offline", "sever link", "drop link", "blackout", "eclipse")):
        return {"intent": "set_link_state", "tool": "set_link_state", "arguments": {"connected": False}}
    if "replay" in text and any(token in text for token in ("load", "open", "request", "hydrate", "switch", "run")):
        return {"intent": "load_replay", "tool": "load_replay", "arguments": {"replay_hint": user_msg.strip()}}
    if any(token in text for token in ("mission pack", "run mission pack", "start mission pack")):
        return {"intent": "start_mission_pack", "tool": "start_mission_pack", "arguments": {"pack_hint": user_msg.strip()}}

    query = _extract_location_query(text)
    if not query:
        return None

    if query == "georgia":
        return {
            "intent": "ambiguous_location",
            "tool": "resolve_location",
            "arguments": {"query": "georgia"},
        }

    mission_words = (
        "scan",
        "mission",
        "timelapse",
        "time lapse",
        "change",
        "changes",
        "construction",
        "monitor",
        "algae",
        "algal",
        "bloom",
        "cyanobacteria",
        "chlorophyll",
        "red tide",
        "water quality",
    )
    intent = "prepare_location_mission" if any(word in text for word in mission_words) else "navigate_map_location"
    return {
        "intent": intent,
        "tool": "resolve_location",
        "arguments": {
            "query": query,
            "country_hint": "US" if any(token in text for token in (" ny", " fl", " florida", " bronx", " davenport", " okeechobee")) else None,
        },
    }
