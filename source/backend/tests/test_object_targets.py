from __future__ import annotations

import json

import pytest

from core.object_targets import (
    delete_custom_target_pack,
    get_custom_target_packs_path,
    get_target_pack,
    list_default_target_packs,
    list_target_packs,
    load_custom_target_packs,
    merge_custom_targets,
    normalize_object_target,
    normalize_object_targets,
    save_custom_target_pack,
)


def test_default_target_packs_load():
    packs = list_default_target_packs()
    pack_ids = {pack["id"] for pack in packs}

    assert {
        "critical_minerals",
        "deforestation",
        "fireline",
        "camp",
        "port",
        "plastic",
        "waterline",
        "algae_bloom",
        "glacier",
        "urban_expansion",
        "lifeline",
    } <= pack_ids
    minerals = get_target_pack("critical_minerals", include_custom=False)
    assert minerals is not None
    assert [target["label"] for target in minerals["targets"]][:3] == [
        "evaporation pond region",
        "tailings region",
        "open-pit expansion",
    ]
    deforestation = get_target_pack("deforestation", include_custom=False)
    assert deforestation is not None
    assert [target["label"] for target in deforestation["targets"]][:3] == [
        "clearing candidate",
        "road expansion",
        "exposed soil region",
    ]
    fireline = get_target_pack("fireline", include_custom=False)
    assert fireline is not None
    assert [target["label"] for target in fireline["targets"]][:2] == ["dark smoke", "burn scar"]
    urban = get_target_pack("urban_expansion", include_custom=False)
    assert urban is not None
    assert [target["label"] for target in urban["targets"]][:3] == [
        "construction footprint",
        "new subdivision region",
        "road expansion corridor",
    ]
    algae = get_target_pack("algae_bloom", include_custom=False)
    assert algae is not None
    assert [target["label"] for target in algae["targets"]][:3] == [
        "probable surface bloom",
        "high chlorophyll signal",
        "cyanobacteria-like signal",
    ]


def test_invalid_pack_id_returns_none(tmp_path):
    assert get_target_pack("", runtime_dir=tmp_path) is None
    assert get_target_pack("missing-pack", runtime_dir=tmp_path) is None


def test_normalize_object_target_rejects_unsafe_label():
    with pytest.raises(ValueError, match="outside the civilian evidence scope"):
        normalize_object_target({"label": "person", "prompt": "Find person", "class_key": "unsafe"})
    with pytest.raises(ValueError, match="outside the civilian evidence scope"):
        normalize_object_target({"label": "weapons cache", "prompt": "Find weapons", "class_key": "unsafe"})
    with pytest.raises(ValueError, match="outside the civilian evidence scope"):
        normalize_object_target({"label": "manatee population", "prompt": "Find manatees", "class_key": "wildlife"})


def test_custom_target_packs_load_from_runtime_dir(tmp_path):
    custom_path = get_custom_target_packs_path(tmp_path)
    custom_path.parent.mkdir(parents=True)
    custom_path.write_text(
        json.dumps(
            {
                "packs": [
                    {
                        "id": "florida_fireline",
                        "name": "Florida Fireline Pack",
                        "description": "Custom fireline evidence terms.",
                        "targets": [
                            {
                                "label": "white roof shelters",
                                "prompt": "Find white roof shelters",
                                "class_key": "structure",
                                "enabled": True,
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    packs = list_target_packs(runtime_dir=tmp_path)
    custom_packs = load_custom_target_packs(runtime_dir=tmp_path)
    custom_pack = get_target_pack("florida_fireline", runtime_dir=tmp_path)

    assert any(pack["id"] == "fireline" for pack in packs)
    assert [pack["id"] for pack in custom_packs] == ["florida_fireline"]
    assert custom_pack is not None
    assert custom_pack["targets"][0]["label"] == "white roof shelters"


def test_normalize_object_targets_merges_duplicate_labels():
    targets = normalize_object_targets(
        [
            {"label": "Road Obstruction", "class_key": "lifeline"},
            {"label": "road obstruction", "class_key": "fallback", "enabled": False},
        ]
    )

    assert targets == [
        {
            "label": "road obstruction",
            "prompt": "Find road obstruction",
            "class_key": "fallback",
            "enabled": False,
        }
    ]


def test_save_custom_target_pack_does_not_modify_defaults(tmp_path):
    saved = save_custom_target_pack(
        {
            "id": "disaster_mobility",
            "name": "Disaster Mobility",
            "description": "Custom mobility evidence terms.",
            "targets": ["road obstruction", {"label": "vehicle queue", "class_key": "mobility"}],
        },
        runtime_dir=tmp_path,
    )

    assert saved["id"] == "disaster_mobility"
    assert get_target_pack("disaster_mobility", runtime_dir=tmp_path) is not None
    assert get_target_pack("disaster_mobility", include_custom=False, runtime_dir=tmp_path) is None


def test_merge_custom_targets_updates_duplicate_labels():
    merged = merge_custom_targets(
        [{"label": "dark smoke", "class_key": "hazard"}],
        [{"label": "Dark Smoke", "class_key": "fallback", "enabled": False}],
    )

    assert len(merged) == 1
    assert merged[0]["label"] == "dark smoke"
    assert merged[0]["class_key"] == "fallback"
    assert merged[0]["enabled"] is False


def test_delete_custom_target_pack_removes_runtime_only_pack(tmp_path):
    save_custom_target_pack(
        {
            "id": "disaster_mobility",
            "name": "Disaster Mobility",
            "description": "Custom mobility evidence terms.",
            "targets": ["road obstruction"],
        },
        runtime_dir=tmp_path,
    )

    assert delete_custom_target_pack("disaster_mobility", runtime_dir=tmp_path) is True
    assert get_target_pack("disaster_mobility", runtime_dir=tmp_path) is None
    assert delete_custom_target_pack("fireline", runtime_dir=tmp_path) is False
