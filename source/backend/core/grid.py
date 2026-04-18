from typing import Any

# Global step size for squared grid cells in degrees (~11km x 11km at equator)
STEP_SIZE = 0.1

def latlng_to_cell(lat: float, lng: float, resolution: int = 5) -> str:
    """Mock h3 function to return a square string identifier."""
    # resolution is ignored for squares, we use step size
    c_lat = round(round(lat / STEP_SIZE) * STEP_SIZE, 4)
    c_lng = round(round(lng / STEP_SIZE) * STEP_SIZE, 4)
    return f"sq_{c_lat}_{c_lng}"

def cell_to_latlng(cell_id: str) -> tuple[float, float]:
    """Parse lat,lng centroid from squarified cell_id."""
    # format is sq_LAT_LNG
    if str(cell_id).startswith("sq_"):
        parts = str(cell_id).split('_')
        return float(parts[1]), float(parts[2])
    return 0.0, 0.0

def cell_to_boundary(cell_id: str) -> list[tuple[float, float]]:
    """Return corner coordinates of the cell. Matches h3.cell_to_boundary."""
    lat, lng = cell_to_latlng(cell_id)
    w = lng - STEP_SIZE / 2
    e = lng + STEP_SIZE / 2
    s = lat - STEP_SIZE / 2
    n = lat + STEP_SIZE / 2
    # Returns [(lat, lng), ...] like h3.cell_to_boundary does
    return [
        (n, w),
        (n, e),
        (s, e),
        (s, w)
    ]

def _to_geojson_ring(cell_id: str) -> list[list[float]]:
    boundary = cell_to_boundary(cell_id)
    # geojson takes [lng, lat]
    ring = [[lng, lat] for lat, lng in boundary]

    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])

    return ring

def generate_scan_grid(lat: float, lng: float, resolution: int = 5, ring_size: int = 6) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    
    center_lat = round(lat / STEP_SIZE) * STEP_SIZE
    center_lng = round(lng / STEP_SIZE) * STEP_SIZE
    
    for i in range(-ring_size, ring_size + 1):
        for j in range(-ring_size, ring_size + 1):
            c_lat = center_lat + i * STEP_SIZE
            c_lng = center_lng + j * STEP_SIZE
            c_lat = round(c_lat, 4)
            c_lng = round(c_lng, 4)
            cell_id = f"sq_{c_lat}_{c_lng}"
            
            features.append(
                {
                    "type": "Feature",
                    "id": cell_id,
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [_to_geojson_ring(cell_id)],
                    },
                    "properties": {
                        "cell_id": cell_id,
                    },
                }
            )

    return {
        "type": "FeatureCollection",
        "features": features,
    }

def generate_grid_for_bbox(bbox: list[float]) -> dict[str, Any]:
    w, s, e, n = bbox
    features: list[dict[str, Any]] = []
    
    import math
    min_lat = math.floor(s / STEP_SIZE) * STEP_SIZE
    max_lat = math.ceil(n / STEP_SIZE) * STEP_SIZE
    min_lng = math.floor(w / STEP_SIZE) * STEP_SIZE
    max_lng = math.ceil(e / STEP_SIZE) * STEP_SIZE
    
    # safeguard to prevent massive grids
    if (max_lat - min_lat) / STEP_SIZE > 50 or (max_lng - min_lng) / STEP_SIZE > 50:
        return generate_scan_grid(s + (n-s)/2, w + (e-w)/2, resolution=5, ring_size=10)

    lat = min_lat
    while lat <= max_lat + 0.0001:
        lng = min_lng
        while lng <= max_lng + 0.0001:
            c_lat = round(lat, 4)
            c_lng = round(lng, 4)
            cell_id = f"sq_{c_lat}_{c_lng}"
            
            features.append(
                {
                    "type": "Feature",
                    "id": cell_id,
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [_to_geojson_ring(cell_id)],
                    },
                    "properties": {
                        "cell_id": cell_id,
                    },
                }
            )
            lng += STEP_SIZE
        lat += STEP_SIZE

    return {
        "type": "FeatureCollection",
        "features": features,
    }