import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from "react";
import type { VlmBox } from "./components/VlmPanel";
import { useTelemetry } from "./hooks/useTelemetry";
import { getApiBaseUrl, generateGridForBbox } from "./utils/telemetry";
import type { Mission } from "./types/mission";

const loadMapVisualizer = () => import("./components/MapVisualizer");
const loadValidationPanel = () => import("./components/ValidationPanel");
const loadSettingsPanel = () => import("./components/SettingsPanel");
const loadAgentDialogue = () => import("./components/AgentDialogue");
const loadGroundAgent = () => import("./components/GroundAgent");
const loadMissionControl = () => import("./components/MissionControl");
const loadTimelapseViewer = () => import("./components/TimelapseViewer");
const loadVlmPanel = () => import("./components/VlmPanel");
const loadAlertsLogs = () => import("./components/AlertsLogs");

const MapVisualizer = lazy(loadMapVisualizer);
const ValidationPanel = lazy(loadValidationPanel);
const SettingsPanel = lazy(loadSettingsPanel);
const AgentDialogue = lazy(loadAgentDialogue);
const GroundAgent = lazy(loadGroundAgent);
const MissionControl = lazy(loadMissionControl);
const TimelapseViewer = lazy(loadTimelapseViewer);
const VlmPanel = lazy(loadVlmPanel);
const AlertsLogs = lazy(loadAlertsLogs);

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


