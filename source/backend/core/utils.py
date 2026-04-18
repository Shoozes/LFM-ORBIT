"""
Shared utility functions for Canopy Sentinel backend.
"""

from datetime import datetime, timezone


def utc_timestamp() -> str:
    """Return the current UTC time as an ISO 8601 string with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
