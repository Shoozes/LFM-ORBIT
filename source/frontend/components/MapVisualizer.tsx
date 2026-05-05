import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import maplibregl, {
  GeoJSONSource,
  LngLatBoundsLike,
  Map as MaplibreMap,
  Marker,
  type MapLayerMouseEvent,
  type PointLike,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { OrbitalScanEventDetail } from "../types/telemetry";
import { useMapPins } from "../hooks/useMapPins";
import type { MapPin } from "../hooks/useMapPins";
import type { VlmBox } from "../types/visualEvidence";
import { colorForVlmBox, unitBoxToGeographicBbox } from "../utils/objectEvidence";
import type { MapCameraRequest } from "../types/mapCamera";

type SpatialMenuState = {
  x: number;
  y: number;
  lng: number;
  lat: number;
  cellId: string | null;
};

type ScanCellState = Record<string, { isAnomaly?: boolean; isDiscarded?: boolean }>;

type MapVisualizerProps = {
  geoJsonGrid: GeoJSON.FeatureCollection | null;
  selectedCellId: string | null;
  onCellClick: (cellId: string) => void;
  /** When true, shift-click creates bbox corners instead of pins */
  drawBboxActive?: boolean;
  drawnBbox?: number[] | null;  // [W,S,E,N]
  onBboxDrawn?: (bbox: number[]) => void;
  /** Activate context modules */
  onMenuAssignBBox?: (bbox: number[]) => void;
  onMenuAgentVideoEval?: (bbox: number[]) => void;
  onMenuGenerateTimelapse?: (bbox: number[]) => void;
  /** Active bounding boxes provided by optional visual evidence tools */
  vlmBoxes?: VlmBox[];
  /** Durable scan paint replayed after map source or tab refreshes */
  scanCellState?: ScanCellState;
  /** True only while a live mission scan is actively moving across cells */
  scanAnimationActive?: boolean;
  /** Changes when a new mission/replay context should clear prior scan paint */
  scanStateKey?: string | number | null;
  /** Programmatic camera target from Ground Agent or mission context */
  cameraRequest?: MapCameraRequest | null;
  onCameraRequestHandled?: (requestId: string) => void;
};

const LOCAL_MAP_STYLE = {
  version: 8,
  name: "LFM Orbit Satellite Style",
  glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
  sources: {
    "esri-satellite": {
      type: "raster",
      tiles: [
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      attribution: "Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics",
      maxzoom: 19,
    },
    "esri-labels": {
      type: "raster",
      tiles: [
        "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      attribution: "© Esri",
      maxzoom: 19,
    },
  },
  layers: [
    {
      id: "background",
      type: "background",
      paint: { "background-color": "#05070b" },
    },
    {
      id: "satellite-basemap",
      type: "raster",
      source: "esri-satellite",
      paint: {
        "raster-opacity": 1.0,
        "raster-saturation": -0.05,
        "raster-brightness-max": 0.92,
        "raster-contrast": 0.12,
      },
    },
    {
      id: "reference-labels",
      type: "raster",
      source: "esri-labels",
      paint: { "raster-opacity": 0.45 },
    },
  ],
};

const SPATIAL_MENU_WIDTH = 256;
const SPATIAL_MENU_HEIGHT = 230;
const SPATIAL_MENU_MARGIN = 12;

function getGridBounds(geoJsonGrid: GeoJSON.FeatureCollection): LngLatBoundsLike | null {
  const coordinates: number[][] = [];
  for (const feature of geoJsonGrid.features) {
    if (feature.geometry.type !== "Polygon") continue;
    for (const ring of feature.geometry.coordinates) {
      for (const point of ring) coordinates.push(point);
    }
  }
  if (coordinates.length === 0) return null;
  const lngs = coordinates.map((p) => p[0]);
  const lats = coordinates.map((p) => p[1]);
  return [
    [Math.min(...lngs), Math.min(...lats)],
    [Math.max(...lngs), Math.max(...lats)],
  ];
}

function getGeoJsonSource(map: MaplibreMap | null, sourceId: string): GeoJSONSource | null {
  if (!map || !map.isStyleLoaded()) return null;
  const source = map.getSource(sourceId);
  if (!source || !("setData" in source)) return null;
  return source as GeoJSONSource;
}

function setFeatureStateIfReady(
  map: MaplibreMap | null,
  sourceId: string,
  id: string | number | null | undefined,
  state: Record<string, unknown>,
): boolean {
  if (!map || id == null || !map.isStyleLoaded() || !map.getSource(sourceId)) return false;
  try {
    map.setFeatureState({ source: sourceId, id }, state);
    return true;
  } catch {
    return false;
  }
}

function applyScanCellState(map: MaplibreMap | null, scanCellState: ScanCellState): void {
  if (!map || !map.isStyleLoaded() || !map.getSource("scan-grid")) return;
  for (const [cellId, state] of Object.entries(scanCellState)) {
    setFeatureStateIfReady(map, "scan-grid", cellId, {
      isScanned: true,
      isAnomaly: Boolean(state.isAnomaly),
      isDiscarded: Boolean(state.isDiscarded),
    });
  }
}

function getTargetCellIdAtPoint(map: MaplibreMap, point: PointLike): string | null {
  if (!map.getLayer("scan-grid-fill")) return null;
  try {
    const features = map.queryRenderedFeatures(point, { layers: ["scan-grid-fill"] });
    return getCellIdFromProperties(features[0]?.properties);
  } catch {
    return null;
  }
}

function getCellIdFromProperties(properties: unknown): string | null {
  if (!properties || typeof properties !== "object") return null;
  const value = (properties as { cell_id?: unknown }).cell_id;
  return typeof value === "string" || typeof value === "number" ? String(value) : null;
}

function formatConfidence(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : "candidate";
}

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function isRecoverableMapRenderError(message: string): boolean {
  return /could not compile .*shader|shader compile|webgl context|maplibre/i.test(message);
}

function buildVlmTooltipHtml(properties: Record<string, unknown>): string {
  const label = escapeHtml(properties.label);
  const confidence = formatConfidence(properties.confidence);
  const bbox = escapeHtml(properties.bbox);
  const prompt = escapeHtml(properties.prompt || "visual grounding");
  const sourceModel = escapeHtml(properties.source_model || "candidate evidence");
  const runtimeMode = escapeHtml(properties.runtime_truth_mode || "unknown");
  const imageryOrigin = escapeHtml(properties.imagery_origin || "unknown");
  const scoringBasis = escapeHtml(properties.scoring_basis || "visual_only");
  return `
    <div class="vlm-box-tooltip" data-testid="vlm-box-tooltip">
      <div class="vlm-box-tooltip-title">${label}</div>
      <div class="vlm-box-tooltip-row"><span>Confidence</span><strong>${confidence}</strong></div>
      <div class="vlm-box-tooltip-row"><span>BBox</span><strong>${bbox}</strong></div>
      <div class="vlm-box-tooltip-row"><span>Prompt</span><strong>${prompt}</strong></div>
      <div class="vlm-box-tooltip-row"><span>Source</span><strong>${sourceModel}</strong></div>
      <div class="vlm-box-tooltip-row"><span>Mode</span><strong>${runtimeMode}</strong></div>
      <div class="vlm-box-tooltip-row"><span>Imagery</span><strong>${imageryOrigin}</strong></div>
      <div class="vlm-box-tooltip-row"><span>Basis</span><strong>${scoringBasis}</strong></div>
    </div>
  `;
}

// ── Marker builders ──────────────────────────────────────────────────────────

function buildMarkerEl(pin: MapPin, onRemove: (id: number) => void, onClick: (cellId: string) => void): HTMLElement {
  const el = document.createElement("div");
  el.className = "map-pin-root";
  el.style.cssText = "cursor:pointer; user-select:none; z-index:1;";

  let symbol: string;
  let bg: string;
  let border: string;
  let textColor: string;
  let shadow: string;

  if (pin.pin_type === "satellite") {
    symbol = "◆";
    bg = "rgba(8, 145, 178, 0.88)";
    border = "#22d3ee";
    textColor = "#e0f2fe";
    shadow = "0 0 14px rgba(34,211,238,0.55), 0 2px 8px rgba(0,0,0,0.6)";
  } else if (pin.pin_type === "ground") {
    symbol = "●";
    bg = "rgba(5, 150, 105, 0.88)";
    border = "#34d399";
    textColor = "#d1fae5";
    shadow = "0 0 14px rgba(52,211,153,0.55), 0 2px 8px rgba(0,0,0,0.6)";
  } else {
    // operator
    symbol = "★";
    bg = "rgba(180, 83, 9, 0.90)";
    border = "#fbbf24";
    textColor = "#fef3c7";
    shadow = "0 0 14px rgba(251,191,36,0.55), 0 2px 8px rgba(0,0,0,0.6)";
  }

  // Severity badge modifier
  let severityRing = "";
  if (pin.severity === "critical") severityRing = "box-shadow: 0 0 0 2px #ef4444, " + shadow + ";";
  else if (pin.severity === "high") severityRing = "box-shadow: 0 0 0 2px #f97316, " + shadow + ";";

  const bubble = document.createElement("div");
  bubble.className = "map-pin-bubble";
  bubble.style.cssText = `
    display: flex; align-items: center; gap: ${pin.label ? "4px" : "0"};
    background: ${bg};
    border: 1.5px solid ${border};
    border-radius: 100px;
    padding: ${pin.label ? "2px 5px 2px 4px" : "2px 4px"};
    font-family: ui-monospace, monospace;
    font-size: 9px;
    font-weight: 600;
    color: ${textColor};
    box-shadow: ${severityRing || shadow};
    white-space: nowrap;
    transition: transform 0.15s ease;
    transform-origin: center center;
  `;

  const symbolEl = document.createElement("span");
  symbolEl.style.cssText = "font-size:10px; line-height:1;";
  symbolEl.textContent = symbol;
  bubble.appendChild(symbolEl);

  if (pin.label) {
    const labelEl = document.createElement("span");
    labelEl.style.cssText = "letter-spacing:0.02em; opacity:0.9; max-width:60px; overflow:hidden; text-overflow:ellipsis;";
    labelEl.textContent = pin.label.length > 10 ? `${pin.label.slice(0, 10)}…` : pin.label;
    bubble.appendChild(labelEl);
  }
  el.appendChild(bubble);

  // Tooltip on hover
  const tooltipText = pin.note
    ? `${pin.label}\n${pin.note}`
    : pin.label;

  bubble.title = tooltipText;

  // Hover scale
  bubble.addEventListener("mouseenter", () => {
    bubble.style.transform = "scale(1.08)";
  });
  bubble.addEventListener("mouseleave", () => {
    bubble.style.transform = "scale(1)";
  });

  // Click to select
  if (pin.cell_id) {
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      onClick(pin.cell_id!);
    });
  }

  // Right-click to remove operator pins
  if (pin.pin_type === "operator") {
    el.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      e.stopPropagation();
      onRemove(pin.id);
    });
  }

  return el;
}

