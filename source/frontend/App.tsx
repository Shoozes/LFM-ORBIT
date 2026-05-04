import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { VlmBox } from "./components/VlmPanel";
import { useTelemetry } from "./hooks/useTelemetry";
import { getApiBaseUrl, generateGridForBbox } from "./utils/telemetry";
import type { Mission } from "./types/mission";
import type { ChatResponse } from "./components/GroundAgentActionCard";
import type { MapCameraRequest } from "./types/mapCamera";

const loadMapVisualizer = () => import("./components/MapVisualizer");
const loadValidationPanel = () => import("./components/ValidationPanel");
const loadSettingsPanel = () => import("./components/SettingsPanel");
const loadAgentDialogue = () => import("./components/AgentDialogue");
const loadGroundAgent = () => import("./components/GroundAgent");
const loadMissionControl = () => import("./components/MissionControl");
const loadTimelapseViewer = () => import("./components/TimelapseViewer");
const loadVlmPanel = () => import("./components/VlmPanel");
const loadAlertsLogs = () => import("./components/AlertsLogs");
const loadProofModePanel = () => import("./components/ProofModePanel");

const MapVisualizer = lazy(loadMapVisualizer);
const ValidationPanel = lazy(loadValidationPanel);
const SettingsPanel = lazy(loadSettingsPanel);
const AgentDialogue = lazy(loadAgentDialogue);
const GroundAgent = lazy(loadGroundAgent);
const MissionControl = lazy(loadMissionControl);
const TimelapseViewer = lazy(loadTimelapseViewer);
const VlmPanel = lazy(loadVlmPanel);
const AlertsLogs = lazy(loadAlertsLogs);
const ProofModePanel = lazy(loadProofModePanel);

type DemoCase = "showcase" | "payload" | "provenance" | "abstain" | "eclipse" | "ice" | "forest";

const SHOWCASE_REPLAY_ID = "atacama_mining_replay";
const SHOWCASE_PRIMARY_CELL_ID = "mining_atacama_open_pit";
const SHOWCASE_FALLBACK_BBOX = [-69.115, -24.29, -69.035, -24.21];
const DEMO_STEPS_BY_CASE: Record<DemoCase, string[]> = {
  showcase: [
    "Step 1: Minerals replay loaded",
    "Step 2: Corridor bbox selected",
    "Step 3: Region targets applied",
    "Step 4: Evidence reviewed",
    "Step 5: Proof JSON compressed",
    "Step 6: Training tags ready",
  ],
  payload: [
    "Step 1: Flood mission loaded",
    "Step 2: Floodplain bbox selected",
    "Step 3: Raw frame measured",
    "Step 4: Evidence reviewed",
    "Step 5: JSON compressed",
    "Step 6: Downlink savings shown",
  ],
  provenance: [
    "Step 1: Minerals mission loaded",
    "Step 2: Corridor bbox selected",
    "Step 3: Source resolved",
    "Step 4: Evidence reviewed",
    "Step 5: Prompt captured",
    "Step 6: Audit JSON ready",
  ],
  abstain: [
    "Step 1: Ice mission loaded",
    "Step 2: BBox selected",
    "Step 3: Quality gate failed",
    "Step 4: Review abstained",
    "Step 5: Alert blocked",
    "Step 6: No downlink sent",
  ],
  ice: [
    "Step 1: Ice replay loaded",
    "Step 2: BBox selected",
    "Step 3: NDSI scored",
    "Step 4: Clouds rejected",
    "Step 5: Confidence weighted",
    "Step 6: Proof packet ready",
  ],
  forest: [
    "Step 1: Rondonia replay ready",
    "Step 2: Select tool confirms bbox",
    "Step 3: Ground Agent action approved",
    "Step 4: CV regions retained",
    "Step 5: Compact proof JSON",
    "Step 6: Training tags exported",
  ],
  eclipse: [
    "Step 1: Maritime mission loaded",
    "Step 2: BBox selected",
    "Step 3: Edge triage passed",
    "Step 4: Link offline",
    "Step 5: Packets queued",
    "Step 6: Queue flushed",
  ],
};

const DEMO_START_PROFILES: Partial<Record<DemoCase, { presetId: string; bbox: number[]; readyLabel: string }>> = {
  payload: {
    presetId: "flood_manchar",
    bbox: [67.63, 26.31, 67.87, 26.55],
    readyLabel: "Payload demo ready",
  },
  provenance: {
    presetId: "mining_atacama",
    bbox: [-69.115, -24.29, -69.035, -24.21],
    readyLabel: "Provenance demo ready",
  },
  abstain: {
    presetId: "ice_greenland",
    bbox: [-51.13, 69.1, -50.97, 69.26],
    readyLabel: "Abstain demo ready",
  },
  ice: {
    presetId: "ice_greenland",
    bbox: [-51.13, 69.1, -50.97, 69.26],
    readyLabel: "Ice proof demo ready",
  },
  forest: {
    presetId: "deforestation_amazon",
    bbox: [-63.15, -10.15, -62.85, -9.85],
    readyLabel: "Rondonia tutorial ready",
  },
  eclipse: {
    presetId: "maritime_suez",
    bbox: [32.5, 29.88, 32.58, 29.96],
    readyLabel: "Eclipse demo ready",
  },
};

