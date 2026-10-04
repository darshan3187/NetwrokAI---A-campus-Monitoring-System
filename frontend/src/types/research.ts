export interface ResearchDataset {
  id: string;
  name: string;
  version: string;
  description: string | null;
  file_size_bytes: number;
  total_flows: number;
  benign_flows: number;
  attack_flows: number;
  features: string[];
  schema_type?: 'native_netflow' | 'adapted_unsw_nb15' | string;
  is_adapted?: boolean;
  adaptation_notes?: string | null;
  is_sample: boolean;
  created_at: string;
}

export interface ResearchDatasetListResponse {
  datasets: ResearchDataset[];
  count: number;
}

export interface ResearchDatasetValidation {
  detected_features: string[];
  missing_features: string[];
  has_label_column: boolean;
  is_paper_compliant: boolean;
  expected_paper_features: string[];
  schema_type?: string;
  is_adapted?: boolean;
  adaptation_notes?: string | null;
  duration_unit?: string;
  validation_status?: string;
  invalid_ip_rows?: number;
  malformed_rows?: number;
}

export interface ResearchDatasetDetail {
  dataset: ResearchDataset;
  sample_rows: Record<string, any>[];
  validation: ResearchDatasetValidation;
}

export interface ResearchExperimentParams {
  nu?: number;
  q?: number;
  learning_rate?: number;
  power?: number;
  scaler_init_count?: number;
  warmup_count?: number;
  eval_count?: number | null;
  contamination?: number;
  n_estimators?: number;
}

export interface ResearchExperimentRunRequest {
  dataset_id: string;
  model_type: 'river_ocsvm' | 'isolation_forest';
  preset_name?: string;
  is_paper_preset?: boolean;
  parameters?: ResearchExperimentParams;
  random_seed?: number;
  num_runs?: number;
}

export interface ConfusionMatrix {
  tn: number;
  fp: number;
  fn: number;
  tp: number;
}

export interface ResearchExperiment {
  id: string;
  dataset_id: string;
  dataset_name: string;
  model_type: string;
  is_paper_preset: boolean;
  preset_name: string;
  parameters: Record<string, any>;
  random_seed: number;
  num_runs: number;
  status: string;
  scaler_init_count: number;
  warmup_count: number;
  eval_count: number;
  total_evaluation_time_sec: number;
  warmup_time_sec: number;
  avg_latency_per_flow_ms: number;
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  false_positive_rate: number;
  true_positive_rate: number;
  confusion_matrix: ConfusionMatrix;
  runs_summary?: any;
  error_message?: string | null;
  created_at: string;
  completed_at?: string | null;
}

export interface ResearchExperimentProgress {
  status: 'idle' | 'preparing' | 'scaler_init' | 'warmup' | 'evaluating' | 'completed' | 'cancelled' | 'failed';
  phase: string;
  current_step: string;
  warmup_progress: number;
  eval_progress: number;
  flows_processed: number;
  total_flows: number;
  flows_per_second: number;
  avg_latency_ms: number;
  current_metrics?: {
    accuracy?: number;
    tp?: number;
    tn?: number;
    fp?: number;
    fn?: number;
    avg_latency_ms?: number;
    f1_score?: number;
    recall?: number;
    precision?: number;
    fpr?: number;
  } | null;
  experiment_id?: string | null;
}

export interface PaperReferenceMetric {
  dataset_name: string;
  model: string;
  scaler: string;
  nu: number;
  q: number;
  learning_rate: number;
  accuracy: number;
  fpr: number;
  recall: number;
  f1_score: number;
  latency_ms_per_flow: number;
  citation: string;
  authors: string;
  paper_title: string;
  arxiv_id: string;
  provenance_note: string;
}

export interface ComparisonSummary {
  proposed_model: ResearchExperiment | null;
  baseline_model: ResearchExperiment | null;
  paper_reference: PaperReferenceMetric[];
}
