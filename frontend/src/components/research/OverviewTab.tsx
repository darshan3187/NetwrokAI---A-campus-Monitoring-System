import React, { useEffect, useState } from 'react';
import {
  ArrowRight,
  Cpu,
  Database,
  BarChart3,
  Play,
} from 'lucide-react';
import { researchApi } from '../../services/researchApi';
import type {
  ResearchDataset,
  ResearchExperiment,
} from '../../types/research';
import { Spinner } from '../common/Spinner';

interface OverviewTabProps {
  onNavigate: (tab: 'overview' | 'dataset' | 'experiment' | 'results' | 'live' | 'research') => void;
}

export const OverviewTab: React.FC<OverviewTabProps> = ({ onNavigate }) => {
  const [loading, setLoading] = useState(true);
  const [datasets, setDatasets] = useState<ResearchDataset[]>([]);
  const [latestExperiment, setLatestExperiment] = useState<ResearchExperiment | null>(null);

  useEffect(() => {
    let mounted = true;
    async function loadData() {
      try {
        const [dsRes, expRes] = await Promise.all([
          researchApi.getDatasets().catch(() => ({ datasets: [], count: 0 })),
          researchApi.getExperiments().catch(() => ({ experiments: [], count: 0 })),
        ]);
        if (mounted) {
          setDatasets(dsRes.datasets);
          setLatestExperiment(expRes.experiments.length > 0 ? expRes.experiments[0] : null);
        }
      } finally {
        if (mounted) setLoading(false);
      }
    }
    loadData();
    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[360px] gap-3">
        <Spinner size="lg" />
        <span className="text-xs text-text-muted font-mono">Loading system status...</span>
      </div>
    );
  }

  const activeDataset = datasets.find((d) => d.is_sample) || datasets[0];

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* 1. Project Name and Short Description */}
      <div className="p-6 rounded-[8px] bg-card-surface border border-border-subtle">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-5">
          <div className="space-y-2 max-w-2xl">
            <h1 className="text-xl md:text-2xl font-bold text-text-primary tracking-tight">
              NetworkAI
            </h1>
            <p className="text-sm text-text-secondary leading-relaxed">
              An online machine learning system for detecting network traffic anomalies. It uses
              streaming unsupervised learning (River Online One-Class SVM) to classify network flows
              and compares performance against an Isolation Forest baseline.
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <button
              onClick={() => onNavigate('experiment')}
              className="px-4 py-2 rounded-[6px] bg-[#0070f3] hover:bg-[#0070f3]/90 text-white text-xs font-semibold flex items-center gap-2 cursor-pointer transition-colors shadow-xs"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Start Experiment</span>
            </button>
          </div>
        </div>
      </div>

      {/* 2. Simple Workflow: Dataset -> Experiment -> Results */}
      <div className="p-5 rounded-[8px] bg-card-surface border border-border-subtle space-y-3">
        <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider font-mono">
          Project Workflow
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          {/* Step 1: Dataset */}
          <div
            onClick={() => onNavigate('dataset')}
            className="p-4 rounded-[6px] bg-elevated-surface/50 border border-border-subtle hover:border-border-hover transition-colors cursor-pointer group space-y-2"
          >
            <div className="flex items-center justify-between">
              <span className="font-semibold text-text-primary flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-[#0070f3]/10 text-[#0070f3] flex items-center justify-center text-[11px] font-mono font-bold">
                  1
                </span>
                <span>Dataset</span>
              </span>
              <ArrowRight className="w-3.5 h-3.5 text-text-muted group-hover:text-text-primary transition-colors" />
            </div>
            <p className="text-text-secondary text-[11px] leading-relaxed">
              Load benchmark NetFlow records or upload a custom CSV containing the 8 standard traffic features.
            </p>
          </div>

          {/* Step 2: Experiment */}
          <div
            onClick={() => onNavigate('experiment')}
            className="p-4 rounded-[6px] bg-elevated-surface/50 border border-border-subtle hover:border-border-hover transition-colors cursor-pointer group space-y-2"
          >
            <div className="flex items-center justify-between">
              <span className="font-semibold text-text-primary flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-[#0070f3]/10 text-[#0070f3] flex items-center justify-center text-[11px] font-mono font-bold">
                  2
                </span>
                <span>Experiment</span>
              </span>
              <ArrowRight className="w-3.5 h-3.5 text-text-muted group-hover:text-text-primary transition-colors" />
            </div>
            <p className="text-text-secondary text-[11px] leading-relaxed">
              Train River Online One-Class SVM on benign warm-up flows or evaluate the Isolation Forest baseline.
            </p>
          </div>

          {/* Step 3: Results */}
          <div
            onClick={() => onNavigate('results')}
            className="p-4 rounded-[6px] bg-elevated-surface/50 border border-border-subtle hover:border-border-hover transition-colors cursor-pointer group space-y-2"
          >
            <div className="flex items-center justify-between">
              <span className="font-semibold text-text-primary flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-[#0070f3]/10 text-[#0070f3] flex items-center justify-center text-[11px] font-mono font-bold">
                  3
                </span>
                <span>Results</span>
              </span>
              <ArrowRight className="w-3.5 h-3.5 text-text-muted group-hover:text-text-primary transition-colors" />
            </div>
            <p className="text-text-secondary text-[11px] leading-relaxed">
              Inspect accuracy, precision, recall, false positive rates, confusion matrices, and model comparison.
            </p>
          </div>
        </div>
      </div>

      {/* 3. Key Status Summary: Model, Active Dataset, Latest Experiment */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Selected ML Model */}
        <div className="p-4 rounded-[8px] bg-card-surface border border-border-subtle flex flex-col justify-between space-y-3">
          <div className="space-y-2">
            <span className="text-[11px] font-mono uppercase text-text-muted">Selected ML Model</span>
            <div className="text-sm font-semibold text-text-primary flex items-center gap-2">
              <Cpu className="w-4 h-4 text-[#0070f3]" />
              <span>River Online One-Class SVM</span>
            </div>
            <p className="text-xs text-text-secondary">
              Streaming unsupervised model with incremental scaling and quantile thresholding.
            </p>
          </div>
          <div className="pt-2 border-t border-border-subtle flex items-center justify-between text-xs text-text-muted">
            <span>Alternative Baseline</span>
            <span className="font-medium text-text-secondary">Isolation Forest</span>
          </div>
        </div>

        {/* Active Dataset */}
        <div className="p-4 rounded-[8px] bg-card-surface border border-border-subtle flex flex-col justify-between space-y-3">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono uppercase text-text-muted">Active Dataset</span>
              {activeDataset && (
                <span className="text-[10px] font-mono text-text-muted bg-elevated-surface px-1.5 py-0.5 rounded border border-border-subtle">
                  {activeDataset.version}
                </span>
              )}
            </div>
            <div className="text-sm font-semibold text-text-primary flex items-center gap-2 truncate">
              <Database className="w-4 h-4 text-[#0070f3]" />
              <span className="truncate">{activeDataset ? activeDataset.name : 'No Dataset Selected'}</span>
            </div>
            <p className="text-xs text-text-secondary">
              {activeDataset ? (
                <span>
                  {activeDataset.total_flows.toLocaleString()} total flows ({activeDataset.benign_flows.toLocaleString()} benign, {activeDataset.attack_flows.toLocaleString()} attack)
                </span>
              ) : (
                'Load the sample benchmark or upload a NetFlow CSV.'
              )}
            </p>
          </div>
          <div className="pt-2 border-t border-border-subtle flex items-center justify-between text-xs">
            <button
              onClick={() => onNavigate('dataset')}
              className="text-[#0070f3] hover:underline font-medium flex items-center gap-1 cursor-pointer"
            >
              <span>Manage Datasets</span>
              <ArrowRight className="w-3 h-3" />
            </button>
            <span className="text-text-muted font-mono">{datasets.length} registered</span>
          </div>
        </div>

        {/* Latest Experiment Status */}
        <div className="p-4 rounded-[8px] bg-card-surface border border-border-subtle flex flex-col justify-between space-y-3">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono uppercase text-text-muted">Latest Experiment Status</span>
              {latestExperiment ? (
                <span className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
                  COMPLETED
                </span>
              ) : (
                <span className="text-[10px] font-mono text-text-muted">NOT RUN</span>
              )}
            </div>
            <div className="text-sm font-semibold text-text-primary flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-[#0070f3]" />
              <span>
                {latestExperiment
                  ? (latestExperiment.model_type === 'river_ocsvm' ? 'River Online OCSVM' : 'Isolation Forest')
                  : 'No Runs Recorded'}
              </span>
            </div>
            <p className="text-xs text-text-secondary">
              {latestExperiment ? (
                <span>
                  Evaluated on {latestExperiment.dataset_name} ({latestExperiment.eval_count.toLocaleString()} flows).
                </span>
              ) : (
                'Run an evaluation on the Experiment tab to generate metrics.'
              )}
            </p>
          </div>
          <div className="pt-2 border-t border-border-subtle flex items-center justify-between text-xs">
            {latestExperiment ? (
              <button
                onClick={() => onNavigate('results')}
                className="text-[#0070f3] hover:underline font-medium flex items-center gap-1 cursor-pointer"
              >
                <span>View Full Results</span>
                <ArrowRight className="w-3 h-3" />
              </button>
            ) : (
              <button
                onClick={() => onNavigate('experiment')}
                className="text-[#0070f3] hover:underline font-medium flex items-center gap-1 cursor-pointer"
              >
                <span>Start Experiment</span>
                <ArrowRight className="w-3 h-3" />
              </button>
            )}
            {latestExperiment && (
              <span className="text-text-muted font-mono text-[11px]">
                {new Date(latestExperiment.created_at).toLocaleDateString()}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