function normalizeDemoCase(value: string | null): DemoCase {
  if (value === "payload") return "payload";
  if (value === "provenance") return "provenance";
  if (value === "abstain") return "abstain";
  if (value === "eclipse") return "eclipse";
  if (value === "ice") return "ice";
  if (value === "forest") return "forest";
  return "showcase";
}

function readDemoQuery(): { enabled: boolean; demoCase: DemoCase } {
  if (typeof window === "undefined") {
    return { enabled: false, demoCase: "showcase" };
  }
  const params = new URLSearchParams(window.location.search);
  return {
    enabled: params.get("demo") === "1",
    demoCase: normalizeDemoCase(params.get("demoCase") ?? params.get("case")),
  };
}

function demoBoxLabel(demoCase: DemoCase): string {
  switch (demoCase) {
    case "payload":
      return "flood extent";
    case "provenance":
      return "mine expansion";
    case "eclipse":
      return "vessel queue";
    case "ice":
      return "ice/snow extent";
    case "forest":
      return "clearing candidate region";
    case "abstain":
      return "quality gate";
    case "showcase":
    default:
      return "mining expansion region";
  }
}

function LoadingPanel({ label, className = "" }: { label: string; className?: string }) {
  return (
    <div className={`flex h-full w-full items-center justify-center bg-zinc-50 text-[10px] font-semibold uppercase tracking-[0.28em] text-zinc-400 ${className}`}>
      Loading {label}...
    </div>
  );
}

async function readApiError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json() as { error?: unknown; detail?: unknown };
    if (typeof payload.error === "string" && payload.error.trim()) {
      return payload.error;
    }
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail;
    }
  } catch {
    return fallback;
  }
  return fallback;
}

async function postAgentBusMessage(
  apiBaseUrl: string,
  payload: { role: string; type: string; message: string },
): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/agent/bus/inject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, `Agent bus injection failed with HTTP ${response.status}.`));
  }
}

function getCellIdFromProperties(properties: unknown): string | null {
  if (!properties || typeof properties !== "object") return null;
  const value = (properties as { cell_id?: unknown }).cell_id;
  return typeof value === "string" || typeof value === "number" ? String(value) : null;
}

function normalizeNumberArray(value: unknown, length: number): number[] | null {
  if (!Array.isArray(value) || value.length !== length) return null;
  const numbers = value.map((entry) => Number(entry));
  return numbers.every((entry) => Number.isFinite(entry)) ? numbers : null;
}

function normalizeCameraNumber(value: unknown): number | undefined {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : undefined;
}

function normalizeStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((entry) => typeof entry === "string" ? entry.trim() : "")
    .filter(Boolean);
}

function findOkAction(response: ChatResponse | undefined, name: string): Record<string, unknown> | null {
  const action = response?.actions?.find((candidate) => candidate.name === name && candidate.status === "ok");
  return action?.result ?? null;
}

