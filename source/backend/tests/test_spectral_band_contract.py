import pytest

from core.indices import (
    compute_blue_green_haze_score,
    compute_dnbr,
    compute_ndmi,
    compute_ndmi_s2,
    compute_nbr,
    compute_nbr_s2,
    compute_ndsi,
    compute_ndsi_from_bands,
    compute_ndvi,
    compute_ndvi_from_bands,
    compute_visible_whiteness,
)


def test_ndvi_requires_explicit_nir_and_red_bands():
    result = compute_ndvi_from_bands({"nir": 0.71, "red": 0.09})

    assert result["available"] is True
    assert result["abstain"] is False
    assert result["ndvi"] == pytest.approx(compute_ndvi(0.71, 0.09))


def test_rgb_only_imagery_cannot_produce_real_ndvi():
    result = compute_ndvi_from_bands({"red": 0.09, "green": 0.22, "blue": 0.18})

    assert result["available"] is False
    assert result["abstain"] is True
    assert result["ndvi"] is None
    assert "NIR and Red" in result["reason"]


def test_missing_nir_returns_unavailable_instead_of_fabricated_ndvi():
    result = compute_ndvi_from_bands({"red": 0.18})

    assert result == {
        "available": False,
        "abstain": True,
        "ndvi": None,
        "reason": "NDVI requires explicit NIR and Red bands.",
    }


def test_non_numeric_bands_return_unavailable_instead_of_raising():
    result = compute_ndvi_from_bands({"nir": "not-a-number", "red": 0.18})

    assert result == {
        "available": False,
        "abstain": True,
        "ndvi": None,
        "reason": "NDVI requires numeric NIR and Red bands.",
    }


def test_ndsi_requires_explicit_green_and_swir1_bands():
    result = compute_ndsi_from_bands({"green": 0.72, "swir1": 0.18})

    assert result["available"] is True
    assert result["abstain"] is False
    assert result["ndsi"] == pytest.approx(compute_ndsi(0.72, 0.18))


def test_rgb_only_imagery_cannot_produce_real_ndsi():
    result = compute_ndsi_from_bands({"red": 0.09, "green": 0.72, "blue": 0.18})

    assert result["available"] is False
    assert result["abstain"] is True
    assert result["ndsi"] is None
    assert "Green and SWIR1" in result["reason"]


def test_sentinel2_burn_and_smoke_helpers_use_explicit_bands():
    assert compute_nbr_s2(0.42, 0.18) == pytest.approx(compute_nbr(0.42, 0.18))
    assert compute_ndmi_s2(0.42, 0.21) == pytest.approx(compute_ndmi(0.42, 0.21))
    assert compute_dnbr(0.62, 0.22) == pytest.approx(0.4)
    assert compute_visible_whiteness(0.5, 0.48, 0.46) == pytest.approx(0.92)
    assert compute_blue_green_haze_score(0.21, 0.20, 0.12) == pytest.approx(0.51)
