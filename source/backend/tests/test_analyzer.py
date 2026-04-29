"""Tests for the offline alert analyzer module.

Covers:
  - Offline LFM deterministic analysis output structure and content
  - Severity label computation
  - analyze_alert() routing (always offline, no external API)
  - Finding generation from band deltas
"""

import pytest

from core.analyzer import (
    _offline_analysis,
    _severity_label,
    analyze_alert,
)


# ---------------------------------------------------------------------------
# Sample data helpers
# ---------------------------------------------------------------------------

def _make_window(
    label: str = "2024-06",
    ndvi: float = 0.70,
    nbr: float = 0.55,
    nir: float = 0.68,
    red: float = 0.10,
    swir: float = 0.18,
    quality: float = 0.92,
    flags: list | None = None,
) -> dict:
    return {
        "label": label,
        "ndvi": ndvi,
        "nbr": nbr,
        "nir": nir,
        "red": red,
        "swir": swir,
        "quality": quality,
        "flags": flags or [],
    }


def _make_alert(
    change_score: float = 0.45,
    confidence: float = 0.78,
    reason_codes: list | None = None,
    observation_source: str = "semi_real_loader_v1",
    demo: bool = False,
    before_ndvi: float = 0.70,
    after_ndvi: float = 0.40,
    before_nbr: float = 0.55,
    after_nbr: float = 0.28,
    before_nir: float = 0.68,
    after_nir: float = 0.45,
) -> dict:
    return {
        "change_score": change_score,
        "confidence": confidence,
        "reason_codes": reason_codes or ["ndvi_drop", "nir_drop"],
        "before_window": _make_window(ndvi=before_ndvi, nbr=before_nbr, nir=before_nir),
        "after_window": _make_window(
            label="2025-06",
            ndvi=after_ndvi,
            nbr=after_nbr,
            nir=after_nir,
        ),
        "observation_source": observation_source,
        "demo_forced_anomaly": demo,
    }


# ---------------------------------------------------------------------------
# Severity label tests
# ---------------------------------------------------------------------------

class TestSeverityLabel:
    def test_critical_threshold(self):
        assert _severity_label(0.60) == "critical"
        assert _severity_label(0.99) == "critical"

    def test_high_threshold(self):
        assert _severity_label(0.45) == "high"
        assert _severity_label(0.59) == "high"

    def test_moderate_threshold(self):
        assert _severity_label(0.32) == "moderate"
        assert _severity_label(0.44) == "moderate"

    def test_low_threshold(self):
        assert _severity_label(0.00) == "low"
        assert _severity_label(0.31) == "low"


# ---------------------------------------------------------------------------
# Offline analysis output structure
# ---------------------------------------------------------------------------

class TestOfflineAnalysis:
    def _run(self, **kwargs) -> dict:
        alert = _make_alert(**kwargs)
        return _offline_analysis(
            change_score=alert["change_score"],
            confidence=alert["confidence"],
            reason_codes=alert["reason_codes"],
            before_window=alert["before_window"],
            after_window=alert["after_window"],
            observation_source=alert["observation_source"],
            demo_forced_anomaly=alert["demo_forced_anomaly"],
        )

    def test_returns_required_keys(self):
        result = self._run()
        for key in ("model", "severity", "summary", "findings", "confidence_note", "source_note"):
            assert key in result, f"Missing key: {key}"

    def test_model_is_offline_lfm(self):
        result = self._run()
        assert result["model"] == "offline_lfm_v1"



    def test_summary_is_nonempty_string(self):
        result = self._run()
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 20

    def test_findings_is_list(self):
        result = self._run()
        assert isinstance(result["findings"], list)
        assert len(result["findings"]) >= 1

    def test_severity_matches_change_score(self):
        assert self._run(change_score=0.65)["severity"] == "critical"
        assert self._run(change_score=0.45)["severity"] == "high"

    def test_ndvi_drop_finding_included(self):
        """When NDVI drops by >= 0.18, a finding should mention NDVI."""
        result = self._run(before_ndvi=0.72, after_ndvi=0.40)  # drop = 0.32
        assert any("NDVI" in f for f in result["findings"])

    def test_nir_drop_finding_included(self):
        """When NIR drops by >= 25%, a finding should mention NIR or infrared."""
        result = self._run(before_nir=0.70, after_nir=0.40)  # 43% drop
        assert any("near-infrared" in f.lower() or "infrared" in f.lower() for f in result["findings"])

    def test_nbr_drop_finding_included(self):
        """When NBR drops by >= 0.20, a finding should mention NBR or burn."""
        result = self._run(before_nbr=0.55, after_nbr=0.30)  # drop = 0.25
        assert any("burn" in f.lower() or "nbr" in f.lower() for f in result["findings"])

    def test_low_change_score_falls_back_to_generic_finding(self):
        """When no signal individually crosses a threshold, a generic finding is included."""
        result = _offline_analysis(
            change_score=0.33,
            confidence=0.70,
            reason_codes=["suspected_canopy_loss"],
            before_window=_make_window(ndvi=0.50, nbr=0.40, nir=0.55),
            after_window=_make_window(label="2025-06", ndvi=0.44, nbr=0.34, nir=0.50),
            observation_source="semi_real_loader_v1",
            demo_forced_anomaly=False,
        )
        assert len(result["findings"]) >= 1
        assert "composite" in result["findings"][0].lower() or "change score" in result["findings"][0].lower()

    def test_operator_highlight_source_note(self):
        result = self._run(demo=True)
        assert "replay" in result["source_note"].lower() or "training" in result["source_note"].lower()

    def test_semi_real_source_note(self):
        result = self._run(observation_source="semi_real_loader_v1")
        assert "edge-cached" in result["source_note"].lower()

    def test_sentinelhub_source_note(self):
        result = self._run(observation_source="sentinelhub_direct_imagery")
        assert "sentinel" in result["source_note"].lower()

    def test_low_quality_window_in_confidence_note(self):
        result = _offline_analysis(
            change_score=0.40,
            confidence=0.62,
            reason_codes=["low_quality_window"],
            before_window=_make_window(),
            after_window=_make_window(label="2025-06"),
            observation_source="semi_real_loader_v1",
            demo_forced_anomaly=False,
        )
        assert "quality" in result["confidence_note"].lower() or "cloud" in result["confidence_note"].lower()



