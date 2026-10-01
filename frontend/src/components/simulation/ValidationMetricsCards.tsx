import React from 'react';
import {
  Target,
  CheckCircle,
  Percent,
  Timer,
  Activity,
} from 'lucide-react';
import type { ValidationMetrics } from '../../types/simulation';

interface ValidationMetricsCardsProps {
  metrics: ValidationMetrics;
  scenarioName: string;
}

export const ValidationMetricsCards: React.FC<ValidationMetricsCardsProps> = ({
  metrics,
}) => {
  const formatPercent = (val: number | null) => (val !== null ? `${(val * 100).toFixed(1)}%` : 'Undefined*');

  const getMetricColor = (val: number | null) => {
    if (val === null) return 'text-text-muted';
    if (val >= 0.90) return 'text-[#0070f3] dark:text-[#3291ff]';
    if (val >= 0.70) return 'text-[#f5a623]';
    return 'text-[#ee0000] dark:text-[#f87171]';
  };

  const getLatencyColor = (latency: number | null) => {
    if (latency === null) return 'text-text-muted';
    if (latency <= 1.0) return 'text-[#0070f3] dark:text-[#3291ff]';
    if (latency <= 3.0) return 'text-[#f5a623]';
    return 'text-[#ee0000] dark:text-[#f87171]';
  };

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      {/* 1. Accuracy Card */}
      <div className="bg-card-surface border border-border-subtle rounded-[12px] p-4 flex flex-col justify-between shadow-[var(--shadow-whisper)]">
        <div className="flex items-center justify-between text-text-secondary text-xs">
          <span className="font-mono uppercase text-[11px] text-text-muted tracking-[0.05em]">Accuracy</span>
          <Target className="w-3.5 h-3.5 text-text-muted" aria-hidden="true" />
        </div>
        <div className="mt-2.5">
          <div className={`text-xl font-bold tabular-nums font-mono tracking-tight ${getMetricColor(metrics.accuracy)}`}>
            {formatPercent(metrics.accuracy)}
          </div>
          <div className="text-[11px] font-mono text-text-muted mt-1">
            (TP + TN) / Total
          </div>
        </div>
      </div>

      {/* 2. Precision Card */}
      <div className="bg-card-surface border border-border-subtle rounded-[12px] p-4 flex flex-col justify-between shadow-[var(--shadow-whisper)]">
        <div className="flex items-center justify-between text-text-secondary text-xs">
          <span className="font-mono uppercase text-[11px] text-text-muted tracking-[0.05em]">Precision</span>
          <Percent className="w-3.5 h-3.5 text-text-muted" aria-hidden="true" />
        </div>
        <div className="mt-2.5">
          <div className={`text-xl font-bold tabular-nums font-mono tracking-tight ${getMetricColor(metrics.precision)}`}>
            {formatPercent(metrics.precision)}
          </div>
          <div className="text-[11px] font-mono text-text-muted mt-1">
            {metrics.precision === null ? 'Undefined (0 alarms)' : 'TP / (TP + FP)'}
          </div>
        </div>
      </div>

      {/* 3. Recall Card */}
      <div className="bg-card-surface border border-border-subtle rounded-[12px] p-4 flex flex-col justify-between shadow-[var(--shadow-whisper)]">
        <div className="flex items-center justify-between text-text-secondary text-xs">
          <span className="font-mono uppercase text-[11px] text-text-muted tracking-[0.05em]">Recall</span>
          <CheckCircle className="w-3.5 h-3.5 text-text-muted" aria-hidden="true" />
        </div>
        <div className="mt-2.5">
          <div className={`text-xl font-bold tabular-nums font-mono tracking-tight ${getMetricColor(metrics.recall)}`}>
            {formatPercent(metrics.recall)}
          </div>
          <div className="text-[11px] font-mono text-text-muted mt-1">
            {metrics.recall === null ? 'Undefined (0 anomalies)' : 'TP / (TP + FN)'}
          </div>
        </div>
      </div>

      {/* 4. F1-Score Card */}
      <div className="bg-card-surface border border-border-subtle rounded-[12px] p-4 flex flex-col justify-between shadow-[var(--shadow-whisper)]">
        <div className="flex items-center justify-between text-text-secondary text-xs">
          <span className="font-mono uppercase text-[11px] text-text-muted tracking-[0.05em]">F1-Score</span>
          <Activity className="w-3.5 h-3.5 text-text-muted" aria-hidden="true" />
        </div>
        <div className="mt-2.5">
          <div className={`text-xl font-bold tabular-nums font-mono tracking-tight ${getMetricColor(metrics.f1_score)}`}>
            {formatPercent(metrics.f1_score)}
          </div>
          <div className="text-[11px] font-mono text-text-muted mt-1">
            {metrics.f1_score === null ? 'Undefined (No Positives)' : 'Harmonic Mean'}
          </div>
        </div>
      </div>

      {/* 5. Detection Latency Card */}
      <div className="bg-card-surface border border-border-subtle rounded-[12px] p-4 flex flex-col justify-between col-span-2 sm:col-span-1 shadow-[var(--shadow-whisper)]">
        <div className="flex items-center justify-between text-text-secondary text-xs">
          <span className="font-mono uppercase text-[11px] text-text-muted tracking-[0.05em]">Latency</span>
          <Timer className="w-3.5 h-3.5 text-text-muted" aria-hidden="true" />
        </div>
        <div className="mt-2.5">
          <div className={`text-xl font-bold tabular-nums font-mono tracking-tight ${getLatencyColor(metrics.detection_latency_seconds)}`}>
            {metrics.detection_latency_seconds !== null
              ? `${metrics.detection_latency_seconds.toFixed(1)}s`
              : 'N/A'}
          </div>
          <div className="text-[11px] font-mono text-text-muted mt-1">
            {metrics.detection_latency_seconds !== null ? 'Onset to first alarm' : 'No detection'}
          </div>
        </div>
      </div>
    </div>
  );
};
