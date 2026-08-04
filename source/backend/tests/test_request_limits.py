"""Deterministic concurrency and timeout tests for expensive local work."""

import asyncio
import threading
import time

import pytest

from core.request_limits import (
    ExpensiveCallBusy,
    ExpensiveCallTimedOut,
    reset_expensive_call_state,
    run_expensive_call,
)


@pytest.mark.asyncio
async def test_busy_call_does_not_enter_the_blocked_operation(monkeypatch):
    monkeypatch.setenv("ORBIT_VLM_MAX_CONCURRENCY", "1")
    monkeypatch.setenv("ORBIT_VLM_TIMEOUT_SECONDS", "1")
    reset_expensive_call_state()

    started = threading.Event()
    release = threading.Event()
    blocked_calls: list[str] = []

    def first_operation():
        started.set()
        release.wait(timeout=2)
        return "first"

    def blocked_operation():
        blocked_calls.append("entered")
        return "blocked"

    first = asyncio.create_task(run_expensive_call("vlm", first_operation))
    assert await asyncio.to_thread(started.wait, 1) is True

    with pytest.raises(ExpensiveCallBusy):
        await run_expensive_call("vlm", blocked_operation)

    assert blocked_calls == []
    release.set()
    assert await first == "first"


@pytest.mark.asyncio
async def test_timeout_returns_without_releasing_slot_early(monkeypatch):
    monkeypatch.setenv("ORBIT_DEPTH_TIMEOUT_SECONDS", "0.05")
    monkeypatch.setenv("ORBIT_DEPTH_MAX_CONCURRENCY", "1")
    reset_expensive_call_state()

    started = threading.Event()

    def slow_operation():
        started.set()
        time.sleep(0.2)
        return "late"

    with pytest.raises(ExpensiveCallTimedOut):
        await run_expensive_call("depth", slow_operation)

    assert started.is_set()
    await asyncio.sleep(0.25)


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_leak_a_semaphore_slot(monkeypatch):
    monkeypatch.setenv("ORBIT_VLM_MAX_CONCURRENCY", "1")
    monkeypatch.setenv("ORBIT_VLM_TIMEOUT_SECONDS", "10")
    reset_expensive_call_state()

    started = threading.Event()
    release = threading.Event()

    def first_operation():
        started.set()
        release.wait(timeout=2)
        return "first"

    first = asyncio.create_task(run_expensive_call("vlm", first_operation))
    assert await asyncio.to_thread(started.wait, 1) is True

    waiter = asyncio.create_task(run_expensive_call("vlm", lambda: "cancelled"))
    await asyncio.sleep(0.05)
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter

    release.set()
    assert await first == "first"
    await asyncio.sleep(0.1)
    assert await run_expensive_call("vlm", lambda: "third") == "third"
