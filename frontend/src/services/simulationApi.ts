/**
 * API client methods for the Controlled Simulation Lab.
 */

import { API_BASE_URL } from './api';
import type {
  ScenarioListResponse,
  SimulationResult,
  SimulationResetResponse,
} from '../types/simulation';

async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    let errorDetail = `Request failed with status ${res.status}`;
    try {
      const errObj = await res.json();
      if (errObj && errObj.detail) {
        errorDetail = errObj.detail;
      }
    } catch {
      // Fallback to text
      const errText = await res.text();
      if (errText) errorDetail = errText;
    }
    throw new Error(errorDetail);
  }

  return (await res.json()) as T;
}

export const simulationApi = {
  /**
   * Fetch all registered controlled simulation scenario definitions.
   */
  async getScenarios(): Promise<ScenarioListResponse> {
    return fetchJson<ScenarioListResponse>('/api/v1/simulation/scenarios');
  },

  /**
   * Execute a controlled simulation run against the isolated AnomalyDetector instance.
   */
  async runSimulation(scenarioId: string, seed: number = 42): Promise<SimulationResult> {
    return fetchJson<SimulationResult>('/api/v1/simulation/run', {
      method: 'POST',
      body: JSON.stringify({
        scenario_id: scenarioId,
        seed,
      }),
    });
  },

  /**
   * Retrieve the most recently completed simulation validation result.
   */
  async getLatestResults(): Promise<SimulationResult | null> {
    try {
      return await fetchJson<SimulationResult>('/api/v1/simulation/results');
    } catch (err: unknown) {
      if (err instanceof Error && err.message.includes('404')) {
        return null;
      }
      return null;
    }
  },

  /**
   * Clear cached simulation validation results.
   */
  async resetSimulation(): Promise<SimulationResetResponse> {
    return fetchJson<SimulationResetResponse>('/api/v1/simulation/reset', {
      method: 'POST',
    });
  },
};