export default function App() {
  const demoQuery = useMemo(readDemoQuery, []);
  const demoSteps = DEMO_STEPS_BY_CASE[demoQuery.demoCase];
  const demoStartProfile = demoQuery.enabled ? DEMO_START_PROFILES[demoQuery.demoCase] : undefined;
  const [drawBboxActive, setDrawBboxActive] = useState(false);
  const [drawnBbox, setDrawnBbox] = useState<number[] | null>(() => (
    demoStartProfile ? [...demoStartProfile.bbox] : null
  ));
  const [vlmBoxes, setVlmBoxes] = useState<VlmBox[]>([]);
  const [showMissionTimelapse, setShowMissionTimelapse] = useState(false);
  const [showBboxTools, setShowBboxTools] = useState(false);
  const [mission, setMission] = useState<Mission | null>(null);
  const [mapCameraRequest, setMapCameraRequest] = useState<MapCameraRequest | null>(null);
  const [missionStopNotice, setMissionStopNotice] = useState<string | null>(null);
  const [proofModeActive, setProofModeActive] = useState(false);
  const [proofMission, setProofMission] = useState<Mission | null>(null);
  const [demoStepIndex, setDemoStepIndex] = useState(0);
  const previousActiveMissionRef = useRef<Mission | null>(null);
  const previewedMissionIdRef = useRef<number | null>(null);
  const apiBaseUrl = getApiBaseUrl();

  const fetchMission = useCallback(async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/api/mission/current`);
      if (res.ok) {
        const d = await res.json() as { mission: Mission | null };
        setMission(d.mission);
        return d.mission;
      }
      console.debug(`Mission refresh failed with HTTP ${res.status}.`);
    } catch (error) {
      console.debug("Mission refresh failed.", error);
    }
    return null;
  }, [apiBaseUrl]);

  useEffect(() => {
    fetchMission();
    const id = setInterval(fetchMission, 5000);
    return () => clearInterval(id);
  }, [fetchMission]);

  useEffect(() => {
    if (mission?.status === "active") {
      previousActiveMissionRef.current = mission;
      setMissionStopNotice(null);
      if (mission.bbox && previewedMissionIdRef.current !== mission.id) {
        setDrawnBbox([...mission.bbox]);
        setVlmBoxes([]);
        setShowMissionTimelapse(false);
        setShowBboxTools(false);
        previewedMissionIdRef.current = mission.id;
      }
      return;
    }
    const previousMission = previousActiveMissionRef.current;
    if (previousMission) {
      setMissionStopNotice(
        `Mission #${previousMission.id} stopped. Scan animation paused until a new live mission starts.`,
      );
      previousActiveMissionRef.current = null;
    }
  }, [mission]);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDrawBboxActive(false);
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, []);

  const {
    geoJsonGrid,
    alerts,
    selectedCellId,
    setSelectedCellId,
    heartbeat,
    selectedAlert,
    connectionState,
    apiHealth,
    metricsSummary,
    isScanComplete,
    refreshTelemetry,
  } = useTelemetry();

  const handleReplayLoaded = useCallback(async (primaryCellId: string | null) => {
    const [, loadedMission] = await Promise.all([
      refreshTelemetry({ replaceAlerts: true }),
      fetchMission(),
    ]);
    setDrawnBbox(loadedMission?.bbox ? [...loadedMission.bbox] : null);
    setVlmBoxes([]);
    setShowMissionTimelapse(false);
    setShowBboxTools(false);
    if (primaryCellId) {
      setSelectedCellId(primaryCellId);
      setActiveTab("inspect");
    } else {
      setActiveTab("logs");
    }
  }, [fetchMission, refreshTelemetry, setSelectedCellId]);

  const handleReplayRescanStarted = useCallback(async (rescanMission: Mission) => {
    await Promise.all([
      refreshTelemetry({ replaceAlerts: true }),
      fetchMission(),
    ]);
    setSelectedCellId(null);
    setDrawnBbox(rescanMission.bbox ? [...rescanMission.bbox] : null);
    setVlmBoxes([]);
    setShowMissionTimelapse(false);
    setShowBboxTools(false);
    setActiveTab("mission");
  }, [fetchMission, refreshTelemetry, setSelectedCellId]);

  const handleOpenTimelapseForCell = (cellId: string) => {
    if (!geoJsonGrid) return;
    const feature = geoJsonGrid.features.find((f) => getCellIdFromProperties(f.properties) === cellId);
    if (!feature || feature.geometry.type !== "Polygon") return;
    const coords = feature.geometry.coordinates[0];
    const lngs = coords.map(c => c[0]);
    const lats = coords.map(c => c[1]);
    const bbox = [Math.min(...lngs), Math.min(...lats), Math.max(...lngs), Math.max(...lats)];
    setDrawnBbox(bbox);
    setShowBboxTools(false);
  };

  const displayGrid = useMemo(() => {
    if (drawnBbox) {
      return generateGridForBbox(drawnBbox);
    }
    return geoJsonGrid;
  }, [drawnBbox, geoJsonGrid]);
  const selectedGridCellCount = displayGrid?.features.length ?? 0;
  const missionPassComplete = Boolean(
    isScanComplete
      || (
        mission?.status === "active"
        && mission.mission_mode !== "replay"
        && selectedGridCellCount > 0
        && Number(mission.cells_scanned ?? 0) >= selectedGridCellCount
      ),
  );

  const [activeTab, setActiveTab] = useState<"agents" | "mission" | "logs" | "inspect" | "settings">(
    demoQuery.enabled ? "mission" : "agents",
  );

  const handleProofModeStart = useCallback(async () => {
    setDemoStepIndex(0);
    setProofModeActive(true);

    let activeMission = mission;
    let requiresSeededReplay = demoQuery.demoCase === "showcase" && !mission?.replay_id;
    let primaryCellId: string | null = selectedCellId ?? (requiresSeededReplay ? SHOWCASE_PRIMARY_CELL_ID : null);

    try {
      const currentResponse = await fetch(`${apiBaseUrl}/api/mission/current`);
      if (currentResponse.ok) {
        const currentPayload = await currentResponse.json() as { mission?: Mission | null };
        if (currentPayload.mission) {
          activeMission = currentPayload.mission;
        }
      }

      requiresSeededReplay = demoQuery.demoCase === "showcase" && !activeMission?.replay_id;
      if (requiresSeededReplay && !primaryCellId) {
        primaryCellId = SHOWCASE_PRIMARY_CELL_ID;
      }

      if (requiresSeededReplay && activeMission?.replay_id !== SHOWCASE_REPLAY_ID) {
        if (activeMission?.replay_id !== SHOWCASE_REPLAY_ID) {
          const response = await fetch(`${apiBaseUrl}/api/replay/load/${SHOWCASE_REPLAY_ID}`, { method: "POST" });
          const payload = await response.json() as {
            mission?: Mission;
            primary_cell_id?: string | null;
            error?: string;
          };
          if (!response.ok) {
            throw new Error(payload.error || `Replay load failed with HTTP ${response.status}.`);
          }
          activeMission = payload.mission ?? activeMission;
          primaryCellId = payload.primary_cell_id ?? primaryCellId;
        }
      }

      if (activeMission) {
        setProofMission(activeMission);
      }
      setDemoStepIndex(1);

      await Promise.all([
        refreshTelemetry({ replaceAlerts: true }),
        fetchMission(),
      ]);

      const bbox = (!requiresSeededReplay && demoStartProfile ? demoStartProfile.bbox : activeMission?.bbox) ?? SHOWCASE_FALLBACK_BBOX;
      setDrawnBbox([...bbox]);
      setShowMissionTimelapse(false);
      setShowBboxTools(false);
      setVlmBoxes([{ label: demoBoxLabel(demoQuery.demoCase), bbox: [0.24, 0.18, 0.74, 0.76] }]);
      if (primaryCellId) {
        setSelectedCellId(primaryCellId);
      }
      setActiveTab("mission");
      setDemoStepIndex(2);
    } catch (error) {
      console.error("Proof Mode failed to load replay", error);
      setProofMission(activeMission);
      setDrawnBbox(SHOWCASE_FALLBACK_BBOX);
      setVlmBoxes([{ label: "mining expansion region", bbox: [0.24, 0.18, 0.74, 0.76] }]);
      if (primaryCellId) {
        setSelectedCellId(primaryCellId);
      }
      setDemoStepIndex(2);
    }
  }, [apiBaseUrl, demoQuery.demoCase, demoStartProfile, fetchMission, mission, refreshTelemetry, selectedCellId, setSelectedCellId]);

  const handleGroundAgentNavigate = useCallback(async (
    target: "mission" | "logs" | "settings" | "object_evidence" | "proof",
  ) => {
    if (target === "proof") {
      await handleProofModeStart();
      return;
    }
    if (target === "object_evidence") {
      const bbox = mission?.bbox ?? drawnBbox;
      if (bbox) {
        setDrawnBbox([...bbox]);
        setVlmBoxes([]);
        setShowMissionTimelapse(false);
        setShowBboxTools(true);
      }
      setActiveTab("mission");
      return;
    }
    setActiveTab(target);
  }, [drawnBbox, handleProofModeStart, mission]);

  const handleGroundAgentActionComplete = useCallback(async (response?: ChatResponse) => {
    const [, refreshedMission] = await Promise.all([
      refreshTelemetry({ replaceAlerts: true }),
      fetchMission(),
    ]);

    const navigateResult = findOkAction(response, "navigate_map");
    if (navigateResult) {
      const center = normalizeNumberArray(navigateResult.center, 2);
      const bbox = normalizeNumberArray(navigateResult.bbox, 4);
      const camera = navigateResult.camera && typeof navigateResult.camera === "object"
        ? navigateResult.camera as Record<string, unknown>
        : {};
      const label = typeof navigateResult.label === "string" && navigateResult.label.trim()
        ? navigateResult.label
        : "Ground Agent camera target";
      if (bbox) {
        setDrawnBbox([...bbox]);
        setVlmBoxes([]);
        setShowMissionTimelapse(false);
        setShowBboxTools(true);
        setSelectedCellId(null);
        setActiveTab("mission");
      }
      if (center) {
        setMapCameraRequest({
          id: `ground-agent-${Date.now()}`,
          label,
          center: [center[0], center[1]],
          bbox,
          zoom: normalizeCameraNumber(camera.zoom),
          pitch: normalizeCameraNumber(camera.pitch),
          bearing: normalizeCameraNumber(camera.bearing),
          reason: typeof navigateResult.reason === "string" ? navigateResult.reason : "Ground Agent repositioned the map camera.",
          source: "Ground Agent",
          locationType: typeof navigateResult.location_type === "string" ? navigateResult.location_type : null,
          terrainContext: typeof navigateResult.terrain_context === "string" ? navigateResult.terrain_context : null,
          missionContext: typeof navigateResult.mission_context === "string" ? navigateResult.mission_context : null,
          semanticTags: normalizeStringArray(navigateResult.semantic_tags),
          suggestedTargets: normalizeStringArray(navigateResult.suggested_targets),
          evidenceGuidance: typeof navigateResult.evidence_guidance === "string" ? navigateResult.evidence_guidance : null,
        });
      }
    } else if (refreshedMission?.bbox) {
      const launchedMission = Boolean(
        findOkAction(response, "start_custom_mission") || findOkAction(response, "start_mission_pack"),
      );
      if (launchedMission) {
        previewedMissionIdRef.current = refreshedMission.id;
      }
      setDrawnBbox([...refreshedMission.bbox]);
      if (launchedMission) {
        setVlmBoxes([]);
        setShowMissionTimelapse(false);
        setShowBboxTools(true);
        setSelectedCellId(null);
        setActiveTab("mission");
      }
    }

    const stopResult = findOkAction(response, "stop_mission");
    if (stopResult) {
      const stoppedMissionId = normalizeCameraNumber(stopResult.stopped_mission_id);
      setMissionStopNotice(
        stoppedMissionId
          ? `Mission #${stoppedMissionId} stopped. Scan animation paused until a new live mission starts.`
          : "No active mission was running. Scan animation is paused until a new live mission starts.",
      );
    }
  }, [fetchMission, refreshTelemetry, setSelectedCellId]);

  const scanAnimationActive = Boolean(
    mission?.status === "active"
      && mission.mission_mode !== "replay"
      && !missionPassComplete,
  );

  useEffect(() => {
    if (selectedCellId && activeTab !== "inspect") {
      setActiveTab("inspect");
    }
  }, [selectedCellId]);

  useEffect(() => {
    if (missionPassComplete) {
      void fetchMission();
      void refreshTelemetry();
    }
  }, [fetchMission, missionPassComplete, refreshTelemetry]);

  useEffect(() => {
    void loadMapVisualizer();
  }, []);

  useEffect(() => {
    if (drawnBbox && showBboxTools) {
      void loadVlmPanel();
    }
    if (drawnBbox && showMissionTimelapse) {
      void loadTimelapseViewer();
    }
  }, [drawnBbox, showBboxTools, showMissionTimelapse]);

  useEffect(() => {
    if (!selectedCellId) {
      return;
    }
    void loadValidationPanel();
    void loadTimelapseViewer();
  }, [selectedCellId]);

  useEffect(() => {
    if (activeTab === "agents") {
      void loadAgentDialogue();
      void loadGroundAgent();
      return;
    }
    if (activeTab === "logs") {
      void loadAlertsLogs();
      return;
    }
    if (activeTab === "settings") {
      void loadSettingsPanel();
      return;
    }
    if (activeTab === "mission") {
      void loadMissionControl();
    }
  }, [activeTab]);

  const linkStatusLabel = apiHealth
    ? connectionState === "open"
      ? "LINK OPEN"
      : connectionState === "connecting" || connectionState === "reconnecting"
        ? "LINK SYNCING"
        : "LINK DEGRADED"
    : "BACKEND OFFLINE";
  const linkStatusDot = apiHealth
    ? connectionState === "open"
      ? "bg-emerald-500 animate-pulse"
      : "bg-amber-400"
    : "bg-red-500";

  return (
    <div className="relative flex h-screen w-screen overflow-hidden bg-zinc-50 text-zinc-900 font-sans text-sm">
      {/* LEFT PANE: MAP */}
      <div className="flex-1 relative h-full">
        <Suspense fallback={<LoadingPanel label="Map" className="bg-[#05070b] text-zinc-500" />}>
          <MapVisualizer
            geoJsonGrid={displayGrid}
            selectedCellId={selectedCellId}
            onCellClick={(id) => {
               setSelectedCellId(id);
            }}
            drawBboxActive={drawBboxActive}
            drawnBbox={drawnBbox}
            onBboxDrawn={(bbox) => {
              setDrawnBbox(bbox);
              setShowBboxTools(true);
              setDrawBboxActive(false);
            }}
            onMenuAssignBBox={(bbox) => {
              setDrawnBbox(bbox);
              setShowBboxTools(true);
              setActiveTab("mission");
            }}
            onMenuGenerateTimelapse={(bbox) => {
              setDrawnBbox(bbox);
              setShowBboxTools(true);
              setShowMissionTimelapse(true);
              setActiveTab("mission");
            }}
            onMenuAgentVideoEval={async (bbox) => {
              setDrawnBbox(bbox);
              setShowBboxTools(true);
              setActiveTab("agents");
              try {
                await postAgentBusMessage(apiBaseUrl, {
                  role: "operator",
                  type: "query",
                  message: `Analyze orbital timeframe for coords [${bbox[0].toFixed(2)}, ${bbox[1].toFixed(2)}]. Determine if seasonality or permanent structural loss.`,
                });

                const res = await fetch(`${apiBaseUrl}/api/analysis/timelapse`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ bbox })
                });
                if (!res.ok) {
                  throw new Error(await readApiError(res, `Timelapse analysis failed with HTTP ${res.status}.`));
                }
                const data = await res.json() as { analysis?: unknown };
                await postAgentBusMessage(apiBaseUrl, {
                  role: "ground",
                  type: "status",
                  message: typeof data.analysis === "string" && data.analysis.trim() ? data.analysis : "Analysis complete.",
                });
              } catch (err) {
                 const message = err instanceof Error ? err.message : "Agent video evaluation failed.";
                 try {
                   await postAgentBusMessage(apiBaseUrl, {
                     role: "ground",
                     type: "error",
                     message: `Agent video evaluation failed: ${message}`,
                   });
                 } catch { /* best effort */ }
              }
            }}
            vlmBoxes={vlmBoxes}
            timelineDate={mission?.end_date ?? mission?.start_date ?? null}
            scanAnimationActive={scanAnimationActive}
            cameraRequest={mapCameraRequest}
            onCameraRequestHandled={(requestId) => {
              setMapCameraRequest((current) => current?.id === requestId ? null : current);
            }}
          />
        </Suspense>

        {/* Simple Connection Status overlay top-left on map */}
        <div className="absolute left-4 top-4 z-10 flex flex-col gap-2">
          <div className="flex items-center gap-2 rounded border border-zinc-200 bg-white/90 px-3 py-1.5 shadow-sm backdrop-blur cursor-default" title="Telemetry Link Status (View Only)">
             <span className={`h-2 w-2 rounded-full ${linkStatusDot}`}></span>
             <span className="text-[10px] uppercase font-bold tracking-widest text-zinc-700">
               {linkStatusLabel}
             </span>
          </div>

          {mission?.status === "active" && (
            <div className={`flex items-center gap-2 rounded px-3 py-1.5 shadow-sm backdrop-blur ${
              mission.mission_mode === "replay"
                ? "border border-cyan-200 bg-cyan-50/90"
                : "border border-emerald-200 bg-emerald-50/90"
            }`}>
               <span className={`h-2 w-2 rounded-full animate-pulse ${
                 mission.mission_mode === "replay" ? "bg-cyan-500" : "bg-emerald-500"
               }`}></span>
               <span className={`text-[10px] uppercase font-bold tracking-widest ${
                 mission.mission_mode === "replay" ? "text-cyan-700" : "text-emerald-700"
               }`}>
                 {mission.mission_mode === "replay" ? `REPLAY ACTIVE: ${mission.replay_id || `#${mission.id}`}` : `MISSION ACTIVE: #${mission.id}`}
               </span>
            </div>
          )}

          {missionStopNotice && mission?.status !== "active" && (
            <div
              data-testid="mission-stopped-notice"
              className="max-w-[360px] rounded border border-amber-200 bg-amber-50/94 px-3 py-2 shadow-sm backdrop-blur"
            >
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-amber-700">Mission Stopped</p>
              <p className="mt-1 text-[11px] leading-relaxed text-amber-900">{missionStopNotice}</p>
            </div>
          )}
        </div>

        {drawBboxActive && (
          <div className="absolute top-8 left-1/2 -translate-x-1/2 z-20 bg-purple-600 outline outline-4 outline-purple-600/30 text-white px-4 py-2 rounded-full text-xs font-bold uppercase tracking-widest shadow-xl flex items-center justify-between gap-4">
            <span className="animate-pulse">DRAWING MODE ACTIVE</span>
            <button
              onClick={() => setDrawBboxActive(false)}
              className="text-[10px] font-bold text-purple-200 hover:text-white flex items-center shrink-0 border border-purple-400 hover:border-purple-300 rounded px-2 py-0.5 ml-2 transition"
            >
              CANCEL [ESC]
            </button>
          </div>
        )}
      </div>

      {/* RIGHT PANE: SIDEBAR */}
      <div className="w-[clamp(500px,38vw,620px)] min-w-[500px] flex flex-col h-full bg-white border-l border-zinc-200 shadow-xl relative z-20 overflow-hidden">

        {/* Tabs Header */}
        <div className="flex items-center border-b border-zinc-200 bg-zinc-50 px-2 pt-2 shrink-0">
           <button data-testid="tab-agents" data-ui-tip="Chat and actions" onClick={() => setActiveTab("agents")} className={`px-4 py-2 text-sm font-medium border-b-2 transition ${activeTab === "agents" ? "border-zinc-900 text-zinc-900" : "border-transparent text-zinc-500 hover:text-zinc-700"}`}>Agent</button>
           <button data-testid="tab-mission" data-ui-tip="Mission setup" onClick={() => setActiveTab("mission")} className={`px-4 py-2 text-sm font-medium border-b-2 transition ${activeTab === "mission" ? "border-zinc-900 text-zinc-900" : "border-transparent text-zinc-500 hover:text-zinc-700"}`}>Mission</button>
           <button data-testid="tab-logs" data-ui-tip="Events and alerts" onClick={() => setActiveTab("logs")} className={`px-4 py-2 text-sm font-medium border-b-2 transition ${activeTab === "logs" ? "border-zinc-900 text-zinc-900" : "border-transparent text-zinc-500 hover:text-zinc-700"}`}>Logs</button>
           {selectedCellId && (
              <button data-testid="tab-inspect" data-ui-tip="Selected cell" onClick={() => setActiveTab("inspect")} className={`px-4 py-2 text-sm font-medium border-b-2 transition ${activeTab === "inspect" ? "border-zinc-900 text-zinc-900" : "border-transparent text-zinc-500 hover:text-zinc-700"}`}>Inspect</button>
           )}
           <button data-testid="tab-settings" data-ui-tip="Providers and model" onClick={() => setActiveTab("settings")} className={`px-4 py-2 text-sm font-medium border-b-2 transition ml-auto ${activeTab === "settings" ? "border-zinc-900 text-zinc-900" : "border-transparent text-zinc-500 hover:text-zinc-700"}`}>Settings</button>
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-y-auto custom-scrollbar flex flex-col">
          {activeTab === "mission" && (
            <div className="flex flex-col h-full">
              <div className="flex-1">
                <div className={drawnBbox && (showBboxTools || showMissionTimelapse) ? "h-[360px] border-b border-zinc-200" : "h-full"}>
                  <Suspense fallback={<LoadingPanel label="Mission" />}>
                    <MissionControl
                      isOpen={true}
                      onClose={() => {}}
                      onDrawBbox={() => setDrawBboxActive(true)}
                      drawnBbox={drawnBbox}
                      onClearBbox={() => { setDrawnBbox(null); setVlmBoxes([]); setShowMissionTimelapse(false); setShowBboxTools(false); }}
                      onOpenTimelapse={() => { setShowBboxTools(true); setShowMissionTimelapse((prev) => !prev); }}
                      onOpenEvidenceTools={() => { setShowBboxTools(true); setShowMissionTimelapse(false); }}
                      mission={mission}
                      onRefresh={fetchMission}
                      isScanComplete={missionPassComplete}
                      onReplayLoaded={handleReplayLoaded}
                      onReplayRescanStarted={handleReplayRescanStarted}
                      onPreviewBbox={(bbox) => {
                        setDrawnBbox(bbox);
                        setVlmBoxes([]);
                        setShowMissionTimelapse(false);
                        setShowBboxTools(false);
                      }}
                      initialPresetId={demoStartProfile?.presetId ?? null}
                    />
                  </Suspense>
                </div>
                {drawnBbox && showMissionTimelapse && (
                  <div className="border-t border-zinc-200">
                    <Suspense fallback={<LoadingPanel label="Timelapse" />}>
                      <TimelapseViewer
                          isOpen={true}
                          onClose={() => setShowMissionTimelapse(false)}
                          bbox={drawnBbox}
                          startDate={mission?.start_date || "2024-06-01"}
                          endDate={mission?.end_date || "2025-06-01"}
                        />
                    </Suspense>
                  </div>
                )}
                {drawnBbox && showBboxTools && (
                  <div>
                    <Suspense fallback={<LoadingPanel label="Evidence Tools" />}>
                      <VlmPanel
                        isOpen={true}
                        onClose={() => { setDrawnBbox(null); setVlmBoxes([]); setShowBboxTools(false); }}
                        activeBbox={drawnBbox}
                        onBoxesUpdate={setVlmBoxes}
                        activeMissionTargets={mission?.object_targets ?? []}
                        targetPackId={mission?.target_pack_id ?? null}
                      />
                    </Suspense>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === "settings" && (
            <div className="flex flex-col h-full">
              <h2 className="text-zinc-500 font-bold tracking-widest uppercase p-6 pb-2 text-xs shrink-0">Provider Settings</h2>
              <Suspense fallback={<LoadingPanel label="Settings" />}>
                <SettingsPanel
                   isOpen={true}
                   onClose={() => {}}
                   apiBaseUrl={apiBaseUrl}
                />
              </Suspense>
            </div>
          )}

          {activeTab === "agents" && (
            <div className="flex flex-col h-full">
               <div className="flex basis-[78%] flex-col min-h-0 border-b border-zinc-200">
                  <h2 className="sr-only">Ground Agent</h2>
                  <div className="flex-1 overflow-hidden">
                    <Suspense fallback={<LoadingPanel label="Ground Agent" />}>
                      <GroundAgent
                        onActionComplete={handleGroundAgentActionComplete}
                        onNavigate={handleGroundAgentNavigate}
                        mission={mission}
                      />
                    </Suspense>
                  </div>
               </div>
               <div className="flex basis-[22%] flex-col min-h-0">
                  <h2 data-testid="header-agent-bus" className="border-b border-zinc-100 bg-zinc-50 px-3 py-2 text-[10px] font-bold uppercase tracking-[0.18em] text-zinc-500 shrink-0">SAT/GND Dialogue Bus</h2>
                  <div className="flex-1 overflow-hidden">
                    <Suspense fallback={<LoadingPanel label="Agent Bus" />}>
                      <AgentDialogue isOpen={true} onClose={() => {}} mission={mission} />
                    </Suspense>
                  </div>
               </div>
            </div>
          )}

          {activeTab === "logs" && (
            <div className="flex flex-col h-full">
              <Suspense fallback={<LoadingPanel label="Logs" />}>
                <AlertsLogs
                   isOpen={true}
                   onClose={() => {}}
                   alerts={alerts}
                   metricsSummary={metricsSummary}
                   apiHealth={apiHealth}
                   heartbeat={heartbeat}
                   selectedCellId={selectedCellId}
                   onSelectCell={(id) => { setSelectedCellId(id); setActiveTab("inspect"); }}
                   mission={mission}
                />
              </Suspense>
            </div>
          )}

          {activeTab === "inspect" && selectedCellId && (
            <div className="flex flex-col h-full p-4">
              <Suspense fallback={<LoadingPanel label="Inspect" className="rounded border border-zinc-200 bg-white" />}>
                <ValidationPanel
                  selectedCellId={selectedCellId}
                  alert={selectedAlert}
                  onOpenTimelapse={() => handleOpenTimelapseForCell(selectedCellId)}
                  mission={mission}
                />
              </Suspense>
              {drawnBbox && (
                <div className="mt-4">
                  <Suspense fallback={<LoadingPanel label="Timelapse" className="rounded border border-zinc-200 bg-white" />}>
                    <TimelapseViewer
                        isOpen={true}
                        onClose={() => {}}
                        bbox={drawnBbox}
                        startDate="2024-06-01"
                        endDate="2025-06-01"
                      />
                  </Suspense>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {demoQuery.enabled && (
        <div
          data-testid="demo-caption"
          className="pointer-events-none absolute bottom-4 left-4 z-50 w-[340px] rounded border border-zinc-800 bg-zinc-950/92 p-3 text-zinc-100 shadow-xl backdrop-blur"
        >
          <div className="mb-3 flex items-center justify-between gap-3">
            <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-200">
              {demoStepIndex === 0
                ? demoStartProfile?.readyLabel ?? "Showcase ready"
                : demoSteps[Math.min(demoStepIndex - 1, demoSteps.length - 1)]}
            </span>
            <button
              type="button"
              data-testid="proof-mode-button"
              onClick={() => void handleProofModeStart()}
              className="pointer-events-auto shrink-0 rounded border border-cyan-300/50 bg-cyan-500/15 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-cyan-100 hover:border-cyan-200"
            >
              Proof Mode
            </button>
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            {demoSteps.map((step, index) => {
              const stepNumber = index + 1;
              const active = demoStepIndex >= stepNumber;
              return (
                <div
                  key={step}
                  data-testid="demo-step"
                  data-active={active ? "true" : "false"}
                  className={`rounded border px-2 py-1 text-[10px] font-semibold ${
                    active
                      ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-100"
                      : "border-zinc-800 bg-zinc-900 text-zinc-500"
                  }`}
                >
                  {step}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {proofModeActive && (
        <Suspense fallback={<LoadingPanel label="Proof Mode" className="absolute inset-0 z-40 bg-zinc-950 text-zinc-400" />}>
          <ProofModePanel
            apiBaseUrl={apiBaseUrl}
            demoCase={demoQuery.demoCase}
            mission={proofMission ?? mission}
            alerts={alerts}
            metricsSummary={metricsSummary}
            selectedCellId={selectedCellId}
            onClose={() => setProofModeActive(false)}
            onStepChange={(stepIndex) => setDemoStepIndex((currentStep) => Math.max(currentStep, stepIndex))}
          />
        </Suspense>
      )}
    </div>
  );
}
