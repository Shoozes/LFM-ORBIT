"""
Spectral index utilities for remote sensing analysis.
Provides pure functions for common vegetation and disturbance indices.
"""

def compute_ndvi(nir: float, red: float) -> float:
    """Normalized Difference Vegetation Index."""
    denominator = nir + red
    if denominator <= 0:
        return 0.0
    return (nir - red) / denominator

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
