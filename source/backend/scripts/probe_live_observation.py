"""Probe configured real imagery providers without falling back to fixtures."""

from __future__ import annotations

import argparse
import json
from typing import Any

from core.config import PROVIDER_SIMSAT_MAPBOX, PROVIDER_SIMSAT_SENTINEL
from core.grid import normalize_bbox
from core.simsat_client import get_simsat_client


def _json(payload: dict[str, Any], *, exit_code: int = 0) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return exit_code


def _parse_bbox(value: str) -> list[float]:
    try:
        parts = [float(part.strip()) for part in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("bbox must be comma-separated numbers") from exc
    try:
        return normalize_bbox(parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _center(bbox: list[float]) -> tuple[float, float]:
    west, south, east, north = bbox
    return (south + north) / 2.0, (west + east) / 2.0


def _response_ok(response: Any) -> bool:
    return bool(response and response.success and response.image_data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe a live real-data provider without fallback.")
    parser.add_argument("--provider", default=PROVIDER_SIMSAT_SENTINEL)
    parser.add_argument("--bbox", required=True, type=_parse_bbox, help="west,south,east,north")
    parser.add_argument("--start", required=True, help="Historical start date for probe context.")
    parser.add_argument("--end", required=True, help="Historical end date for probe context.")
    args = parser.parse_args()

    if args.provider not in {PROVIDER_SIMSAT_SENTINEL, PROVIDER_SIMSAT_MAPBOX}:
        return _json(
            {
                "provider": args.provider,
                "available": False,
                "fallback_used": False,
                "reason": "probe currently supports simsat_sentinel and simsat_mapbox only",
            },
            exit_code=1,
        )

    lat, lng = _center(args.bbox)
    client = get_simsat_client()
    try:
        if args.provider == PROVIDER_SIMSAT_MAPBOX:
            responses = [
                client.fetch_mapbox_current(lat=lat, lng=lng, width=512, height=512),
            ]
            imagery_origin = "simsat_mapbox"
        else:
            responses = [
                client.fetch_sentinel_historical(lat=lat, lng=lng, date=args.start),
                client.fetch_sentinel_historical(lat=lat, lng=lng, date=args.end),
                client.fetch_sentinel_current(lat=lat, lng=lng),
            ]
            imagery_origin = "simsat"
    finally:
        client.close()

    successes = [response for response in responses if _response_ok(response)]
    if not successes:
        errors = [response.error for response in responses if response and response.error]
        return _json(
            {
                "provider": args.provider,
                "available": False,
                "runtime_truth_mode": "realtime",
                "imagery_origin": imagery_origin,
                "frames": 0,
                "valid_pixels": False,
                "fallback_used": False,
                "reason": errors[0] if errors else "provider unavailable or not configured",
            },
            exit_code=1,
        )

    return _json(
        {
            "provider": args.provider,
            "available": True,
            "runtime_truth_mode": "realtime",
            "imagery_origin": imagery_origin,
            "frames": len(successes),
            "valid_pixels": True,
            "fallback_used": False,
            "content_lengths": [len(response.image_data or b"") for response in successes],
        }
    )


if __name__ == "__main__":
    raise SystemExit(main())
