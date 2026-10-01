import React from 'react';
import {
  Play,
  RotateCw,
  Clock,
  Tag,
  CheckCircle2,
} from 'lucide-react';
import { Badge } from '../common/Badge';
import type { ScenarioMeta } from '../../types/simulation';

interface ScenarioSelectorProps {
  scenarios: ScenarioMeta[];
  selectedScenarioId: string;
  onSelectScenario: (scenarioId: string) => void;
  seed: number;
  onChangeSeed: (seed: number) => void;
  isRunning: boolean;
  onRunSimulation: () => void;
}

export const ScenarioSelector: React.FC<ScenarioSelectorProps> = ({
  scenarios,
  selectedScenarioId,
  onSelectScenario,
  seed,
  onChangeSeed,
  isRunning,
  onRunSimulation,
}) => {
  const categoryVariant = (cat: string): 'neutral' | 'success' | 'warning' | 'error' => {
    switch (cat.toLowerCase()) {
      case 'baseline':
        return 'success';
      case 'throughput anomaly':
      case 'ratio anomaly':
      case 'packet rate anomaly':
        return 'error';
      case 'recovery':
      case 'trend drift':
        return 'warning';
      default:
        return 'neutral';
    }
  };

  return (
    <div className="bg-card-surface border border-border-subtle rounded-[12px] p-5 space-y-4 shadow-[var(--shadow-whisper)]">
      {/* Header and Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border-subtle">
        <div>
          <h2 className="text-sm font-semibold text-text-primary tracking-[-0.28px]">
            Simulation Scenario Selection
          </h2>
          <p className="text-xs text-text-secondary mt-0.5">
            Select a synthetic workload profile to evaluate the Isolation Forest detector under deterministic conditions
          </p>
        </div>

        {/* Action Controls: Seed & Run Button */}
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5 bg-elevated-surface px-2.5 py-1 rounded-[6px] border border-border-subtle text-xs font-mono">
            <span className="text-text-muted text-[11px]">Seed:</span>
            <input
              type="number"
              name="simulation_seed"
              value={seed}
              onChange={(e) => onChangeSeed(parseInt(e.target.value, 10) || 42)}
              disabled={isRunning}
              className="w-14 bg-transparent text-text-primary font-mono font-medium focus-visible:outline-none text-center"
              title="Deterministic random seed"
              aria-label="Simulation random seed"
            />
          </div>

          <button
            onClick={onRunSimulation}
            disabled={isRunning}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-[#171717] dark:bg-[#ededed] hover:opacity-90 text-white dark:text-black font-medium text-xs transition-opacity shadow-xs cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-text-primary"
            aria-label="Execute synthetic scenario"
          >
            {isRunning ? (
              <>
                <RotateCw className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
                <span>Simulating…</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" aria-hidden="true" />
                <span>Run Scenario</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Scenario Grid Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2.5">
        {scenarios.map((sc) => {
          const isSelected = sc.scenario_id === selectedScenarioId;
          return (
            <button
              key={sc.scenario_id}
              type="button"
              onClick={() => onSelectScenario(sc.scenario_id)}
              disabled={isRunning}
              className={`p-3.5 rounded-[12px] border text-left transition-colors cursor-pointer flex flex-col justify-between space-y-2 group relative focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-text-primary ${
                isSelected
                  ? 'bg-elevated-surface border-text-primary shadow-xs'
                  : 'bg-card-surface border-border-subtle hover:border-border-hover hover:bg-elevated-surface/50'
              }`}
              aria-pressed={isSelected}
            >
              <div>
                <div className="flex items-center justify-between gap-1 mb-1.5">
                  <Badge variant={categoryVariant(sc.category)} size="sm">
                    {sc.category}
                  </Badge>
                  <div className="flex items-center gap-1 text-[11px] font-mono text-text-muted">
                    <Clock className="w-3 h-3" aria-hidden="true" />
                    <span>{sc.duration_seconds}s</span>
                  </div>
                </div>

                <div className="text-xs font-semibold text-text-primary tracking-tight">
                  {sc.name}
                </div>

                <p className="text-xs text-text-secondary mt-1 line-clamp-2 leading-relaxed">
                  {sc.description}
                </p>
              </div>

              <div className="pt-2 border-t border-border-subtle flex items-center justify-between text-[11px] font-mono text-text-muted">
                <div className="flex items-center gap-1">
                  <Tag className="w-3 h-3" aria-hidden="true" />
                  <span>{sc.scenario_id}</span>
                </div>
                {isSelected && (
                  <span className="flex items-center gap-1 text-[#0070f3] dark:text-[#3291ff] font-medium">
                    <CheckCircle2 className="w-3 h-3" aria-hidden="true" /> Active
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
