/**
 * Centralized API client for communicating with the FastAPI backend.
 */

import type {
  AnomalyEvent,
  AnomalyListResponse,
  AnomalySummaryResponse,
  HealthResponse,
  HistoricalMetricsResponse,
  InterfaceListResponse,
  MonitoringControlResponse,
  MonitoringSummary,
  NetworkMetric,
} from '../types/metrics';


export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export const WS_URL =
  import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000/ws/metrics';

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
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
      throw new ApiError(errorDetail, res.status);
    }

    return (await res.json()) as T;
  } catch (err: unknown) {
    if (err instanceof ApiError) {
      throw err;
    }
    const message = err instanceof Error ? err.message : 'Network request failed';
    throw new ApiError(message, 0);
  }
}

export const api = {
  getHealth: () => request<HealthResponse>('/api/v1/health'),

  getInterfaces: () => request<InterfaceListResponse>('/api/v1/interfaces'),

  getCurrentMetrics: () => request<NetworkMetric>('/api/v1/metrics/current'),

  getHistory: (params?: {
    interface?: string;
    limit?: number;
    start_time?: string;
    end_time?: string;
  }) => {
    const query = new URLSearchParams();
    if (params?.interface) query.append('interface', params.interface);
    if (params?.limit) query.append('limit', String(params.limit));
    if (params?.start_time) query.append('start_time', params.start_time);
    if (params?.end_time) query.append('end_time', params.end_time);

    const queryString = query.toString();
    const endpoint = `/api/v1/metrics/history${queryString ? `?${queryString}` : ''}`;
    return request<HistoricalMetricsResponse>(endpoint);
  },

  getSummary: () => request<MonitoringSummary>('/api/v1/summary'),

  startMonitoring: (interfaceName?: string, intervalSeconds: number = 1.0) =>
    request<MonitoringControlResponse>('/api/v1/monitoring/start', {
      method: 'POST',
      body: JSON.stringify({
        interface: interfaceName || null,
        interval_seconds: intervalSeconds,
      }),
    }),

  stopMonitoring: () =>
    request<MonitoringControlResponse>('/api/v1/monitoring/stop', {
      method: 'POST',
    }),

  getAnomalies: (params?: {
    limit?: number;
    interface?: string;
    severity?: string;
    start_time?: string;
    end_time?: string;
  }) => {
    const query = new URLSearchParams();
    if (params?.limit) query.append('limit', String(params.limit));
    if (params?.interface) query.append('interface', params.interface);
    if (params?.severity) query.append('severity', params.severity);
    if (params?.start_time) query.append('start_time', params.start_time);
    if (params?.end_time) query.append('end_time', params.end_time);

    const qs = query.toString();
    return request<AnomalyListResponse>(`/api/v1/anomalies${qs ? `?${qs}` : ''}`);
  },

  getLatestAnomaly: (interfaceName?: string) => {
    const query = new URLSearchParams();
    if (interfaceName) query.append('interface', interfaceName);
    const qs = query.toString();
    return request<AnomalyEvent | null>(`/api/v1/anomalies/latest${qs ? `?${qs}` : ''}`);
  },

  getAnomalySummary: () => request<AnomalySummaryResponse>('/api/v1/anomalies/summary'),
};

