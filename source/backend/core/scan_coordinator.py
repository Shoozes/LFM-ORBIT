"""Single-producer fan-out for telemetry WebSocket consumers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from fastapi import WebSocket

logger = logging.getLogger(__name__)

_QUEUE_SIZE = 256
_subscribers: set[asyncio.Queue[str | None]] = set()
_producer_task: asyncio.Task | None = None
_producer_generation = 0
_producer_task_generation: int | None = None
_producer_mission_owned = False
_state_loop: asyncio.AbstractEventLoop | None = None
_state_lock: asyncio.Lock | None = None
_last_payload: str | None = None
_active_engine: str | None = None
_active_mission_id: int | None = None
_active_owner_task: asyncio.Task | None = None

Producer = Callable[[Callable[[str], Awaitable[None]]], Awaitable[None]]


def _loop_state() -> tuple[asyncio.AbstractEventLoop, asyncio.Lock]:
    global _state_loop, _state_lock, _producer_task, _last_payload
    global _producer_generation, _producer_task_generation, _producer_mission_owned
    global _active_engine, _active_mission_id, _active_owner_task
    loop = asyncio.get_running_loop()
    if _state_loop is not loop:
        # Test clients can create short-lived event loops. Do not carry queues
        # or tasks from a closed loop into the next one.
        _subscribers.clear()
        _producer_task = None
        _producer_generation = 0
        _producer_task_generation = None
        _producer_mission_owned = False
        _last_payload = None
        _active_engine = None
        _active_mission_id = None
        _active_owner_task = None
        _state_loop = loop
        _state_lock = asyncio.Lock()
    assert _state_lock is not None
    return loop, _state_lock


async def claim_scan_engine(engine: str, mission_id: int | None) -> bool:
    """Claim the process-local live scan slot for one engine and mission.

    The lease is deliberately process-local because the scanner and the
    optional satellite agent currently share one FastAPI process. A finished
    or cancelled owner is treated as stale so a replacement engine can
    recover without requiring a process restart.
    """
    global _active_engine, _active_mission_id, _active_owner_task
    engine = str(engine or "").strip()
    if not engine:
        return False

    _, lock = _loop_state()
    owner = asyncio.current_task()
    async with lock:
        owner_is_stale = _active_owner_task is None or _active_owner_task.done()
        if _active_engine is not None and _active_engine != engine and not owner_is_stale:
            return False
        _active_engine = engine
        _active_mission_id = mission_id
        _active_owner_task = owner
        return True


def _release_scan_engine_locked(engine: str, releasing_task: asyncio.Task | None) -> None:
    global _active_engine, _active_mission_id, _active_owner_task
    owner_is_current = (
        _active_owner_task is None
        or _active_owner_task is releasing_task
        or _active_owner_task.done()
    )
    if _active_engine == engine and owner_is_current:
        _active_engine = None
        _active_mission_id = None
        _active_owner_task = None


async def release_scan_engine(engine: str, owner: asyncio.Task | None = None) -> None:
    """Release the live scan slot when the current engine stops scanning."""
    _, lock = _loop_state()
    async with lock:
        _release_scan_engine_locked(engine, owner or asyncio.current_task())


async def scan_engine_state() -> dict[str, int | str | None]:
    """Return a small diagnostic snapshot for tests and runtime observability."""
    _, lock = _loop_state()
    async with lock:
        return {
            "engine": _active_engine,
            "mission_id": _active_mission_id,
            "owner_active": bool(_active_owner_task and not _active_owner_task.done()),
            "producer_mission_owned": _producer_mission_owned,
        }


def _has_active_live_mission() -> bool:
    """Check mission ownership lazily to avoid importing mission state at module load."""
    try:
        from core.mission import get_active_mission

        mission = get_active_mission()
        return bool(mission and mission.get("mission_mode") != "replay")
    except Exception:
        logger.warning(
            "Unable to resolve active mission while closing telemetry subscriber; preserving producer",
            exc_info=True,
        )
        return True


async def ensure_shared_scan(producer: Producer, *, mission_owned: bool = False) -> None:
    """Ensure one producer exists, optionally making its lifetime mission-owned."""
    global _producer_task, _producer_generation, _producer_task_generation, _producer_mission_owned
    _, lock = _loop_state()
    async with lock:
        if _producer_task is None or _producer_task.done():
            _producer_generation += 1
            _producer_task_generation = _producer_generation
            _producer_mission_owned = mission_owned
            _producer_task = asyncio.create_task(_run_producer(producer, _producer_generation))
        elif mission_owned:
            _producer_mission_owned = True


async def stop_shared_scan() -> None:
    """Stop the shared producer regardless of whether viewers are connected."""
    global _producer_task, _producer_task_generation, _producer_mission_owned, _last_payload
    _, lock = _loop_state()
    task_to_cancel: asyncio.Task | None = None
    async with lock:
        if _producer_task is not None and not _producer_task.done():
            task_to_cancel = _producer_task
        _producer_task = None
        _producer_task_generation = None
        _producer_mission_owned = False
        _last_payload = None
    if task_to_cancel is not None:
        task_to_cancel.cancel()
        await asyncio.gather(task_to_cancel, return_exceptions=True)


async def _publish(payload: str) -> None:
    global _last_payload
    _last_payload = payload
    for queue in tuple(_subscribers):
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            # A slow browser must not pause scoring for every other consumer.
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                logger.debug("Dropping telemetry update for a saturated subscriber")


async def _run_producer(producer: Producer, generation: int | None = None) -> None:
    try:
        await producer(_publish)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Shared telemetry producer stopped unexpectedly")
    finally:
        global _last_payload, _producer_task, _producer_task_generation, _producer_mission_owned
        current_task = asyncio.current_task()
        _, lock = _loop_state()
        async with lock:
            owns_shared_state = generation is None or (
                _producer_task is current_task and _producer_task_generation == generation
            )
            if owns_shared_state:
                _last_payload = None
                _producer_task = None
                _producer_task_generation = None
                _producer_mission_owned = False
                _release_scan_engine_locked("telemetry", current_task)
                subscribers = tuple(_subscribers)
            else:
                # A newer producer owns the shared state. The old task may
                # still be unwinding after cancellation, but it must not
                # clear its payload or signal the newer subscribers.
                subscribers = ()
                _release_scan_engine_locked("telemetry", current_task)
        for queue in subscribers:
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                logger.debug("Unable to signal telemetry producer shutdown")


async def stream_shared_scan(websocket: WebSocket, producer: Producer) -> None:
    """Subscribe one WebSocket to a process-wide scan producer."""
    global _producer_task, _producer_task_generation, _producer_mission_owned, _last_payload
    global _producer_generation
    _, lock = _loop_state()
    queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=_QUEUE_SIZE)

    async with lock:
        _subscribers.add(queue)
        if _last_payload is not None:
            queue.put_nowait(_last_payload)
        if _producer_task is None or _producer_task.done():
            _producer_generation += 1
            _producer_task_generation = _producer_generation
            _producer_mission_owned = False
            _producer_task = asyncio.create_task(_run_producer(producer, _producer_generation))

    try:
        while True:
            payload = await queue.get()
            if payload is None:
                return
            await websocket.send_text(payload)
    finally:
        task_to_cancel: asyncio.Task | None = None
        async with lock:
            _subscribers.discard(queue)
            if (
                not _subscribers
                and _producer_task is not None
                and not _producer_task.done()
                and not _producer_mission_owned
                and not _has_active_live_mission()
            ):
                task_to_cancel = _producer_task
                _producer_task = None
                _producer_task_generation = None
                _last_payload = None
        if task_to_cancel is not None:
            task_to_cancel.cancel()
            await asyncio.gather(task_to_cancel, return_exceptions=True)
