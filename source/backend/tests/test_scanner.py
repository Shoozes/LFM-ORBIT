import asyncio
import json

import pytest
from fastapi import WebSocketDisconnect

from core.scanner import (
    _quality_gate_fallback_score,
    _rejection_reason_from_exception,
    _score_unavailable_fallback_score,
    stream_region_scan,
)


def test_rejection_reason_from_exception_preserves_qc_low_valid_pixels():
    reason = _rejection_reason_from_exception(
        ValueError("Scene Quality Rejected: Insufficient Valid Pixels")
    )

    assert reason == "insufficient_valid_pixels"


def test_rejection_reason_from_exception_defaults_to_scan_failure():
    assert _rejection_reason_from_exception(RuntimeError("provider unavailable")) == "scan_failure"


def test_provider_failures_do_not_force_positive_alerts():
    score = _score_unavailable_fallback_score("scan_failure")

    assert score["change_score"] == 0.0
    assert score["confidence"] == 0.0
    assert "score_unavailable" in score["reason_codes"]
    assert "suspected_canopy_loss" not in score["reason_codes"]


def test_quality_gate_fallback_score_blocks_alert_transmission():
    score = _quality_gate_fallback_score("insufficient_valid_pixels")

    assert score["change_score"] == 0.0
    assert score["confidence"] == 0.0
    assert "quality_gate_failed" in score["reason_codes"]
    assert "suspected_canopy_loss" not in score["reason_codes"]


def test_telemetry_stream_stays_idle_without_active_mission(monkeypatch):
    messages = []

    class FakeWebSocket:
        async def send_text(self, payload: str):
            messages.append(json.loads(payload))
            if len(messages) >= 2:
                raise WebSocketDisconnect()

    monkeypatch.setattr("core.scanner.get_active_mission", lambda: None)

    def fail_score(_cell_id, _observer=None):
        raise AssertionError("scanner should not score cells without an active mission")

    monkeypatch.setattr("core.scanner.score_cell_change", fail_score)

    with pytest.raises(WebSocketDisconnect):
        asyncio.run(stream_region_scan(FakeWebSocket()))

    assert messages[0]["type"] == "grid_init"
    assert messages[0]["data"]["features"] == []
    assert messages[1] == {"type": "scan_complete"}


def test_telemetry_clients_share_one_scan_producer(monkeypatch):
    import core.scan_coordinator as coordinator

    producer_calls = 0
    published = asyncio.Event()

    async def producer(publish):
        nonlocal producer_calls
        producer_calls += 1
        await publish(json.dumps({"type": "shared", "value": producer_calls}))
        await published.wait()

    messages: list[dict] = []

    class FakeWebSocket:
        def __init__(self):
            self.first = asyncio.Event()

        async def send_text(self, payload: str):
            messages.append(json.loads(payload))
            self.first.set()

    async def run():
        first = FakeWebSocket()
        second = FakeWebSocket()
        first_task = asyncio.create_task(coordinator.stream_shared_scan(first, producer))
        await first.first.wait()
        second_task = asyncio.create_task(coordinator.stream_shared_scan(second, producer))
        await asyncio.sleep(0)
        published.set()
        await asyncio.sleep(0)
        first_task.cancel()
        second_task.cancel()
        await asyncio.gather(first_task, second_task, return_exceptions=True)

    asyncio.run(run())

    assert producer_calls == 1
    assert messages == [{"type": "shared", "value": 1}, {"type": "shared", "value": 1}]


def test_mission_owned_scan_survives_without_viewers():
    import core.scan_coordinator as coordinator

    async def run():
        started = asyncio.Event()
        stop = asyncio.Event()

        async def producer(publish):
            started.set()
            await stop.wait()

        await coordinator.ensure_shared_scan(producer, mission_owned=True)
        await started.wait()
        state = await coordinator.scan_engine_state()
        assert state["producer_mission_owned"] is True

        await asyncio.sleep(0)
        assert coordinator._producer_task is not None
        assert coordinator._producer_task.done() is False

        stop.set()
        await coordinator.stop_shared_scan()
        assert coordinator._producer_task is None

    asyncio.run(run())


def test_live_scan_lease_prevents_two_engines_from_scanning_same_mission():
    import core.scan_coordinator as coordinator

    async def run():
        assert await coordinator.claim_scan_engine("satellite_agent", 41) is True
        assert await coordinator.claim_scan_engine("telemetry", 41) is False
        assert (await coordinator.scan_engine_state())["engine"] == "satellite_agent"
        await coordinator.release_scan_engine("satellite_agent")
        assert await coordinator.claim_scan_engine("telemetry", 41) is True
        await coordinator.release_scan_engine("telemetry")

    asyncio.run(run())


