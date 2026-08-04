"""Small, dependency-free limits for request shape and expensive work."""

from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import dataclass
from typing import Any


DEFAULT_MAX_REQUEST_BODY_BYTES = 20_000_000
MAX_JSON_DEPTH = 8
MAX_JSON_OBJECT_KEYS = 128
MAX_JSON_ARRAY_ITEMS = 256
MAX_JSON_STRING_CHARS = 1_000_000
MAX_JSON_BINARY_STRING_CHARS = 16_000_000
_BINARY_FIELD_NAMES = {
    "data_url",
    "image_b64",
    "image_data_url",
    "timelapse_b64",
    "context_thumb",
}


class ExpensiveCallBusy(RuntimeError):
    """Raised when a local resource is already at its configured concurrency."""


class ExpensiveCallTimedOut(TimeoutError):
    """Raised when an expensive local operation exceeds its response budget."""


@dataclass(frozen=True)
class ExpensiveCallPolicy:
    name: str
    max_concurrency: int
    timeout_seconds: float
    acquire_timeout_seconds: float


_EXPENSIVE_CALL_DEFAULTS: dict[str, tuple[int, float]] = {
    "analysis": (1, 90.0),
    "timelapse": (1, 90.0),
    "image_review": (1, 90.0),
    "vlm": (1, 60.0),
    "depth": (1, 1.0),
}
_semaphore_lock = threading.Lock()
_semaphores: dict[tuple[str, int], threading.BoundedSemaphore] = {}


def _positive_int_env(name: str, default: int, *, maximum: int = 16) -> int:
    try:
        value = int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default
    return max(1, min(value, maximum))


def _positive_float_env(name: str, default: float, *, maximum: float = 300.0) -> float:
    try:
        value = float(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default
    if value != value or value <= 0:
        return default
    return max(0.05, min(value, maximum))


def get_expensive_call_policies() -> dict[str, ExpensiveCallPolicy]:
    """Return safe, environment-tunable budgets for resource-heavy operations."""
    policies: dict[str, ExpensiveCallPolicy] = {}
    for name, (default_concurrency, default_timeout) in _EXPENSIVE_CALL_DEFAULTS.items():
        env_name = name.upper().replace("-", "_")
        timeout = _positive_float_env(
            f"ORBIT_{env_name}_TIMEOUT_SECONDS",
            default_timeout,
        )
        policies[name] = ExpensiveCallPolicy(
            name=name,
            max_concurrency=_positive_int_env(
                f"ORBIT_{env_name}_MAX_CONCURRENCY",
                default_concurrency,
            ),
            timeout_seconds=timeout,
            acquire_timeout_seconds=min(1.0, max(0.05, timeout / 10.0)),
        )
    return policies


def get_expensive_call_limits() -> dict[str, dict[str, int | float]]:
    """Return public numeric limits without exposing implementation state."""
    return {
        name: {
            "max_concurrency": policy.max_concurrency,
            "timeout_seconds": policy.timeout_seconds,
        }
        for name, policy in get_expensive_call_policies().items()
    }


def reset_expensive_call_state() -> None:
    """Clear cached semaphores for isolated tests and controlled local reconfiguration."""
    with _semaphore_lock:
        _semaphores.clear()


def _get_semaphore(policy: ExpensiveCallPolicy) -> threading.BoundedSemaphore:
    key = (policy.name, policy.max_concurrency)
    with _semaphore_lock:
        semaphore = _semaphores.get(key)
        if semaphore is None:
            semaphore = threading.BoundedSemaphore(policy.max_concurrency)
            _semaphores[key] = semaphore
        return semaphore


async def _acquire_slot(semaphore: threading.BoundedSemaphore, timeout_seconds: float) -> bool:
    """Acquire a thread-backed slot without leaking it if the caller disconnects."""
    acquire_task = asyncio.create_task(
        asyncio.to_thread(semaphore.acquire, True, timeout_seconds)
    )

    def release_if_acquired(completed: asyncio.Task) -> None:
        try:
            if completed.result():
                semaphore.release()
        except BaseException:
            # Cancellation or executor failure means no slot was acquired here.
            return

    try:
        return await asyncio.shield(acquire_task)
    except asyncio.CancelledError:
        acquire_task.add_done_callback(release_if_acquired)
        raise


async def run_expensive_call(name: str, operation, *args, **kwargs):
    """Run a blocking provider/model operation with a process-wide cap and response timeout.

    A timed-out worker cannot be force-killed safely from Python. Its semaphore slot is
    therefore held until the worker actually exits, preventing a timeout storm from
    exceeding the configured concurrency while the caller receives a bounded response.
    """
    policies = get_expensive_call_policies()
    try:
        policy = policies[name]
    except KeyError as exc:
        raise ValueError(f"unknown expensive call policy: {name}") from exc

    semaphore = _get_semaphore(policy)
    acquired = await _acquire_slot(semaphore, policy.acquire_timeout_seconds)
    if not acquired:
        raise ExpensiveCallBusy(
            f"{name} is at its local concurrency limit; retry after the active operation finishes"
        )

    worker = asyncio.create_task(asyncio.to_thread(operation, *args, **kwargs))
    try:
        result = await asyncio.wait_for(
            asyncio.shield(worker),
            timeout=policy.timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        worker.add_done_callback(lambda _: semaphore.release())
        raise ExpensiveCallTimedOut(
            f"{name} exceeded its {policy.timeout_seconds:g}-second local time budget"
        ) from exc
    except asyncio.CancelledError:
        worker.add_done_callback(lambda _: semaphore.release())
        raise
    except BaseException:
        semaphore.release()
        raise
    else:
        semaphore.release()
        return result


def get_max_request_body_bytes() -> int:
    raw = os.getenv("ORBIT_MAX_REQUEST_BODY_BYTES", str(DEFAULT_MAX_REQUEST_BODY_BYTES)).strip()
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_REQUEST_BODY_BYTES
    return max(1_000_000, min(value, 64_000_000))


def validate_json_shape(value: Any, *, path: str = "$", depth: int = 0, field_name: str = "") -> None:
    """Reject unexpectedly deep, broad, or oversized JSON structures."""
    if depth > MAX_JSON_DEPTH:
        raise ValueError(f"JSON nesting exceeds the {MAX_JSON_DEPTH}-level limit at {path}")
    if isinstance(value, dict):
        if len(value) > MAX_JSON_OBJECT_KEYS:
            raise ValueError(f"JSON object exceeds the {MAX_JSON_OBJECT_KEYS}-key limit at {path}")
        for key, child in value.items():
            key_text = str(key)
            if len(key_text) > 200:
                raise ValueError(f"JSON key is too long at {path}")
            validate_json_shape(
                child,
                path=f"{path}.{key_text}",
                depth=depth + 1,
                field_name=key_text,
            )
        return
    if isinstance(value, list):
        if len(value) > MAX_JSON_ARRAY_ITEMS:
            raise ValueError(f"JSON array exceeds the {MAX_JSON_ARRAY_ITEMS}-item limit at {path}")
        for index, child in enumerate(value):
            validate_json_shape(child, path=f"{path}[{index}]", depth=depth + 1, field_name=field_name)
        return
    if isinstance(value, str):
        limit = (
            MAX_JSON_BINARY_STRING_CHARS
            if field_name.lower() in _BINARY_FIELD_NAMES
            else MAX_JSON_STRING_CHARS
        )
        if len(value) > limit:
            raise ValueError(f"JSON string exceeds the {limit}-character limit at {path}")
