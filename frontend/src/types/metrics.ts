/**
 * TypeScript definitions for NetworkAI telemetry, API payloads, and WebSocket events.
 */

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error';
  database: 'connected' | 'disconnected' | 'error';
  monitoring: 'running' | 'stopped';
  active_interface: string | null;
  timestamp: string;
}

export interface InterfaceDetail {
  name: string;
  bytes_sent: number;
  bytes_recv: number;
  packets_sent: number;
  packets_recv: number;
  is_up: boolean;
  speed_mbps: number | null;
}

export interface InterfaceListResponse {
  interfaces: string[];
  details: InterfaceDetail[];
  active_interface: string | null;
  count: number;
}

export interface AnomalyEvaluation {
  score: number;
  severity: 'Normal' | 'Unusual Traffic' | 'High Anomaly' | string;
  is_anomaly: boolean;
  method: string;
  explanation: string;
}

export interface RollingAnomalyPoint {
  timestamp: string;
  timeLabel: string;
  score: number;
  severity: string;
  isAnomaly: boolean;
  download_mbps: number;
  upload_mbps: number;
}


export interface NetworkMetric {
  id?: number | null;
  timestamp: string;
  interface: string;
  upload_mbps: number;
  download_mbps: number;
  packets_sent_per_sec: number;
  packets_received_per_sec: number;
  cumulative_sent_mb: number;
  cumulative_received_mb: number;
  session_transferred_mb: number;
  is_initial_sample?: boolean;
  anomaly?: AnomalyEvaluation | null;
}


export interface HistoricalMetricsResponse {
  interface: string | null;
  total_returned: number;
  limit: number;
  metrics: NetworkMetric[];
}

export interface MonitoringSummary {
  interface: string | null;
  is_monitoring: boolean;
  current_upload_mbps: number;
  current_download_mbps: number;
  peak_upload_mbps: number;
  peak_download_mbps: number;
  session_transferred_mb: number;
  cumulative_sent_mb: number;
  cumulative_received_mb: number;
  total_stored_samples: number;
  session_samples_collected: number;
  monitoring_duration_seconds: number;
}

export interface MonitoringControlResponse {
  status: string;
  message: string;
  interface?: string | null;
  interval_seconds?: number;
}

export type WebSocketMessage =
  | {
      type: 'initial_state' | 'metric_update';
      data: NetworkMetric;
    }
  | {
      type: 'anomaly_event';
      data: AnomalyEvent;
    }
  | {
      type: 'device_telemetry';
      device_id: string;
      data: Record<string, any>;
    };


export interface ActivityEvent {
  id: string;
  timestamp: string;
  type: 'info' | 'success' | 'warning' | 'alert';
  message: string;
  details?: string;
}

export interface AnomalyEvent {
  id: number;
  timestamp: string;
  interface: string;
  anomaly_score: number;
  severity: string;
  detection_method: string;
  metrics_snapshot: Record<string, any>;
  explanation: string;
}

export interface AnomalyListResponse {
  total_returned: number;
  limit: number;
  events: AnomalyEvent[];
}

export interface AnomalySummaryResponse {
  total_anomalies: number;
  unusual_traffic_count: number;
  high_anomaly_count: number;
  latest_anomaly: AnomalyEvent | null;
  model_status: string;
  is_trained: boolean;
  samples_observed: number;
  active_interface: string | null;
}

