/**
 * TypeScript types for Phase 6: Topology Change Detection & Alerting Engine.
 * Aligns strictly with backend FastAPI schemas in app/schemas.py.
 */

export type AlertSeverity = 'critical' | 'warning' | 'info';
export type AlertStatus = 'open' | 'acknowledged' | 'resolved';

export type AlertEventType =
  | 'new_neighbor'
  | 'neighbor_stale'
  | 'neighbor_restored'
  | 'interface_changed'
  | 'protocol_changed'
  | 'discovery_failed'
  | 'discovery_unsupported';

export interface TopologyAlert {
  id: string;
  event_type: AlertEventType | string;
  severity: AlertSeverity | string;
  status: AlertStatus | string;
  source_device_id: string;
  source_device_name: string | null;
  remote_device_id: string | null;
  remote_device_name: string | null;
  remote_chassis_id: string | null;
  local_interface: string | null;
  remote_port_id: string | null;
  protocol: string | null;
  message: string;
  details: string | null;
  first_detected_at: string;
  last_seen_at: string;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  acknowledgement_note: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution_note: string | null;
  occurrence_count: number;
  is_mock: boolean;
  discovery_source: 'mock' | 'snmp' | string;
}

export interface TopologyAlertListResponse {
  total: number;
  open_count: number;
  acknowledged_count: number;
  resolved_count: number;
  alerts: TopologyAlert[];
  timestamp: string;
}

export interface TopologyAlertSummaryResponse {
  total_alerts: number;
  open_alerts: number;
  acknowledged_alerts: number;
  resolved_alerts: number;
  by_severity: Record<string, number>;
  by_event_type: Record<string, number>;
  mock_alerts_count: number;
  actual_alerts_count: number;
  timestamp: string;
}

export interface AlertFilterOptions {
  status: string; // 'all' | 'open' | 'acknowledged' | 'resolved'
  severity: string; // 'all' | 'critical' | 'warning' | 'info'
  eventType: string; // 'all' | AlertEventType
  deviceId: string;
  dataSource: string; // 'all' | 'actual' | 'mock'
  searchQuery: string;
}

export interface AlertAcknowledgePayload {
  acknowledged_by?: string;
  note?: string;
}

export interface AlertResolvePayload {
  resolved_by?: string;
  note?: string;
}
