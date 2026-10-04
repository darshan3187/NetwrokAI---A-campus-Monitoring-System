/**
 * API client for Research Experiment and Dataset endpoints.
 */

import { API_BASE_URL } from './api';
import type {
  ComparisonSummary,
  PaperReferenceMetric,
  ResearchDataset,
  ResearchDatasetDetail,
  ResearchDatasetListResponse,
  ResearchExperiment,
  ResearchExperimentProgress,
  ResearchExperimentRunRequest,
} from '../types/research';

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
    const isFormData = options?.body instanceof FormData;
    const headers: Record<string, string> = {
      ...(options?.headers as Record<string, string> || {}),
    };
    if (!isFormData) {
      headers['Content-Type'] = 'application/json';
    }

    const res = await fetch(url, {
      ...options,
      headers,
    });

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const body = await res.json();
        if (body?.detail) {
          errorDetail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
        }
      } catch {
        // Fallback to HTTP error
      }
      throw new ApiError(errorDetail, res.status);
    }

    return (await res.json()) as T;
  } catch (err: unknown) {
    if (err instanceof ApiError) {
      throw err;
    }
    const message = err instanceof Error ? err.message : 'Unknown network failure';
    throw new ApiError(`Network request failed: ${message}`, 0);
  }
}

export const researchApi = {
  // Datasets
  async getDatasets(): Promise<ResearchDatasetListResponse> {
    return request<ResearchDatasetListResponse>('/api/v1/research/datasets');
  },

  async uploadDataset(formData: FormData): Promise<ResearchDataset> {
    return request<ResearchDataset>('/api/v1/research/datasets/upload', {
      method: 'POST',
      body: formData,
    });
  },

  async loadSampleDataset(): Promise<ResearchDataset> {
    return request<ResearchDataset>('/api/v1/research/datasets/sample', {
      method: 'POST',
    });
  },

  async getDatasetDetail(datasetId: string): Promise<ResearchDatasetDetail> {
    return request<ResearchDatasetDetail>(`/api/v1/research/datasets/${encodeURIComponent(datasetId)}`);
  },

  async deleteDataset(datasetId: string): Promise<{ status: string; message: string }> {
    return request<{ status: string; message: string }>(
      `/api/v1/research/datasets/${encodeURIComponent(datasetId)}`,
      { method: 'DELETE' }
    );
  },

  // Experiments
  async getExperiments(): Promise<{ experiments: ResearchExperiment[]; count: number }> {
    return request<{ experiments: ResearchExperiment[]; count: number }>('/api/v1/research/experiments');
  },

  async runExperiment(req: ResearchExperimentRunRequest): Promise<ResearchExperimentProgress> {
    return request<ResearchExperimentProgress>('/api/v1/research/experiments/run', {
      method: 'POST',
      body: JSON.stringify(req),
    });
  },

  async getActiveExperimentProgress(): Promise<ResearchExperimentProgress> {
    return request<ResearchExperimentProgress>('/api/v1/research/experiments/active');
  },

  async cancelActiveExperiment(): Promise<{ status: string; message: string }> {
    return request<{ status: string; message: string }>('/api/v1/research/experiments/cancel', {
      method: 'POST',
    });
  },

  async cancelExperiment(): Promise<{ status: string; message: string }> {
    return this.cancelActiveExperiment();
  },

  async getExperimentDetail(experimentId: string): Promise<ResearchExperiment> {
    return request<ResearchExperiment>(`/api/v1/research/experiments/${encodeURIComponent(experimentId)}`);
  },

  async deleteExperiment(experimentId: string): Promise<{ status: string; message: string }> {
    return request<{ status: string; message: string }>(
      `/api/v1/research/experiments/${encodeURIComponent(experimentId)}`,
      { method: 'DELETE' }
    );
  },

  // Reference & Comparisons
  async getReferenceBenchmarks(): Promise<PaperReferenceMetric[]> {
    return request<PaperReferenceMetric[]>('/api/v1/research/reference');
  },

  async getComparisonSummary(): Promise<ComparisonSummary> {
    return request<ComparisonSummary>('/api/v1/research/compare');
  },
};