def test_finished_scan_producer_does_not_replay_stale_payload():
    import core.scan_coordinator as coordinator

    async def producer(publish):
        await publish(json.dumps({"type": "old"}))
        raise RuntimeError("producer failed")

    async def run():
        await coordinator._run_producer(producer)
        assert coordinator._last_payload is None
        assert (await coordinator.scan_engine_state())["engine"] is None

    asyncio.run(run())


def test_cancelled_scan_owner_can_be_replaced():
    import core.scan_coordinator as coordinator

    async def run():
        started = asyncio.Event()
        stop = asyncio.Event()

        async def owner():
            assert await coordinator.claim_scan_engine("satellite_agent", 7) is True
            started.set()
            await stop.wait()

        task = asyncio.create_task(owner())
        await started.wait()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

        assert await coordinator.claim_scan_engine("telemetry", 7) is True
        await coordinator.release_scan_engine("telemetry")

    asyncio.run(run())


def test_confirmation_policy_separates_single_and_distinct_acquisition(monkeypatch):
    import core.scanner as scanner

    class Config:
        demo_mode_loop_scan = False
        confirmation_policy = "distinct_acquisition"
        confirmation_required_acquisitions = 2

    monkeypatch.setattr(scanner, "REGION", Config())
    counts = iter((1, 2))
    removed: list[tuple[int, str]] = []
    monkeypatch.setattr(scanner, "upsert_candidate", lambda _mission_id, _cell_id: next(counts))
    monkeypatch.setattr(scanner, "remove_candidate", lambda mission_id, cell_id: removed.append((mission_id, cell_id)))

    assert scanner.confirm_anomaly_candidate(9, "cell-a", {"confirmation_policy": "single_acquisition"}) is True
    assert scanner.confirm_anomaly_candidate(9, "cell-a", {"confirmation_policy": "distinct_acquisition"}) is False
    assert scanner.confirm_anomaly_candidate(9, "cell-a", {"confirmation_policy": "distinct_acquisition"}) is True
    assert removed == [(9, "cell-a"), (9, "cell-a")]


def test_confirmation_policy_rejects_unknown_override_to_safe_default(monkeypatch):
    import core.scanner as scanner

    class Config:
        demo_mode_loop_scan = False
        confirmation_policy = "distinct_acquisition"
        confirmation_required_acquisitions = 2

    monkeypatch.setattr(scanner, "REGION", Config())
    assert scanner.confirmation_policy_for_mission({"confirmation_policy": "alert_everything"}) == "distinct_acquisition"


def test_active_mission_lookup_failure_preserves_scan_producer(monkeypatch):
    import core.scan_coordinator as coordinator

    def fail_lookup():
        raise RuntimeError("database temporarily unavailable")

    monkeypatch.setattr("core.mission.get_active_mission", fail_lookup)
    assert coordinator._has_active_live_mission() is True


def test_stale_producer_cleanup_cannot_signal_new_subscriber(monkeypatch):
    import core.scan_coordinator as coordinator

    monkeypatch.setattr(coordinator, "_has_active_live_mission", lambda: False)

    async def run():
        old_started = asyncio.Event()
        old_cancelled = asyncio.Event()
        release_old = asyncio.Event()
        new_message = asyncio.Event()
        stop_new = asyncio.Event()

        async def old_producer(publish):
            await publish(json.dumps({"type": "old"}))
            old_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                old_cancelled.set()
                await release_old.wait()

        async def new_producer(publish):
            await publish(json.dumps({"type": "new"}))
            await stop_new.wait()

        class FakeWebSocket:
            def __init__(self):
                self.messages: list[dict] = []

            async def send_text(self, payload: str):
                self.messages.append(json.loads(payload))
                if self.messages[-1]["type"] == "new":
                    new_message.set()

        first_socket = FakeWebSocket()
        first_task = asyncio.create_task(coordinator.stream_shared_scan(first_socket, old_producer))
        await old_started.wait()
        first_task.cancel()
        await old_cancelled.wait()

        second_socket = FakeWebSocket()
        second_task = asyncio.create_task(coordinator.stream_shared_scan(second_socket, new_producer))
        await new_message.wait()
        release_old.set()
        await asyncio.gather(first_task, return_exceptions=True)
        assert coordinator._last_payload == json.dumps({"type": "new"})

        stop_new.set()
        await asyncio.gather(second_task, return_exceptions=True)

    asyncio.run(run())
