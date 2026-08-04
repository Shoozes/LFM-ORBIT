"""Stable identity helpers for evidence used in anomaly confirmation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


_IDENTITY_FIELDS = (
    "acquisition_key",
    "acquisition_id",
    "source_asset_id",
    "frame_hash",
    "before_frame_hash",
    "after_frame_hash",
)


def build_acquisition_key(evidence: Mapping[str, Any]) -> str:
    """Return a deterministic key for one provider acquisition/evidence pair.

    Providers can supply an acquisition or frame identifier. Until they do,
    the source, cell, and exact temporal windows are fingerprinted. This makes
    repeated scans over the same cached evidence idempotent while preserving a
    clear extension point for provider asset IDs and frame hashes.
    """
    direct_key = str(evidence.get("acquisition_key", "")).strip()
    if direct_key:
        return direct_key

    explicit_identity: dict[str, Any] = {}
    for field in _IDENTITY_FIELDS:
        value = evidence.get(field)
        if isinstance(value, str):
            value = value.strip()
        if value not in (None, ""):
            explicit_identity[field] = value
    if explicit_identity:
        material: dict[str, Any] = {"explicit": explicit_identity}
    else:
        material = {
            "source": evidence.get("source", evidence.get("observation_source")),
            "cell_id": evidence.get("cell_id"),
            "before": evidence.get("before", evidence.get("before_window")),
            "after": evidence.get("after", evidence.get("after_window")),
        }
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
