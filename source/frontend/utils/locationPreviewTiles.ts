import type { LocationBbox, LocationPreviewTile } from "../types/location";

const ESRI_WORLD_IMAGERY_TILE =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function lonLatToTile(lng: number, lat: number, z: number): { x: number; y: number } {
  const safeLat = clamp(lat, -85.05112878, 85.05112878);
  const latRad = (safeLat * Math.PI) / 180;
  const n = 2 ** z;
  const x = Math.floor(((lng + 180) / 360) * n);
  const y = Math.floor(((1 - Math.asinh(Math.tan(latRad)) / Math.PI) / 2) * n);

  return {
    x: clamp(x, 0, n - 1),
    y: clamp(y, 0, n - 1),
  };
}

function estimateZoomForBbox(bbox: LocationBbox): number {
  const [west, south, east, north] = bbox;
  const lonSpan = Math.max(0.0001, Math.abs(east - west));
  const latSpan = Math.max(0.0001, Math.abs(north - south));
  const span = Math.max(lonSpan, latSpan);

  return clamp(Math.floor(Math.log2(360 / (span * 2.4))), 4, 14);
}

function tileUrl(template: string, tile: Omit<LocationPreviewTile, "url">): string {
  return template
    .replace("{z}", String(tile.z))
    .replace("{x}", String(tile.x))
    .replace("{y}", String(tile.y));
}

export function buildPreviewTiles(bbox: LocationBbox): LocationPreviewTile[] {
  const [west, south, east, north] = bbox;
  const centerLng = (west + east) / 2;
  const centerLat = (south + north) / 2;
  const z = estimateZoomForBbox(bbox);
  const centerTile = lonLatToTile(centerLng, centerLat, z);
  const maxIndex = 2 ** z - 1;
  const tiles: LocationPreviewTile[] = [];

  for (let dy = -1; dy <= 1; dy += 1) {
    for (let dx = -1; dx <= 1; dx += 1) {
      const tile = {
        z,
        x: clamp(centerTile.x + dx, 0, maxIndex),
        y: clamp(centerTile.y + dy, 0, maxIndex),
      };

      tiles.push({
        ...tile,
        url: tileUrl(ESRI_WORLD_IMAGERY_TILE, tile),
      });
    }
  }

  return tiles;
}
