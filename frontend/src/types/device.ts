/**
 * TypeScript definitions for Campus Multi-Device Registry (Phase 1).
 */

export type DeviceType = 'router' | 'switch' | 'access_point' | 'server' | 'host' | 'other';
export type CollectionMethod = 'local_psutil' | 'snmp' | 'netflow' | 'api' | 'manual' | 'mock';
export type MonitoringStatus = 'active' | 'inactive' | 'maintenance';
export type ConnectionStatus = 'online' | 'offline' | 'unknown';
export type ReachabilityState = 'configured' | 'reachable' | 'unreachable' | 'unsupported';
export type ComputedStatus = 'online' | 'unreachable' | 'stale' | 'maintenance' | 'unknown' | 'unsupported';

export interface Device {
  id: string;
  name: string;
  ip_address: string;
  device_type: DeviceType;
  building: string;
  department: string;
  floor: string;
  location_description: string | null;
  vendor_model: string | null;
  collection_method: CollectionMethod;
  monitoring_status: MonitoringStatus;
  connection_status: ConnectionStatus;
  // Remote polling runtime fields (Phase 2)
  last_poll_at?: string | null;
  last_poll_status?: string | null;
  last_poll_error?: string | null;
  reachability?: ReachabilityState;
  polling_enabled?: boolean;
  polling_interval_seconds?: number;
  // Reliable status fields (Phase 3)
  computed_status?: ComputedStatus;
  is_stale?: boolean;
  created_at: string;
  updated_at: string;
}

export interface DeviceCreatePayload {
  id?: string;
  name: string;
  ip_address: string;
  device_type: DeviceType;
  building: string;
  department: string;
  floor: string;
  location_description?: string;
  vendor_model?: string;
  collection_method?: CollectionMethod;
  monitoring_status?: MonitoringStatus;
  connection_status?: ConnectionStatus;
}

export interface DeviceUpdatePayload {
  name?: string;
  ip_address?: string;
  device_type?: DeviceType;
  building?: string;
  department?: string;
  floor?: string;
  location_description?: string;
  vendor_model?: string;
  collection_method?: CollectionMethod;
  monitoring_status?: MonitoringStatus;
  connection_status?: ConnectionStatus;
}

export interface DeviceListResponse {
  total: number;
  devices: Device[];
}

export interface DeviceSummaryResponse {
  total_devices: number;
  online_count: number;
  offline_count: number;
  unknown_count: number;
  active_count: number;
  inactive_count: number;
  maintenance_count: number;
  by_type: Record<string, number>;
  by_department: Record<string, number>;
  by_building: Record<string, number>;
  by_status: Record<string, number>;
  by_collection_method: Record<string, number>;
}

export interface DeviceFilterParams {
  device_type?: string;
  department?: string;
  building?: string;
  floor?: string;
  monitoring_status?: string;
  connection_status?: string;
  search?: string;
}

export interface DeviceTelemetry {
  id?: number;
  device_id: string;
  interface_index?: number | null;
  interface_name: string;
  timestamp: string;
  bytes_sent: number;
  bytes_recv: number;
  packets_sent: number;
  packets_recv: number;
  upload_mbps: number;
  download_mbps: number;
  packets_sent_per_sec: number;
  packets_recv_per_sec: number;
  errors_in: number;
  errors_out: number;
  discards_in: number;
  discards_out: number;
  collection_method: string;
  data_validity: 'valid' | 'initial_sample' | 'counter_reset' | 'mock' | 'error';
  oper_status: string;
}

export interface DeviceTelemetryHistoryResponse {
  device_id: string;
  interface_name?: string | null;
  total_returned: number;
  limit: number;
  telemetry: DeviceTelemetry[];
}

export interface DeviceHealthResponse {
  device_id: string;
  name: string;
  ip_address: string;
  reachability: ReachabilityState;
  polling_enabled: boolean;
  polling_interval_seconds: number;
  last_poll_at: string | null;
  last_poll_status: string | null;
  last_poll_error: string | null;
  timestamp: string;
}

export interface CampusTelemetrySummary {
  total_devices: number;
  polling_enabled_count: number;
  reachable_count: number;
  unreachable_count: number;
  configured_count: number;
  unsupported_count: number;
  // Phase 3 refined status counts
  online_count: number;
  stale_count: number;
  unknown_count: number;
  maintenance_count: number;
  last_successful_poll: string | null;
  total_polling_errors: number;
  total_telemetry_samples: number;
  latest_campus_upload_mbps: number;
  latest_campus_download_mbps: number;
  total_errors: number;
  total_discards: number;
  timestamp: string;
}

export interface CampusDeviceNode {
  id: string;
  name: string;
  ip_address: string;
  device_type: DeviceType;
  vendor_model: string | null;
  collection_method: CollectionMethod;
  monitoring_status: MonitoringStatus;
  connection_status: ConnectionStatus;
  reachability: ReachabilityState;
  computed_status: ComputedStatus;
  is_stale: boolean;
  polling_enabled: boolean;
  polling_interval_seconds: number;
  last_poll_at: string | null;
  latest_upload_mbps: number;
  latest_download_mbps: number;
  latest_oper_status: string;
}

export interface CampusDepartmentNode {
  department: string;
  total_devices: number;
  online_devices: number;
  unreachable_devices: number;
  devices: CampusDeviceNode[];
}

export interface CampusFloorNode {
  floor: string;
  total_devices: number;
  online_devices: number;
  departments: CampusDepartmentNode[];
}

export interface CampusBuildingNode {
  building: string;
  total_devices: number;
  online_devices: number;
  unreachable_devices: number;
  floors: CampusFloorNode[];
}

export interface CampusHierarchyResponse {
  campus_name: string;
  total_devices: number;
  total_buildings: number;
  total_departments: number;
  buildings: CampusBuildingNode[];
  timestamp: string;
}

export interface CampusTimelinePoint {
  timestamp: string;
  upload_mbps: number;
  download_mbps: number;
  sample_count: number;
  reporting_devices: number;
}

export interface CampusTimelineResponse {
  time_range: string;
  total_samples: number;
  timeline: CampusTimelinePoint[];
  timestamp: string;
}

export interface DeviceComparisonItem {
  device_id: string;
  name: string;
  ip_address: string;
  device_type: DeviceType;
  building: string;
  floor: string;
  department: string;
  collection_method: CollectionMethod;
  computed_status: ComputedStatus;
  reachability: ReachabilityState;
  polling_enabled: boolean;
  upload_mbps: number;
  download_mbps: number;
  packets_sent_per_sec: number;
  packets_recv_per_sec: number;
  errors: number;
  discards: number;
  last_poll_at: string | null;
}

export interface DeviceComparisonResponse {
  total_devices: number;
  devices: DeviceComparisonItem[];
  timestamp: string;
}
