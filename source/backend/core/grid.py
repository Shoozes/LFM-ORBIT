import math
from typing import Any, Sequence

# Global step size for squared grid cells in degrees (~11km x 11km at equator)
STEP_SIZE = 0.1


def normalize_bbox(bbox: Sequence[float]) -> list[float]:
    """Validate and normalize a WGS84 bbox as [west, south, east, north]."""
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        raise ValueError("bbox must contain exactly four values: [west, south, east, north]")

    try:
        west, south, east, north = [float(value) for value in bbox]
    except (TypeError, ValueError) as exc:
        raise ValueError("bbox values must be numeric") from exc

    if not all(math.isfinite(value) for value in (west, south, east, north)):
        raise ValueError("bbox values must be finite")
    if not (-180.0 <= west < east <= 180.0):
        raise ValueError("bbox longitude bounds must satisfy -180 <= west < east <= 180")
    if not (-90.0 <= south < north <= 90.0):
        raise ValueError("bbox latitude bounds must satisfy -90 <= south < north <= 90")

    return [west, south, east, north]


def is_supported_cell_id(cell_id: str) -> bool:
    """Return whether a cell id can be resolved by the current square-grid runtime."""
    text = str(cell_id)
    if not text.startswith("sq_"):
        return False
    try:
        lat, lng = cell_to_latlng(text)
    except (IndexError, TypeError, ValueError):
        return False
    return math.isfinite(lat) and math.isfinite(lng) and -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0


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
        if len(parts) != 3:
            raise ValueError(f"Invalid square cell id: {cell_id}")
        return float(parts[1]), float(parts[2])
    return 0.0, 0.0

def get_cell_neighbors(cell_id: str, radius: int = 1) -> list[str]:
    """Return a list of neighboring cell IDs within a given radius using the mocked step size."""
    lat, lng = cell_to_latlng(cell_id)
    if lat == 0.0 and lng == 0.0:
        return []

    neighbors = []
    for i in range(-radius, radius + 1):
        for j in range(-radius, radius + 1):
            if i == 0 and j == 0:
                continue
            c_lat = round(lat + i * STEP_SIZE, 4)
            c_lng = round(lng + j * STEP_SIZE, 4)
            neighbors.append(f"sq_{c_lat}_{c_lng}")

    return neighbors

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
    w, s, e, n = normalize_bbox(bbox)
    features: list[dict[str, Any]] = []

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
