import React from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  Cpu,
  Database,
  Wifi,
  Sparkles,
  Layers,
  AlertTriangle,
  Radio,
} from 'lucide-react';
import { Badge } from '../common/Badge';
import { useTheme } from '../../context/ThemeContext';
import type { AnomalyEvaluation, AnomalySummaryResponse } from '../../types/metrics';
import type { ConnectionStatus } from '../../hooks/useWebSocket';

interface AnomalyOverviewProps {
  evaluation: AnomalyEvaluation | null;
  summary: AnomalySummaryResponse | null;
  activeInterface: string | null;
  wsStatus: ConnectionStatus;
  isLoading: boolean;
  error: string | null;
}

export const AnomalyOverview: React.FC<AnomalyOverviewProps> = ({
  evaluation,
  summary,
  activeInterface,
  wsStatus,
  isLoading,
  error,
}) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const currentScore = evaluation?.score ?? 0.0;
  const severity = evaluation?.severity ?? (summary?.model_status === 'warming_up' ? 'Warming Up' : 'Normal');
  const detectionMethod = evaluation?.method ?? (summary?.is_trained ? 'isolation_forest' : 'warmup');
  const explanation = evaluation?.explanation ?? (
    summary?.model_status === 'warming_up'
      ? `Calibrating baseline (${summary.samples_observed}/20 samples collected). Anomaly scoring will activate once the host baseline is calibrated.`
      : 'Telemetric parameters within normal statistical baseline profile.'
  );

  const samplesObserved = summary?.samples_observed ?? 0;
  const totalAnomalies = summary?.total_anomalies ?? 0;
  const unusualCount = summary?.unusual_traffic_count ?? 0;
  const highCount = summary?.high_anomaly_count ?? 0;
  const isTrained = summary?.is_trained ?? false;
  const modelStatus = summary?.model_status ?? 'warming_up';

  const severityBadgeVariant = (sev: string): 'success' | 'warning' | 'error' | 'neutral' => {
    switch (sev.toLowerCase()) {
      case 'normal':
        return 'success';
      case 'unusual traffic':
      case 'warming up':
        return 'warning';
      case 'high anomaly':
        return 'error';
      default:
        return 'neutral';
    }
  };

  const getScoreColor = (score: number): string => {
    if (score >= 0.8) return isDark ? '#f87171' : '#ee0000';
    if (score >= 0.6) return isDark ? '#fbbf24' : '#f5a623';
    return isDark ? '#3291ff' : '#0070f3';
  };

  const formatMethodName = (method: string): string => {
    switch (method) {
      case 'isolation_forest':
        return 'Isolation Forest (100 Trees)';
      case 'statistical_fallback':
        return 'Statistical Z-Score Fallback';
      case 'warmup':
        return 'Baseline Warm-Up Calibration';
      case 'initial_baseline':
        return 'First-Sample Baseline';
      default:
        return method;
    }
  };

  return (
    <div className="space-y-4">
      {/* API / Offline Error Banner */}
      {error && (
        <div className="p-3 rounded-[8px] bg-[#ee0000]/10 border border-[#ee0000]/25 text-[#ee0000] dark:text-[#f87171] text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" aria-hidden="true" />
            <span>AI Telemetry Notice: {error}</span>
          </div>
        </div>
      )}

      {/* Top Banner: Engine Status & Active Adapter */}
      <div className="bg-card-surface border border-border-subtle rounded-[12px] p-5 shadow-[var(--shadow-whisper)]">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-border-subtle">
          <div className="flex items-start gap-3">
            <div className={`p-2.5 rounded-[8px] border ${
              severity === 'High Anomaly'
                ? 'bg-[#ee0000]/10 border-[#ee0000]/25 text-[#ee0000] dark:text-[#f87171]'
                : severity === 'Unusual Traffic'
                ? 'bg-[#f5a623]/10 border-[#f5a623]/25 text-[#f5a623]'
                : 'bg-[#0070f3]/10 border-[#0070f3]/25 text-[#0070f3] dark:text-[#3291ff]'
            }`}>
              {severity === 'High Anomaly' ? (
                <ShieldAlert className="w-5 h-5" aria-hidden="true" />
              ) : severity === 'Unusual Traffic' ? (
                <AlertTriangle className="w-5 h-5" aria-hidden="true" />
              ) : (
                <ShieldCheck className="w-5 h-5" aria-hidden="true" />
              )}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-text-primary tracking-[-0.4px]">
                  AI Network Anomaly Detection Engine
                </h2>
                <Badge variant={isTrained ? 'success' : 'warning'} size="sm">
                  {modelStatus === 'active' ? 'Active' : modelStatus === 'warming_up' ? 'Warming Up' : 'Ready'}
                </Badge>
                {isLoading && (
                  <span className="text-xs text-[#0070f3] font-mono animate-pulse">
                    Syncing…
                  </span>
                )}
              </div>
              <p className="text-xs text-text-secondary mt-0.5">
                Unsupervised telemetry inspection using scikit-learn Isolation Forest on multi-dimensional socket vectors
              </p>
            </div>
          </div>

          {/* Quick status pill tags */}
          <div className="flex items-center gap-2 text-xs flex-wrap font-mono">
            <div className="px-2.5 py-1 rounded-[6px] bg-elevated-surface border border-border-subtle flex items-center gap-1.5 text-text-secondary">
              <Wifi className="w-3.5 h-3.5 text-text-muted" aria-hidden="true" />
              <span>Adapter:</span>
              <span className="text-text-primary font-medium">{activeInterface || 'None'}</span>
            </div>

            <div className="px-2.5 py-1 rounded-[6px] bg-elevated-surface border border-border-subtle flex items-center gap-1.5 text-text-secondary">
              <Radio className={`w-3.5 h-3.5 ${wsStatus === 'connected' ? 'text-[#0070f3]' : 'text-[#f5a623]'}`} aria-hidden="true" />
              <span>Stream:</span>
              <span className="capitalize text-text-primary font-medium">{wsStatus}</span>
            </div>
          </div>
        </div>

        {/* Diagnostic Explanation Banner */}
        <div className="mt-4 p-3 rounded-[8px] bg-elevated-surface border border-border-subtle flex items-start gap-2.5">
          <Sparkles className="w-4 h-4 text-[#0070f3] shrink-0 mt-0.5" aria-hidden="true" />
          <div className="text-xs leading-relaxed">
            <span className="text-text-muted font-mono font-medium mr-1.5 uppercase tracking-[0.05em]">DIAGNOSTIC:</span>
            <span className="text-text-primary font-medium">{explanation}</span>
          </div>
        </div>

        {/* Warm-Up Progress Bar (if in warm-up) */}
        {!isTrained && (
          <div className="mt-3 p-3 rounded-[8px] bg-elevated-surface border border-border-subtle">
            <div className="flex items-center justify-between text-xs mb-1.5 font-mono">
              <span className="text-text-secondary flex items-center gap-1.5 font-medium">
                <Cpu className="w-3.5 h-3.5 text-[#f5a623]" aria-hidden="true" /> Baseline Warm-Up Calibration Progress
              </span>
              <span className="text-text-primary tabular-nums font-semibold">
                {Math.min(samplesObserved, 20)} / 20 samples ({Math.min(100, Math.round((samplesObserved / 20) * 100))}%)
              </span>
            </div>
            <div className="w-full h-1.5 bg-card-surface border border-border-subtle rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-[#007cf0] to-[#00dfd8] transition-[width] duration-300"
                style={{ width: `${Math.min(100, (samplesObserved / 20) * 100)}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* 4 Focused Anomaly Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Card 1: Live Anomaly Score */}
        <div className="bg-card-surface border border-border-subtle rounded-[12px] p-4 flex flex-col justify-between shadow-[var(--shadow-whisper)]">
          <div className="flex items-center justify-between text-xs text-text-secondary font-mono">
            <span className="font-medium uppercase tracking-[0.05em] text-[11px] text-text-muted">Anomaly Score</span>
            <Badge variant={severityBadgeVariant(severity)} size="sm">
              {severity}
            </Badge>
          </div>
          <div className="my-2.5 flex items-baseline gap-2">
            <span
              className="text-2xl font-bold font-mono tabular-nums tracking-[-0.6px]"
              style={{ color: getScoreColor(currentScore) }}
            >
              {currentScore.toFixed(2)}
            </span>
            <span className="text-xs text-text-muted font-mono">/ 1.00</span>
          </div>
          {/* Progress bar visual */}
          <div className="w-full h-1.5 bg-elevated-surface rounded-full overflow-hidden mt-1">
            <div
              className="h-full transition-[width] duration-300"
              style={{
                width: `${Math.min(100, Math.max(3, currentScore * 100))}%`,
                backgroundColor: getScoreColor(currentScore),
              }}
            />
          </div>
        </div>

        {/* Card 2: Model Inference Engine */}
        <div className="bg-card-surface border border-border-subtle rounded-[12px] p-4 flex flex-col justify-between shadow-[var(--shadow-whisper)]">
          <div className="flex items-center justify-between text-xs text-text-secondary">
            <span className="font-mono uppercase tracking-[0.05em] text-[11px] text-text-muted font-medium">Detection Method</span>
            <Cpu className="w-3.5 h-3.5 text-text-muted" aria-hidden="true" />
          </div>
          <div className="my-2">
            <div className="text-sm font-semibold text-text-primary truncate">
              {formatMethodName(detectionMethod)}
            </div>
            <div className="text-xs text-text-muted mt-0.5 font-mono">
              {isTrained ? 'Contamination: 0.05' : 'Collecting baseline'}
            </div>
          </div>
          <div className="text-[11px] text-text-muted font-mono">
            Random State: 42
          </div>
        </div>

        {/* Card 3: Training & Telemetry Samples */}
        <div className="bg-card-surface border border-border-subtle rounded-[12px] p-4 flex flex-col justify-between shadow-[var(--shadow-whisper)]">
          <div className="flex items-center justify-between text-xs text-text-secondary">
            <span className="font-mono uppercase tracking-[0.05em] text-[11px] text-text-muted font-medium">Processed Samples</span>
            <Layers className="w-3.5 h-3.5 text-text-muted" aria-hidden="true" />
          </div>
          <div className="my-2">
            <div className="text-2xl font-bold text-text-primary tabular-nums tracking-[-0.6px]">
              {samplesObserved.toLocaleString()}
            </div>
            <div className="text-xs text-text-muted mt-0.5 font-mono">
              Feature vector: 15 attrs
            </div>
          </div>
          <div className="text-[11px] text-text-muted font-mono">
            Window: 30 samples
          </div>
        </div>

        {/* Card 4: Persisted Anomaly Events */}
        <div className="bg-card-surface border border-border-subtle rounded-[12px] p-4 flex flex-col justify-between shadow-[var(--shadow-whisper)]">
          <div className="flex items-center justify-between text-xs text-text-secondary">
            <span className="font-mono uppercase tracking-[0.05em] text-[11px] text-text-muted font-medium">Persisted Events</span>
            <Database className="w-3.5 h-3.5 text-text-muted" aria-hidden="true" />
          </div>
          <div className="my-2">
            <div className="text-2xl font-bold text-text-primary tabular-nums tracking-[-0.6px]">
              {totalAnomalies}
            </div>
            <div className="text-xs text-text-muted flex items-center gap-2 mt-0.5 font-mono">
              <span className="text-[#f5a623] font-medium tabular-nums">{unusualCount} Unusual</span>
              <span>•</span>
              <span className="text-[#ee0000] dark:text-[#f87171] font-medium tabular-nums">{highCount} High</span>
            </div>
          </div>
          <div className="text-[11px] text-text-muted font-mono">
            Cooldown: 10s debounce
          </div>
        </div>
      </div>
    </div>
  );
};
