import { useState, useEffect } from "react";
import type { AnalysisStatus } from "../types/telemetry";

type ProviderInfo = {
  available: boolean;
  description: string;
  credential_source?: string;
};

type ProviderStatus = {
  active_provider: string;
  providers: Record<string, ProviderInfo>;
  sentinel_secret_detected: boolean;
  sentinel_credential_source: string;
  fallback_order: string[];
};

type SimSatStatus = {
  simsat_base_url: string;
  simsat_available: boolean;
  timeout_seconds: number;
  endpoints: {
    sentinel_historical: string;
    sentinel_current: string;
  };
};

type SettingsPanelProps = {
  isOpen: boolean;
  onClose: () => void;
  apiBaseUrl: string;
};

function providerDisplayName(key: string): string {
  if (key === "simsat_sentinel") return "SimSat Sentinel";
  if (key === "sentinelhub_direct") return "Sentinel Hub Direct";
  return key;
}

export default function SettingsPanel({ isOpen, onClose, apiBaseUrl }: SettingsPanelProps) {
  const [providerStatus, setProviderStatus] = useState<ProviderStatus | null>(null);
  const [simsatStatus, setSimsatStatus] = useState<SimSatStatus | null>(null);
  const [analysisStatus, setAnalysisStatus] = useState<AnalysisStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Settings State
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [savingSettings, setSavingSettings] = useState(false);


  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (isOpen) {
      fetchStatus();
    }
  }, [isOpen, apiBaseUrl]);

  async function fetchStatus() {
    setLoading(true);
    setError(null);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    try {
      const [providerRes, simsatRes, analysisRes] = await Promise.all([
        fetch(`${apiBaseUrl}/api/provider/status`, { signal: controller.signal }).catch(() => null),
        fetch(`${apiBaseUrl}/api/simsat/status`, { signal: controller.signal }).catch(() => null),
        fetch(`${apiBaseUrl}/api/analysis/status`, { signal: controller.signal }).catch(() => null),
      ]);
      clearTimeout(timeoutId);

      if (!providerRes && !simsatRes && !analysisRes) {
        throw new Error("Backend offline. Cannot connect to Canopy Sentinel API.");
      }

      if (providerRes?.ok) {
        setProviderStatus(await providerRes.json());
      }

      if (simsatRes?.ok) {
        setSimsatStatus(await simsatRes.json());
      }

      if (analysisRes?.ok) {
        setAnalysisStatus(await analysisRes.json());
      }

      if (providerRes && !providerRes.ok) {
        throw new Error(`HTTP ${providerRes.status}`);
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        setError("Request timed out. Backend is too slow or unreachable.");
      } else {
        setError(err instanceof Error ? err.message : "Failed to fetch status");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveSettings() {
    if (!clientId || !clientSecret) return;
    setSavingSettings(true);
    try {
      const res = await fetch(`${apiBaseUrl}/api/settings/credentials`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: clientId, client_secret: clientSecret })
      });
      if (res.ok) {
        setClientId("");
        setClientSecret("");
        await fetchStatus();
      } else {
        setError("Failed to save credentials.");
      }
    } catch (e) {
      setError("Network error saving credentials.");
    } finally {
      setSavingSettings(false);
    }
  }


  if (!isOpen) {
    return null;
  }

  return (
    <div className="flex flex-col h-full w-full overflow-hidden bg-white">
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5 custom-scrollbar">
          {error && (
            <div className="rounded border border-red-200 bg-red-50 p-3">
              <p className="text-xs text-red-600 font-medium">{error}</p>
            </div>
          )}

          <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs uppercase tracking-wider font-semibold text-zinc-500">Provider Status</p>
              <button
                type="button"
                onClick={fetchStatus}
                disabled={loading}
                className="text-[10px] uppercase font-bold text-zinc-500 hover:text-zinc-700 disabled:text-zinc-300 transition"
              >
                {loading ? "Checking..." : "Refresh"}
              </button>
            </div>

            {providerStatus ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <p className="text-zinc-500 font-semibold mb-1">Active Provider</p>
                    <p className="text-emerald-700 font-bold">
                      {providerDisplayName(providerStatus.active_provider)}
                    </p>
                  </div>
                  <div>
                    <p className="text-zinc-500 font-semibold mb-1">Sentinel Credentials</p>
                    <p className={`font-semibold ${providerStatus.sentinel_secret_detected ? "text-emerald-700" : "text-amber-600"}`}>
                      {providerStatus.sentinel_secret_detected
                        ? `Configured (${providerStatus.sentinel_credential_source})`
                        : "Missing"}
                    </p>
                  </div>
                </div>

                <div>
                  <p className="text-zinc-500 font-semibold text-[10px] uppercase tracking-wider mb-2">Provider Tiers</p>
                  <div className="space-y-2 text-xs">
                    {Object.entries(providerStatus.providers).map(([key, info]) => (
                      <div
                        key={key}
                        className={`flex items-center justify-between rounded border p-2 ${
                          key === providerStatus.active_provider
                            ? "border-emerald-200 bg-emerald-50"
                            : "border-zinc-200 bg-white"
                        }`}
                      >
                        <div>
                          <span className="text-zinc-800 font-medium">{providerDisplayName(key)}</span>
                          {key === providerStatus.active_provider && (
                            <span className="ml-2 text-emerald-700 text-[10px] font-bold uppercase tracking-wider">● Active</span>
                          )}
                        </div>
                        <span className={`text-[10px] font-bold uppercase tracking-wider ${info.available ? "text-emerald-600" : "text-zinc-400"}`}>
                          {info.available ? "Available" : "Unavailable"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-zinc-500 font-semibold text-[10px] uppercase tracking-wider mb-1">Fallback Order</p>
                  <p className="text-xs text-zinc-700 font-medium">
                    {(providerStatus.fallback_order || []).map(providerDisplayName).join(" → ")}
                  </p>
                </div>
              </div>
            ) : loading ? (
              <div className="text-center py-4">
                <p className="text-xs text-zinc-400 font-semibold uppercase tracking-wider">Loading...</p>
              </div>
            ) : (
              <div className="text-center py-4 rounded bg-red-50 border border-red-200 mt-4">
                <p className="text-xs text-red-600 font-bold uppercase tracking-widest">Backend Offline</p>
                <p className="text-[10px] text-red-400 mt-1">Start uvicorn or the FASTAPI server.</p>
              </div>
            )}
          </div>

          <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4">
            <p className="text-xs uppercase tracking-wider font-semibold text-zinc-500 mb-3">SimSat API</p>

            {simsatStatus ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <p className="text-zinc-500 font-semibold mb-1">Base URL</p>
                    <p className="text-zinc-900 font-medium break-all">{simsatStatus.simsat_base_url}</p>
                  </div>
                  <div>
                    <p className="text-zinc-500 font-semibold mb-1">Connection</p>
                    <p className={`font-semibold ${simsatStatus.simsat_available ? "text-emerald-700" : "text-red-600"}`}>
                      {simsatStatus.simsat_available ? "Available" : "Unavailable"}
                    </p>
                  </div>
                  <div>
                    <p className="text-zinc-500 font-semibold mb-1">Timeout</p>
                    <p className="text-zinc-700 font-medium">{simsatStatus.timeout_seconds}s</p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-4 rounded border border-red-200 bg-red-50 mt-4">
                <p className="text-xs text-red-600 font-bold uppercase tracking-widest">Backend Offline</p>
              </div>
            )}
          </div>

          <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4">
            <p className="text-xs uppercase tracking-wider font-semibold text-zinc-500 mb-3">Local Model</p>

            {analysisStatus ? (
              <div className="space-y-4 text-xs">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <p className="text-zinc-500 font-semibold mb-1">Default Model</p>
                    <p className="text-emerald-700 font-bold">{analysisStatus.default_model}</p>
                  </div>
                  <div>
                    <p className="text-zinc-500 font-semibold mb-1">Offline Ready</p>
                    <p className="text-emerald-700 font-bold">Yes</p>
                  </div>
                </div>
                <div>
                  <p className="text-zinc-500 font-semibold mb-1">Satellite Inference Engine</p>
                  <p className={`font-semibold ${
                    analysisStatus.satellite_inference_loaded ? "text-emerald-700" : "text-amber-600"
                  }`}>
                    {analysisStatus.satellite_inference_loaded
                      ? "Loaded (GGUF)"
                      : "Standby — model file not yet fetched"}
                  </p>
                </div>
                <div>
                  <p className="text-zinc-500 font-semibold text-[10px] uppercase tracking-wider mb-2">Model Tiers</p>
                  <div className="space-y-2">
                    {Object.entries(analysisStatus.models).map(([key, info]) => (
                      <div
                        key={key}
                        className={`flex items-center justify-between rounded border p-2 ${
                          key === analysisStatus.default_model
                            ? "border-emerald-200 bg-emerald-50"
                            : "border-zinc-200 bg-white"
                        }`}
                      >
                        <div>
                          <span className="text-zinc-800 font-medium">{key}</span>
                          {key === analysisStatus.default_model && (
                            <span className="ml-2 text-emerald-700 text-[10px] font-bold uppercase tracking-wider">● Default</span>
                          )}
                        </div>
                        <span className={`text-[10px] uppercase tracking-wider font-bold ${info.available ? "text-emerald-600" : "text-zinc-400"}`}>
                          {info.available ? "Available" : "Unavailable"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
                <p className="text-zinc-500 text-[10px] italic">{analysisStatus.note}</p>
              </div>
            ) : (
              <div className="text-center py-4 rounded border border-red-200 bg-red-50 mt-4">
                <p className="text-xs text-red-600 font-bold uppercase tracking-widest">Backend Offline</p>
              </div>
            )}
          </div>

          <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4">
            <p className="text-xs uppercase tracking-wider font-semibold text-zinc-500 mb-1">Configuration</p>
            <p className="text-xs text-zinc-500 mb-4">
              Update Sentinel Hub direct credentials for image processing.
            </p>
            <div className="flex flex-col gap-3 mb-4">
              <input
                type="text"
                placeholder="Sentinel Client ID"
                value={clientId}
                onChange={e => setClientId(e.target.value)}
                className="rounded border border-zinc-300 bg-white px-3 py-2 text-zinc-900 focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500 outline-none text-xs"
              />
              <input
                type="password"
                placeholder="Sentinel Client Secret"
                value={clientSecret}
                onChange={e => setClientSecret(e.target.value)}
                className="rounded border border-zinc-300 bg-white px-3 py-2 text-zinc-900 focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500 outline-none text-xs"
              />
              <button
                type="button"
                onClick={handleSaveSettings}
                disabled={savingSettings || !clientId || !clientSecret}
                className="rounded border border-zinc-300 bg-white py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-100 transition disabled:opacity-50"
              >
                {savingSettings ? "Saving..." : "Save Credentials"}
              </button>
            </div>
            
            <div className="space-y-3 text-xs text-zinc-500">
              <div>
                <p className="text-zinc-600 font-semibold mb-1">Observation Provider</p>
                <p>Explicit provider override: simsat_sentinel or sentinelhub_direct.</p>
              </div>
            </div>
          </div>
        </div>

    </div>
  );
}
