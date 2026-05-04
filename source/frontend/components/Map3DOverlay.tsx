import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl, {
  LngLatBoundsLike,
  Map as MaplibreMap,
  type MapLayerMouseEvent,
  type StyleSpecification,
} from "maplibre-gl";
import type { VlmBox } from "./VlmPanel";
import { colorForVlmBox, unitBoxToGeographicBbox } from "../utils/objectEvidence";
import {
  bboxCenter,
  get3DContextWarning,
  isValidGeographicBbox,
  type Map3DContext,
} from "../utils/geo3d";
import { readDepthMapStats } from "../utils/depthMapStats";
import { getApiBaseUrl } from "../utils/telemetry";

type Map3DOverlayProps = {
  open: boolean;
  activeBbox: number[] | null;
  vlmBoxes: VlmBox[];
  timelineDate?: string | null;
  onClose: () => void;
};

type Map3DLoadState = "idle" | "loading" | "ready" | "error" | "unavailable";

type ObjectTooltip = {
  x: number;
  y: number;
  label: string;
  confidence: string;
  source: string;
  mode: string;
};

type PolygonProperties = {
  label: string;
  labelText: string;
  confidence: string;
  color: string;
  height: number;
  source: string;
  mode: string;
};

type ReliefProperties = {
  label: string;
  height: number;
  color: string;
};

type DepthStatus = {
  enabled?: boolean;
  available?: boolean;
  reason?: string;
  device?: string;
  model_id?: string;
};

type AiContextSummary = {
  statusLabel: string;
  cueLabel: string;
  detail: string;
  modelNote: string;
};

const DEFAULT_CONTEXT_DATE = "2026-04-30";
const DEFAULT_TERRAIN_EXAGGERATION = 3.2;
const RELIEF_GRID_SIZE = 14;
const DEFAULT_SATELLITE_TILE =
  "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg";
const DEFAULT_TERRAIN_TILEJSON = "https://demotiles.maplibre.org/terrain-tiles/tiles.json";

