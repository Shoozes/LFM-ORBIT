"""Spectral index utilities for remote sensing analysis."""

from typing import Any

def compute_ndvi(nir: float, red: float) -> float:
    """Normalized Difference Vegetation Index."""
    denominator = nir + red
    if denominator <= 0:
        return 0.0
    return (nir - red) / denominator

def compute_ndsi(green: float, swir1: float) -> float:
    """Normalized Difference Snow Index."""
    denominator = green + swir1
    if denominator <= 0:
        return 0.0
    return (green - swir1) / denominator

def compute_ndwi(green: float, nir: float) -> float:
    """Green/NIR Normalized Difference Water Index."""
    denominator = green + nir
    if denominator <= 0:
        return 0.0
    return (green - nir) / denominator

def compute_ndvi_from_bands(bands: dict[str, Any]) -> dict[str, Any]:
    """Compute NDVI only when explicit NIR and Red bands are available."""
    if "nir" not in bands or "red" not in bands:
        return {
            "available": False,
            "abstain": True,
            "ndvi": None,
            "reason": "NDVI requires explicit NIR and Red bands.",
        }
    try:
        nir = float(bands["nir"])
        red = float(bands["red"])
    except (TypeError, ValueError):
        return {
            "available": False,
            "abstain": True,
            "ndvi": None,
            "reason": "NDVI requires numeric NIR and Red bands.",
        }
    return {
        "available": True,
        "abstain": False,
        "ndvi": compute_ndvi(nir, red),
        "reason": "",
    }

def compute_ndsi_from_bands(bands: dict[str, Any]) -> dict[str, Any]:
    """Compute NDSI only when explicit Green and SWIR1 bands are available."""
    if "green" not in bands or "swir1" not in bands:
        return {
            "available": False,
            "abstain": True,
            "ndsi": None,
            "reason": "NDSI requires explicit Green and SWIR1 bands.",
        }
    try:
        green = float(bands["green"])
        swir1 = float(bands["swir1"])
    except (TypeError, ValueError):
        return {
            "available": False,
            "abstain": True,
            "ndsi": None,
            "reason": "NDSI requires numeric Green and SWIR1 bands.",
        }
    return {
        "available": True,
        "abstain": False,
        "ndsi": compute_ndsi(green, swir1),
        "reason": "",
    }

def compute_evi2(nir: float, red: float) -> float:
    """Two-band Enhanced Vegetation Index (EVI2).
    More stable in dense canopy than NDVI.
    """
    denominator = nir + 2.4 * red + 1.0
    if denominator <= 0:
        return 0.0
    return 2.5 * (nir - red) / denominator

def compute_nbr(nir: float, swir2: float) -> float:
    """Normalized Burn Ratio.
    Typically uses SWIR2 (Band 12 on Sentinel-2).
    """
    denominator = nir + swir2
    if denominator <= 0:
        return 0.0
    return (nir - swir2) / denominator

def compute_ndmi(nir: float, swir1: float) -> float:
    """Normalized Difference Moisture Index.
    Typically uses SWIR1 (Band 11 on Sentinel-2).
    """
    denominator = nir + swir1
    if denominator <= 0:
        return 0.0
    return (nir - swir1) / denominator

def compute_swir_nir_ratio(nir: float, swir: float) -> float:
    """Bare soil / structural dryness proxy.
    Soil exposure causes high SWIR and low NIR. Spike indicates clearance.
    """
    if nir <= 0:
        return 0.0
    return swir / nir
