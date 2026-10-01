export interface ScenarioMeta {
  scenario_id: string;
  name: string;
  category: string;
  description: string;
  duration_seconds: number;
  expected_behavior: string;
}

export interface ScenarioListResponse {
  scenarios: ScenarioMeta[];
  count: number;
}

export interface SimulationRunRequest {
  scenario_id: string;
  seed?: number;
}

export interface ConfusionMatrix {
  true_positives: number;
  true_negatives: number;
  false_positives: number;
  false_negatives: number;
  total_samples: number;
}

export interface ValidationMetrics {
  precision: number | null;
  recall: number | null;
  f1_score: number | null;
  accuracy: number;
  detection_latency_seconds: number | null;
}

export interface SimulationTimelinePoint {
  step: number;
  timestamp: string;
  download_mbps: number;
  upload_mbps: number;
  packets_per_sec: number;
  ground_truth_anomaly: boolean;
  expected_severity: string;
  predicted_score: number;
  predicted_severity: string;
  is_detected: boolean;
  detection_method: string;
  explanation: string;
}

export interface SimulationResult {
  scenario_id: string;
  scenario_name: string;
  category: string;
  description: string;
  seed: number;
  duration_seconds: number;
  evaluated_at: string;
  confusion_matrix: ConfusionMatrix;
  metrics: ValidationMetrics;
  timeline: SimulationTimelinePoint[];
  expected_behavior: string;
  disclaimer: string;
}

export interface SimulationResetResponse {
  status: string;
  message: string;
}
