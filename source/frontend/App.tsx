import { useState, useMemo } from "react";
import MapVisualizer from "./components/MapVisualizer";
import ValidationPanel from "./components/ValidationPanel";
import SettingsPanel from "./components/SettingsPanel";
import AgentDialogue from "./components/AgentDialogue";
import GroundAgent from "./components/GroundAgent";
import MissionControl from "./components/MissionControl";
import TimelapseViewer from "./components/TimelapseViewer";
import VlmPanel, { type VlmBox } from "./components/VlmPanel";
import AlertsLogs from "./components/AlertsLogs";
import { useTelemetry } from "./hooks/useTelemetry";
import { getApiBaseUrl, generateGridForBbox } from "./utils/telemetry";
import { Mission } from "./types/mission";
import { useCallback, useEffect } from "react";


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
  } = useTelemetry();

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

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zinc-50 text-zinc-900 font-sans text-sm">
      {/* LEFT PANE: MAP */}
      <div className="flex-1 relative h-full">
        <MapVisualizer
          geoJsonGrid={displayGrid}
          selectedCellId={selectedCellId}
          onCellClick={(id) => {
             setSelectedCellId(id);
             if (id) {
               // Optional: scroll sidebar to details if we were implementing refs, 
               // but for now it will just expand.
             }
          }}
          drawBboxActive={drawBboxActive}
          drawnBbox={drawnBbox}
          onBboxDrawn={(bbox) => {
            setDrawnBbox(bbox);
            setDrawBboxActive(false);
          }}
          onMenuAssignBBox={(bbox) => {
            setDrawnBbox(bbox);
          }}
          onMenuGenerateTimelapse={(bbox) => {
            setDrawnBbox(bbox);
          }}
          onMenuAgentVideoEval={async (bbox) => {
            try {
              await fetch(`${apiBaseUrl}/api/agent/bus/inject`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  role: "operator",
                  type: "query",
                  message: `Analyze orbital timeframe for coords [${bbox[0].toFixed(2)}, ${bbox[1].toFixed(2)}]. Determine if seasonality or permanent structural loss.`
                })
              });
              
              const res = await fetch(`${apiBaseUrl}/api/analysis/timelapse`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ bbox })
              });
              if (res.ok) {
                const data = await res.json();
                await fetch(`${apiBaseUrl}/api/agent/bus/inject`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    role: "ground",
                    type: "status",
                    message: data.analysis || "Analysis complete."
                  })
                });
              }
            } catch (err) {
               console.error("Agent Video Eval failed:", err);
            }
          }}
          vlmBoxes={vlmBoxes}
        />
        
        {/* Simple Connection Status overlay top-left on map */}
        <div className="absolute left-4 top-4 z-10 flex flex-col gap-2">
          <div className="flex items-center gap-2 rounded border border-zinc-200 bg-white/90 px-3 py-1.5 shadow-sm backdrop-blur">
             <span className={`h-2 w-2 rounded-full ${connectionState === "open" ? "bg-emerald-500 animate-pulse" : "bg-zinc-400"}`}></span>
             <span className="text-[10px] uppercase font-bold tracking-widest text-zinc-700">
               {connectionState === "open" ? "LINK OPEN" : "DISCONNECTED"}
             </span>
          </div>
          
          {mission?.status === "active" && (
            <div className="flex items-center gap-2 rounded border border-emerald-200 bg-emerald-50/90 px-3 py-1.5 shadow-sm backdrop-blur">
               <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
               <span className="text-[10px] uppercase font-bold tracking-widest text-emerald-700">
                 MISSION ACTIVE: #{mission.id}
               </span>
            </div>
          )}
        </div>
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
                <MissionControl
                  isOpen={true}
                  onClose={() => {}}
                  onDrawBbox={() => setDrawBboxActive(true)}
                  drawnBbox={drawnBbox}
                  onClearBbox={() => { setDrawnBbox(null); setVlmBoxes([]); setShowMissionTimelapse(false); }}
                  onOpenTimelapse={() => setShowMissionTimelapse((prev) => !prev)}
                  mission={mission}
                  onRefresh={fetchMission}
                  isScanComplete={false}
                />
                {drawnBbox && (
                  <div className="border-t border-zinc-200">
                    <VlmPanel
                      isOpen={true}
                      onClose={() => { setDrawnBbox(null); setVlmBoxes([]); }}
                      activeBbox={drawnBbox}
                      onBoxesUpdate={setVlmBoxes}
                    />
                  </div>
                )}
                {drawnBbox && showMissionTimelapse && (
                  <div className="border-t border-zinc-200">
                     <TimelapseViewer
                        isOpen={true}
                        onClose={() => setShowMissionTimelapse(false)}
                        bbox={drawnBbox}
                        startDate={mission?.start_date || "2024-06-01"}
                        endDate={mission?.end_date || "2025-06-01"}
                      />
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === "settings" && (
            <div className="flex flex-col h-full">
              <h2 className="text-zinc-500 font-bold tracking-widest uppercase p-6 pb-2 text-xs shrink-0">Provider Settings</h2>
              <SettingsPanel
                 isOpen={true}
                 onClose={() => {}}
                 apiBaseUrl={apiBaseUrl}
              />
            </div>
          )}

          {activeTab === "agents" && (
            <div className="flex flex-col h-full">
               <div className="flex-1 flex flex-col min-h-0 border-b border-zinc-200">
                  <h2 className="text-zinc-500 font-bold tracking-widest uppercase p-4 pb-0 text-xs shrink-0">Agent Dialogue Bus</h2>
                  <div className="flex-1 overflow-hidden">
                    <AgentDialogue isOpen={true} onClose={() => {}} />
                  </div>
               </div>
               <div className="flex-1 flex flex-col min-h-0">
                  <h2 className="text-zinc-500 font-bold tracking-widest uppercase p-4 pb-0 text-xs shrink-0">Ground Agent Assistant</h2>
                  <div className="flex-1 overflow-hidden">
                    <GroundAgent />
                  </div>
               </div>
            </div>
          )}

          {activeTab === "logs" && (
            <div className="flex flex-col h-full">
               <AlertsLogs
                  isOpen={true}
                  onClose={() => {}}
                  alerts={alerts}
                  metricsSummary={metricsSummary}
                  apiHealth={apiHealth}
                  heartbeat={heartbeat}
                  selectedCellId={selectedCellId}
                  onSelectCell={(id) => { setSelectedCellId(id); setActiveTab("inspect"); }}
               />
            </div>
          )}

          {activeTab === "inspect" && selectedCellId && (
            <div className="flex flex-col h-full p-4">
              <ValidationPanel 
                selectedCellId={selectedCellId} 
                alert={selectedAlert} 
                onOpenGallery={() => {}}
                onOpenTimelapse={() => handleOpenTimelapseForCell(selectedCellId)}
              />
              {drawnBbox && (
                <div className="mt-4">
                   <TimelapseViewer
                      isOpen={true}
                      onClose={() => {}}
                      bbox={drawnBbox}
                      startDate="2024-06-01"
                      endDate="2025-06-01"
                    />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
