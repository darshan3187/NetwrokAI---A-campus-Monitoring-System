/**
 * API client for Campus Multi-Device Registry endpoints.
 */

import { API_BASE_URL } from './api';
import type {
  CampusHierarchyResponse,
  CampusTelemetrySummary,
  CampusTimelineResponse,
  Device,
  DeviceComparisonResponse,
  DeviceCreatePayload,
  DeviceFilterParams,
  DeviceHealthResponse,
  DeviceListResponse,
  DeviceSummaryResponse,
  DeviceTelemetry,
  DeviceTelemetryHistoryResponse,
  DeviceUpdatePayload,
} from '../types/device';

class DeviceApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'DeviceApiError';
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
      throw new DeviceApiError(errorDetail, res.status);
    }

    return (await res.json()) as T;
  } catch (err: unknown) {
    if (err instanceof DeviceApiError) {
      throw err;
    }
    const message = err instanceof Error ? err.message : 'Network request failed';
    throw new DeviceApiError(message, 0);
  }
}

export const deviceApi = {
  getDevices: (params?: DeviceFilterParams) => {
    const query = new URLSearchParams();
    if (params?.device_type) query.append('device_type', params.device_type);
    if (params?.department) query.append('department', params.department);
    if (params?.building) query.append('building', params.building);
    if (params?.floor) query.append('floor', params.floor);
    if (params?.monitoring_status) query.append('monitoring_status', params.monitoring_status);
    if (params?.connection_status) query.append('connection_status', params.connection_status);
    if (params?.search) query.append('search', params.search);

    const qs = query.toString();
    return request<DeviceListResponse>(`/api/v1/devices${qs ? `?${qs}` : ''}`);
  },

  getDevice: (id: string) => request<Device>(`/api/v1/devices/${encodeURIComponent(id)}`),

  getSummary: () => request<DeviceSummaryResponse>('/api/v1/devices/summary'),

  createDevice: (payload: DeviceCreatePayload) =>
    request<Device>('/api/v1/devices', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateDevice: (id: string, payload: DeviceUpdatePayload) =>
    request<Device>(`/api/v1/devices/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  deleteDevice: (id: string) =>
    request<{ status: string; message: string; device_id: string }>(
      `/api/v1/devices/${encodeURIComponent(id)}`,
      { method: 'DELETE' }
    ),

  // Phase 2 Remote Telemetry & Polling APIs
  getLatestTelemetry: (id: string, iface?: string) => {
    const qs = iface ? `?interface=${encodeURIComponent(iface)}` : '';
    return request<DeviceTelemetry>(`/api/v1/devices/${encodeURIComponent(id)}/telemetry/latest${qs}`);
  },

  getTelemetryHistory: (id: string, limit: number = 50, iface?: string) => {
    const params = new URLSearchParams();
    params.append('limit', limit.toString());
    if (iface) params.append('interface', iface);
    return request<DeviceTelemetryHistoryResponse>(
      `/api/v1/devices/${encodeURIComponent(id)}/telemetry/history?${params.toString()}`
    );
  },

  getDeviceHealth: (id: string) =>
    request<DeviceHealthResponse>(`/api/v1/devices/${encodeURIComponent(id)}/health`),

  startMonitoring: (id: string, intervalSeconds?: number) =>
    request<Device>(`/api/v1/devices/${encodeURIComponent(id)}/monitoring/start`, {
      method: 'POST',
      body: intervalSeconds ? JSON.stringify({ interval_seconds: intervalSeconds }) : undefined,
    }),

  stopMonitoring: (id: string) =>
    request<Device>(`/api/v1/devices/${encodeURIComponent(id)}/monitoring/stop`, {
      method: 'POST',
    }),

  getCampusTelemetrySummary: () =>
    request<CampusTelemetrySummary>('/api/v1/devices/telemetry/summary'),

  // Phase 3 Campus Overview & Multi-Device Integration APIs
  getHierarchy: () =>
    request<CampusHierarchyResponse>('/api/v1/devices/hierarchy'),

  getTimeline: (hours: number = 1) =>
    request<CampusTimelineResponse>(`/api/v1/devices/telemetry/timeline?hours=${hours}`),

  getComparison: () =>
    request<DeviceComparisonResponse>('/api/v1/devices/telemetry/comparison'),
};
