import pytest

from core.indices import compute_ndvi, compute_ndvi_from_bands


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


def test_missing_nir_returns_unavailable_instead_of_fake_ndvi():
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
