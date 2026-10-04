import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Play,
  Square,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  Cpu,
  Database,
  BarChart3,
  Clock,
} from 'lucide-react';
import { researchApi } from '../../services/researchApi';
import type {
  ResearchDataset,
  ResearchExperimentParams,
  ResearchExperimentProgress,
} from '../../types/research';
import { Spinner } from '../common/Spinner';

interface ExperimentTabProps {
  onRunCompleted?: () => void;
  onNavigateToResults?: () => void;
}

export const ExperimentTab: React.FC<ExperimentTabProps> = ({
  onRunCompleted,
  onNavigateToResults,
}) => {
  const [datasets, setDatasets] = useState<ResearchDataset[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>('');
  const [modelType, setModelType] = useState<'river_ocsvm' | 'isolation_forest'>('river_ocsvm');
  const [preset, setPreset] = useState<'fast_demo' | 'benchmark' | 'custom'>('fast_demo');

  // Hyperparameters
  const [nu, setNu] = useState<number>(0.05);
  const [q, setQ] = useState<number>(0.99);
  const [eta, setEta] = useState<number>(0.1);
  const [power, setPower] = useState<number>(0.5);
  const [scalerInitCount, setScalerInitCount] = useState<number>(200);
  const [warmupCount, setWarmupCount] = useState<number>(1000);
  const [evalCount, setEvalCount] = useState<number | ''>(800);
  const [randomSeed, setRandomSeed] = useState<number>(42);
  const [numRuns, setNumRuns] = useState<number>(1);

  // Runtime state
  const [progress, setProgress] = useState<ResearchExperimentProgress>({
    status: 'idle',
    phase: 'Ready',
    current_step: 'No experiment currently running.',
    warmup_progress: 0,
    eval_progress: 0,
    flows_processed: 0,
    total_flows: 0,
    flows_per_second: 0,
    avg_latency_ms: 0,
    current_metrics: null,
  });

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load available datasets
  const fetchDatasets = useCallback(async () => {
    try {
      const res = await researchApi.getDatasets();
      setDatasets(res.datasets);
      if (res.datasets.length > 0 && !selectedDatasetId) {
        const sample = res.datasets.find((d) => d.is_sample) || res.datasets[0];
        setSelectedDatasetId(sample.id);
      }
    } catch (err: any) {
      setErrorMsg(`Failed to load datasets: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  }, [selectedDatasetId]);

  useEffect(() => {
    fetchDatasets();
  }, [fetchDatasets]);

  // Apply Presets
  const applyPreset = (presetName: 'fast_demo' | 'benchmark' | 'custom') => {
    setPreset(presetName);
    if (presetName === 'fast_demo') {
      setNu(0.05);
      setQ(0.99);
      setEta(0.1);
      setPower(0.5);
      setScalerInitCount(200);
      setWarmupCount(1000);
      setEvalCount(800);
      setNumRuns(1);
    } else if (presetName === 'benchmark') {
      setNu(0.05);
      setQ(0.99);
      setEta(0.1);
      setPower(0.5);
      setScalerInitCount(1000);
      setWarmupCount(100000);
      setEvalCount('');
      setNumRuns(1);
    }
  };

  // Poll progress while running
  const isRunning = ['preparing', 'scaler_init', 'warmup', 'evaluating'].includes(progress.status);

  useEffect(() => {
    const checkProgress = async () => {
      try {
        const snap = await researchApi.getActiveExperimentProgress();
        setProgress(snap);
        if (snap.status === 'completed' || snap.status === 'failed' || snap.status === 'cancelled') {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
          if (snap.status === 'completed' && onRunCompleted) {
            onRunCompleted();
          }
        }
      } catch {
        // Silently retry next poll
      }
    };

    checkProgress();

    if (isRunning && !pollIntervalRef.current) {
      pollIntervalRef.current = setInterval(checkProgress, 600);
    }

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [isRunning, onRunCompleted]);

  const handleStartExperiment = async () => {
    if (!selectedDatasetId) {
      setErrorMsg('Please select a dataset to run the experiment.');
      return;
    }

    setErrorMsg(null);
    setIsSubmitting(true);

    const params: ResearchExperimentParams = {
      nu,
      q,
      learning_rate: eta,
      power,
      scaler_init_count: scalerInitCount,
      warmup_count: warmupCount,
      eval_count: evalCount === '' ? null : Number(evalCount),
      contamination: 0.05,
    };

    try {
      const initSnap = await researchApi.runExperiment({
        dataset_id: selectedDatasetId,
        model_type: modelType,
        preset_name: preset === 'benchmark' ? 'NF-UNSW-NB15' : 'Fast-Demo',
        is_paper_preset: preset !== 'custom',
        parameters: params,
        random_seed: randomSeed,
        num_runs: numRuns,
      });
      setProgress(initSnap);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to start experiment.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancelExperiment = async () => {
    try {
      await researchApi.cancelExperiment();
      const snap = await researchApi.getActiveExperimentProgress();
      setProgress(snap);
    } catch (err: any) {
      setErrorMsg(`Cancel failed: ${err.message}`);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[360px] gap-3">
        <Spinner size="lg" />
        <span className="text-xs text-text-muted font-mono">Loading experiment workspace...</span>
      </div>
    );
  }

  const selectedDataset = datasets.find((d) => d.id === selectedDatasetId);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border-subtle pb-4">
        <div>
          <h1 className="text-lg font-bold text-text-primary tracking-tight">
            Experiment
          </h1>
          <p className="text-xs text-text-secondary mt-0.5">
            Configure and run network flow anomaly detection using River Online One-Class SVM or the Isolation Forest baseline.
          </p>
        </div>

        {progress.status === 'completed' && onNavigateToResults && (
          <button
            onClick={onNavigateToResults}
            className="px-3.5 py-1.5 rounded-[6px] bg-[#0070f3] text-white text-xs font-semibold hover:bg-[#0070f3]/90 transition-colors flex items-center gap-1.5 cursor-pointer self-start md:self-auto"
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span>View Results</span>
          </button>
        )}
      </div>

      {errorMsg && (
        <div className="p-3.5 rounded-[6px] bg-red-500/10 border border-red-500/25 flex items-center justify-between gap-3 text-xs text-red-500">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
          <button
            onClick={() => setErrorMsg(null)}
            className="text-[11px] underline hover:opacity-80 cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Grid: Left Configuration Panel (7 cols) & Right Execution Monitor (5 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Configuration Form */}
        <div className="lg:col-span-7 space-y-5">
          {/* 1. Dataset Selection Card */}
          <div className="p-4 rounded-[8px] bg-card-surface border border-border-subtle space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-text-primary uppercase tracking-wider font-mono flex items-center gap-2">
                <Database className="w-3.5 h-3.5 text-[#0070f3]" />
                <span>1. Dataset</span>
              </label>
              {selectedDataset && (
                <span className="text-[11px] font-mono text-text-muted">
                  {selectedDataset.total_flows.toLocaleString()} flows
                </span>
              )}
            </div>

            <select
              value={selectedDatasetId}
              onChange={(e) => setSelectedDatasetId(e.target.value)}
              disabled={isRunning}
              className="w-full px-3 py-2 rounded-[6px] bg-elevated-surface text-text-primary border border-border-subtle text-xs focus:outline-none focus:ring-1 focus:ring-[#0070f3] disabled:opacity-50"
            >
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.version}) — {d.total_flows.toLocaleString()} flows {d.is_sample ? '[Sample]' : ''}
                </option>
              ))}
            </select>

            {selectedDataset && (
              <div className="p-2.5 rounded-[6px] bg-elevated-surface/50 border border-border-subtle text-[11px] text-text-secondary flex items-center justify-between">
                <span>Class Distribution:</span>
                <span className="font-mono">
                  <span className="text-emerald-600 dark:text-emerald-400 font-semibold">{selectedDataset.benign_flows.toLocaleString()} benign</span>
                  {' '}/ {selectedDataset.attack_flows.toLocaleString()} attack
                </span>
              </div>
            )}
          </div>

          {/* 2. Model Selection */}
          <div className="p-4 rounded-[8px] bg-card-surface border border-border-subtle space-y-3">
            <label className="text-xs font-semibold text-text-primary uppercase tracking-wider font-mono flex items-center gap-2">
              <Cpu className="w-3.5 h-3.5 text-[#0070f3]" />
              <span>2. Anomaly Detection Model</span>
            </label>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setModelType('river_ocsvm')}
                disabled={isRunning}
                className={`p-3 rounded-[6px] border text-left cursor-pointer transition-all ${
                  modelType === 'river_ocsvm'
                    ? 'bg-[#0070f3]/10 border-[#0070f3] text-text-primary'
                    : 'bg-elevated-surface border-border-subtle text-text-secondary hover:text-text-primary'
                }`}
              >
                <div className="font-semibold text-xs text-text-primary">
                  River Online One-Class SVM
                </div>
                <div className="text-[11px] text-text-muted mt-1 leading-snug">
                  Streaming SGD with incremental MaxAbsScaler and dynamic quantile thresholding.
                </div>
              </button>

              <button
                type="button"
                onClick={() => setModelType('isolation_forest')}
                disabled={isRunning}
                className={`p-3 rounded-[6px] border text-left cursor-pointer transition-all ${
                  modelType === 'isolation_forest'
                    ? 'bg-[#0070f3]/10 border-[#0070f3] text-text-primary'
                    : 'bg-elevated-surface border-border-subtle text-text-secondary hover:text-text-primary'
                }`}
              >
                <div className="font-semibold text-xs text-text-primary">
                  Isolation Forest Baseline
                </div>
                <div className="text-[11px] text-text-muted mt-1 leading-snug">
                  Batch ensemble of randomized decision trees evaluated as a comparative baseline.
                </div>
              </button>
            </div>
          </div>

          {/* 3. Parameters */}
          <div className="p-4 rounded-[8px] bg-card-surface border border-border-subtle space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-text-primary uppercase tracking-wider font-mono flex items-center gap-2">
                <Sliders className="w-3.5 h-3.5 text-[#0070f3]" />
                <span>3. Parameters</span>
              </label>

              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => applyPreset('fast_demo')}
                  disabled={isRunning}
                  className={`px-2 py-0.5 rounded text-[11px] font-medium cursor-pointer transition-colors ${
                    preset === 'fast_demo' ? 'bg-[#0070f3] text-white' : 'bg-elevated-surface text-text-secondary hover:text-text-primary'
                  }`}
                >
                  Fast Demo
                </button>
                <button
                  type="button"
                  onClick={() => applyPreset('benchmark')}
                  disabled={isRunning}
                  className={`px-2 py-0.5 rounded text-[11px] font-medium cursor-pointer transition-colors ${
                    preset === 'benchmark' ? 'bg-[#0070f3] text-white' : 'bg-elevated-surface text-text-secondary hover:text-text-primary'
                  }`}
                >
                  Full Benchmark
                </button>
                <button
                  type="button"
                  onClick={() => setPreset('custom')}
                  disabled={isRunning}
                  className={`px-2 py-0.5 rounded text-[11px] font-medium cursor-pointer transition-colors ${
                    preset === 'custom' ? 'bg-[#0070f3] text-white' : 'bg-elevated-surface text-text-secondary hover:text-text-primary'
                  }`}
                >
                  Custom
                </button>
              </div>
            </div>

            {/* Hyperparameter Inputs */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="space-y-1">
                <span className="text-[11px] text-text-muted" title="Expected upper bound on training error fraction">
                  Nu (Outlier Bound)
                </span>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max="0.5"
                  value={nu}
                  onChange={(e) => {
                    setNu(parseFloat(e.target.value) || 0.05);
                    setPreset('custom');
                  }}
                  disabled={isRunning}
                  className="w-full px-2.5 py-1.5 rounded-[4px] bg-elevated-surface text-text-primary border border-border-subtle font-mono text-xs"
                />
              </div>

              <div className="space-y-1">
                <span className="text-[11px] text-text-muted" title="Anomaly cutoff percentile for anomaly scoring">
                  Quantile q
                </span>
                <input
                  type="number"
                  step="0.01"
                  min="0.5"
                  max="0.999"
                  value={q}
                  onChange={(e) => {
                    setQ(parseFloat(e.target.value) || 0.99);
                    setPreset('custom');
                  }}
                  disabled={isRunning}
                  className="w-full px-2.5 py-1.5 rounded-[4px] bg-elevated-surface text-text-primary border border-border-subtle font-mono text-xs"
                />
              </div>

              <div className="space-y-1">
                <span className="text-[11px] text-text-muted" title="Initial learning rate for SGD optimization">
                  Learning Rate (eta)
                </span>
                <input
                  type="number"
                  step="0.05"
                  min="0.01"
                  max="1.0"
                  value={eta}
                  onChange={(e) => {
                    setEta(parseFloat(e.target.value) || 0.1);
                    setPreset('custom');
                  }}
                  disabled={isRunning}
                  className="w-full px-2.5 py-1.5 rounded-[4px] bg-elevated-surface text-text-primary border border-border-subtle font-mono text-xs"
                />
              </div>

              <div className="space-y-1">
                <span className="text-[11px] text-text-muted" title="Exponent for inverse scaling learning rate decay">
                  Power (Schedule)
                </span>
                <input
                  type="number"
                  step="0.1"
                  min="0.1"
                  max="1.0"
                  value={power}
                  onChange={(e) => {
                    setPower(parseFloat(e.target.value) || 0.5);
                    setPreset('custom');
                  }}
                  disabled={isRunning}
                  className="w-full px-2.5 py-1.5 rounded-[4px] bg-elevated-surface text-text-primary border border-border-subtle font-mono text-xs"
                />
              </div>

              <div className="space-y-1">
                <span className="text-[11px] text-text-muted" title="Benign flows to initialize MaxAbsScaler">
                  Scaler Init Flows
                </span>
                <input
                  type="number"
                  step="100"
                  min="10"
                  value={scalerInitCount}
                  onChange={(e) => {
                    setScalerInitCount(parseInt(e.target.value) || 200);
                    setPreset('custom');
                  }}
                  disabled={isRunning}
                  className="w-full px-2.5 py-1.5 rounded-[4px] bg-elevated-surface text-text-primary border border-border-subtle font-mono text-xs"
                />
              </div>

              <div className="space-y-1">
                <span className="text-[11px] text-text-muted" title="Benign flows to train the initial model">
                  Warm-up Flows
                </span>
                <input
                  type="number"
                  step="500"
                  min="20"
                  value={warmupCount}
                  onChange={(e) => {
                    setWarmupCount(parseInt(e.target.value) || 1000);
                    setPreset('custom');
                  }}
                  disabled={isRunning}
                  className="w-full px-2.5 py-1.5 rounded-[4px] bg-elevated-surface text-text-primary border border-border-subtle font-mono text-xs"
                />
              </div>

              <div className="space-y-1">
                <span className="text-[11px] text-text-muted" title="Seed for reproducible test sampling">
                  Random Seed
                </span>
                <input
                  type="number"
                  value={randomSeed}
                  onChange={(e) => setRandomSeed(parseInt(e.target.value) || 42)}
                  disabled={isRunning}
                  className="w-full px-2.5 py-1.5 rounded-[4px] bg-elevated-surface text-text-primary border border-border-subtle font-mono text-xs"
                />
              </div>

              <div className="space-y-1">
                <span className="text-[11px] text-text-muted" title="Repeated evaluation runs (1 to 12)">
                  Runs (1-12)
                </span>
                <input
                  type="number"
                  min="1"
                  max="12"
                  value={numRuns}
                  onChange={(e) => setNumRuns(Math.min(12, Math.max(1, parseInt(e.target.value) || 1)))}
                  disabled={isRunning}
                  className="w-full px-2.5 py-1.5 rounded-[4px] bg-elevated-surface text-text-primary border border-border-subtle font-mono text-xs"
                />
              </div>
            </div>

            {/* Launch Controls */}
            <div className="pt-3 border-t border-border-subtle flex items-center justify-between">
              <span className="text-[11px] text-text-muted font-mono">
                {preset === 'custom' ? 'Custom Parameters' : `Preset: ${preset === 'fast_demo' ? 'Fast Demo' : 'Full Benchmark'}`}
              </span>

              <div className="flex items-center gap-2">
                {isRunning ? (
                  <button
                    type="button"
                    onClick={handleCancelExperiment}
                    className="px-4 py-2 rounded-[6px] bg-red-600 hover:bg-red-700 text-white text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
                  >
                    <Square className="w-3.5 h-3.5 fill-current" />
                    <span>Cancel Run</span>
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleStartExperiment}
                    disabled={isSubmitting}
                    className="px-5 py-2 rounded-[6px] bg-[#0070f3] hover:bg-[#0070f3]/90 text-white text-xs font-semibold flex items-center gap-1.5 cursor-pointer disabled:opacity-50 transition-colors shadow-xs"
                  >
                    {isSubmitting ? (
                      <>
                        <Spinner size="sm" />
                        <span>Starting...</span>
                      </>
                    ) : (
                      <>
                        <Play className="w-3.5 h-3.5 fill-current" />
                        <span>Start Experiment</span>
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Right: Execution Monitor */}
        <div className="lg:col-span-5 space-y-5">
          <div className="p-4 rounded-[8px] bg-card-surface border border-border-subtle space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-text-primary uppercase tracking-wider font-mono flex items-center gap-2">
                <Clock className="w-3.5 h-3.5 text-[#0070f3]" />
                <span>Execution Status</span>
              </span>

              <span
                className={`text-[11px] font-mono px-2 py-0.5 rounded font-medium ${
                  isRunning
                    ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/25'
                    : progress.status === 'completed'
                    ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25'
                    : progress.status === 'failed'
                    ? 'bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/25'
                    : 'bg-elevated-surface text-text-muted border border-border-subtle'
                }`}
              >
                {progress.status.toUpperCase()}
              </span>
            </div>

            {/* Current Step Description */}
            <div className="p-3 rounded-[6px] bg-elevated-surface border border-border-subtle text-xs space-y-1">
              <div className="text-[11px] font-mono text-text-muted uppercase">Phase: {progress.phase}</div>
              <div className="text-text-primary font-medium">{progress.current_step}</div>
            </div>

            {/* Progress Bars */}
            <div className="space-y-3">
              {/* Warmup Progress */}
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-text-muted">Benign Warm-Up</span>
                  <span className="font-mono text-text-primary">{progress.warmup_progress.toFixed(1)}%</span>
                </div>
                <div className="w-full h-2 rounded-full bg-elevated-surface overflow-hidden border border-border-subtle">
                  <div
                    className="h-full bg-[#0070f3] transition-all duration-300"
                    style={{ width: `${progress.warmup_progress}%` }}
                  />
                </div>
              </div>

              {/* Evaluation Progress */}
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-text-muted">Streaming Evaluation</span>
                  <span className="font-mono text-text-primary">{progress.eval_progress.toFixed(1)}%</span>
                </div>
                <div className="w-full h-2 rounded-full bg-elevated-surface overflow-hidden border border-border-subtle">
                  <div
                    className="h-full bg-emerald-500 transition-all duration-300"
                    style={{ width: `${progress.eval_progress}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Real-time Telemetry Stats */}
            <div className="grid grid-cols-2 gap-3 pt-2 text-xs">
              <div className="p-2.5 rounded-[6px] bg-elevated-surface/50 border border-border-subtle space-y-0.5">
                <span className="text-[10px] text-text-muted font-mono uppercase">Flows Processed</span>
                <div className="text-sm font-semibold font-mono text-text-primary">
                  {progress.flows_processed.toLocaleString()}
                  {progress.total_flows > 0 && (
                    <span className="text-xs text-text-muted font-normal"> / {progress.total_flows.toLocaleString()}</span>
                  )}
                </div>
              </div>

              <div className="p-2.5 rounded-[6px] bg-elevated-surface/50 border border-border-subtle space-y-0.5">
                <span className="text-[10px] text-text-muted font-mono uppercase">Throughput</span>
                <div className="text-sm font-semibold font-mono text-text-primary">
                  {progress.flows_per_second.toFixed(0)} <span className="text-xs text-text-muted font-normal">flows/s</span>
                </div>
              </div>

              <div className="p-2.5 rounded-[6px] bg-elevated-surface/50 border border-border-subtle space-y-0.5">
                <span className="text-[10px] text-text-muted font-mono uppercase">Latency / Flow</span>
                <div className="text-sm font-semibold font-mono text-text-primary">
                  {progress.avg_latency_ms.toFixed(4)} <span className="text-xs text-text-muted font-normal">ms</span>
                </div>
              </div>

              <div className="p-2.5 rounded-[6px] bg-elevated-surface/50 border border-border-subtle space-y-0.5">
                <span className="text-[10px] text-text-muted font-mono uppercase">Interim Accuracy</span>
                <div className="text-sm font-semibold font-mono text-text-primary">
                  {progress.current_metrics?.accuracy !== undefined
                    ? `${(progress.current_metrics.accuracy * 100).toFixed(2)}%`
                    : '---'}
                </div>
              </div>
            </div>

            {progress.status === 'completed' && (
              <div className="p-3 rounded-[6px] bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-between text-xs">
                <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span>Experiment completed successfully.</span>
                </div>
                {onNavigateToResults && (
                  <button
                    onClick={onNavigateToResults}
                    className="text-xs font-semibold text-text-primary underline hover:opacity-80 cursor-pointer"
                  >
                    View Results &rarr;
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
