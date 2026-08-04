"""Shared limits and decoding helpers for request-supplied image payloads."""

from __future__ import annotations

import base64
import binascii


# Keep the API and optional adapters on the same resource-safety contract.
MAX_IMAGE_B64_CHARS = 15_000_000
MAX_IMAGE_BYTES = 12_000_000


def strip_data_url(value: str) -> str:
    payload = value.strip()
    if "," in payload and payload.lower().startswith("data:"):
        return payload.split(",", 1)[1].strip()
    return payload


def decode_base64_payload(
    value: str,
    *,
    max_chars: int = MAX_IMAGE_B64_CHARS,
    max_bytes: int = MAX_IMAGE_BYTES,
) -> bytes:
    """Decode bounded base64 data without allowing unbounded input allocation."""
    payload = strip_data_url(value)
    if not payload:
        raise ValueError("image_b64 is required")
    if len(payload) > max_chars:
        raise ValueError(f"image_b64 exceeds the {max_chars} character limit")
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("image_b64 must be valid base64 image data") from exc
    if len(raw) > max_bytes:
        raise ValueError(f"decoded image exceeds the {max_bytes} byte limit")
    return raw
