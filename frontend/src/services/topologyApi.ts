/**
 * API client for Network Topology Discovery endpoints.
 * Integrates with Phase 4 backend REST APIs under /api/v1/topology/*.
 */

import { API_BASE_URL } from './api';
import type {
  TopologyLinkListResponse,
  UnresolvedNeighborsResponse,
  TopologyDiscoveryTriggerResponse,
  DeviceNeighborsResponse,
  DeviceDiscoveryStatusResponse,
} from '../types/topology';

class TopologyApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'TopologyApiError';
    this.status = status;
  }
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options?.headers || {}),
      },
    });

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const body = await res.json();
        if (body?.detail) {
          errorDetail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
        }
      } catch {
        // use default errorDetail
      }
      throw new TopologyApiError(errorDetail, res.status);
    }

    return (await res.json()) as T;
  } catch (err: unknown) {
    if (err instanceof TopologyApiError) {
      throw err;
    }
    const message = err instanceof Error ? err.message : 'Network request failed';
    throw new TopologyApiError(message, 0);
  }
}

export interface GetLinksParams {
  source_device_id?: string;
  protocol?: string;
  link_status?: string;
  resolution_state?: string;
  limit?: number;
}

export const topologyApi = {
  /**
   * Fetch discovered topology links with optional filters.
   */
  getLinks: (params?: GetLinksParams): Promise<TopologyLinkListResponse> => {
    const query = new URLSearchParams();
    if (params?.source_device_id) query.append('source_device_id', params.source_device_id);
    if (params?.protocol && params.protocol !== 'all') query.append('protocol', params.protocol);
    if (params?.link_status && params.link_status !== 'all') query.append('link_status', params.link_status);
    if (params?.resolution_state && params.resolution_state !== 'all') query.append('resolution_state', params.resolution_state);
    if (params?.limit) query.append('limit', String(params.limit));

    const qs = query.toString();
    return request<TopologyLinkListResponse>(`/api/v1/topology/links${qs ? `?${qs}` : ''}`);
  },

  /**
   * Fetch all discovered neighbors that remain unmapped to registered devices.
   */
  getUnresolvedNeighbors: (): Promise<UnresolvedNeighborsResponse> => {
    return request<UnresolvedNeighborsResponse>('/api/v1/topology/unresolved');
  },

  /**
   * Trigger read-only LLDP/CDP discovery against a registered device.
   */
  triggerDiscovery: (deviceId: string): Promise<TopologyDiscoveryTriggerResponse> => {
    return request<TopologyDiscoveryTriggerResponse>(
      `/api/v1/topology/devices/${encodeURIComponent(deviceId)}/discover`,
      { method: 'POST' }
    );
  },

  /**
   * Fetch all links where the specified device is either source or destination.
   */
  getDeviceNeighbors: (deviceId: string): Promise<DeviceNeighborsResponse> => {
    return request<DeviceNeighborsResponse>(
      `/api/v1/topology/devices/${encodeURIComponent(deviceId)}/neighbors`
    );
  },

  /**
   * Fetch current discovery execution status and protocol capabilities for a device.
   */
  getDiscoveryStatus: (deviceId: string): Promise<DeviceDiscoveryStatusResponse> => {
    return request<DeviceDiscoveryStatusResponse>(
      `/api/v1/topology/devices/${encodeURIComponent(deviceId)}/status`
    );
  },
};