export default function App() {
  const [drawBboxActive, setDrawBboxActive] = useState(false);
  const [drawnBbox, setDrawnBbox] = useState<number[] | null>(null);
  const [vlmBoxes, setVlmBoxes] = useState<VlmBox[]>([]);
  const [showMissionTimelapse, setShowMissionTimelapse] = useState(false);
  const [mission, setMission] = useState<Mission | null>(null);
  const apiBaseUrl = getApiBaseUrl();

  const fetchMission = useCallback(async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/api/mission/current`);
      if (res.ok) {
        const d = await res.json() as { mission: Mission | null };
        setMission(d.mission);
      }
    } catch { /* ignore */ }
  }, [apiBaseUrl]);

  useEffect(() => {
    fetchMission();
    const id = setInterval(fetchMission, 5000);
    return () => clearInterval(id);
  }, [fetchMission]);

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
    await Promise.all([
      refreshTelemetry({ replaceAlerts: true }),
      fetchMission(),
    ]);
    setDrawnBbox(null);
    setVlmBoxes([]);
    setShowMissionTimelapse(false);
    if (primaryCellId) {
      setSelectedCellId(primaryCellId);
      setActiveTab("inspect");
    } else {
      setActiveTab("logs");
    }
  }, [fetchMission, refreshTelemetry, setSelectedCellId]);

  const handleOpenTimelapseForCell = (cellId: string) => {
    if (!geoJsonGrid) return;
    const feature = geoJsonGrid.features.find(f => (f.properties as any)?.cell_id === cellId);
    if (!feature || feature.geometry.type !== "Polygon") return;
    const coords = feature.geometry.coordinates[0];
    const lngs = coords.map(c => c[0]);
    const lats = coords.map(c => c[1]);
    const bbox = [Math.min(...lngs), Math.min(...lats), Math.max(...lngs), Math.max(...lats)];
    setDrawnBbox(bbox);
  };

  const displayGrid = useMemo(() => {
    if (drawnBbox) {
      return generateGridForBbox(drawnBbox);
    }
    return geoJsonGrid;
  }, [drawnBbox, geoJsonGrid]);

  const [activeTab, setActiveTab] = useState<"mission" | "agents" | "logs" | "inspect" | "settings">("mission");

  useEffect(() => {
    if (selectedCellId && activeTab !== "inspect") {
      setActiveTab("inspect");
    }
  }, [selectedCellId]);

  useEffect(() => {
    void loadMapVisualizer();
  }, []);

  useEffect(() => {
    if (drawnBbox) {
      void loadVlmPanel();
    }
    if (drawnBbox && showMissionTimelapse) {
      void loadTimelapseViewer();
    }
  }, [drawnBbox, showMissionTimelapse]);

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

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zinc-50 text-zinc-900 font-sans text-sm">
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
              setDrawBboxActive(false);
            }}
            onMenuAssignBBox={(bbox) => {
              setDrawnBbox(bbox);
              setActiveTab("mission");
            }}
            onMenuGenerateTimelapse={(bbox) => {
              setDrawnBbox(bbox);
              setShowMissionTimelapse(true);
              setActiveTab("mission");
            }}
            onMenuAgentVideoEval={async (bbox) => {
              setDrawnBbox(bbox);
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
          />
        </Suspense>

        {/* Simple Connection Status overlay top-left on map */}
        <div className="absolute left-4 top-4 z-10 flex flex-col gap-2">
          <div className="flex items-center gap-2 rounded border border-zinc-200 bg-white/90 px-3 py-1.5 shadow-sm backdrop-blur cursor-default" title="Telemetry Link Status (View Only)">
             <span className={`h-2 w-2 rounded-full ${connectionState === "open" ? "bg-emerald-500 animate-pulse" : "bg-zinc-400"}`}></span>
             <span className="text-[10px] uppercase font-bold tracking-widest text-zinc-700">
               {connectionState === "open" ? "LINK OPEN" : "DISCONNECTED"}
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
      <div className="w-[450px] min-w-[450px] flex flex-col h-full bg-white border-l border-zinc-200 shadow-xl relative z-20 overflow-hidden">

        {/* Tabs Header */}
        <div className="flex items-center border-b border-zinc-200 bg-zinc-50 px-2 pt-2 shrink-0">
           <button data-testid="tab-mission" onClick={() => setActiveTab("mission")} className={`px-4 py-2 text-sm font-medium border-b-2 transition ${activeTab === "mission" ? "border-zinc-900 text-zinc-900" : "border-transparent text-zinc-500 hover:text-zinc-700"}`}>Mission</button>
           <button data-testid="tab-agents" onClick={() => setActiveTab("agents")} className={`px-4 py-2 text-sm font-medium border-b-2 transition ${activeTab === "agents" ? "border-zinc-900 text-zinc-900" : "border-transparent text-zinc-500 hover:text-zinc-700"}`}>Agents</button>
           <button data-testid="tab-logs" onClick={() => setActiveTab("logs")} className={`px-4 py-2 text-sm font-medium border-b-2 transition ${activeTab === "logs" ? "border-zinc-900 text-zinc-900" : "border-transparent text-zinc-500 hover:text-zinc-700"}`}>Logs</button>
           {selectedCellId && (
              <button data-testid="tab-inspect" onClick={() => setActiveTab("inspect")} className={`px-4 py-2 text-sm font-medium border-b-2 transition ${activeTab === "inspect" ? "border-zinc-900 text-zinc-900" : "border-transparent text-zinc-500 hover:text-zinc-700"}`}>Inspect</button>
           )}
           <button data-testid="tab-settings" onClick={() => setActiveTab("settings")} className={`px-4 py-2 text-sm font-medium border-b-2 transition ml-auto ${activeTab === "settings" ? "border-zinc-900 text-zinc-900" : "border-transparent text-zinc-500 hover:text-zinc-700"}`}>Settings</button>
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-y-auto custom-scrollbar flex flex-col">
          {activeTab === "mission" && (
            <div className="flex flex-col h-full">
              <div className="flex-1">
                <div className={drawnBbox ? "h-[360px] border-b border-zinc-200" : "h-full"}>
                  <Suspense fallback={<LoadingPanel label="Mission" />}>
                    <MissionControl
                      isOpen={true}
                      onClose={() => {}}
                      onDrawBbox={() => setDrawBboxActive(true)}
                      drawnBbox={drawnBbox}
                      onClearBbox={() => { setDrawnBbox(null); setVlmBoxes([]); setShowMissionTimelapse(false); }}
                      onOpenTimelapse={() => setShowMissionTimelapse((prev) => !prev)}
                      mission={mission}
                      onRefresh={fetchMission}
                      isScanComplete={isScanComplete}
                      onReplayLoaded={handleReplayLoaded}
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
                {drawnBbox && (
                  <div>
                    <Suspense fallback={<LoadingPanel label="VLM" />}>
                      <VlmPanel
                        isOpen={true}
                        onClose={() => { setDrawnBbox(null); setVlmBoxes([]); }}
                        activeBbox={drawnBbox}
                        onBoxesUpdate={setVlmBoxes}
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
               <div className="flex-1 flex flex-col min-h-0 border-b border-zinc-200">
                  <h2 data-testid="header-agent-bus" className="text-zinc-500 font-bold tracking-widest uppercase p-4 pb-0 text-xs shrink-0">Agent Dialogue Bus</h2>
                  <div className="flex-1 overflow-hidden">
                    <Suspense fallback={<LoadingPanel label="Agent Bus" />}>
                      <AgentDialogue isOpen={true} onClose={() => {}} mission={mission} />
                    </Suspense>
                  </div>
               </div>
               <div className="flex-1 flex flex-col min-h-0">
                  <h2 className="text-zinc-500 font-bold tracking-widest uppercase p-4 pb-0 text-xs shrink-0">Ground Agent Assistant</h2>
                  <div className="flex-1 overflow-hidden">
                    <Suspense fallback={<LoadingPanel label="Ground Agent" />}>
                      <GroundAgent />
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
    </div>
  );
}
