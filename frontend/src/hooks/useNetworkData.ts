/**
 * Primary telemetry hook integrating REST endpoints, WebSocket streaming, and state management.
 * Provides unified real-time traffic statistics and AI anomaly observability.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../services/api';
import type {
  ActivityEvent,
  AnomalyEvent,
  AnomalySummaryResponse,
  HealthResponse,
  InterfaceDetail,
  MonitoringSummary,
  NetworkMetric,
  RollingAnomalyPoint,
  WebSocketMessage,
} from '../types/metrics';
import { useWebSocket } from './useWebSocket';
import type { ConnectionStatus } from './useWebSocket';

const MAX_ROLLING_SAMPLES = 30;
const MAX_ROLLING_ANOMALY_SAMPLES = 50;

export function useNetworkData() {
  const [metrics, setMetrics] = useState<NetworkMetric | null>(null);
  const [prevMetrics, setPrevMetrics] = useState<NetworkMetric | null>(null);
  const [rollingHistory, setRollingHistory] = useState<NetworkMetric[]>([]);
  const [interfaces, setInterfaces] = useState<InterfaceDetail[]>([]);
  const [activeInterface, setActiveInterface] = useState<string | null>(null);
  const [isMonitoring, setIsMonitoring] = useState<boolean>(true);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [summary, setSummary] = useState<MonitoringSummary | null>(null);
  const [activities, setActivities] = useState<ActivityEvent[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSwitching, setIsSwitching] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Anomaly engine state
  const [anomalySummary, setAnomalySummary] = useState<AnomalySummaryResponse | null>(null);
  const [anomalyEvents, setAnomalyEvents] = useState<AnomalyEvent[]>([]);
  const [rollingAnomalyHistory, setRollingAnomalyHistory] = useState<RollingAnomalyPoint[]>([]);
  const [isAnomalyLoading, setIsAnomalyLoading] = useState<boolean>(false);
  const [anomalyError, setAnomalyError] = useState<string | null>(null);

  const prevPeakRef = useRef<{ up: number; down: number }>({ up: 0, down: 0 });

  const addActivity = useCallback((type: ActivityEvent['type'], message: string, details?: string) => {
    setActivities((prev) => [
      {
        id: `${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
        timestamp: new Date().toLocaleTimeString(),
        type,
        message,
        details,
      },
      ...prev.slice(0, 49), // Keep latest 50 events
    ]);
  }, []);

  // Fetch anomaly data from backend
  const refreshAnomalies = useCallback(async () => {
    setIsAnomalyLoading(true);
    setAnomalyError(null);
    try {
      const [sumData, eventsData] = await Promise.all([
        api.getAnomalySummary(),
        api.getAnomalies({ limit: 50 }),
      ]);
      setAnomalySummary(sumData);
      setAnomalyEvents(eventsData.events || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch anomaly statistics';
      setAnomalyError(msg);
    } finally {
      setIsAnomalyLoading(false);
    }
  }, []);

  // WebSocket message handler
  const handleWebSocketMessage = useCallback(
    (message: WebSocketMessage) => {
      // 1. Handle dedicated anomaly alert event
      if (message.type === 'anomaly_event') {
        const event = message.data;
        addActivity(
          'alert',
          `AI Anomaly Detected (${event.severity})`,
          `${event.explanation} (Score: ${event.anomaly_score.toFixed(2)})`
        );
        // Prepend to persistent event history
        setAnomalyEvents((prev) => [event, ...prev.filter((e) => e.id !== event.id).slice(0, 49)]);
        // Trigger background summary refresh to update counters
        api.getAnomalySummary().then(setAnomalySummary).catch(() => {});
        return;
      }

      // 2. Ignore remote campus device telemetry events in local host monitoring hook
      if (message.type === 'device_telemetry') {
        return;
      }

      // 3. Handle live local host telemetry updates (initial_state or metric_update)
      const sample = message.data;
      if (!sample) return;

      setMetrics((current) => {
        if (current) setPrevMetrics(current);
        return sample;
      });

      // Track active interface
      if (sample.interface) {
        setActiveInterface(sample.interface);
      }

      // Add to rolling traffic throughput history
      setRollingHistory((prev) => {
        if (prev.length > 0 && prev[prev.length - 1].timestamp === sample.timestamp) {
          return prev;
        }
        const updated = [...prev, sample];
        return updated.length > MAX_ROLLING_SAMPLES
          ? updated.slice(updated.length - MAX_ROLLING_SAMPLES)
          : updated;
      });

      // Track rolling anomaly score history for real-time timeline chart
      if (sample.anomaly) {
        const date = new Date(sample.timestamp);
        const timeLabel = !isNaN(date.getTime())
          ? date.toLocaleTimeString('en-US', { hour12: false })
          : '';

        const point: RollingAnomalyPoint = {
          timestamp: sample.timestamp,
          timeLabel,
          score: sample.anomaly.score,
          severity: sample.anomaly.severity,
          isAnomaly: sample.anomaly.is_anomaly,
          download_mbps: sample.download_mbps,
          upload_mbps: sample.upload_mbps,
        };

        setRollingAnomalyHistory((prev) => {
          if (prev.length > 0 && prev[prev.length - 1].timestamp === point.timestamp) {
            return prev;
          }
          const updated = [...prev, point];
          return updated.length > MAX_ROLLING_ANOMALY_SAMPLES
            ? updated.slice(updated.length - MAX_ROLLING_ANOMALY_SAMPLES)
            : updated;
        });
      }

      // Detect volumetric peak throughput events
      if (sample.download_mbps > 5.0 && sample.download_mbps > prevPeakRef.current.down * 1.5) {
        prevPeakRef.current.down = sample.download_mbps;
        addActivity('info', `High download throughput observed`, `${sample.download_mbps.toFixed(2)} Mbps`);
      }
    },
    [addActivity]
  );

  // WebSocket status change handler
  const handleWebSocketStatus = useCallback(
    (status: ConnectionStatus) => {
      if (status === 'connected') {
        addActivity('success', 'WebSocket stream connected', 'Real-time telemetry active');
      } else if (status === 'disconnected') {
        addActivity('warning', 'WebSocket disconnected', 'Attempting reconnection...');
      } else if (status === 'error') {
        addActivity('alert', 'WebSocket connection error');
      }
    },
    [addActivity]
  );

  const { status: wsStatus, reconnect: reconnectWs } = useWebSocket({
    onMessage: handleWebSocketMessage,
    onStatusChange: handleWebSocketStatus,
    enabled: true,
  });

  // Fetch initial state & REST endpoints
  const refreshAll = useCallback(async () => {
    try {
      setError(null);
      const [healthData, ifaceData, summaryData] = await Promise.all([
        api.getHealth(),
        api.getInterfaces(),
        api.getSummary(),
      ]);

      setHealth(healthData);
      setInterfaces(ifaceData.details || []);
      setActiveInterface(healthData.active_interface || ifaceData.active_interface || null);
      setIsMonitoring(healthData.monitoring === 'running');
      setSummary(summaryData);

      // Attempt to load current metric if not yet streamed
      try {
        const cur = await api.getCurrentMetrics();
        setMetrics((prev) => prev || cur);
      } catch {
        // May be initial startup
      }

      // Also refresh anomaly history & summary
      await refreshAnomalies();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to connect to backend server';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [refreshAnomalies]);

  useEffect(() => {
    refreshAll();
    const interval = setInterval(() => {
      // Periodic background polling for summary, health, and anomaly status
      api.getHealth().then(setHealth).catch(() => {});
      api.getSummary().then(setSummary).catch(() => {});
      api.getAnomalySummary().then(setAnomalySummary).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, [refreshAll]);

  // Switch interface handler
  const selectInterface = useCallback(
    async (interfaceName: string) => {
      if (interfaceName === activeInterface) return;
      setIsSwitching(true);
      setError(null);

      try {
        addActivity('info', `Switching target adapter to ${interfaceName}...`);
        await api.startMonitoring(interfaceName, 1.0);
        setActiveInterface(interfaceName);
        setRollingHistory([]); // Reset stale chart data
        setRollingAnomalyHistory([]); // Reset anomaly chart data for new adapter
        addActivity('success', `Active adapter switched to ${interfaceName}`);
        await refreshAll();
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : `Failed to switch to interface ${interfaceName}`;
        setError(msg);
        addActivity('alert', `Failed to switch adapter: ${msg}`);
      } finally {
        setIsSwitching(false);
      }
    },
    [activeInterface, addActivity, refreshAll]
  );

  // Toggle monitoring loop
  const toggleMonitoring = useCallback(
    async (start: boolean) => {
      setError(null);
      try {
        if (start) {
          await api.startMonitoring(activeInterface || undefined, 1.0);
          setIsMonitoring(true);
          addActivity('success', `Monitoring resumed on ${activeInterface || 'adapter'}`);
        } else {
          await api.stopMonitoring();
          setIsMonitoring(false);
          addActivity('warning', 'Monitoring stopped by user');
        }
        await refreshAll();
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to update monitoring state';
        setError(msg);
        addActivity('alert', `Monitoring toggle failed: ${msg}`);
      }
    },
    [activeInterface, addActivity, refreshAll]
  );

  // Calculate trends (throughput delta from previous reading)
  const downloadTrend = prevMetrics && metrics
    ? metrics.download_mbps - prevMetrics.download_mbps
    : 0;

  const uploadTrend = prevMetrics && metrics
    ? metrics.upload_mbps - prevMetrics.upload_mbps
    : 0;

  return {
    metrics,
    rollingHistory,
    interfaces,
    activeInterface,
    isMonitoring,
    health,
    summary,
    activities,
    isLoading,
    isSwitching,
    error,
    wsStatus,
    downloadTrend,
    uploadTrend,
    selectInterface,
    toggleMonitoring,
    refreshAll,
    reconnectWs,

    // Anomaly engine state & handlers
    anomalySummary,
    anomalyEvents,
    rollingAnomalyHistory,
    isAnomalyLoading,
    anomalyError,
    refreshAnomalies,
  };
}
