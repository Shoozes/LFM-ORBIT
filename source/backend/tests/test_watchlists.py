from core.watchlists import build_mission_from_watchlist_asset, get_watchlist, list_watchlist_assets, list_watchlists


def test_southeast_fireline_watchlist_loads():
    watchlist = get_watchlist("southeast_fire_lifeline_watch")
    listed = list_watchlists()

    assert watchlist is not None
    assert watchlist["display_name"] == "Southeast Fireline Watch"
    assert len(list_watchlist_assets("southeast_fire_lifeline_watch") or []) == 2
    assert any(item["watchlist_id"] == "southeast_fire_lifeline_watch" for item in listed)
    assert all(":\\" not in item["path"] for item in listed)


def test_start_mission_from_watchlist_asset(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "mission.sqlite"))

    mission = build_mission_from_watchlist_asset(
        "southeast_fire_lifeline_watch",
        "ga_highway82_fire_candidate",
    )

    assert mission["bbox"] == [-81.916, 31.143, -81.756, 31.303]
    assert mission["target_pack_id"] == "fireline"
    assert {target["label"] for target in mission["object_targets"]} >= {"dark smoke", "burn scar"}
