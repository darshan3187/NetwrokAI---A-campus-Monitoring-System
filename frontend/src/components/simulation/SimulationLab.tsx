import React, { useState, useEffect, useCallback } from 'react';
import {
  FlaskConical,
  RotateCcw,
  AlertTriangle,
  Info,
  Cpu,
} from 'lucide-react';
import { simulationApi } from '../../services/simulationApi';
import type { ScenarioMeta, SimulationResult } from '../../types/simulation';
import { ScenarioSelector } from './ScenarioSelector';
import { ValidationMetricsCards } from './ValidationMetricsCards';
import { ConfusionMatrixCard } from './ConfusionMatrixCard';
import { SimulationCharts } from './SimulationCharts';
import { Spinner } from '../common/Spinner';

export const SimulationLab: React.FC = () => {
  const [scenarios, setScenarios] = useState<ScenarioMeta[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('sudden_download_spike');
  const [seed, setSeed] = useState<number>(42);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isResetting, setIsResetting] = useState<boolean>(false);

  // Load registered scenarios and latest completed result on mount
  const loadInitialData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const scenariosRes = await simulationApi.getScenarios();
      setScenarios(scenariosRes.scenarios || []);
      if (scenariosRes.scenarios.length > 0 && !selectedScenarioId) {
        setSelectedScenarioId(scenariosRes.scenarios[0].scenario_id);
      }

      const latest = await simulationApi.getLatestResults();
      if (latest) {
        setResult(latest);
        setSelectedScenarioId(latest.scenario_id);
        setSeed(latest.seed);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to connect to simulation API';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [selectedScenarioId]);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Execute simulation
  const handleRunSimulation = async () => {
    setIsRunning(true);
    setError(null);
    try {
      const simResult = await simulationApi.runSimulation(selectedScenarioId, seed);
      setResult(simResult);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Simulation execution failed';
      setError(msg);
    } finally {
      setIsRunning(false);
    }
  };

  // Reset simulation state
  const handleReset = async () => {
    setIsResetting(true);
    try {
      await simulationApi.resetSimulation();
      setResult(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to reset simulation';
      setError(msg);
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Top Banner: Lab Title and Mandatory Synthetic Disclaimer */}
      <div className="bg-card-surface border border-border-subtle rounded-[12px] p-5 shadow-[var(--shadow-whisper)]">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-border-subtle">
          <div className="flex items-start gap-3">
            <div className="p-2.5 rounded-[8px] bg-[#0070f3]/10 border border-[#0070f3]/25 text-[#0070f3]">
              <FlaskConical className="w-5 h-5" aria-hidden="true" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-text-primary tracking-[-0.4px]">
                  Controlled Network Anomaly Simulation & Validation Lab
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-[4px] bg-[#0070f3]/10 text-[#0070f3] dark:text-[#3291ff] border border-[#0070f3]/25 font-semibold uppercase tracking-[0.05em]">
                  Isolated Environment
                </span>
              </div>
              <p className="text-xs text-text-secondary mt-0.5">
                Deterministic validation harness for evaluating the Isolation Forest engine against labeled telemetry scenarios
              </p>
            </div>
          </div>

          {/* Reset Button */}
          {result && (
            <button
              onClick={handleReset}
              disabled={isResetting || isRunning}
              className="flex items-center gap-1.5 px-3 py-1 rounded-[6px] bg-card-surface border border-border-subtle hover:border-border-hover text-xs text-text-secondary hover:text-text-primary transition-colors cursor-pointer disabled:opacity-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-text-primary font-mono"
              title="Clear simulation results"
              aria-label="Reset simulation lab"
            >
              <RotateCcw className={`w-3.5 h-3.5 ${isResetting ? 'animate-spin' : ''}`} aria-hidden="true" />
              <span>Reset Lab</span>
            </button>
          )}
        </div>

        {/* Mandatory Simulation Disclaimer Card */}
        <div className="mt-4 p-3 rounded-[8px] bg-elevated-surface border border-border-subtle flex items-start gap-2.5">
          <Info className="w-4 h-4 text-[#0070f3] shrink-0 mt-0.5" aria-hidden="true" />
          <div className="text-xs leading-relaxed text-text-secondary">
            <span className="text-text-primary font-mono font-medium mr-1.5 uppercase tracking-[0.05em]">SAFETY & RESEARCH NOTICE:</span>
            Simulation strictly executes against application-level synthetic telemetry vectors in-memory.
            No packets, floods, or network modifications are transmitted across physical adapters or external networks.
            Results are simulation-specific and do not represent benchmarked real-world cyberattack or DDoS detection guarantees.
          </div>
        </div>
      </div>

      {/* Global Error Banner */}
      {error && (
        <div className="p-3.5 rounded-[8px] bg-[#ee0000]/10 border border-[#ee0000]/25 text-[#ee0000] dark:text-[#f87171] text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </div>
          <button
            onClick={loadInitialData}
            className="underline hover:opacity-80 font-mono cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="py-12 flex flex-col items-center justify-center space-y-3">
          <Spinner size="lg" />
          <p className="text-xs font-mono text-text-secondary">Loading simulation scenarios and model state…</p>
        </div>
      )}

      {/* Scenario Selector */}
      {!isLoading && (
        <ScenarioSelector
          scenarios={scenarios}
          selectedScenarioId={selectedScenarioId}
          onSelectScenario={(id) => setSelectedScenarioId(id)}
          seed={seed}
          onChangeSeed={(s) => setSeed(s)}
          isRunning={isRunning}
          onRunSimulation={handleRunSimulation}
        />
      )}

      {/* Empty State before first run */}
      {!isLoading && !result && !isRunning && (
        <div className="py-16 flex flex-col items-center justify-center text-center p-6 bg-card-surface rounded-[12px] border border-dashed border-border-subtle shadow-[var(--shadow-whisper)]">
          <div className="w-12 h-12 rounded-full bg-[#0070f3]/10 border border-[#0070f3]/25 flex items-center justify-center mb-3">
            <Cpu className="w-6 h-6 text-[#0070f3]" aria-hidden="true" />
          </div>
          <h3 className="text-sm font-semibold text-text-primary tracking-[-0.28px]">
            Ready to Launch Simulation
          </h3>
          <p className="text-xs text-text-secondary max-w-md mt-1 leading-relaxed">
            Select a scenario above and click <span className="text-[#0070f3] font-semibold">Run Scenario</span> to generate synthetic telemetry, stream it through the isolated Isolation Forest model, and compute statistical validation metrics.
          </p>
        </div>
      )}

      {/* Active Run Results */}
      {!isLoading && result && (
        <div className="space-y-4">
          {/* Validation Metrics KPI Cards */}
          <ValidationMetricsCards
            metrics={result.metrics}
            scenarioName={result.scenario_name}
          />

          {/* 2x2 Confusion Matrix */}
          <ConfusionMatrixCard matrix={result.confusion_matrix} />

          {/* Telemetry and Anomaly Score Charts */}
          <SimulationCharts
            timeline={result.timeline}
            scenarioName={result.scenario_name}
          />
        </div>
      )}
    </div>
  );
};