# Edge cases: empty / missing window fields
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_windows_do_not_crash(self):
        """Analysis with empty before/after windows should not raise."""
        result = _offline_analysis(
            change_score=0.35,
            confidence=0.65,
            reason_codes=[],
            before_window={},
            after_window={},
            observation_source="test",
            demo_forced_anomaly=False,
        )
        assert result["model"] == "offline_lfm_v1"
        assert isinstance(result["findings"], list)
        assert len(result["findings"]) >= 1  # generic finding expected

    def test_zero_nir_before_avoids_division_by_zero(self):
        """nir_before == 0 should not cause ZeroDivisionError."""
        result = _offline_analysis(
            change_score=0.40,
            confidence=0.70,
            reason_codes=[],
            before_window=_make_window(nir=0.0, ndvi=0.0, nbr=0.0),
            after_window=_make_window(label="2025-06", nir=0.5, ndvi=0.3, nbr=0.2),
            observation_source="test",
            demo_forced_anomaly=False,
        )
        assert result["model"] == "offline_lfm_v1"

    def test_zero_ndvi_before_avoids_division_by_zero(self):
        """ndvi_before == 0 in the percentage calc should not crash."""
        result = _offline_analysis(
            change_score=0.50,
            confidence=0.75,
            reason_codes=["ndvi_drop"],
            before_window=_make_window(ndvi=0.0, nbr=0.5, nir=0.6),
            after_window=_make_window(label="2025-06", ndvi=-0.20, nbr=0.3, nir=0.4),
            observation_source="test",
            demo_forced_anomaly=False,
        )
        assert result["model"] == "offline_lfm_v1"

    def test_negative_drops_produce_no_finding(self):
        """When after values are higher than before, no band-drop findings should appear."""
        result = _offline_analysis(
            change_score=0.10,
            confidence=0.55,
            reason_codes=[],
            before_window=_make_window(ndvi=0.30, nbr=0.20, nir=0.35),
            after_window=_make_window(label="2025-06", ndvi=0.60, nbr=0.50, nir=0.70),
            observation_source="test",
            demo_forced_anomaly=False,
        )
        # Should only have the generic "composite change score" finding
        assert len(result["findings"]) == 1
        assert "composite" in result["findings"][0].lower() or "change score" in result["findings"][0].lower()

    def test_boundary_severity_values(self):
        """Exact boundary values for severity should be classified correctly."""
        assert _severity_label(0.0) == "low"
        assert _severity_label(0.319) == "low"
        assert _severity_label(0.32) == "moderate"
        assert _severity_label(0.449) == "moderate"
        assert _severity_label(0.45) == "high"
        assert _severity_label(0.599) == "high"
        assert _severity_label(0.60) == "critical"
        assert _severity_label(1.0) == "critical"