// ── Component ────────────────────────────────────────────────────────────────

export default function MapVisualizer({
  geoJsonGrid,
  selectedCellId,
  onCellClick,
  drawBboxActive = false,
  drawnBbox = null,
  onBboxDrawn,
  onMenuAssignBBox,
  onMenuAgentVideoEval,
  onMenuGenerateTimelapse,
  vlmBoxes = [],
  scanCellState = {},
  scanAnimationActive = true,
  scanStateKey = null,
  cameraRequest = null,
  onCameraRequestHandled,
}: MapVisualizerProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MaplibreMap | null>(null);
  const firstMenuButtonRef = useRef<HTMLButtonElement | null>(null);
  const selectedCellIdRef = useRef<string | null>(selectedCellId);
  const scanCellStateRef = useRef<ScanCellState>(scanCellState);
  const previousSelectedCellId = useRef<string | null>(null);
  const didFitBounds = useRef(false);
  // Use a plain object as a map from pin id → Marker to avoid clash with MapLibre Map type
  const markerRefs = useRef<Record<number, Marker>>({});
  const pinTooltipTimeoutRef = useRef<number | null>(null);
  const vlmPopupRef = useRef<maplibregl.Popup | null>(null);
  const vlmHoverHandlersAttachedRef = useRef(false);
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);
  const [pinTooltip, setPinTooltip] = useState<string | null>(null);
  const [cameraHud, setCameraHud] = useState<MapCameraRequest | null>(null);
  const [cameraMoveState, setCameraMoveState] = useState<"idle" | "moving" | "arrived">("idle");

  // Satellite sweeping effect
  const cellCentroidsRef = useRef<Record<string, [number, number]>>({});
  const sweepTimeoutRef = useRef<number | null>(null);
  const scanStateTimeoutsRef = useRef<Set<number>>(new Set());
  const scanAnimationActiveRef = useRef(scanAnimationActive);
  const handledCameraRequestRef = useRef<string | null>(null);
  const cameraHudTimeoutRef = useRef<number | null>(null);
  const dragPanWasEnabledRef = useRef<boolean | null>(null);

  // Bbox draw state
  const bboxStartRef = useRef<[number, number] | null>(null);
  const [bboxPreview, setBboxPreview] = useState<number[] | null>(null);

  // Context Menu state
  const [contextMenu, setContextMenu] = useState<SpatialMenuState | null>(null);

  const { pins, dropPin, removePin, error: pinError } = useMapPins();

  const clearSatelliteFootprint = useCallback((map: MaplibreMap | null = mapRef.current) => {
    if (sweepTimeoutRef.current) {
      window.clearTimeout(sweepTimeoutRef.current);
      sweepTimeoutRef.current = null;
    }
    const source = getGeoJsonSource(map, "satellite-footprint");
    source?.setData({ type: "FeatureCollection", features: [] });
  }, []);

  useEffect(() => {
    const markBasemapDegraded = () => {
      setMapError((current) => current ?? "Basemap rendering degraded. Scoring is unaffected.");
    };
    const onError = (event: ErrorEvent) => {
      const message = event.error instanceof Error ? event.error.message : event.message;
      if (!isRecoverableMapRenderError(message)) return;
      markBasemapDegraded();
      event.preventDefault();
    };
    const onUnhandledRejection = (event: PromiseRejectionEvent) => {
      const message = event.reason instanceof Error ? event.reason.message : String(event.reason ?? "");
      if (!isRecoverableMapRenderError(message)) return;
      markBasemapDegraded();
      event.preventDefault();
    };

    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onUnhandledRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onUnhandledRejection);
    };
  }, []);

  const showPinTooltip = useCallback((message: string) => {
    if (pinTooltipTimeoutRef.current) {
      window.clearTimeout(pinTooltipTimeoutRef.current);
    }
    setPinTooltip(message);
    pinTooltipTimeoutRef.current = window.setTimeout(() => {
      setPinTooltip(null);
      pinTooltipTimeoutRef.current = null;
    }, 3000);
  }, []);

  const clearPinTooltip = useCallback(() => {
    if (pinTooltipTimeoutRef.current) {
      window.clearTimeout(pinTooltipTimeoutRef.current);
      pinTooltipTimeoutRef.current = null;
    }
    setPinTooltip(null);
  }, []);

  const unprojectPointer = useCallback((event: ReactPointerEvent<HTMLElement>): [number, number] | null => {
    const map = mapRef.current;
    if (!map) return null;
    const rect = map.getContainer().getBoundingClientRect();
    const lngLat = map.unproject([event.clientX - rect.left, event.clientY - rect.top]);
    return [lngLat.lng, lngLat.lat];
  }, []);

  const beginBboxPointer = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    if (!drawBboxActiveRef.current || event.button !== 0) return;
    const start = unprojectPointer(event);
    if (!start) return;
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    bboxStartRef.current = start;
    setBboxPreview([start[0], start[1], start[0], start[1]]);
  }, [unprojectPointer]);

  const updateBboxPointer = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    if (!drawBboxActiveRef.current || !bboxStartRef.current) return;
    const current = unprojectPointer(event);
    if (!current) return;
    event.preventDefault();
    event.stopPropagation();
    const [startLng, startLat] = bboxStartRef.current;
    const [lng, lat] = current;
    setBboxPreview([
      Math.min(startLng, lng),
      Math.min(startLat, lat),
      Math.max(startLng, lng),
      Math.max(startLat, lat),
    ]);
  }, [unprojectPointer]);

  const finishBboxPointer = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    if (!drawBboxActiveRef.current || !bboxStartRef.current) return;
    const current = unprojectPointer(event);
    event.preventDefault();
    event.stopPropagation();
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      // Browser may already release capture after cancellation.
    }
    if (!current) {
      bboxStartRef.current = null;
      setBboxPreview(null);
      return;
    }
    const [startLng, startLat] = bboxStartRef.current;
    const [lng, lat] = current;
    bboxStartRef.current = null;
    setBboxPreview(null);
    if (Math.abs(lng - startLng) < 0.001 || Math.abs(lat - startLat) < 0.001) {
      return;
    }
    onBboxDrawn?.([
      Math.min(startLng, lng),
      Math.min(startLat, lat),
      Math.max(startLng, lng),
      Math.max(startLat, lat),
    ]);
  }, [onBboxDrawn, unprojectPointer]);

  const cancelBboxPointer = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    bboxStartRef.current = null;
    setBboxPreview(null);
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      // Browser may already release capture after cancellation.
    }
  }, []);

  useEffect(() => {
    scanAnimationActiveRef.current = scanAnimationActive;
    if (!scanAnimationActive) {
      clearSatelliteFootprint();
      for (const timeoutId of scanStateTimeoutsRef.current) {
        window.clearTimeout(timeoutId);
      }
      scanStateTimeoutsRef.current.clear();
    }
  }, [clearSatelliteFootprint, scanAnimationActive]);

  useEffect(() => {
    if (pinError) clearPinTooltip();
  }, [pinError, clearPinTooltip]);

  // Mutable refs to resolve stale closures during single-mount map hooks
  const onCellClickRef = useRef(onCellClick);
  const dropPinRef = useRef(dropPin);
  const geoJsonGridRef = useRef(geoJsonGrid);
  const drawBboxActiveRef = useRef(drawBboxActive);

  useLayoutEffect(() => {
    onCellClickRef.current = onCellClick;
    dropPinRef.current = dropPin;
    geoJsonGridRef.current = geoJsonGrid;
    drawBboxActiveRef.current = drawBboxActive;
    selectedCellIdRef.current = selectedCellId;
  }, [onCellClick, dropPin, geoJsonGrid, drawBboxActive, selectedCellId]);

  useEffect(() => {
    scanCellStateRef.current = scanCellState;
    applyScanCellState(mapRef.current, scanCellState);
  }, [scanCellState]);

  const gridBounds = useMemo(() => {
    if (!geoJsonGrid) return null;
    return getGridBounds(geoJsonGrid);
  }, [geoJsonGrid]);

  const clampMenuPosition = (x: number, y: number) => {
    const container = mapRef.current?.getContainer() ?? mapContainer.current;
    const width = container?.clientWidth ?? SPATIAL_MENU_WIDTH;
    const height = container?.clientHeight ?? SPATIAL_MENU_HEIGHT;
    return {
      x: Math.min(Math.max(SPATIAL_MENU_MARGIN, x), Math.max(SPATIAL_MENU_MARGIN, width - SPATIAL_MENU_WIDTH - SPATIAL_MENU_MARGIN)),
      y: Math.min(Math.max(SPATIAL_MENU_MARGIN, y), Math.max(SPATIAL_MENU_MARGIN, height - SPATIAL_MENU_HEIGHT - SPATIAL_MENU_MARGIN)),
    };
  };

  const openSpatialMenu = (
    x: number,
    y: number,
    lng: number,
    lat: number,
    targetCellId: string | null,
  ) => {
    const position = clampMenuPosition(x, y);
    setContextMenu({
      ...position,
      lng,
      lat,
      cellId: targetCellId,
    });
  };

  const openSpatialMenuAtMapCenter = () => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const center = map.getCenter();
    const point = map.project(center);
    const cellId = getTargetCellIdAtPoint(map, point);
    openSpatialMenu(point.x, point.y, center.lng, center.lat, cellId);
  };

  useEffect(() => {
    if (!contextMenu) return;
    window.setTimeout(() => firstMenuButtonRef.current?.focus(), 0);
  }, [contextMenu]);

  // Map init
  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: LOCAL_MAP_STYLE as never,
      center: [-69.075, -24.25],
      zoom: 9,
      pitch: 40,
      attributionControl: false,
    });

    mapRef.current = map;

    map.on("error", (event: unknown) => {
      const message = (event as { error?: { message?: string } }).error?.message ?? "";
      const isRenderIssue = /shader|webgl|style/i.test(message);
      setMapError((current) => current ?? (
        isRenderIssue
          ? "Basemap rendering degraded. Scoring is unaffected."
          : "Basemap imagery unavailable. Scoring is unaffected."
      ));
    });

    map.on("load", () => {
      setMapError(null);
      map.addSource("scan-grid", {
        type: "geojson",
        data: geoJsonGridRef.current ?? ({ type: "FeatureCollection", features: [] } as GeoJSON.FeatureCollection),
        promoteId: "cell_id"
      });

      map.addSource("satellite-footprint", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] }
      });

      // Outer glow pulse for scanning footprint
      map.addLayer({
        id: "satellite-footprint-glow",
        type: "circle",
        source: "satellite-footprint",
        paint: {
          "circle-radius": 80,
          "circle-color": "#22d3ee",
          "circle-blur": 1.5,
          "circle-opacity": 0.45
        }
      });

      // Inner core tracking for footprint
      map.addLayer({
        id: "satellite-footprint-core",
        type: "circle",
        source: "satellite-footprint",
        paint: {
          "circle-radius": 15,
          "circle-color": "#e0f2fe",
          "circle-blur": 0.5,
          "circle-opacity": 0.8
        }
      });

      map.addLayer({
        id: "scan-grid-fill",
        type: "fill",
        source: "scan-grid",
        paint: {
          "fill-color": [
            "case",
            ["boolean", ["feature-state", "isSelected"], false], "#00ff88",
            ["boolean", ["feature-state", "isAlert"], false], "#ef4444",
            ["boolean", ["feature-state", "isAnomaly"], false], "#fbbf24",
            ["boolean", ["feature-state", "isScanned"], false], "#22c55e",
            ["boolean", ["feature-state", "isDiscarded"], false], "#4ade80",
            "#ffffff",
          ],
          "fill-opacity": [
            "case",
            ["boolean", ["feature-state", "isSelected"], false], 0.50,
            ["boolean", ["feature-state", "isAlert"], false], 0.6,
            ["boolean", ["feature-state", "isAnomaly"], false], 0.45,
            ["boolean", ["feature-state", "isScanned"], false], 0.35,
            ["boolean", ["feature-state", "isDiscarded"], false], 0.15,
            0.10,
          ],
        },
      });

      map.addLayer({
        id: "scan-grid-outline",
        type: "line",
        source: "scan-grid",
        paint: {
          "line-color": [
            "case",
            ["boolean", ["feature-state", "isSelected"], false], "#00ff88",
            ["boolean", ["feature-state", "isAlert"], false], "#ef4444",
            ["boolean", ["feature-state", "isAnomaly"], false], "#fbbf24",
            ["boolean", ["feature-state", "isScanned"], false], "#16a34a",
            "rgba(255, 255, 255, 0.6)",
          ],
          "line-width": [
            "case",
            ["boolean", ["feature-state", "isSelected"], false], 2.5,
            ["boolean", ["feature-state", "isAlert"], false], 2.0,
            ["boolean", ["feature-state", "isAnomaly"], false], 1.5,
            1.5,
          ],
          "line-opacity": 0.9,
        },
      });

      map.addSource("bbox-preview", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] }
      });

      map.addLayer({
        id: "bbox-preview-line",
        type: "line",
        source: "bbox-preview",
        paint: {
          "line-color": "#22d3ee",
          "line-dasharray": [4, 2],
          "line-width": 2,
        }
      });
      
      map.addLayer({
        id: "bbox-preview-fill",
        type: "fill",
        source: "bbox-preview",
        paint: {
          "fill-color": "#22d3ee",
          "fill-opacity": 0.05,
        }
      });

      // Cell click
      map.on("click", "scan-grid-fill", (event) => {
        const feature = event.features?.[0];
        const cellId = feature?.properties?.cell_id || feature?.id;
        if (typeof cellId === "string" || typeof cellId === "number") {
          onCellClickRef.current(String(cellId));
        }
      });

      // Context menu
      map.on("contextmenu", (event) => {
        event.originalEvent.preventDefault();
        
        let targetCellId: string | null = null;
        targetCellId = getTargetCellIdAtPoint(map, event.point);

        openSpatialMenu(event.point.x, event.point.y, event.lngLat.lng, event.lngLat.lat, targetCellId);
      });

      map.on("dragstart", () => {
        setContextMenu(null);
      });
      map.on("zoomstart", () => {
        setContextMenu(null);
      });
      map.on("click", () => {
        setContextMenu((prev) => prev ? null : prev);
      });

      applyScanCellState(map, scanCellStateRef.current);
      const activeSelectedCellId = selectedCellIdRef.current;
      if (activeSelectedCellId) {
        setFeatureStateIfReady(map, "scan-grid", activeSelectedCellId, { isSelected: true });
        previousSelectedCellId.current = activeSelectedCellId;
      }

      setMapReady(true);
    });

    return () => {
      if (sweepTimeoutRef.current) {
        window.clearTimeout(sweepTimeoutRef.current);
        sweepTimeoutRef.current = null;
      }
      if (pinTooltipTimeoutRef.current) {
        window.clearTimeout(pinTooltipTimeoutRef.current);
        pinTooltipTimeoutRef.current = null;
      }
      if (cameraHudTimeoutRef.current) {
        window.clearTimeout(cameraHudTimeoutRef.current);
        cameraHudTimeoutRef.current = null;
      }
      vlmPopupRef.current?.remove();
      vlmPopupRef.current = null;
      for (const timeoutId of scanStateTimeoutsRef.current) {
        window.clearTimeout(timeoutId);
      }
      scanStateTimeoutsRef.current.clear();
      map.remove();
      mapRef.current = null;
    };
  }, []); // Run strictly once on mount.

  // Grid data update
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !geoJsonGrid || !map.isStyleLoaded()) return; // Added isStyleLoaded safety check

    // Index centroids for radar effect
    const centroids: Record<string, [number, number]> = {};
    for (const f of geoJsonGrid.features) {
       if (f.geometry.type === "Polygon") {
          const coords = f.geometry.coordinates[0];
          const cellId = getCellIdFromProperties(f.properties);
          if (!cellId) continue;
          let sumLng = 0; let sumLat = 0;
          for (const c of coords) {
             sumLng += c[0]; sumLat += c[1];
          }
          if (coords.length > 0) {
             centroids[cellId] = [sumLng / coords.length, sumLat / coords.length];
          }
       }
    }
    cellCentroidsRef.current = centroids;

    const source = getGeoJsonSource(map, "scan-grid");
    source?.setData(geoJsonGrid);
    try {
      map.removeFeatureState({ source: "scan-grid" });
      applyScanCellState(map, scanCellStateRef.current);
      previousSelectedCellId.current = null;
      const activeSelectedCellId = selectedCellIdRef.current;
      if (activeSelectedCellId) {
        setFeatureStateIfReady(map, "scan-grid", activeSelectedCellId, { isSelected: true });
        previousSelectedCellId.current = activeSelectedCellId;
      }
    } catch {
      // Best effort only; stale feature-state cleanup must not break map rendering.
    }
    if (!didFitBounds.current && gridBounds) {
      map.fitBounds(gridBounds, { padding: 40, duration: 0 });
      didFitBounds.current = true;
    }
  }, [geoJsonGrid, gridBounds]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded() || !map.getSource("scan-grid")) return;
    try {
      map.removeFeatureState({ source: "scan-grid" });
      previousSelectedCellId.current = null;
      const activeSelectedCellId = selectedCellIdRef.current;
      if (activeSelectedCellId) {
        setFeatureStateIfReady(map, "scan-grid", activeSelectedCellId, { isSelected: true });
        previousSelectedCellId.current = activeSelectedCellId;
      }
    } catch {
      // Best effort only; new mission paint reset should not interrupt scanning.
    }
    clearSatelliteFootprint(map);
  }, [clearSatelliteFootprint, scanStateKey]);

  // Selected cell highlight
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    if (previousSelectedCellId.current && previousSelectedCellId.current !== selectedCellId) {
      setFeatureStateIfReady(map, "scan-grid", previousSelectedCellId.current, { isSelected: false });
    }
    if (selectedCellId) {
      setFeatureStateIfReady(map, "scan-grid", selectedCellId, { isSelected: true });
      previousSelectedCellId.current = selectedCellId;
    }
  }, [selectedCellId]);

  // Scan animation
  useEffect(() => {
    const handleScan = (event: Event) => {
      const scanEvent = event as CustomEvent<OrbitalScanEventDetail>;
      const map = mapRef.current;
      if (!map || !map.isStyleLoaded()) return;
      if (!scanAnimationActiveRef.current) {
        clearSatelliteFootprint(map);
        return;
      }
      const { cell_id: cellId, is_anomaly: isAnomaly } = scanEvent.detail;
      
      // Update cell visual
      setFeatureStateIfReady(map, "scan-grid", cellId, { isScanned: true });
      
      // Move realtime footprint array
      const centroid = cellCentroidsRef.current[cellId];
      if (centroid) {
         const footprintSource = getGeoJsonSource(map, "satellite-footprint");
         footprintSource?.setData({
            type: "FeatureCollection",
            features: [{
              type: "Feature",
              geometry: { type: "Point", coordinates: centroid },
              properties: {}
            }]
         });
         
         if (sweepTimeoutRef.current) window.clearTimeout(sweepTimeoutRef.current);
         sweepTimeoutRef.current = window.setTimeout(() => {
            const m = mapRef.current;
            const s = getGeoJsonSource(m, "satellite-footprint");
            s?.setData({ type: "FeatureCollection", features: [] });
          }, 350);
      }
      
      
      const timeoutId = window.setTimeout(() => {
        scanStateTimeoutsRef.current.delete(timeoutId);
        const currentMap = mapRef.current;
        setFeatureStateIfReady(currentMap, "scan-grid", cellId, {
          isScanned: true,
          isAnomaly,
          isDiscarded: !isAnomaly,
        });
      }, 120);
      scanStateTimeoutsRef.current.add(timeoutId);
    };
    window.addEventListener("orbital-scan", handleScan);
    return () => {
      window.removeEventListener("orbital-scan", handleScan);
      for (const timeoutId of scanStateTimeoutsRef.current) {
        window.clearTimeout(timeoutId);
      }
      scanStateTimeoutsRef.current.clear();
    };
  }, [clearSatelliteFootprint]);



  // BBox preview sync
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const source = getGeoJsonSource(map, "bbox-preview");
    if (!source) return;
    
    const activeBbox = bboxPreview ?? drawnBbox;

    if (activeBbox) {
      const [w, s, e, n] = activeBbox;
      const data: GeoJSON.FeatureCollection = {
        type: "FeatureCollection",
        features: [{
          type: "Feature",
          geometry: {
            type: "Polygon",
            coordinates: [[[w, n], [e, n], [e, s], [w, s], [w, n]]]
          },
          properties: {}
        }]
      };
      source.setData(data);
    } else {
      source.setData({ type: "FeatureCollection", features: [] });
    }
  }, [bboxPreview, drawnBbox, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !drawnBbox) return;
    const [west, south, east, north] = drawnBbox;
    map.fitBounds([[west, south], [east, north]], { padding: 96, duration: 0 });
  }, [drawnBbox, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !cameraRequest) return;
    if (handledCameraRequestRef.current === cameraRequest.id) return;
    const [lng, lat] = cameraRequest.center;
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) return;

    handledCameraRequestRef.current = cameraRequest.id;
    setCameraHud(cameraRequest);
    setCameraMoveState("moving");
    if (cameraHudTimeoutRef.current) {
      window.clearTimeout(cameraHudTimeoutRef.current);
    }
    cameraHudTimeoutRef.current = window.setTimeout(() => {
      setCameraHud(null);
      setCameraMoveState("idle");
      cameraHudTimeoutRef.current = null;
    }, 6500);

    const bbox = Array.isArray(cameraRequest.bbox) && cameraRequest.bbox.length === 4
      ? cameraRequest.bbox
      : null;
    if (bbox) {
      const [west, south, east, north] = bbox;
      map.fitBounds([[west, south], [east, north]], {
        padding: 92,
        duration: 700,
      });
    }

    const moveCamera = () => {
      if (mapRef.current !== map) return;
      map.once("moveend", () => {
        if (mapRef.current === map) setCameraMoveState("arrived");
      });
      map.easeTo({
        center: [lng, lat],
        zoom: cameraRequest.zoom ?? Math.max(map.getZoom(), 11.8),
        pitch: cameraRequest.pitch ?? 58,
        bearing: cameraRequest.bearing ?? -24,
        duration: 950,
      });
    };

    window.setTimeout(moveCamera, bbox ? 170 : 0);

    onCameraRequestHandled?.(cameraRequest.id);
  }, [cameraRequest, mapReady, onCameraRequestHandled]);

  // Sync pins → MapLibre markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const existingIds = new Set(pins.map((p) => p.id));
    const renderedIds = Object.keys(markerRefs.current).map(Number);

    // Remove stale markers
    for (const id of renderedIds) {
      if (!existingIds.has(id)) {
        markerRefs.current[id]?.remove();
        delete markerRefs.current[id];
      }
    }

    // Add or update markers
    for (const pin of pins) {
      if (markerRefs.current[pin.id]) {
        markerRefs.current[pin.id].setLngLat([pin.lng, pin.lat]);
      } else {
        const el = buildMarkerEl(pin, removePin, (cellId) => onCellClickRef.current(cellId));
        const marker = new maplibregl.Marker({ element: el, anchor: "center" })
          .setLngLat([pin.lng, pin.lat])
          .addTo(map);
        markerRefs.current[pin.id] = marker;
      }
      
      // Upgrade grid color to Alert! if it's confirmed by ground agent
      if (pin.pin_type === "ground" && pin.cell_id) {
         setFeatureStateIfReady(map, "scan-grid", pin.cell_id, { isAlert: true, isAnomaly: false });
      }
    }
  }, [pins, mapReady, removePin]);

  // Sync optional visual evidence boxes
  const vlmGeoJson = useMemo(() => {
    const features: GeoJSON.Feature[] = [];
    if (!drawnBbox || vlmBoxes.length === 0) {
        return { type: "FeatureCollection", features } as GeoJSON.FeatureCollection;
    }
    for (let i = 0; i < vlmBoxes.length; i++) {
        const box = vlmBoxes[i];
        const [boxWest, boxSouth, boxEast, boxNorth] = unitBoxToGeographicBbox(drawnBbox, box);

        features.push({
            type: "Feature",
            id: `vlm-box-${i}`,
            properties: {
              label: box.label,
              bbox: `[${box.bbox.map((entry) => entry.toFixed(2)).join(", ")}]`,
              confidence: box.confidence ?? null,
              color: colorForVlmBox(box),
              prompt: box.prompt ?? "",
              source_model: box.source_model ?? "",
              runtime_truth_mode: box.runtime_truth_mode ?? "",
              imagery_origin: box.imagery_origin ?? "",
              scoring_basis: box.scoring_basis ?? "",
            },
            geometry: {
                type: "Polygon",
                coordinates: [[
                    [boxWest, boxNorth],
                    [boxEast, boxNorth],
                    [boxEast, boxSouth],
                    [boxWest, boxSouth],
                    [boxWest, boxNorth]
                ]]
            }
        });
    }
    return { type: "FeatureCollection", features } as GeoJSON.FeatureCollection;
  }, [vlmBoxes, drawnBbox]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    
    if (!map.getSource("vlm-boxes")) {
       map.addSource("vlm-boxes", { type: "geojson", data: vlmGeoJson });

       map.addLayer({
          id: "vlm-boxes-fill",
          type: "fill",
          source: "vlm-boxes",
          paint: {
            "fill-color": ["coalesce", ["get", "color"], "#00ff88"],
            "fill-opacity": 0.14
          }
       });

       map.addLayer({
          id: "vlm-boxes-glow",
          type: "line",
          source: "vlm-boxes",
          paint: {
            "line-color": ["coalesce", ["get", "color"], "#00ff88"],
            "line-opacity": 0.88,
            "line-width": 12,
            "line-blur": 6
          }
       });
       
       map.addLayer({
          id: "vlm-boxes-line",
          type: "line",
          source: "vlm-boxes",
          paint: {
            "line-color": ["coalesce", ["get", "color"], "#00ff88"],
            "line-width": 3.2,
            "line-opacity": 0.98
          }
       });

       map.addLayer({
          id: "vlm-boxes-label",
          type: "symbol",
          source: "vlm-boxes",
          layout: {
             "text-field": ["get", "label"],
             "text-anchor": "bottom-left",
             "text-offset": [0, -0.4],
             "text-size": 12,
          },
          paint: {
             "text-color": "#ecfeff",
             "text-halo-color": "#020617",
             "text-halo-width": 3
          }
       });
    } else {
       (map.getSource("vlm-boxes") as GeoJSONSource).setData(vlmGeoJson);
    }

    if (!vlmHoverHandlersAttachedRef.current) {
      const showObjectTooltip = (event: MapLayerMouseEvent) => {
        const feature = event.features?.[0];
        if (!feature?.properties) return;
        map.getCanvas().style.cursor = "help";
        vlmPopupRef.current?.remove();
        vlmPopupRef.current = new maplibregl.Popup({
          closeButton: false,
          closeOnClick: false,
          className: "vlm-map-popup",
          offset: 14,
        })
          .setLngLat(event.lngLat)
          .setHTML(buildVlmTooltipHtml(feature.properties as Record<string, unknown>))
          .addTo(map);
      };

      const moveObjectTooltip = (event: MapLayerMouseEvent) => {
        if (vlmPopupRef.current) {
          vlmPopupRef.current.setLngLat(event.lngLat);
        }
      };

      const hideObjectTooltip = () => {
        map.getCanvas().style.cursor = drawBboxActiveRef.current ? "crosshair" : "";
        vlmPopupRef.current?.remove();
        vlmPopupRef.current = null;
      };

      for (const layerId of ["vlm-boxes-fill", "vlm-boxes-line"]) {
        map.on("mouseenter", layerId, showObjectTooltip);
        map.on("mousemove", layerId, moveObjectTooltip);
        map.on("mouseleave", layerId, hideObjectTooltip);
      }
      vlmHoverHandlersAttachedRef.current = true;
    }
  }, [vlmGeoJson, mapReady]);

  // Cursor and gesture ownership when bbox drawing is active
  useLayoutEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const canvas = map.getCanvas();
    canvas.style.cursor = drawBboxActive ? "crosshair" : "";
    if (drawBboxActive) {
      if (dragPanWasEnabledRef.current === null) {
        dragPanWasEnabledRef.current = map.dragPan.isEnabled();
      }
      map.dragPan.disable();
      return;
    }
    bboxStartRef.current = null;
    setBboxPreview(null);
    if (dragPanWasEnabledRef.current ?? true) {
      map.dragPan.enable();
    }
    dragPanWasEnabledRef.current = null;
  }, [drawBboxActive]);

  return (
    <div data-testid="map-visualizer" className="relative w-full h-full bg-[#05070b]">
      <div ref={mapContainer} className="w-full h-full" />
      {drawBboxActive && (
        <div
          data-testid="bbox-draw-hitbox"
          className="absolute inset-0 z-[5] cursor-crosshair touch-none"
          onPointerDown={beginBboxPointer}
          onPointerMove={updateBboxPointer}
          onPointerUp={finishBboxPointer}
          onPointerCancel={cancelBboxPointer}
        />
      )}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,_rgba(56,189,248,0.12),_transparent_26%),linear-gradient(180deg,_rgba(2,6,23,0.12)_0%,_rgba(2,6,23,0.26)_100%)]" />

      {cameraHud && (
        <div
          data-testid="map-camera-hud"
          className="pointer-events-none absolute left-1/2 top-5 z-20 w-[min(430px,calc(100%-2rem))] -translate-x-1/2 rounded-lg border border-cyan-200/45 bg-zinc-950/82 px-4 py-3 text-cyan-50 shadow-[0_0_30px_rgba(34,211,238,0.24)] backdrop-blur-md"
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-200">Camera Target</p>
              <p className="mt-1 text-sm font-semibold text-white">{cameraHud.label}</p>
              {cameraHud.locationType && (
                <p className="mt-1 text-[11px] font-medium text-cyan-100">{cameraHud.locationType}</p>
              )}
            </div>
            <span className="rounded border border-white/15 bg-white/10 px-2 py-1 text-[10px] font-bold uppercase tracking-[0.18em] text-cyan-100">
              {cameraMoveState === "arrived" ? "Arrived" : cameraHud.source ?? "Ground Agent"}
            </span>
          </div>
          <div className="mt-2 grid grid-cols-3 gap-2 text-[10px] uppercase tracking-[0.14em] text-zinc-300">
            <span>Lng {cameraHud.center[0].toFixed(4)}</span>
            <span>Lat {cameraHud.center[1].toFixed(4)}</span>
            <span>Pitch {Math.round(cameraHud.pitch ?? 58)} deg</span>
          </div>
          {cameraHud.reason && (
            <p className="mt-2 text-[11px] leading-relaxed text-zinc-300">{cameraHud.reason}</p>
          )}
          {(cameraHud.terrainContext || cameraHud.missionContext) && (
            <div className="mt-2 grid gap-2 text-[11px] leading-relaxed text-zinc-300 sm:grid-cols-2">
              {cameraHud.terrainContext && (
                <p>
                  <span className="font-semibold text-cyan-100">Terrain: </span>
                  {cameraHud.terrainContext}
                </p>
              )}
              {cameraHud.missionContext && (
                <p>
                  <span className="font-semibold text-cyan-100">Use: </span>
                  {cameraHud.missionContext}
                </p>
              )}
            </div>
          )}
          {cameraHud.suggestedTargets && cameraHud.suggestedTargets.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {cameraHud.suggestedTargets.slice(0, 4).map((target) => (
                <span
                  key={target}
                  className="rounded border border-cyan-200/20 bg-cyan-300/10 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.14em] text-cyan-50"
                >
                  {target}
                </span>
              ))}
            </div>
          )}
          {cameraHud.evidenceGuidance && (
            <p className="mt-2 border-t border-white/10 pt-2 text-[10px] leading-relaxed text-amber-100">
              {cameraHud.evidenceGuidance}
            </p>
          )}
        </div>
      )}

      {!scanAnimationActive && drawnBbox && (
        <div
          data-testid="map-scan-paused-hint"
          className="pointer-events-none absolute left-5 bottom-24 z-20 rounded border border-amber-200/45 bg-zinc-950/72 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-100 shadow-lg backdrop-blur-md"
        >
          Scan animation paused - selected area ready
        </div>
      )}

      {scanAnimationActive && drawnBbox && (
        <div
          data-testid="map-scan-active-hint"
          className="pointer-events-none absolute left-5 bottom-24 z-20 flex items-center gap-2 rounded border border-emerald-200/45 bg-zinc-950/72 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-100 shadow-lg backdrop-blur-md"
        >
          <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
          <span>Scan in progress - watching selected cells</span>
        </div>
      )}

      {/* Grid legend */}
      <div className="absolute right-5 top-5 max-w-[230px] rounded-lg border border-white/10 bg-zinc-950/52 px-3 py-2 text-[10px] uppercase tracking-[0.18em] text-zinc-300 shadow-lg backdrop-blur-md pointer-events-none">
        <p className="mb-1.5 text-[9px] font-bold text-zinc-500">Legend</p>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[9px] tracking-[0.12em]">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            <span>selected</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-red-500" />
            <span>alert!</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-amber-400" />
            <span>interesting</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-green-500" />
            <span>scanned</span>
          </div>
        </div>
        {vlmBoxes.length > 0 && (
          <div data-testid="vlm-object-box-legend" className="mt-2 border-t border-white/10 pt-2 space-y-1">
            <p className="text-[9px] font-bold text-zinc-500">Evidence</p>
            {vlmBoxes.slice(0, 4).map((box, index) => (
              <div key={`${box.label}-${index}`} className="flex items-center gap-2">
                <span
                  className="h-2 w-3 rounded-full"
                  style={{
                    backgroundColor: colorForVlmBox(box),
                    boxShadow: `0 0 12px ${colorForVlmBox(box)}`,
                  }}
                />
                <span className="text-gray-400">{box.label}</span>
              </div>
            ))}
            <p className="text-[9px] text-gray-400 mt-1">Hover boxes for details</p>
          </div>
        )}
      </div>

      <button
        type="button"
        data-testid="map-actions-button"
        aria-label="Open spatial options at map center"
        title="Open spatial options at map center"
        data-ui-tip="Spatial tools"
        data-ui-tip-position="left"
        className="absolute bottom-5 right-5 z-20 rounded border border-white/15 bg-zinc-950/70 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-100 shadow-lg backdrop-blur-md transition hover:border-cyan-300/60 hover:bg-cyan-950/70 focus:outline-none focus:ring-2 focus:ring-cyan-300 disabled:cursor-not-allowed disabled:opacity-50"
        disabled={!mapReady}
        onMouseDown={(event) => event.stopPropagation()}
        onClick={(event) => {
          event.stopPropagation();
          openSpatialMenuAtMapCenter();
        }}
      >
        Map Actions
      </button>

      {/* Operator Right Click Context Menu */}
      {contextMenu && (
        <div 
          role="menu"
          aria-label="Spatial options"
          className="absolute z-50 rounded-xl border border-white/10 bg-zinc-900/75 backdrop-blur-md shadow-[0_4px_30px_rgba(0,0,0,0.5)] py-2 outline-none flex flex-col w-64"
          style={{ top: contextMenu.y, left: contextMenu.x }}
          onMouseLeave={() => setContextMenu(null)}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setContextMenu(null);
            }
          }}
        >
          <div className="px-3 pb-2 mb-2 border-b border-gray-800 flex items-center justify-between">
            <span className="text-[9px] uppercase tracking-[0.2em] font-mono text-cyan-500">Spatial Options</span>
            <span className="text-[8px] text-gray-500">[{contextMenu.lng.toFixed(2)}, {contextMenu.lat.toFixed(2)}]</span>
          </div>
          
          <button 
            ref={firstMenuButtonRef}
            type="button"
            role="menuitem"
            className="text-left px-4 py-2 text-xs font-mono text-gray-300 hover:bg-cyan-900/40 hover:text-cyan-300 transition-colors"
            onClick={() => {
              const buffer = 0.05;
              const bbox = [contextMenu.lng - buffer, contextMenu.lat - buffer, contextMenu.lng + buffer, contextMenu.lat + buffer];
              onMenuAssignBBox?.(bbox);
              setContextMenu(null);
            }}
          >
            ◫ Set Mission BBox Here
          </button>
          
          <button 
             type="button"
             role="menuitem"
             className="text-left px-4 py-2 text-xs font-mono text-gray-300 hover:bg-cyan-900/40 hover:text-cyan-300 transition-colors"
             onClick={() => {
              const buffer = 0.05;
              const bbox = [contextMenu.lng - buffer, contextMenu.lat - buffer, contextMenu.lng + buffer, contextMenu.lat + buffer];
              onMenuGenerateTimelapse?.(bbox);
              setContextMenu(null);
             }}
          >
             ▷ Generate Temporal Timelapse
          </button>
          
          <button 
             type="button"
             role="menuitem"
             className="text-left px-4 py-2 text-xs font-mono text-cyan-300 hover:bg-cyan-800 hover:text-white transition-colors border-y border-gray-800 my-1 font-semibold"
             onClick={() => {
              const buffer = 0.05;
              const bbox = [contextMenu.lng - buffer, contextMenu.lat - buffer, contextMenu.lng + buffer, contextMenu.lat + buffer];
              onMenuAgentVideoEval?.(bbox);
              setContextMenu(null);
             }}
          >
             ◈ Agent Video Evaluation
          </button>
          
          <button 
             type="button"
             role="menuitem"
             className="text-left px-4 py-2 text-xs font-mono text-emerald-400 hover:bg-emerald-900/40 hover:text-emerald-300 transition-colors"
             onClick={() => {
              void dropPin(contextMenu.lat, contextMenu.lng).then((saved) => {
                if (saved) {
                  showPinTooltip(`★ Operator pin dropped at ${contextMenu.lat.toFixed(4)}, ${contextMenu.lng.toFixed(4)}`);
                }
              });
              setContextMenu(null);
             }}
          >
             ◆ Drop Operator Pin
          </button>
        </div>
      )}

      {/* Pin dropped toast */}
      {pinTooltip && (
        <div className="absolute bottom-16 left-1/2 -translate-x-1/2 rounded-xl border border-amber-800/60 bg-black/80 px-4 py-2 text-xs text-amber-300 backdrop-blur-sm transition-all">
          {pinTooltip}
        </div>
      )}

      {pinError && (
        <div className="absolute bottom-16 left-1/2 max-w-[min(90%,32rem)] -translate-x-1/2 rounded-xl border border-red-900/60 bg-red-950/80 px-4 py-2 text-xs text-red-100 shadow-lg backdrop-blur-sm">
          {pinError}
        </div>
      )}

      {/* Basemap credit */}
      <div className="absolute bottom-5 left-5 rounded-2xl border border-white/10 bg-zinc-900/40 px-4 py-3 text-xs text-zinc-300 backdrop-blur-md shadow-lg pointer-events-none">
        <div className="mb-1 flex items-center gap-2">
          <p className="text-gray-500 tracking-[0.3em]">SATELLITE BASEMAP</p>
          <span className="rounded-full border border-cyan-900/70 bg-cyan-500/10 px-2 py-0.5 text-[9px] uppercase tracking-[0.24em] text-cyan-200">
            context
          </span>
        </div>
        <p>Esri World Imagery · Maxar · Earthstar Geographics. Context only.</p>
        <p className="text-gray-600 mt-1 text-[10px]">© Esri · Not part of detection or scoring</p>
        {mapError && (
          <p className="mt-1 text-[10px] text-amber-300">{mapError}</p>
        )}
      </div>
    </div>
  );
}
