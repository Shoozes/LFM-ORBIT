import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  AlertItem,
  ApiHealth,
  ApiMetricsSummary,
  ConnectionState,
  RecentAlertsResponse,
  ScanHeartbeat,
  TelemetryMessage,
} from "../types/telemetry";
import {
  createOrbitalScanEvent,
  getApiBaseUrl,
  getWebSocketUrl,
  mergeAlertLists,
  parseTelemetryMessage,
  toAlertItem,
} from "../utils/telemetry";

export type UseTelemetryState = {
  geoJsonGrid: GeoJSON.FeatureCollection | null;
  regionId: string;
  displayName: string;
  bandwidthSaved: number;
  alerts: AlertItem[];
  selectedCellId: string | null;
  setSelectedCellId: React.Dispatch<React.SetStateAction<string | null>>;
  heartbeat: ScanHeartbeat | null;
  selectedAlert: AlertItem | null;
  connectionState: ConnectionState;
  apiHealth: ApiHealth | null;
  metricsSummary: ApiMetricsSummary | null;
  isScanComplete: boolean;
  refreshTelemetry: (options?: { replaceAlerts?: boolean }) => Promise<void>;
};

async function fetchJson<T>(url: string, signal?: AbortSignal): Promise<T | null> {
  try {
    const response = await fetch(url, signal ? { signal } : undefined);

    if (!response.ok) {
      return null;
    }

    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export function useTelemetry(): UseTelemetryState {
  const apiBaseUrl = getApiBaseUrl();
  const telemetryUrl = getWebSocketUrl(apiBaseUrl);

  const [geoJsonGrid, setGeoJsonGrid] = useState<GeoJSON.FeatureCollection | null>(null);
  const [regionId, setRegionId] = useState<string>("unlocked");
  const [displayName, setDisplayName] = useState<string>("Region not loaded");
  const [bandwidthSaved, setBandwidthSaved] = useState<number>(0);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [selectedCellId, setSelectedCellId] = useState<string | null>(null);
  const [heartbeat, setHeartbeat] = useState<ScanHeartbeat | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const [apiHealth, setApiHealth] = useState<ApiHealth | null>(null);
  const [metricsSummary, setMetricsSummary] = useState<ApiMetricsSummary | null>(null);
  const [isScanComplete, setIsScanComplete] = useState<boolean>(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttempts = useRef(0);
  const mountedRef = useRef(true);
  const refreshAbortRef = useRef<AbortController | null>(null);
  const refreshSequenceRef = useRef(0);
  const metricsInFlightRef = useRef(false);
  const MAX_RECONNECT_ATTEMPTS = 10;
  const BASE_RECONNECT_DELAY_MS = 1000;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      refreshAbortRef.current?.abort();
      refreshAbortRef.current = null;
    };
  }, []);

  const refreshTelemetry = useCallback(async (options?: { replaceAlerts?: boolean }) => {
    const replaceAlerts = options?.replaceAlerts ?? false;
    const requestSequence = ++refreshSequenceRef.current;
    refreshAbortRef.current?.abort();
    const controller = new AbortController();
    refreshAbortRef.current = controller;

    try {
      const [health, recent, metrics] = await Promise.all([
        fetchJson<ApiHealth>(`${apiBaseUrl}/api/health`, controller.signal),
        fetchJson<RecentAlertsResponse>(`${apiBaseUrl}/api/alerts/recent?limit=50`, controller.signal),
        fetchJson<ApiMetricsSummary>(`${apiBaseUrl}/api/metrics/summary`, controller.signal),
      ]);

      if (
        controller.signal.aborted ||
        !mountedRef.current ||
        requestSequence !== refreshSequenceRef.current
      ) {
        return;
      }

      if (health) {
        setApiHealth(health);
        setRegionId(health.region_id);
        setDisplayName(health.display_name);
      }

      if (recent) {
        setAlerts((current) => (replaceAlerts ? recent.alerts : mergeAlertLists(current, recent.alerts)));
        if (recent.region_id) {
          setRegionId(recent.region_id);
        }
      }

      if (metrics) {
        setMetricsSummary(metrics);
        setBandwidthSaved(metrics.total_bandwidth_saved_mb);
      }
    } finally {
      if (refreshAbortRef.current === controller) {
        refreshAbortRef.current = null;
      }
    }
  }, [apiBaseUrl]);

  useEffect(() => {
    void refreshTelemetry({ replaceAlerts: true });
  }, [refreshTelemetry]);

  useEffect(() => {
    const controller = new AbortController();

    const refreshMetrics = async () => {
      if (metricsInFlightRef.current || controller.signal.aborted) {
        return;
      }
      metricsInFlightRef.current = true;
      try {
        const metrics = await fetchJson<ApiMetricsSummary>(
          `${apiBaseUrl}/api/metrics/summary`,
          controller.signal,
        );
        if (controller.signal.aborted || !mountedRef.current || !metrics) {
          return;
        }
        setMetricsSummary(metrics);
        setBandwidthSaved(metrics.total_bandwidth_saved_mb);
      } finally {
        metricsInFlightRef.current = false;
      }
    };

    const intervalId = window.setInterval(() => {
      void refreshMetrics();
    }, 5000);

    return () => {
      controller.abort();
      window.clearInterval(intervalId);
    };
  }, [apiBaseUrl]);

  useEffect(() => {
    let cancelled = false;

    function connect() {
      if (cancelled) return;

      const socket = new WebSocket(telemetryUrl);
      wsRef.current = socket;
      setConnectionState(reconnectAttempts.current > 0 ? "reconnecting" : "connecting");
      setIsScanComplete(false);

      socket.onopen = () => {
        if (cancelled) return;
        if (reconnectAttempts.current > 0) {
          void (async () => {
            const recent = await fetchJson<RecentAlertsResponse>(`${apiBaseUrl}/api/alerts/recent?limit=50`);
            if (!cancelled && recent) {
              setAlerts((current) => mergeAlertLists(current, recent.alerts));
            }
          })();
        }
        reconnectAttempts.current = 0;
        setConnectionState("open");
      };

      socket.onerror = () => {
        if (cancelled || !mountedRef.current) return;
        setConnectionState("error");
      };

      socket.onclose = () => {
        wsRef.current = null;
        if (cancelled || !mountedRef.current) {
          return;
        }
        if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = Math.min(
            BASE_RECONNECT_DELAY_MS * Math.pow(2, reconnectAttempts.current),
            30000,
          );
          reconnectAttempts.current += 1;
          setConnectionState("reconnecting");
          reconnectTimer.current = setTimeout(connect, delay);
        } else {
          setConnectionState("closed");
        }
      };

      socket.onmessage = (event) => {
        if (cancelled) return;
        const message: TelemetryMessage | null = parseTelemetryMessage(event.data);

        if (!message) {
          return;
        }

        if (message.type === "grid_init") {
          setGeoJsonGrid(message.data);
          setRegionId(message.region.region_id);
          setDisplayName(message.region.display_name);
          setIsScanComplete(false);
          return;
        }

        if (message.type === "scan_complete") {
          setIsScanComplete(true);
          return;
        }

        setHeartbeat(message.heartbeat);

        if (message.is_anomaly) {
          setAlerts((current) => mergeAlertLists(current, [toAlertItem(message)]));
        }

        window.dispatchEvent(createOrbitalScanEvent(message));
      };
    }

    const initialConnectTimer = window.setTimeout(connect, 0);

    return () => {
      cancelled = true;
      window.clearTimeout(initialConnectTimer);
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [apiBaseUrl, telemetryUrl]);

  const selectedAlert = useMemo(() => {
    if (!selectedCellId) {
      return null;
    }

    return alerts.find((alert) => alert.cell_id === selectedCellId) ?? null;
  }, [alerts, selectedCellId]);

  return {
    geoJsonGrid,
    regionId,
    displayName,
    bandwidthSaved,
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
  };
}
