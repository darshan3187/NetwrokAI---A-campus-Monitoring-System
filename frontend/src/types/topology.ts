/**
 * TypeScript types for Phase 5: Network Topology Visualization.
 * Aligns strictly with backend FastAPI schemas in app/schemas.py.
 */

import type { Device, DeviceType, ComputedStatus } from './device';

export type TopologyProtocol = 'lldp' | 'cdp';
export type TopologyDiscoverySource = 'snmp' | 'mock';
export type TopologyResolutionState = 'resolved' | 'unresolved';
export type TopologyLinkStatus = 'active' | 'stale' | 'down';
export type TopologyDiscoveryStatus = 'idle' | 'in_progress' | 'success' | 'failed' | 'unsupported' | 'empty';

export interface TopologyLink {
  id: number;
  source_device_id: string;
  local_interface: string;
  remote_device_id: string | null;
  remote_chassis_id: string;
  remote_chassis_id_subtype: string | null;
  remote_port_id: string;
  remote_port_id_subtype: string | null;
  remote_port_desc: string | null;
  remote_system_name: string | null;
  remote_system_desc: string | null;
  protocol: TopologyProtocol;
  discovered_at: string;
  last_seen_at: string;
  discovery_source: TopologyDiscoverySource;
  resolution_state: TopologyResolutionState;
  link_status: TopologyLinkStatus;
  is_mock: boolean;
  is_stale: boolean;
}

export interface TopologyLinkListResponse {
  total_links: number;
  resolved_links: number;
  unresolved_links: number;
  stale_links: number;
  links: TopologyLink[];
  timestamp: string;
}

export interface DeviceNeighborsResponse {
  device_id: string;
  device_name: string | null;
  total_neighbors: number;
  neighbors: TopologyLink[];
  timestamp: string;
}

export interface TopologyDiscoveryTriggerResponse {
  device_id: string;
  success: boolean;
  status: TopologyDiscoveryStatus;
  protocol_used: string;
  neighbors_found: number;
  neighbors_resolved: number;
  message: string;
  duration_ms: number;
  timestamp: string;
}

export interface DeviceDiscoveryStatusResponse {
  device_id: string;
  status: TopologyDiscoveryStatus;
  protocol: string;
  lldp_supported: boolean;
  cdp_supported: boolean;
  discovered_neighbors_count: number;
  resolved_neighbors_count: number;
  last_discovery_at: string | null;
  last_discovery_duration_ms: number | null;
  last_error: string | null;
  timestamp: string;
}

export interface UnresolvedNeighborsResponse {
  total_unresolved: number;
  unresolved_neighbors: TopologyLink[];
  timestamp: string;
}

export interface TopologyFilterOptions {
  building: string;
  deviceType: string;
  protocol: string;
  linkStatus: string;
  resolutionState: string;
  dataSource: string; // 'all' | 'actual' | 'mock'
  searchQuery: string;
}

/**
 * Graph node model for interactive SVG rendering.
 */
export interface TopologyNode {
  id: string;
  label: string;
  ipAddress: string;
  deviceType: DeviceType | 'unresolved';
  building: string;
  floor: string;
  department: string;
  isUnresolved: boolean;
  isMock: boolean;
  computedStatus: ComputedStatus;
  deviceRecord?: Device;
  remoteChassisId?: string;
  remoteSystemDesc?: string;
  x: number;
  y: number;
  vx?: number;
  vy?: number;
  degree: number;
}

/**
 * Graph edge model connecting two topology nodes.
 */
export interface TopologyEdge {
  id: string;
  source: string; // source node id
  target: string; // target node id
  sourceInterface: string;
  targetInterface: string;
  protocol: TopologyProtocol | 'mixed';
  linkStatus: TopologyLinkStatus;
  isStale: boolean;
  isMock: boolean;
  resolutionState: TopologyResolutionState;
  lastSeenAt: string;
  discoveredAt: string;
  linkRecord: TopologyLink;
  isBidirectional?: boolean;
  reciprocalLinkRecord?: TopologyLink | null;
  conflictingProtocols?: boolean;
  sourceDeviceName?: string;
  targetDeviceName?: string;
}

export interface TopologyGraphData {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}
