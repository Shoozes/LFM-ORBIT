"""Smoke-test the optional manifest-resolved GGUF satellite model path."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from core.inference import generate, model_status


def run_model_smoke(*, require_present: bool = False, max_tokens: int = 16) -> dict[str, Any]:
    status = model_status()
    model_path = Path(str(status.get("path") or ""))
    if not model_path.exists():
        payload = {
            "format": "orbit_satellite_model_smoke_v1",
            "status": "missing" if require_present else "skipped",
            "reason": "model file not found",
            "model": status,
        }
        if require_present:
            payload["error"] = "A manifest-resolved GGUF is required for this smoke path."
        return payload

    result = generate(
        "Return one short JSON object describing whether this Orbit satellite model is loaded.",
        max_tokens=max(1, int(max_tokens)),
    )
    loaded = bool(model_status().get("loaded"))
    return {
        "format": "orbit_satellite_model_smoke_v1",
        "status": "passed" if loaded else "failed",
        "model": model_status(),
        "response": result.get("response", ""),
        "tool_calls": result.get("tool_calls", []),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test the optional Orbit GGUF satellite model.")
    parser.add_argument("--require-present", action="store_true", help="Fail when the manifest-resolved model file is missing.")
    parser.add_argument("--max-tokens", type=int, default=16, help="Maximum smoke-generation tokens.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    payload = run_model_smoke(require_present=args.require_present, max_tokens=args.max_tokens)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] in {"passed", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
