/**
 * API client for Topology Change Detection & Alerting endpoints (Phase 6).
 * Interacts with backend REST APIs under /api/v1/alerts/*.
 */

import { API_BASE_URL } from './api';
import type {
  TopologyAlert,
  TopologyAlertListResponse,
  TopologyAlertSummaryResponse,
  AlertAcknowledgePayload,
  AlertResolvePayload,
} from '../types/alert';

class AlertApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'AlertApiError';
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
        // default error
      }
      throw new AlertApiError(errorDetail, res.status);
    }

    return (await res.json()) as T;
  } catch (err: unknown) {
    if (err instanceof AlertApiError) {
      throw err;
    }
    const message = err instanceof Error ? err.message : 'Network request failed';
    throw new AlertApiError(message, 0);
  }
}

export interface GetAlertsParams {
  status?: string;
  severity?: string;
  event_type?: string;
  device_id?: string;
  is_mock?: boolean;
  start_time?: string;
  end_time?: string;
  limit?: number;
  offset?: number;
}

export async function fetchAlerts(params?: GetAlertsParams): Promise<TopologyAlertListResponse> {
  const query = new URLSearchParams();
  if (params?.status && params.status !== 'all') query.set('status', params.status);
  if (params?.severity && params.severity !== 'all') query.set('severity', params.severity);
  if (params?.event_type && params.event_type !== 'all') query.set('event_type', params.event_type);
  if (params?.device_id) query.set('device_id', params.device_id);
  if (params?.is_mock !== undefined) query.set('is_mock', String(params.is_mock));
  if (params?.start_time) query.set('start_time', params.start_time);
  if (params?.end_time) query.set('end_time', params.end_time);
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.offset !== undefined) query.set('offset', String(params.offset));

  const qs = query.toString();
  return request<TopologyAlertListResponse>(`/api/v1/alerts${qs ? `?${qs}` : ''}`);
}

export async function fetchAlertById(alertId: string): Promise<TopologyAlert> {
  return request<TopologyAlert>(`/api/v1/alerts/${encodeURIComponent(alertId)}`);
}

export async function fetchAlertSummary(params?: {
  device_id?: string;
  is_mock?: boolean;
}): Promise<TopologyAlertSummaryResponse> {
  const query = new URLSearchParams();
  if (params?.device_id) query.set('device_id', params.device_id);
  if (params?.is_mock !== undefined) query.set('is_mock', String(params.is_mock));

  const qs = query.toString();
  return request<TopologyAlertSummaryResponse>(`/api/v1/alerts/summary${qs ? `?${qs}` : ''}`);
}

export async function acknowledgeAlert(
  alertId: string,
  payload?: AlertAcknowledgePayload
): Promise<TopologyAlert> {
  return request<TopologyAlert>(`/api/v1/alerts/${encodeURIComponent(alertId)}/acknowledge`, {
    method: 'POST',
    body: JSON.stringify(payload || {}),
  });
}

export async function resolveAlert(
  alertId: string,
  payload?: AlertResolvePayload
): Promise<TopologyAlert> {
  return request<TopologyAlert>(`/api/v1/alerts/${encodeURIComponent(alertId)}/resolve`, {
    method: 'POST',
    body: JSON.stringify(payload || {}),
  });
}
