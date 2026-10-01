import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  icon: LucideIcon;
  trendValue?: number;
  trendLabel?: string;
  breakdown?: React.ReactNode;
  accentColor?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  unit,
  icon: Icon,
  trendValue,
  trendLabel = 'vs prev sample',
  breakdown,
  accentColor,
}) => {
  const isPositive = trendValue !== undefined && trendValue > 0.001;
  const isNegative = trendValue !== undefined && trendValue < -0.001;
  const isNeutral = !isPositive && !isNegative;

  return (
    <div className="bg-card-surface border border-border-subtle hover:border-border-hover transition-colors rounded-[12px] p-5 flex flex-col justify-between shadow-[var(--shadow-whisper)]">
      {/* Top: Label and subtle icon */}
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-mono font-medium uppercase tracking-[0.05em] text-text-muted">
          {title}
        </span>
        <div className="p-1 rounded-[6px] bg-elevated-surface text-text-muted" aria-hidden="true">
          <Icon className="w-3.5 h-3.5" style={{ color: accentColor }} />
        </div>
      </div>

      {/* Middle: Value & Unit */}
      <div className="my-3 flex items-baseline">
        <span className="text-2xl font-semibold text-text-primary tabular-nums tracking-[-0.6px]">
          {value}
        </span>
        {unit && (
          <span className="ml-1.5 text-xs font-mono text-text-muted">
            {unit}
          </span>
        )}
      </div>

      {/* Bottom: Trend or Breakdown */}
      <div className="pt-2.5 border-t border-border-subtle flex items-center justify-between text-xs">
        {breakdown ? (
          <div className="text-text-secondary truncate w-full text-[11px] font-mono">
            {breakdown}
          </div>
        ) : trendValue !== undefined ? (
          <div className="flex items-center gap-1.5">
            {isPositive && (
              <span className="flex items-center gap-0.5 text-[#0070f3] dark:text-[#3291ff] font-medium tabular-nums font-mono text-[11px]">
                <TrendingUp className="w-3 h-3" aria-hidden="true" />
                +{trendValue.toFixed(3)}
              </span>
            )}
            {isNegative && (
              <span className="flex items-center gap-0.5 text-[#ee0000] dark:text-[#f87171] font-medium tabular-nums font-mono text-[11px]">
                <TrendingDown className="w-3 h-3" aria-hidden="true" />
                {trendValue.toFixed(3)}
              </span>
            )}
            {isNeutral && (
              <span className="flex items-center gap-0.5 text-text-muted tabular-nums font-mono text-[11px]">
                <Minus className="w-3 h-3" aria-hidden="true" />
                0.000
              </span>
            )}
            <span className="text-text-muted text-[11px] font-mono">{trendLabel}</span>
          </div>
        ) : (
          <span className="text-text-muted text-[11px] font-mono">Host telemetry</span>
        )}
      </div>
    </div>
  );
};
