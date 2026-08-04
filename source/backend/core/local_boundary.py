"""Shared local-runtime boundary checks for HTTP and WebSocket surfaces."""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable


def is_local_host(host: str | None) -> bool:
    value = str(host or "").strip().lower()
    if value in {"localhost", "testclient"}:
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def is_allowed_origin(origin: str | None, allowed_origins: Iterable[str]) -> bool:
    value = str(origin or "").strip()
    if not value:
        # Native clients and tests do not always send an Origin header. The
        # local-host check remains mandatory for those connections.
        return True
    return value in {str(item).strip() for item in allowed_origins if str(item).strip()}
