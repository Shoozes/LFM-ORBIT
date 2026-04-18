"""
Link State — shared in-memory flag controlling SAT→GND link connectivity.

Simulates satellite downlink blackout. When the link is severed:
- The satellite agent continues posting FLAG messages (they accumulate in the queue).
- The ground agent pauses consuming flags (marks them unread so they persist).
- On restore: ground agent immediately flushes the accumulated queue.

This is an in-memory flag (not persisted across restarts), which is correct for
demo purposes — a real severed link would be a network event, not a DB state.
"""

import logging

logger = logging.getLogger(__name__)

_link_severed: bool = False


def is_link_connected() -> bool:
    return not _link_severed


def set_link_state(connected: bool) -> None:
    global _link_severed
    previous = _link_severed
    _link_severed = not connected
    if previous != _link_severed:
        state_str = "CONNECTED" if connected else "SEVERED"
        logger.warning("[LINK] Downlink state changed → %s", state_str)
