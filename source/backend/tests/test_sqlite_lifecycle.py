from __future__ import annotations

import sqlite3

import pytest


@pytest.mark.parametrize("module_name", ["core.agent_bus", "core.queue", "core.loader", "satellite_debug"])
def test_runtime_sqlite_context_closes_connections(module_name, monkeypatch, tmp_path):
    if module_name == "core.agent_bus":
        monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
        from core.agent_bus import _connect
    elif module_name == "core.queue":
        monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "dtn_queue.sqlite"))
        from core.queue import _connect
    elif module_name == "core.loader":
        import core.loader as loader

        monkeypatch.setattr(loader, "CACHE_PATH", str(tmp_path / "api_cache.sqlite"))
        loader._init_cache()
        _connect = loader._connect
    else:
        monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "debug_bus.sqlite"))
        from satellite_debug import _connect

    with _connect() as connection:
        connection.execute("CREATE TABLE lifecycle_probe (value INTEGER)")
        connection.execute("INSERT INTO lifecycle_probe (value) VALUES (1)")

    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT value FROM lifecycle_probe")
