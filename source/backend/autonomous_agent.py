"""Retired standalone satellite-agent prototype.

The production runtime starts `core.satellite_agent` and `core.ground_agent`
from `api.main`. This historical script used stale credential parsing,
external paths, and direct DB mutation, so it is intentionally disabled.
"""

from __future__ import annotations

EXIT_CODE_RETIRED = 2


def run_agent() -> int:
    """Return a clear non-zero status instead of running the retired prototype."""
    print(
        "autonomous_agent.py is retired. "
        "Use `uvicorn api.main:app` or the root run scripts for the supported runtime."
    )
    return EXIT_CODE_RETIRED


if __name__ == "__main__":
    raise SystemExit(run_agent())
