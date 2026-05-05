from core.scanner import _resume_progress_for_mission


def test_resume_progress_clamps_to_grid_size():
    cells_scanned, flags_found = _resume_progress_for_mission(
        {"cells_scanned": 42, "flags_found": 3},
        total_cells=16,
    )

    assert cells_scanned == 16
    assert flags_found == 3


def test_resume_progress_tolerates_bad_state():
    cells_scanned, flags_found = _resume_progress_for_mission(
        {"cells_scanned": "bad", "flags_found": 3},
        total_cells=16,
    )

    assert cells_scanned == 0
    assert flags_found == 0
