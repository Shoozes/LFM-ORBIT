export type GeoPoint = {
  lng: number;
  lat: number;
  alt?: number;
};

export type LocalPoint3D = {
  x: number;
  y: number;
  z: number;
};

export type Map3DOrigin = {
  lng: number;
  lat: number;
  alt: number;
};

export type Map3DContext = {
  id: string;
  name: string;
  capturedAt: string;
  sourceName: string;
  attribution: string;
  origin: Map3DOrigin;
  isTimelineFrame: false;
  tilesetUrl?: string;
  accuracyMeters?: number;
  notes?: string;
};

const WGS84_A = 6378137.0;
const WGS84_E2 = 6.69437999014e-3;
const METERS_PER_DEGREE_AT_EQUATOR = 111320;

export function isValidGeographicBbox(value: number[] | null | undefined): value is [number, number, number, number] {
  if (!Array.isArray(value) || value.length !== 4) return false;
  const [west, south, east, north] = value;
  return (
    value.every((entry) => Number.isFinite(entry)) &&
    west >= -180 &&
    east <= 180 &&
    south >= -90 &&
    north <= 90 &&
    west < east &&
    south < north
  );
}

export function degreesToRadians(value: number): number {
  return value * Math.PI / 180;
}

export function lonLatAltToEcef(point: GeoPoint): [number, number, number] {
  const lon = degreesToRadians(point.lng);
  const lat = degreesToRadians(point.lat);
  const alt = point.alt ?? 0;

  const sinLat = Math.sin(lat);
  const cosLat = Math.cos(lat);
  const sinLon = Math.sin(lon);
  const cosLon = Math.cos(lon);
  const n = WGS84_A / Math.sqrt(1 - WGS84_E2 * sinLat * sinLat);

  return [
    (n + alt) * cosLat * cosLon,
    (n + alt) * cosLat * sinLon,
    (n * (1 - WGS84_E2) + alt) * sinLat,
  ];
}

export function lonLatAltToLocal(point: GeoPoint, origin: Map3DOrigin): LocalPoint3D {
  const [x, y, z] = lonLatAltToEcef(point);
  const [ox, oy, oz] = lonLatAltToEcef(origin);

  const dx = x - ox;
  const dy = y - oy;
  const dz = z - oz;

  const lon = degreesToRadians(origin.lng);
  const lat = degreesToRadians(origin.lat);

  const sinLat = Math.sin(lat);
  const cosLat = Math.cos(lat);
  const sinLon = Math.sin(lon);
  const cosLon = Math.cos(lon);

  const east = -sinLon * dx + cosLon * dy;
  const north = -sinLat * cosLon * dx - sinLat * sinLon * dy + cosLat * dz;
  const up = cosLat * cosLon * dx + cosLat * sinLon * dy + sinLat * dz;

  return { x: east, y: up, z: -north };
}

export function bboxCenter(bbox: number[]): { lng: number; lat: number } {
  const [west, south, east, north] = bbox;
  return {
    lng: (west + east) / 2,
    lat: (south + north) / 2,
  };
}

export function bboxToRing(bbox: number[], altitude = 2): GeoPoint[] {
  const [west, south, east, north] = bbox;
  return [
    { lng: west, lat: north, alt: altitude },
    { lng: east, lat: north, alt: altitude },
    { lng: east, lat: south, alt: altitude },
    { lng: west, lat: south, alt: altitude },
  ];
}

export function get3DContextWarning(timelineDate: string | null | undefined, contextCapturedAt: string): string | null {
  if (!timelineDate) return null;
  const timeline = new Date(timelineDate);
  const captured = new Date(contextCapturedAt);
  if (Number.isNaN(timeline.getTime()) || Number.isNaN(captured.getTime())) return null;

  const millisecondsPerDay = 1000 * 60 * 60 * 24;
  const differenceDays = Math.abs(timeline.getTime() - captured.getTime()) / millisecondsPerDay;
  if (differenceDays <= 30) return null;
  return timeline < captured
    ? "The 3D view is newer than the selected timeline date. Use it for spatial context only."
    : "The 3D view is older than the selected timeline date. Use it for spatial context only.";
}

export function estimateBboxSizeMeters(bbox: number[]): { width: number; depth: number } {
  const [west, south, east, north] = bbox;
  const centerLat = (south + north) / 2;
  const width = Math.abs(east - west) * METERS_PER_DEGREE_AT_EQUATOR * Math.cos(degreesToRadians(centerLat));
  const depth = Math.abs(north - south) * METERS_PER_DEGREE_AT_EQUATOR;
  return {
    width: Math.max(width, 80),
    depth: Math.max(depth, 80),
  };
}
