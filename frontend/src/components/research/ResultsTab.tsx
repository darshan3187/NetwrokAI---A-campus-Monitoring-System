import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart3,
  Trash2,
  Cpu,
  ShieldCheck,
  RefreshCw,
  Info,
} from 'lucide-react';
import { researchApi } from '../../services/researchApi';
import type {
  ComparisonSummary,
  ResearchExperiment,
} from '../../types/research';
import { Spinner } from '../common/Spinner';

export const ResultsTab: React.FC = () => {
  const [experiments, setExperiments] = useState<ResearchExperiment[]>([]);
  const [selectedExperiment, setSelectedExperiment] = useState<ResearchExperiment | null>(null);
  const [comparison, setComparison] = useState<ComparisonSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadAllResults = useCallback(async () => {
    setIsLoading(true);
    try {
      const [expRes, compRes] = await Promise.all([
        researchApi.getExperiments(),
        researchApi.getComparisonSummary(),
      ]);
      setExperiments(expRes.experiments);
      if (expRes.experiments.length > 0) {
        setSelectedExperiment(expRes.experiments[0]);
      }
      setComparison(compRes);
    } catch (err: any) {
      setErrorMsg(`Failed to load results: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAllResults();
  }, [loadAllResults]);

  const handleDelete = async (id: string) => {
    if (!window.confirm('Delete this experiment record?')) return;
    try {
      await researchApi.deleteExperiment(id);
      await loadAllResults();
    } catch (err: any) {
      setErrorMsg(`Failed to delete experiment: ${err.message}`);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[360px] gap-3">
        <Spinner size="lg" />
        <span className="text-xs text-text-muted font-mono">Loading evaluation results...</span>
      </div>
    );
  }

  const exp = selectedExperiment;
  const proposed = comparison?.proposed_model;
  const baseline = comparison?.baseline_model;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border-subtle pb-4">
        <div>
          <h1 className="text-lg font-bold text-text-primary tracking-tight">
            Results & Model Evaluation
          </h1>
          <p className="text-xs text-text-secondary mt-0.5">
            Empirical evaluation metrics, confusion matrix decomposition, and side-by-side model comparison.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {experiments.length > 1 && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-text-muted">Selected Run:</span>
              <select
                value={selectedExperiment?.id || ''}
                onChange={(e) => {
                  const found = experiments.find((x) => x.id === e.target.value);
                  if (found) setSelectedExperiment(found);
                }}
                className="px-2.5 py-1.5 rounded-[4px] bg-elevated-surface text-text-primary border border-border-subtle text-xs font-mono"
              >
                {experiments.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.model_type === 'river_ocsvm' ? 'River OCSVM' : 'Isolation Forest'} — {e.dataset_name} ({(e.accuracy * 100).toFixed(2)}%)
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            onClick={loadAllResults}
            className="p-1.5 rounded-[4px] bg-elevated-surface hover:bg-hover-surface text-text-secondary hover:text-text-primary border border-border-subtle transition-colors cursor-pointer"
            title="Refresh results"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="p-3.5 rounded-[6px] bg-red-500/10 border border-red-500/25 flex items-center justify-between text-xs text-red-500">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="underline cursor-pointer">
            Dismiss
          </button>
        </div>
      )}

      {exp ? (
        <div className="space-y-6">
          {/* 1. Primary Evaluation Metrics Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {/* Accuracy */}
            <div className="p-3.5 rounded-[6px] bg-card-surface border border-border-subtle space-y-1.5">
              <span className="text-[10px] font-mono uppercase text-text-muted block">Accuracy</span>
              <div className="text-xl font-bold font-mono text-text-primary">
                {(exp.accuracy * 100).toFixed(2)}%
              </div>
              <p className="text-[10px] text-text-muted leading-tight">
                Overall percentage of correct predictions (benign &amp; attack).
              </p>
            </div>

            {/* Precision */}
            <div className="p-3.5 rounded-[6px] bg-card-surface border border-border-subtle space-y-1.5">
              <span className="text-[10px] font-mono uppercase text-text-muted block">Precision</span>
              <div className="text-xl font-bold font-mono text-text-primary">
                {(exp.precision * 100).toFixed(2)}%
              </div>
              <p className="text-[10px] text-text-muted leading-tight">
                Percentage of predicted attacks that were actual attacks.
              </p>
            </div>

            {/* Recall */}
            <div className="p-3.5 rounded-[6px] bg-card-surface border border-border-subtle space-y-1.5">
              <span className="text-[10px] font-mono uppercase text-text-muted block">Recall (Detection Rate)</span>
              <div className="text-xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
                {(exp.recall * 100).toFixed(2)}%
              </div>
              <p className="text-[10px] text-text-muted leading-tight">
                Percentage of actual network attacks caught by the model.
              </p>
            </div>

            {/* F1-Score */}
            <div className="p-3.5 rounded-[6px] bg-card-surface border border-border-subtle space-y-1.5">
              <span className="text-[10px] font-mono uppercase text-text-muted block">F1 Score</span>
              <div className="text-xl font-bold font-mono text-[#0070f3]">
                {(exp.f1_score * 100).toFixed(2)}%
              </div>
              <p className="text-[10px] text-text-muted leading-tight">
                Harmonic mean balancing precision and recall.
              </p>
            </div>

            {/* False Positive Rate */}
            <div className="p-3.5 rounded-[6px] bg-card-surface border border-border-subtle space-y-1.5">
              <span className="text-[10px] font-mono uppercase text-text-muted block">False Positive Rate</span>
              <div className="text-xl font-bold font-mono text-amber-600 dark:text-amber-400">
                {(exp.false_positive_rate * 100).toFixed(2)}%
              </div>
              <p className="text-[10px] text-text-muted leading-tight">
                Percentage of benign flows mistakenly flagged as attacks.
              </p>
            </div>

            {/* Decision Latency */}
            <div className="p-3.5 rounded-[6px] bg-card-surface border border-border-subtle space-y-1.5">
              <span className="text-[10px] font-mono uppercase text-text-muted block">Decision Latency</span>
              <div className="text-xl font-bold font-mono text-text-primary">
                {exp.avg_latency_per_flow_ms.toFixed(4)} <span className="text-xs font-normal text-text-muted">ms</span>
              </div>
              <p className="text-[10px] text-text-muted leading-tight">
                Average processing time per network flow.
              </p>
            </div>
          </div>

          {/* 2. Confusion Matrices (River Online OCSVM vs Isolation Forest) */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Left: River Online OCSVM Confusion Matrix */}
            <div className="p-4 rounded-[8px] bg-card-surface border border-border-subtle space-y-3">
              <div className="flex items-center justify-between border-b border-border-subtle pb-2.5">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-[#0070f3]" />
                  <div>
                    <h2 className="text-xs font-bold text-text-primary font-mono uppercase tracking-wide">
                      River Online One-Class SVM
                    </h2>
                    <span className="text-[10px] text-text-muted">Streaming Unsupervised Learning</span>
                  </div>
                </div>
                {proposed && (
                  <span className="text-[11px] font-mono text-[#0070f3] font-semibold">
                    Acc: {(proposed.accuracy * 100).toFixed(2)}%
                  </span>
                )}
              </div>

              {proposed ? (
                (() => {
                  const cm = proposed.confusion_matrix || { tn: 0, fp: 0, fn: 0, tp: 0 };
                  const total = cm.tn + cm.fp + cm.fn + cm.tp || 1;
                  return (
                    <div className="grid grid-cols-2 gap-2 text-center text-xs">
                      <div className="p-3 rounded-[6px] bg-emerald-500/10 border border-emerald-500/25 space-y-1">
                        <span className="text-[10px] font-mono uppercase text-emerald-600 dark:text-emerald-400 font-semibold block">
                          True Negative (TN)
                        </span>
                        <div className="text-lg font-bold font-mono text-emerald-600 dark:text-emerald-400">
                          {cm.tn.toLocaleString()}
                        </div>
                        <div className="text-[10px] text-text-muted font-mono">
                          {((cm.tn / total) * 100).toFixed(1)}% (benign correctly passed)
                        </div>
                      </div>

                      <div className="p-3 rounded-[6px] bg-amber-500/10 border border-amber-500/25 space-y-1">
                        <span className="text-[10px] font-mono uppercase text-amber-600 dark:text-amber-400 font-semibold block">
                          False Positive (FP)
                        </span>
                        <div className="text-lg font-bold font-mono text-amber-600 dark:text-amber-400">
                          {cm.fp.toLocaleString()}
                        </div>
                        <div className="text-[10px] text-text-muted font-mono">
                          {((cm.fp / total) * 100).toFixed(1)}% (false alarms)
                        </div>
                      </div>

                      <div className="p-3 rounded-[6px] bg-red-500/10 border border-red-500/25 space-y-1">
                        <span className="text-[10px] font-mono uppercase text-red-600 dark:text-red-400 font-semibold block">
                          False Negative (FN)
                        </span>
                        <div className="text-lg font-bold font-mono text-red-600 dark:text-red-400">
                          {cm.fn.toLocaleString()}
                        </div>
                        <div className="text-[10px] text-text-muted font-mono">
                          {((cm.fn / total) * 100).toFixed(1)}% (missed attacks)
                        </div>
                      </div>

                      <div className="p-3 rounded-[6px] bg-[#0070f3]/10 border border-[#0070f3]/25 space-y-1">
                        <span className="text-[10px] font-mono uppercase text-[#0070f3] font-semibold block">
                          True Positive (TP)
                        </span>
                        <div className="text-lg font-bold font-mono text-[#0070f3]">
                          {cm.tp.toLocaleString()}
                        </div>
                        <div className="text-[10px] text-text-muted font-mono">
                          {((cm.tp / total) * 100).toFixed(1)}% (attacks detected)
                        </div>
                      </div>
                    </div>
                  );
                })()
              ) : (
                <div className="p-6 text-center text-xs text-text-muted">
                  No River Online OCSVM run recorded yet.
                </div>
              )}
            </div>

            {/* Right: Isolation Forest Confusion Matrix */}
            <div className="p-4 rounded-[8px] bg-card-surface border border-border-subtle space-y-3">
              <div className="flex items-center justify-between border-b border-border-subtle pb-2.5">
                <div className="flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-text-secondary" />
                  <div>
                    <h2 className="text-xs font-bold text-text-primary font-mono uppercase tracking-wide">
                      Isolation Forest Baseline
                    </h2>
                    <span className="text-[10px] text-text-muted">Batch Decision Tree Ensemble</span>
                  </div>
                </div>
                {baseline && (
                  <span className="text-[11px] font-mono text-text-primary font-semibold">
                    Acc: {(baseline.accuracy * 100).toFixed(2)}%
                  </span>
                )}
              </div>

              {baseline ? (
                (() => {
                  const cm = baseline.confusion_matrix || { tn: 0, fp: 0, fn: 0, tp: 0 };
                  const total = cm.tn + cm.fp + cm.fn + cm.tp || 1;
                  return (
                    <div className="grid grid-cols-2 gap-2 text-center text-xs">
                      <div className="p-3 rounded-[6px] bg-emerald-500/10 border border-emerald-500/25 space-y-1">
                        <span className="text-[10px] font-mono uppercase text-emerald-600 dark:text-emerald-400 font-semibold block">
                          True Negative (TN)
                        </span>
                        <div className="text-lg font-bold font-mono text-emerald-600 dark:text-emerald-400">
                          {cm.tn.toLocaleString()}
                        </div>
                        <div className="text-[10px] text-text-muted font-mono">
                          {((cm.tn / total) * 100).toFixed(1)}% (benign correctly passed)
                        </div>
                      </div>

                      <div className="p-3 rounded-[6px] bg-amber-500/10 border border-amber-500/25 space-y-1">
                        <span className="text-[10px] font-mono uppercase text-amber-600 dark:text-amber-400 font-semibold block">
                          False Positive (FP)
                        </span>
                        <div className="text-lg font-bold font-mono text-amber-600 dark:text-amber-400">
                          {cm.fp.toLocaleString()}
                        </div>
                        <div className="text-[10px] text-text-muted font-mono">
                          {((cm.fp / total) * 100).toFixed(1)}% (false alarms)
                        </div>
                      </div>

                      <div className="p-3 rounded-[6px] bg-red-500/10 border border-red-500/25 space-y-1">
                        <span className="text-[10px] font-mono uppercase text-red-600 dark:text-red-400 font-semibold block">
                          False Negative (FN)
                        </span>
                        <div className="text-lg font-bold font-mono text-red-600 dark:text-red-400">
                          {cm.fn.toLocaleString()}
                        </div>
                        <div className="text-[10px] text-text-muted font-mono">
                          {((cm.fn / total) * 100).toFixed(1)}% (missed attacks)
                        </div>
                      </div>

                      <div className="p-3 rounded-[6px] bg-[#0070f3]/10 border border-[#0070f3]/25 space-y-1">
                        <span className="text-[10px] font-mono uppercase text-[#0070f3] font-semibold block">
                          True Positive (TP)
                        </span>
                        <div className="text-lg font-bold font-mono text-[#0070f3]">
                          {cm.tp.toLocaleString()}
                        </div>
                        <div className="text-[10px] text-text-muted font-mono">
                          {((cm.tp / total) * 100).toFixed(1)}% (attacks detected)
                        </div>
                      </div>
                    </div>
                  );
                })()
              ) : (
                <div className="p-6 text-center text-xs text-text-muted">
                  No Isolation Forest baseline run recorded yet. Run one on the Experiment tab to compare.
                </div>
              )}
            </div>
          </div>

          {/* 3. Model Comparison Table: Online OCSVM vs Isolation Forest */}
          <div className="p-4 rounded-[8px] bg-card-surface border border-border-subtle space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <h2 className="text-xs font-semibold text-text-primary uppercase tracking-wider font-mono flex items-center gap-2">
                <BarChart3 className="w-3.5 h-3.5 text-[#0070f3]" />
                <span>Model Comparison (Measured Locally)</span>
              </h2>

              <span className="text-[11px] font-mono text-text-muted">
                Evaluated on 50/50 balanced test partition
              </span>
            </div>

            <div className="overflow-x-auto border border-border-subtle rounded-[6px]">
              <table className="w-full text-xs text-left">
                <thead className="bg-elevated-surface text-text-muted font-mono uppercase text-[10px] border-b border-border-subtle">
                  <tr>
                    <th className="px-3 py-2.5">Metric / Property</th>
                    <th className="px-3 py-2.5 text-[#0070f3]">
                      River Online One-Class SVM
                      <span className="block text-[9px] font-normal lowercase text-text-muted">Local Run</span>
                    </th>
                    <th className="px-3 py-2.5 text-text-primary">
                      Isolation Forest Baseline
                      <span className="block text-[9px] font-normal lowercase text-text-muted">Local Run</span>
                    </th>
                    <th className="px-3 py-2.5 text-text-muted">
                      Published Paper Benchmark
                      <span className="block text-[9px] font-normal lowercase text-text-muted">arXiv:2509.01375 Table 3</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle font-mono text-text-secondary">
                  <tr>
                    <td className="px-3 py-2 font-medium text-text-primary">Learning Paradigm</td>
                    <td className="px-3 py-2 text-[#0070f3]">Online Streaming (SGD)</td>
                    <td className="px-3 py-2">Batch Ensemble (Random Trees)</td>
                    <td className="px-3 py-2 text-text-muted">Online Streaming (River)</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 font-medium text-text-primary">Accuracy</td>
                    <td className="px-3 py-2 font-bold text-text-primary">
                      {proposed ? `${(proposed.accuracy * 100).toFixed(2)}%` : '---'}
                    </td>
                    <td className="px-3 py-2">
                      {baseline ? `${(baseline.accuracy * 100).toFixed(2)}%` : '---'}
                    </td>
                    <td className="px-3 py-2 text-text-muted">98.32%</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 font-medium text-text-primary">Precision</td>
                    <td className="px-3 py-2 font-bold text-text-primary">
                      {proposed ? `${(proposed.precision * 100).toFixed(2)}%` : '---'}
                    </td>
                    <td className="px-3 py-2">
                      {baseline ? `${(baseline.precision * 100).toFixed(2)}%` : '---'}
                    </td>
                    <td className="px-3 py-2 text-text-muted">97.93%</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 font-medium text-text-primary">Recall (Detection Rate)</td>
                    <td className="px-3 py-2 font-bold text-emerald-600 dark:text-emerald-400">
                      {proposed ? `${(proposed.recall * 100).toFixed(2)}%` : '---'}
                    </td>
                    <td className="px-3 py-2">
                      {baseline ? `${(baseline.recall * 100).toFixed(2)}%` : '---'}
                    </td>
                    <td className="px-3 py-2 text-text-muted">98.15%</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 font-medium text-text-primary">F1 Score</td>
                    <td className="px-3 py-2 font-bold text-[#0070f3]">
                      {proposed ? `${(proposed.f1_score * 100).toFixed(2)}%` : '---'}
                    </td>
                    <td className="px-3 py-2">
                      {baseline ? `${(baseline.f1_score * 100).toFixed(2)}%` : '---'}
                    </td>
                    <td className="px-3 py-2 text-text-muted">98.04%</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 font-medium text-text-primary">False Positive Rate (FPR)</td>
                    <td className="px-3 py-2 font-bold text-amber-600 dark:text-amber-400">
                      {proposed ? `${(proposed.false_positive_rate * 100).toFixed(2)}%` : '---'}
                    </td>
                    <td className="px-3 py-2">
                      {baseline ? `${(baseline.false_positive_rate * 100).toFixed(2)}%` : '---'}
                    </td>
                    <td className="px-3 py-2 text-text-muted">2.84%</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 font-medium text-text-primary">Average Decision Latency</td>
                    <td className="px-3 py-2 font-bold text-text-primary">
                      {proposed ? `${proposed.avg_latency_per_flow_ms.toFixed(4)} ms/flow` : '---'}
                    </td>
                    <td className="px-3 py-2">
                      {baseline ? `${baseline.avg_latency_per_flow_ms.toFixed(4)} ms/flow` : '---'}
                    </td>
                    <td className="px-3 py-2 text-text-muted">&lt; 0.033 ms/flow</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="p-3 rounded-[6px] bg-elevated-surface text-[11px] text-text-secondary flex items-start gap-2 border border-border-subtle">
              <Info className="w-4 h-4 text-[#0070f3] shrink-0 mt-0.5" />
              <span>
                <strong>Academic Distinction:</strong> The Local Run columns reflect measurements calculated directly on your system with the current dataset sample. The Published Paper Reference is included from Alberto Miguel-Diez et al. (2025) for comparison against full 100,000-flow warmup benchmarks.
              </span>
            </div>
          </div>

          {/* 4. Selected Experiment Configuration Details */}
          <div className="p-4 rounded-[8px] bg-card-surface border border-border-subtle space-y-3">
            <h2 className="text-xs font-semibold text-text-primary uppercase tracking-wider font-mono">
              Experiment Configuration
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-2.5 rounded-[4px] bg-elevated-surface/50 border border-border-subtle">
                <span className="text-[10px] text-text-muted block">Dataset</span>
                <span className="font-semibold text-text-primary font-mono">{exp.dataset_name}</span>
              </div>
              <div className="p-2.5 rounded-[4px] bg-elevated-surface/50 border border-border-subtle">
                <span className="text-[10px] text-text-muted block">Evaluated Flows</span>
                <span className="font-semibold text-text-primary font-mono">{exp.eval_count.toLocaleString()}</span>
              </div>
              <div className="p-2.5 rounded-[4px] bg-elevated-surface/50 border border-border-subtle">
                <span className="text-[10px] text-text-muted block">Model Type</span>
                <span className="font-semibold text-text-primary font-mono">{exp.model_type === 'river_ocsvm' ? 'River Online OCSVM' : 'Isolation Forest'}</span>
              </div>
              <div className="p-2.5 rounded-[4px] bg-elevated-surface/50 border border-border-subtle">
                <span className="text-[10px] text-text-muted block">Random Seed</span>
                <span className="font-semibold text-text-primary font-mono">{exp.random_seed}</span>
              </div>
            </div>
          </div>

          {/* 5. Experiment History */}
          <div className="p-4 rounded-[8px] bg-card-surface border border-border-subtle space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold text-text-primary uppercase tracking-wider font-mono">
                Experiment Run History ({experiments.length} Runs)
              </h2>
              <span className="text-[11px] font-mono text-text-muted">
                Saved in local SQLite
              </span>
            </div>

            <div className="overflow-x-auto border border-border-subtle rounded-[6px]">
              <table className="w-full text-xs text-left">
                <thead className="bg-elevated-surface text-text-muted font-mono uppercase text-[10px] border-b border-border-subtle">
                  <tr>
                    <th className="px-3 py-2">TIME</th>
                    <th className="px-3 py-2">MODEL</th>
                    <th className="px-3 py-2">DATASET</th>
                    <th className="px-3 py-2">FLOWS</th>
                    <th className="px-3 py-2">ACCURACY</th>
                    <th className="px-3 py-2">F1</th>
                    <th className="px-3 py-2">FPR</th>
                    <th className="px-3 py-2">LATENCY</th>
                    <th className="px-3 py-2">ACTION</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle font-mono text-text-secondary">
                  {experiments.map((r) => (
                    <tr
                      key={r.id}
                      onClick={() => setSelectedExperiment(r)}
                      className={`cursor-pointer transition-colors ${
                        selectedExperiment?.id === r.id
                          ? 'bg-[#0070f3]/5 border-l-2 border-[#0070f3]'
                          : 'hover:bg-elevated-surface/50'
                      }`}
                    >
                      <td className="px-3 py-2 text-text-muted">
                        {new Date(r.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </td>
                      <td className="px-3 py-2 font-medium text-text-primary">
                        {r.model_type === 'river_ocsvm' ? 'River OCSVM' : 'Isolation Forest'}
                      </td>
                      <td className="px-3 py-2">{r.dataset_name}</td>
                      <td className="px-3 py-2">{r.eval_count.toLocaleString()}</td>
                      <td className="px-3 py-2 font-semibold text-text-primary">{(r.accuracy * 100).toFixed(2)}%</td>
                      <td className="px-3 py-2 text-[#0070f3]">{(r.f1_score * 100).toFixed(2)}%</td>
                      <td className="px-3 py-2 text-amber-600 dark:text-amber-400">{(r.false_positive_rate * 100).toFixed(2)}%</td>
                      <td className="px-3 py-2">{r.avg_latency_per_flow_ms.toFixed(4)} ms</td>
                      <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => handleDelete(r.id)}
                          className="text-text-muted hover:text-red-500 transition-colors cursor-pointer p-1"
                          title="Delete run"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-12 rounded-[8px] bg-card-surface border border-border-subtle text-center space-y-3">
          <div className="w-10 h-10 rounded-full bg-elevated-surface text-text-muted flex items-center justify-center mx-auto">
            <BarChart3 className="w-5 h-5" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-text-primary">No Experiment Results Available</h3>
            <p className="text-xs text-text-muted max-w-md mx-auto">
              Run an evaluation on the Experiment tab to measure accuracy, confusion matrices, and latency.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
