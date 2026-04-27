import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import maplibregl, { GeoJSONSource, LngLatBoundsLike, Map as MaplibreMap, Marker, type PointLike } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { OrbitalScanEventDetail } from "../types/telemetry";
import { useMapPins } from "../hooks/useMapPins";
import type { MapPin } from "../hooks/useMapPins";
import type { VlmBox } from "./VlmPanel";

type SpatialMenuState = {
  x: number;
  y: number;
  lng: number;
  lat: number;
  cellId: string | null;
};

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
  /** Active bounding boxes provided by VLM Panel */
  vlmBoxes?: VlmBox[];
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

function getTargetCellIdAtPoint(map: MaplibreMap, point: PointLike): string | null {
  if (!map.getLayer("scan-grid-fill")) return null;
  try {
    const features = map.queryRenderedFeatures(point, { layers: ["scan-grid-fill"] });
    return typeof features[0]?.properties?.cell_id === "string" ? features[0].properties.cell_id : null;
  } catch {
    return null;
  }
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
}: MapVisualizerProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MaplibreMap | null>(null);
  const firstMenuButtonRef = useRef<HTMLButtonElement | null>(null);
  const previousSelectedCellId = useRef<string | null>(null);
  const didFitBounds = useRef(false);
  // Use a plain object as a map from pin id → Marker to avoid clash with MapLibre Map type
  const markerRefs = useRef<Record<number, Marker>>({});
  const pinTooltipTimeoutRef = useRef<number | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [shiftHeld, setShiftHeld] = useState(false);
  const [pinTooltip, setPinTooltip] = useState<string | null>(null);

  // Satellite sweeping effect
  const cellCentroidsRef = useRef<Record<string, [number, number]>>({});
  const sweepTimeoutRef = useRef<number | null>(null);
  const scanStateTimeoutsRef = useRef<Set<number>>(new Set());

  // Bbox draw state
  const bboxStartRef = useRef<[number, number] | null>(null);
  const [bboxPreview, setBboxPreview] = useState<number[] | null>(null);

  // Context Menu state
  const [contextMenu, setContextMenu] = useState<SpatialMenuState | null>(null);

  const { pins, dropPin, removePin, error: pinError } = useMapPins();

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

  useEffect(() => {
    if (pinError) clearPinTooltip();
  }, [pinError, clearPinTooltip]);

  // Mutable refs to resolve stale closures during single-mount map hooks
  const onCellClickRef = useRef(onCellClick);
  const dropPinRef = useRef(dropPin);
  const geoJsonGridRef = useRef(geoJsonGrid);
  const drawBboxActiveRef = useRef(drawBboxActive);

  useEffect(() => {
    onCellClickRef.current = onCellClick;
    dropPinRef.current = dropPin;
    geoJsonGridRef.current = geoJsonGrid;
    drawBboxActiveRef.current = drawBboxActive;
  }, [onCellClick, dropPin, geoJsonGrid, drawBboxActive]);

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

  // Track shift key
  useEffect(() => {
    const down = (e: KeyboardEvent) => { if (e.key === "Shift") setShiftHeld(true); };
    const up = (e: KeyboardEvent) => { if (e.key === "Shift") setShiftHeld(false); };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => { window.removeEventListener("keydown", down); window.removeEventListener("keyup", up); };
  }, []);

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
      center: [-60.025, -3.119],
      zoom: 6,
      pitch: 40,
      attributionControl: false,
    });

    mapRef.current = map;

    map.on("load", () => {
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

      // Shift-click anywhere to drop operator pin (only when not drawing bbox)
      map.on("click", (event) => {
        if (!event.originalEvent.shiftKey || drawBboxActiveRef.current) return;
        const { lng, lat } = event.lngLat;
        void dropPinRef.current(lat, lng).then((saved) => {
          if (saved) {
            showPinTooltip(`★ Operator pin dropped at ${lat.toFixed(4)}, ${lng.toFixed(4)}`);
          }
        });
      });

      // Mouse drag for bbox
      map.on("mousedown", (event) => {
        if (!drawBboxActiveRef.current) return;
        // Don't intercept right clicks
        if (event.originalEvent.button !== 0) return;
        
        event.preventDefault();
        map.dragPan.disable(); // Stop the map from panning while dragging
        
        const { lng, lat } = event.lngLat;
        bboxStartRef.current = [lng, lat];
        setBboxPreview([lng, lat, lng, lat]);
      });

      map.on("mousemove", (event) => {
        if (!drawBboxActiveRef.current || !bboxStartRef.current) return;
        const { lng, lat } = event.lngLat;
        const [startLng, startLat] = bboxStartRef.current;
        setBboxPreview([
          Math.min(startLng, lng), Math.min(startLat, lat),
          Math.max(startLng, lng), Math.max(startLat, lat),
        ]);
      });

      map.on("mouseup", (event) => {
        if (!drawBboxActiveRef.current || !bboxStartRef.current) return;
        map.dragPan.enable();
        
        const { lng, lat } = event.lngLat;
        const [startLng, startLat] = bboxStartRef.current;
        
        // Prevent accidental micro-drags or clicks (width < 0.001 deg)
        if (Math.abs(lng - startLng) < 0.001 || Math.abs(lat - startLat) < 0.001) {
             bboxStartRef.current = null;
             setBboxPreview(null);
             return;
        }

        const bbox = [
          Math.min(startLng, lng),
          Math.min(startLat, lat),
          Math.max(startLng, lng),
          Math.max(startLat, lat),
        ];
        
        bboxStartRef.current = null;
        setBboxPreview(null);
        onBboxDrawn?.(bbox);
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
          let sumLng = 0; let sumLat = 0;
          for (const c of coords) {
             sumLng += c[0]; sumLat += c[1];
          }
          if (coords.length > 0) {
             centroids[(f.properties as any).cell_id] = [sumLng / coords.length, sumLat / coords.length];
          }
       }
    }
    cellCentroidsRef.current = centroids;

    const source = getGeoJsonSource(map, "scan-grid");
    source?.setData(geoJsonGrid);
    if (!didFitBounds.current && gridBounds) {
      map.fitBounds(gridBounds, { padding: 40, duration: 0 });
      didFitBounds.current = true;
    }
  }, [geoJsonGrid, gridBounds]);

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
  }, []);



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

  // Sync VLM GeoJSON boxes
  const vlmGeoJson = useMemo(() => {
    const features: GeoJSON.Feature[] = [];
    if (!drawnBbox || vlmBoxes.length === 0) {
        return { type: "FeatureCollection", features } as GeoJSON.FeatureCollection;
    }
    const [west, south, east, north] = drawnBbox;

    for (let i = 0; i < vlmBoxes.length; i++) {
        const box = vlmBoxes[i];
        const [ymin, xmin, ymax, xmax] = box.bbox;
        // Map normalized coords back to geographic coords relative to the drawnBox.
        // Assuming normalized (0,0) is top-left -> (north, west).
        const boxNorth = north - (north - south) * ymin;
        const boxSouth = north - (north - south) * ymax;
        const boxWest = west + (east - west) * xmin;
        const boxEast = west + (east - west) * xmax;

        features.push({
            type: "Feature",
            id: `vlm-box-${i}`,
            properties: { label: box.label },
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
          id: "vlm-boxes-line",
          type: "line",
          source: "vlm-boxes",
          paint: {
            "line-color": "#00ff88",
            "line-width": 2
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
             "text-color": "#012a14",
             "text-halo-color": "#00ff88",
             "text-halo-width": 3
          }
       });
    } else {
       (map.getSource("vlm-boxes") as GeoJSONSource).setData(vlmGeoJson);
    }
  }, [vlmGeoJson, mapReady]);

  // Cursor style when shift held or bbox active
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const canvas = map.getCanvas();
    canvas.style.cursor = (shiftHeld || drawBboxActive) ? "crosshair" : "";
  }, [shiftHeld, drawBboxActive]);

  return (
    <div className="relative w-full h-full bg-[#05070b]">
      <div ref={mapContainer} className="w-full h-full" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,_rgba(56,189,248,0.12),_transparent_26%),linear-gradient(180deg,_rgba(2,6,23,0.12)_0%,_rgba(2,6,23,0.26)_100%)]" />

      {/* Grid legend */}
      <div className="absolute right-5 top-5 rounded-2xl border border-white/10 bg-zinc-900/40 px-4 py-3 text-[10px] uppercase tracking-[0.28em] text-zinc-300 backdrop-blur-md shadow-lg pointer-events-none">
        <p className="mb-2 text-gray-500">GRID LEGEND</p>
        <div className="space-y-1.5 text-[10px] tracking-[0.22em]">
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
            <span>recently scanned</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-white border border-gray-400" />
            <span>unscanned</span>
          </div>
        </div>
        <div className="mt-3 border-t border-gray-800/70 pt-2 space-y-1.5">
          <p className="text-gray-600 mb-1">PINS</p>
          <div className="flex items-center gap-2">
            <span className="text-cyan-400 text-[11px]">◆</span>
            <span className="text-gray-400">satellite flag</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-emerald-400 text-[11px]">●</span>
            <span className="text-gray-400">ground truth</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-amber-400 text-[11px]">★</span>
            <span className="text-gray-400">operator mark</span>
          </div>
          <p className="text-[9px] text-gray-700 mt-1">Shift+click to pin · Right-click to remove</p>
        </div>
      </div>

      <button
        type="button"
        data-testid="map-actions-button"
        aria-label="Open spatial options at map center"
        title="Open spatial options at map center"
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

      {/* Shift-click hint / Draw bbox mode */}
      {shiftHeld && (
        <div className="pointer-events-none absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-2xl border backdrop-blur-md px-5 py-3 text-sm font-mono
         border-zinc-300/30 bg-zinc-900/50 text-white shadow-xl">
          {drawBboxActive
            ? (bboxStartRef.current ? "⊡ Click second corner to complete area" : "⊡ Click first corner to start area selection")
            : "★ Click to drop an operator pin"}
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
        <p>
          {mapReady
            ? "Esri World Imagery · Maxar · Earthstar Geographics. Context only."
            : "Loading satellite imagery…"}
        </p>
        <p className="text-gray-600 mt-1 text-[10px]">© Esri · Not part of detection or scoring</p>
      </div>
    </div>
  );
}
