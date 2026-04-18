/**
 * TimelapseViewer — filmstrip visualization of historical scan data.
 *
 * Uses the /api/timelapse/generate endpoint to build a sequence
 * of image frames over the given time range acting as a simulated
 * time-series representation.
 */
import { useEffect, useState } from "react";
import { getApiBaseUrl } from "../utils/telemetry";

type TimelapsePayload = {
  video_b64: string;
  frames_count: number;
  format: string;
};

type TimelapseViewerProps = {
  isOpen: boolean;
  onClose: () => void;
  bbox: number[]; // [W, S, E, N]
  startDate: string;
  endDate: string;
};

export default function TimelapseViewer({
  isOpen,
  onClose,
  bbox,
  startDate,
  endDate,
}: TimelapseViewerProps) {
  const [timelapse, setTimelapse] = useState<TimelapsePayload | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const apiBase = getApiBaseUrl();

  useEffect(() => {
    if (!isOpen) return;

    let mounted = true;
    const fetchFrames = async () => {
      console.log("[TimelapseViewer] Starting fetch for bbox:", bbox);
      setIsLoading(true);
      setError(null);
      try {
        const res = await fetch(`${apiBase}/api/timelapse/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            bbox,
            start_date: startDate || "2024-01-01",
            end_date: endDate || "2024-12-31",
            steps: 24,
          }),
        });
        
        if (!res.ok) {
          throw new Error(`Server returned ${res.status}: ${res.statusText}`);
        }

        if (mounted) {
          const data = (await res.json()) as TimelapsePayload;
          console.log("[TimelapseViewer] Received data, frames:", data.frames_count);
          setTimelapse(data);
          
          // Acknowledge in Agent Dialogue
          fetch(`${apiBase}/api/agent/bus/inject`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              role: "ground",
              type: "status",
              message: `Timelapse generation complete. Exported ${data.frames_count} historical frames for the target sector.`
            })
          }).catch(() => {});
        }
      } catch (err: any) {
        console.error("[TimelapseViewer] Fetch failed:", err);
        if (mounted) setError(err.message || "Failed to generate timelapse.");
      } finally {
        if (mounted) setIsLoading(false);
      }
    };

    void fetchFrames();

    return () => {
      mounted = false;
    };
  }, [isOpen, bbox, startDate, endDate, apiBase]);

  if (!isOpen) return null;

  return (
    <div className="flex flex-col h-full w-full bg-white border border-zinc-200 rounded-lg overflow-hidden mt-4 shadow-sm min-h-[300px]">
      {/* Panel */}
      <div className="flex-1 flex flex-col w-full bg-transparent">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4 flex-shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-[10px] uppercase font-bold tracking-wider text-zinc-900">
              Orbital Timelapse
            </span>
            <span className="rounded border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-[10px] font-medium text-zinc-500 uppercase tracking-wider">
              {startDate} / {endDate}
            </span>
          </div>
          <button 
            onClick={onClose}
            className="text-zinc-400 hover:text-zinc-600 transition"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="relative flex-1 bg-zinc-50 flex flex-col min-h-[200px] justify-center">
          {isLoading && (
            <div className="flex flex-col gap-4 items-center justify-center p-8 text-center text-zinc-500 text-xs font-semibold uppercase tracking-wider">
              <span className="animate-pulse">Loading historic frame sequence…</span>
            </div>
          )}

          {error && !isLoading && (
            <div className="flex flex-col gap-2 items-center justify-center p-8 text-center text-red-500 text-xs font-semibold uppercase tracking-wider">
              <span>{error}</span>
              <button 
                onClick={() => window.location.reload()} 
                className="mt-2 px-3 py-1 rounded border border-red-200 bg-white hover:bg-red-50 transition"
              >
                Retry Request
              </button>
            </div>
          )}

          {!isLoading && !error && timelapse && (
            <>
              {/* Video sequence viewer */}
              <div className="relative flex-1 flex items-center justify-center bg-black/5 w-full overflow-hidden">
                <video
                  src={timelapse.video_b64}
                  autoPlay
                  loop
                  controls
                  className="w-full h-full object-contain transition-opacity duration-300 ease-in-out"
                />
              </div>

              {/* Controls */}
              <div className="p-4 border-t border-zinc-200 bg-white flex gap-4 items-center justify-between">
                <div className="text-[10px] text-zinc-500 font-semibold uppercase tracking-wider">
                  Extracted {timelapse.frames_count} historical frames
                </div>
              </div>
            </>
          )}

          {!isLoading && !error && !timelapse && (
            <div className="flex items-center justify-center p-8 text-zinc-400 text-[10px] uppercase font-bold tracking-widest">
              No sequence data available
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