function configuredSatelliteTiles(): string[] {
  const value = import.meta.env.VITE_LFM_3D_SATELLITE_TILES;
  if (typeof value !== "string" || !value.trim()) return [DEFAULT_SATELLITE_TILE];
  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function configuredTerrainUrl(): string {
  const value = import.meta.env.VITE_LFM_3D_TERRAIN_TILEJSON;
  return typeof value === "string" && value.trim() ? value.trim() : DEFAULT_TERRAIN_TILEJSON;
}

function formatTimelineDate(value: string | null | undefined): string {
  if (!value) return "current 2D map state";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toISOString().slice(0, 10);
}

function confidenceLabel(box: VlmBox): string {
  return typeof box.confidence === "number" && Number.isFinite(box.confidence)
    ? box.confidence.toFixed(2)
    : "candidate";
}

function hashNumber(input: string): number {
  let hash = 2166136261;
  for (let index = 0; index < input.length; index += 1) {
    hash ^= input.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function seededRandom(seed: number): () => number {
  let state = seed || 1;
  return () => {
    state = Math.imul(1664525, state) + 1013904223;
    return ((state >>> 0) / 4294967296);
  };
}

function makeFallbackSatelliteImage(activeBbox: number[], boxes: VlmBox[]): string {
  const random = seededRandom(hashNumber(activeBbox.map((entry) => entry.toFixed(4)).join(",")));
  const canvas = document.createElement("canvas");
  canvas.width = 768;
  canvas.height = 768;
  const context = canvas.getContext("2d");
  if (!context) return "";

  const gradient = context.createLinearGradient(0, 0, canvas.width, canvas.height);
  gradient.addColorStop(0, "#082f35");
  gradient.addColorStop(0.34, "#174f35");
  gradient.addColorStop(0.68, "#57612f");
  gradient.addColorStop(1, "#7a5a36");
  context.fillStyle = gradient;
  context.fillRect(0, 0, canvas.width, canvas.height);

  for (let index = 0; index < 4600; index += 1) {
    const x = random() * canvas.width;
    const y = random() * canvas.height;
    const radius = 0.8 + random() * 4.2;
    const green = Math.floor(58 + random() * 98);
    context.fillStyle = `rgba(${Math.floor(18 + random() * 72)}, ${green}, ${Math.floor(32 + random() * 64)}, ${0.12 + random() * 0.24})`;
    context.beginPath();
    context.arc(x, y, radius, 0, Math.PI * 2);
    context.fill();
  }

  for (let band = 0; band < 13; band += 1) {
    const yBase = (band / 12) * canvas.height;
    context.strokeStyle = `rgba(255, 255, 255, ${band % 3 === 0 ? 0.14 : 0.08})`;
    context.lineWidth = band % 3 === 0 ? 1.8 : 1;
    context.beginPath();
    for (let x = -32; x <= canvas.width + 32; x += 28) {
      const y = yBase
        + Math.sin((x / canvas.width) * Math.PI * 2 + band * 0.9) * (18 + band * 1.2)
        + Math.cos((x / canvas.width) * Math.PI * 4 + band) * 7;
      if (x === -32) context.moveTo(x, y);
      else context.lineTo(x, y);
    }
    context.stroke();
  }

  for (let ridge = 0; ridge < 18; ridge += 1) {
    const x = random() * canvas.width;
    context.strokeStyle = ridge % 2 === 0 ? "rgba(0, 0, 0, 0.12)" : "rgba(255, 255, 255, 0.08)";
    context.lineWidth = 6 + random() * 12;
    context.beginPath();
    context.moveTo(x - 240, -20);
    context.bezierCurveTo(
      x - 120 + random() * 80,
      canvas.height * 0.28,
      x + 80 - random() * 80,
      canvas.height * 0.66,
      x + 220,
      canvas.height + 20,
    );
    context.stroke();
  }

  const roads: Array<Array<[number, number]>> = [
    [[0.05, 0.72], [0.26, 0.6], [0.49, 0.54], [0.75, 0.39], [0.95, 0.27]],
    [[0.22, 0.08], [0.32, 0.26], [0.44, 0.42], [0.56, 0.64], [0.7, 0.91]],
    [[0.38, 0.55], [0.29, 0.74], [0.17, 0.91]],
  ];
  roads.forEach((road, index) => {
    context.lineCap = "round";
    context.lineJoin = "round";
    context.strokeStyle = "rgba(198, 178, 130, 0.82)";
    context.lineWidth = index === 0 ? 10 : 7;
    context.beginPath();
    road.forEach(([x, y], pointIndex) => {
      if (pointIndex === 0) context.moveTo(x * canvas.width, y * canvas.height);
      else context.lineTo(x * canvas.width, y * canvas.height);
    });
    context.stroke();
  });

  boxes.forEach((box, index) => {
    const [west, south, east, north] = unitBoxToGeographicBbox(activeBbox, box);
    const [bboxWest, bboxSouth, bboxEast, bboxNorth] = activeBbox;
    const x = ((west - bboxWest) / Math.max(bboxEast - bboxWest, Number.EPSILON)) * canvas.width;
    const y = (1 - ((north - bboxSouth) / Math.max(bboxNorth - bboxSouth, Number.EPSILON))) * canvas.height;
    const width = Math.max(((east - west) / Math.max(bboxEast - bboxWest, Number.EPSILON)) * canvas.width, 24);
    const height = Math.max(((north - south) / Math.max(bboxNorth - bboxSouth, Number.EPSILON)) * canvas.height, 24);
    context.save();
    context.translate(x + width / 2, y + height / 2);
    context.rotate((index % 3 - 1) * 0.08);
    context.fillStyle = box.label.toLowerCase().includes("road")
      ? "rgba(176, 150, 104, 0.72)"
      : "rgba(171, 107, 56, 0.72)";
    context.strokeStyle = colorForVlmBox(box);
    context.lineWidth = 4;
    context.beginPath();
    context.roundRect(-width / 2, -height / 2, width, height, 10);
    context.fill();
    context.stroke();
    context.restore();
  });

  return canvas.toDataURL("image/jpeg", 0.82);
}

async function fetchDepthStatus(): Promise<DepthStatus | null> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/api/depth/status`, {
      cache: "no-store",
    });
    if (!response.ok) return null;
    return await response.json() as DepthStatus;
  } catch {
    return null;
  }
}

function fallbackAiSummary(depthStatus: DepthStatus | null, activeBbox: number[], boxes: VlmBox[]): AiContextSummary {
  const [west, south, east, north] = activeBbox;
  const areaSignal = Math.abs(east - west) * Math.abs(north - south);
  const cueLabel = boxes.length > 0
    ? "bbox + CV region structure"
    : areaSignal > 0.01
      ? "terrain-scale context"
      : "local terrain context";
  const statusLabel = depthStatus?.available
    ? depthStatus.enabled
      ? "Depth Anything ready"
      : "Depth Anything installed, disabled"
    : "Depth Anything optional";
  const reason = depthStatus?.reason ? ` ${depthStatus.reason}.` : "";
  return {
    statusLabel,
    cueLabel,
    detail: `Fast mode is using MapLibre terrain, satellite texture, and ${boxes.length} CV region overlay(s).${reason}`,
    modelNote: "No per-frame model inference was run; use this as AI review context only.",
  };
}

function summarizeCanvasContext(
  canvas: HTMLCanvasElement,
  depthStatus: DepthStatus | null,
  activeBbox: number[],
  boxes: VlmBox[],
): AiContextSummary {
  try {
    const stats = readDepthMapStats(canvas, { sampleSize: 96 });
    const textureRange = stats.max - stats.min;
    const cueLabel = stats.stddev > 0.14
      ? "strong surface/relief variation"
      : stats.stddev > 0.07
        ? "moderate structural variation"
        : "low structural variation";
    const statusLabel = depthStatus?.available
      ? depthStatus.enabled
        ? "Depth Anything ready"
        : "Depth Anything installed, disabled"
      : "Depth Anything optional";
    const modelText = depthStatus?.enabled && depthStatus.available
      ? `Depth Anything can be run on selected still frames on ${depthStatus.device ?? "auto device"} when a review needs it.`
      : "Depth Anything is not auto-run here; the fast cue comes from the rendered terrain/satellite canvas.";
    return {
      statusLabel,
      cueLabel,
      detail: `Canvas cue ${stats.backend}: range ${textureRange.toFixed(2)}, stddev ${stats.stddev.toFixed(2)}, ${boxes.length} CV region overlay(s).`,
      modelNote: `${modelText} Static 3D tiles remain dated context, not timelapse evidence.`,
    };
  } catch {
    return fallbackAiSummary(depthStatus, activeBbox, boxes);
  }
}

function makeContext(activeBbox: number[] | null): Map3DContext | null {
  if (!isValidGeographicBbox(activeBbox)) return null;
  const center = bboxCenter(activeBbox);
  return {
    id: "selected-area-maplibre-terrain",
    name: "Selected Area 3D Terrain Context",
    capturedAt: DEFAULT_CONTEXT_DATE,
    sourceName: "No-auth MapLibre satellite terrain",
    attribution: "Sentinel-2 cloudless by EOX plus public MapLibre DEM terrain",
    origin: { lng: center.lng, lat: center.lat, alt: 0 },
    isTimelineFrame: false,
    accuracyMeters: 20,
    notes: "Used as visual reference only. Not synchronized to timeline imagery.",
  };
}

function bboxPolygonFeature(bbox: number[]): GeoJSON.FeatureCollection<GeoJSON.Polygon, { label: string }> {
  const [west, south, east, north] = bbox;
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: { label: "Selected mission area" },
        geometry: {
          type: "Polygon",
          coordinates: [[
            [west, north],
            [east, north],
            [east, south],
            [west, south],
            [west, north],
          ]],
        },
      },
    ],
  };
}

function reliefHeight(
  xIndex: number,
  yIndex: number,
  gridSize: number,
  activeBbox: number[],
): number {
  const [west, south, east, north] = activeBbox;
  const seed = hashNumber(activeBbox.map((entry) => entry.toFixed(3)).join(","));
  const x = xIndex / Math.max(gridSize - 1, 1);
  const y = yIndex / Math.max(gridSize - 1, 1);
  const longitudeSignal = Math.sin((west + (east - west) * x + seed * 0.000001) * 8.7);
  const latitudeSignal = Math.cos((south + (north - south) * y - seed * 0.000001) * 10.9);
  const ridgeA = Math.sin((x * 2.8 + y * 1.45 + (seed % 17) * 0.07) * Math.PI);
  const ridgeB = Math.cos((x * -1.9 + y * 3.35 + (seed % 29) * 0.05) * Math.PI);
  const basin = 1 - Math.min(1, Math.hypot(x - 0.48, y - 0.52) * 1.55);
  const normalized = 0.5
    + longitudeSignal * 0.12
    + latitudeSignal * 0.12
    + ridgeA * 0.18
    + ridgeB * 0.14
    + basin * 0.22;
  return Math.max(40, Math.min(520, 70 + normalized * 430));
}

function reliefColor(height: number): string {
  if (height > 420) return "#9a7b50";
  if (height > 310) return "#6f7d43";
  if (height > 210) return "#386f47";
  return "#1d5d4c";
}

function localReliefFeatureCollection(
  activeBbox: number[],
): GeoJSON.FeatureCollection<GeoJSON.Polygon, ReliefProperties> {
  const [west, south, east, north] = activeBbox;
  const lonStep = (east - west) / RELIEF_GRID_SIZE;
  const latStep = (north - south) / RELIEF_GRID_SIZE;
  const features: GeoJSON.Feature<GeoJSON.Polygon, ReliefProperties>[] = [];

  for (let xIndex = 0; xIndex < RELIEF_GRID_SIZE; xIndex += 1) {
    for (let yIndex = 0; yIndex < RELIEF_GRID_SIZE; yIndex += 1) {
      const cellWest = west + lonStep * xIndex;
      const cellEast = xIndex === RELIEF_GRID_SIZE - 1 ? east : cellWest + lonStep;
      const cellSouth = south + latStep * yIndex;
      const cellNorth = yIndex === RELIEF_GRID_SIZE - 1 ? north : cellSouth + latStep;
      const height = reliefHeight(xIndex, yIndex, RELIEF_GRID_SIZE, activeBbox);
      features.push({
        type: "Feature",
        properties: {
          label: "local relief mesh",
          height,
          color: reliefColor(height),
        },
        geometry: {
          type: "Polygon",
          coordinates: [[
            [cellWest, cellNorth],
            [cellEast, cellNorth],
            [cellEast, cellSouth],
            [cellWest, cellSouth],
            [cellWest, cellNorth],
          ]],
        },
      });
    }
  }

  return {
    type: "FeatureCollection",
    features,
  };
}

function cvBoxFeatureCollection(
  activeBbox: number[],
  boxes: VlmBox[],
): GeoJSON.FeatureCollection<GeoJSON.Polygon, PolygonProperties> {
  return {
    type: "FeatureCollection",
    features: boxes.map((box, index) => {
      const [west, south, east, north] = unitBoxToGeographicBbox(activeBbox, box);
      const confidence = confidenceLabel(box);
      return {
        type: "Feature",
        properties: {
          label: box.label,
      labelText: `${box.label} ${confidence}`,
      confidence,
      color: colorForVlmBox(box),
      height: 180 + index * 56,
      source: box.source_model ?? "candidate evidence",
      mode: box.runtime_truth_mode ?? "unknown",
        },
        geometry: {
          type: "Polygon",
          coordinates: [[
            [west, north],
            [east, north],
            [east, south],
            [west, south],
            [west, north],
          ]],
        },
      };
    }),
  };
}

function build3DStyle(activeBbox: number[], boxes: VlmBox[], terrainExaggeration: number): StyleSpecification {
  const [west, south, east, north] = activeBbox;
  return {
    version: 8,
    name: "LFM Orbit No-Auth 3D Satellite Terrain",
    glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
    sources: {
      satellite: {
        type: "raster",
        tiles: configuredSatelliteTiles(),
        tileSize: 256,
        attribution: "Sentinel-2 cloudless by EOX",
        maxzoom: 17,
      },
      "local-context": {
        type: "image",
        url: makeFallbackSatelliteImage(activeBbox, boxes),
        coordinates: [
          [west, north],
          [east, north],
          [east, south],
          [west, south],
        ],
      },
      terrain: {
        type: "raster-dem",
        url: configuredTerrainUrl(),
        tileSize: 256,
        attribution: "MapLibre demo terrain",
      },
      "terrain-shade": {
        type: "raster-dem",
        url: configuredTerrainUrl(),
        tileSize: 256,
        attribution: "MapLibre demo terrain",
      },
    },
    layers: [
      {
        id: "background",
        type: "background",
        paint: {
          "background-color": "#173b32",
        },
      },
      {
        id: "local-context",
        type: "raster",
        source: "local-context",
        paint: {
          "raster-opacity": 0.98,
          "raster-saturation": 0.2,
          "raster-contrast": 0.32,
        },
      },
      {
        id: "satellite",
        type: "raster",
        source: "satellite",
        paint: {
          "raster-opacity": 0.72,
          "raster-saturation": 0.16,
          "raster-contrast": 0.18,
        },
      },
      {
        id: "terrain-relief",
        type: "hillshade",
        source: "terrain-shade",
        paint: {
          "hillshade-exaggeration": 0.48,
          "hillshade-shadow-color": "rgba(2, 6, 23, 0.62)",
          "hillshade-highlight-color": "rgba(255, 255, 255, 0.34)",
          "hillshade-accent-color": "rgba(8, 145, 178, 0.16)",
        },
      },
    ],
    terrain: {
      source: "terrain",
      exaggeration: terrainExaggeration,
    },
  };
}

function addMissionLayers(map: MaplibreMap, activeBbox: number[], vlmBoxes: VlmBox[]): void {
  map.addSource("local-relief-mesh-3d", {
    type: "geojson",
    data: localReliefFeatureCollection(activeBbox),
  });
  map.addLayer({
    id: "local-relief-mesh-3d",
    type: "fill-extrusion",
    source: "local-relief-mesh-3d",
    paint: {
      "fill-extrusion-color": ["coalesce", ["get", "color"], "#386f47"],
      "fill-extrusion-height": ["*", ["coalesce", ["get", "height"], 120], 1],
      "fill-extrusion-base": 0,
      "fill-extrusion-opacity": 0.32,
      "fill-extrusion-vertical-gradient": true,
    },
  });

  map.addSource("mission-bbox-3d", {
    type: "geojson",
    data: bboxPolygonFeature(activeBbox),
  });
  map.addLayer({
    id: "mission-bbox-3d-fill",
    type: "fill",
    source: "mission-bbox-3d",
    paint: {
      "fill-color": "#06b6d4",
      "fill-opacity": 0.14,
    },
  });
  map.addLayer({
    id: "mission-bbox-3d-line",
    type: "line",
    source: "mission-bbox-3d",
    paint: {
      "line-color": "#67e8f9",
      "line-width": 3,
      "line-opacity": 0.96,
    },
  });

  map.addSource("cv-boxes-3d", {
    type: "geojson",
    data: cvBoxFeatureCollection(activeBbox, vlmBoxes),
  });
  map.addLayer({
    id: "cv-3d-fill",
    type: "fill-extrusion",
    source: "cv-boxes-3d",
    paint: {
      "fill-extrusion-color": ["coalesce", ["get", "color"], "#22d3ee"],
      "fill-extrusion-height": ["coalesce", ["get", "height"], 120],
      "fill-extrusion-base": 0,
      "fill-extrusion-opacity": 0.68,
      "fill-extrusion-vertical-gradient": true,
    },
  });
  map.addLayer({
    id: "cv-3d-outline",
    type: "line",
    source: "cv-boxes-3d",
    paint: {
      "line-color": ["coalesce", ["get", "color"], "#22d3ee"],
      "line-width": 2,
      "line-opacity": 0.96,
    },
  });
  map.addLayer({
    id: "cv-3d-label",
    type: "symbol",
    source: "cv-boxes-3d",
    layout: {
      "text-field": ["get", "labelText"],
      "text-size": 12,
      "text-font": ["Noto Sans Regular"],
      "text-anchor": "center",
      "text-allow-overlap": true,
      "symbol-placement": "point",
    },
    paint: {
      "text-color": "#f8fafc",
      "text-halo-color": "rgba(2, 6, 23, 0.9)",
      "text-halo-width": 2,
    },
  });
}

export default function Map3DOverlay({
  open,
  activeBbox,
  vlmBoxes,
  timelineDate,
  onClose,
}: Map3DOverlayProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MaplibreMap | null>(null);
  const [loadState, setLoadState] = useState<Map3DLoadState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<ObjectTooltip | null>(null);
  const [terrainExaggeration, setTerrainExaggeration] = useState(DEFAULT_TERRAIN_EXAGGERATION);
  const [aiContextEnabled, setAiContextEnabled] = useState(false);
  const [aiContextSummary, setAiContextSummary] = useState<AiContextSummary | null>(null);
  const [aiContextLoading, setAiContextLoading] = useState(false);

  const context = useMemo(() => makeContext(activeBbox), [activeBbox]);
  const contextWarning = useMemo(
    () => (context ? get3DContextWarning(timelineDate, context.capturedAt) : null),
    [context, timelineDate],
  );

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    map.setTerrain({ source: "terrain", exaggeration: terrainExaggeration });
    if (map.getLayer("local-relief-mesh-3d")) {
      map.setPaintProperty("local-relief-mesh-3d", "fill-extrusion-height", [
        "*",
        ["coalesce", ["get", "height"], 120],
        Math.max(0.4, terrainExaggeration / DEFAULT_TERRAIN_EXAGGERATION),
      ]);
    }
  }, [terrainExaggeration]);

  useEffect(() => {
    if (!open || !aiContextEnabled || loadState !== "ready" || !isValidGeographicBbox(activeBbox)) {
      if (!aiContextEnabled) setAiContextSummary(null);
      return;
    }

    let cancelled = false;
    setAiContextLoading(true);
    const timer = window.setTimeout(async () => {
      const depthStatus = await fetchDepthStatus();
      if (cancelled) return;
      const canvas = mapRef.current?.getCanvas();
      const summary = canvas
        ? summarizeCanvasContext(canvas, depthStatus, activeBbox, vlmBoxes)
        : fallbackAiSummary(depthStatus, activeBbox, vlmBoxes);
      if (!cancelled) {
        setAiContextSummary(summary);
        setAiContextLoading(false);
      }
    }, 160);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [activeBbox, aiContextEnabled, loadState, open, vlmBoxes]);

  useEffect(() => {
    if (!open) {
      setLoadState("idle");
      setTooltip(null);
      setAiContextSummary(null);
      setAiContextLoading(false);
      return;
    }
    if (!isValidGeographicBbox(activeBbox) || !context) {
      setLoadState("unavailable");
      return;
    }
    if (!mountRef.current) return;

    let cancelled = false;
    setLoadState("loading");
    setErrorMessage(null);

    try {
      if (import.meta.env.DEV && window.localStorage.getItem("lfm_force_3d_error") === "1") {
        throw new Error("Forced 3D context error for renderer diagnostics.");
      }

      const center = bboxCenter(activeBbox);
      const map = new maplibregl.Map({
        container: mountRef.current,
        center: [center.lng, center.lat],
        zoom: 12.4,
        pitch: 76,
        bearing: -26,
        maxPitch: 85,
        attributionControl: { compact: true },
        canvasContextAttributes: {
          preserveDrawingBuffer: true,
        },
        style: build3DStyle(activeBbox, vlmBoxes, terrainExaggeration),
      });
      mapRef.current = map;
      map.getCanvas().setAttribute("data-testid", "map-3d-canvas");
      map.getCanvas().setAttribute("aria-label", "No-auth 3D satellite terrain canvas");

      map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
      map.addControl(new maplibregl.TerrainControl({
        source: "terrain",
        exaggeration: terrainExaggeration,
      }), "top-right");

      const handleMouseMove = (event: MapLayerMouseEvent) => {
        const feature = event.features?.[0];
        const properties = feature?.properties as Partial<PolygonProperties> | undefined;
        if (!properties?.label) return;
        map.getCanvas().style.cursor = "help";
        setTooltip({
          x: event.point.x + 16,
          y: event.point.y + 16,
          label: properties.label,
          confidence: properties.confidence ?? "candidate",
          source: properties.source ?? "candidate evidence",
          mode: properties.mode ?? "unknown",
        });
      };
      const handleMouseLeave = () => {
        map.getCanvas().style.cursor = "";
        setTooltip(null);
      };

      const handleStyleReady = () => {
        if (cancelled) return;
        addMissionLayers(map, activeBbox, vlmBoxes);
        map.fitBounds(activeBbox as LngLatBoundsLike, {
          padding: 88,
          duration: 0,
        });
        map.jumpTo({
          center: [center.lng, center.lat],
          pitch: 76,
          bearing: -26,
        });
        map.setTerrain({ source: "terrain", exaggeration: terrainExaggeration });
        map.setPaintProperty("local-relief-mesh-3d", "fill-extrusion-height", [
          "*",
          ["coalesce", ["get", "height"], 120],
          Math.max(0.4, terrainExaggeration / DEFAULT_TERRAIN_EXAGGERATION),
        ]);
        map.on("mousemove", "cv-3d-fill", handleMouseMove);
        map.on("mouseleave", "cv-3d-fill", handleMouseLeave);
        window.requestAnimationFrame(() => {
          if (!cancelled) setLoadState("ready");
        });
      };
      if (map.isStyleLoaded()) {
        handleStyleReady();
      } else {
        map.once("style.load", handleStyleReady);
      }

      return () => {
        cancelled = true;
        setTooltip(null);
        map.off("style.load", handleStyleReady);
        map.off("mousemove", "cv-3d-fill", handleMouseMove);
        map.off("mouseleave", "cv-3d-fill", handleMouseLeave);
        map.remove();
        if (mapRef.current === map) mapRef.current = null;
      };
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "3D context view failed to initialize.");
      setLoadState("error");
    }
  }, [activeBbox, context, open, vlmBoxes]);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [onClose, open]);

  if (!open) return null;

  return (
    <div
      data-testid="map-3d-panel"
      className="absolute inset-0 z-30 overflow-hidden bg-[#05070b]"
      role="dialog"
      aria-label="3D satellite terrain context"
      aria-modal="false"
    >
      <div ref={mountRef} className="h-full w-full" />

      <div className="absolute left-4 top-4 max-w-[340px] rounded-lg border border-white/20 bg-zinc-950/72 px-3 py-2.5 text-xs text-zinc-100 shadow-2xl backdrop-blur-md">
        <div className="mb-2 flex items-center justify-between gap-3">
          <strong className="text-[11px] uppercase tracking-[0.18em] text-cyan-100">3D satellite terrain</strong>
          <span
            data-testid="map-3d-tiles-mode"
            className="rounded border border-cyan-300/30 bg-cyan-300/10 px-1.5 py-0.5 text-[9px] uppercase tracking-[0.12em] text-cyan-100"
          >
            no auth
          </span>
        </div>
        <div className="space-y-1 leading-snug text-zinc-300">
          <p>Timeline: {formatTimelineDate(timelineDate)}</p>
          <p>Context: {context?.capturedAt ?? DEFAULT_CONTEXT_DATE}</p>
          <p>This 3D view is terrain/context, not a satellite acquisition frame.</p>
          <p>Relief boost: {terrainExaggeration.toFixed(1)}x</p>
          <p data-testid="map-3d-relief-mesh-label">Local relief mesh: on</p>
          <p>Imagery: Sentinel-2 cloudless by EOX</p>
          <p>Objects found: {vlmBoxes.length}</p>
          {contextWarning && <p className="text-amber-200">{contextWarning}</p>}
          <p className="text-zinc-500">Boxes are candidate review context.</p>
        </div>

        {vlmBoxes.length > 0 && (
          <div data-testid="map-3d-cv-list" className="mt-3 flex flex-wrap gap-1.5">
            {vlmBoxes.slice(0, 5).map((box, index) => (
              <button
                key={`${box.label}-${index}`}
                type="button"
                data-testid="map-3d-cv-chip"
                className="rounded border border-white/15 bg-zinc-950/60 px-2 py-1 text-[10px] font-semibold text-zinc-100 transition hover:border-cyan-200/60 focus:outline-none focus:ring-2 focus:ring-cyan-300"
                style={{ boxShadow: `inset 3px 0 0 ${colorForVlmBox(box)}` }}
                onMouseEnter={() => setTooltip({
                  x: 24,
                  y: 360 + index * 18,
                  label: box.label,
                  confidence: confidenceLabel(box),
                  source: box.source_model ?? "candidate evidence",
                  mode: box.runtime_truth_mode ?? "unknown",
                })}
                onFocus={() => setTooltip({
                  x: 24,
                  y: 360 + index * 18,
                  label: box.label,
                  confidence: confidenceLabel(box),
                  source: box.source_model ?? "candidate evidence",
                  mode: box.runtime_truth_mode ?? "unknown",
                })}
                onMouseLeave={() => setTooltip(null)}
                onBlur={() => setTooltip(null)}
              >
                {box.label} {confidenceLabel(box)}
              </button>
            ))}
          </div>
        )}

        <label className="mt-3 block text-[10px] uppercase tracking-[0.14em] text-zinc-400">
          Relief boost
          <span className="ml-2 font-semibold text-cyan-100">{terrainExaggeration.toFixed(1)}x</span>
          <input
            data-testid="map-3d-terrain-slider"
            className="mt-2 block h-1.5 w-full cursor-pointer accent-cyan-300"
            type="range"
            min="0.8"
            max="8"
            step="0.1"
            value={terrainExaggeration}
            onChange={(event) => setTerrainExaggeration(Number(event.currentTarget.value))}
          />
        </label>

        <div className="mt-3 rounded-md border border-emerald-300/20 bg-emerald-300/8 p-2.5">
          <label className="flex items-center justify-between gap-3 text-[10px] uppercase tracking-[0.14em] text-emerald-100">
            <span>Structure cue</span>
            <input
              data-testid="map-3d-ai-toggle"
              className="h-4 w-4 accent-emerald-300"
              type="checkbox"
              checked={aiContextEnabled}
              onChange={(event) => setAiContextEnabled(event.currentTarget.checked)}
            />
          </label>
          {aiContextEnabled && (
            <div
              data-testid="map-3d-ai-summary"
              className="mt-2 rounded border border-white/10 bg-zinc-950/45 p-2 text-[11px] leading-relaxed text-zinc-200"
            >
              {aiContextLoading && "Reading fast terrain/canvas structure cue..."}
              {!aiContextLoading && aiContextSummary && (
                <>
                  <p className="font-semibold text-emerald-100">{aiContextSummary.statusLabel}</p>
                  <p>{aiContextSummary.cueLabel}</p>
                  <p className="text-zinc-400">{aiContextSummary.detail}</p>
                  <p className="text-zinc-500">{aiContextSummary.modelNote}</p>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="absolute bottom-4 left-4 rounded-md border border-white/15 bg-zinc-950/70 px-3 py-2 text-[10px] uppercase tracking-[0.14em] text-zinc-300 backdrop-blur-md">
        Drag pan · Scroll zoom · Right-drag tilt
      </div>

      {loadState !== "ready" && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#05070b]/72 text-center text-xs font-semibold uppercase tracking-[0.24em] text-zinc-300">
          {loadState === "loading" && "Loading 3D satellite terrain..."}
          {loadState === "unavailable" && "3D context needs a selected area."}
          {loadState === "error" && (
            <span className="max-w-md normal-case tracking-normal text-red-100">
              {errorMessage ?? "3D context view failed to initialize."}
            </span>
          )}
        </div>
      )}

      {tooltip && (
        <div
          data-testid="map-3d-object-tooltip"
          className="pointer-events-none absolute max-w-[280px] rounded-md border border-cyan-300/30 bg-zinc-950/90 px-3 py-2 text-[10px] text-zinc-100 shadow-[0_0_24px_rgba(34,211,238,0.26)] backdrop-blur"
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          <div className="mb-1 text-[11px] font-bold uppercase tracking-[0.12em] text-cyan-100">{tooltip.label}</div>
          <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
            <span className="text-zinc-500">Confidence</span>
            <strong className="text-right">{tooltip.confidence}</strong>
            <span className="text-zinc-500">Source</span>
            <strong className="text-right">{tooltip.source}</strong>
            <span className="text-zinc-500">Mode</span>
            <strong className="text-right">{tooltip.mode}</strong>
          </div>
        </div>
      )}

      <button
        type="button"
        data-testid="map-3d-close"
        aria-label="Return to 2D map"
        title="Return to 2D map"
        data-ui-tip="2D map"
        data-ui-tip-position="left"
        data-active="true"
        className="view-flip-button absolute bottom-20 right-5 z-40 flex h-14 w-14 items-center justify-center rounded-full border border-white/30 bg-white text-[15px] font-black tracking-tight text-zinc-950 shadow-[0_8px_24px_rgba(0,0,0,0.34),0_0_18px_rgba(34,211,238,0.16)] backdrop-blur-md transition hover:border-cyan-200/70 hover:bg-cyan-50 focus:outline-none focus:ring-2 focus:ring-cyan-300"
        onClick={onClose}
      >
        <span>2D</span>
      </button>
    </div>
  );
}
