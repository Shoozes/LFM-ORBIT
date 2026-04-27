from core import observation_store


def test_training_ready_requires_ground_and_satellite(monkeypatch, tmp_path):
    monkeypatch.setattr(observation_store, "_STORE_DIR", tmp_path)

    bbox = [-63.1, -10.2, -62.9, -10.0]
    observation_store.save_observation(
        bbox=bbox,
        agent_role="satellite",
        vlm_text="Satellite saw canopy fragmentation.",
        cell_id="sq_-10.0_-63.0",
    )

    first_record = observation_store.load_observation(bbox)
    assert first_record is not None
    assert first_record["training_ready"] is False

    observation_store.save_observation(
        bbox=bbox,
        agent_role="ground",
        vlm_text="Ground confirmed structural canopy loss.",
        cell_id="sq_-10.0_-63.0",
    )

    second_record = observation_store.load_observation(bbox)
    assert second_record is not None
    assert second_record["training_ready"] is True


def test_clear_observations_removes_saved_records(monkeypatch, tmp_path):
    monkeypatch.setattr(observation_store, "_STORE_DIR", tmp_path)

    observation_store.save_observation(
        bbox=[-63.1, -10.2, -62.9, -10.0],
        agent_role="satellite",
        vlm_text="Primary corridor.",
        cell_id="sq_a",
    )
    observation_store.save_observation(
        bbox=[-63.3, -10.4, -63.1, -10.2],
        agent_role="ground",
        vlm_text="Secondary corridor.",
        cell_id="sq_b",
    )

    assert len(observation_store.list_observations()) == 2
    removed = observation_store.clear_observations()

    assert removed == 2
    assert observation_store.list_observations() == []


def test_list_observations_skips_corrupt_records(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(observation_store, "_STORE_DIR", tmp_path)
    caplog.set_level("DEBUG", logger="core.observation_store")
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")

    records = observation_store.list_observations()

    assert records == []
    assert "Skipping unreadable observation broken.json" in caplog.text
