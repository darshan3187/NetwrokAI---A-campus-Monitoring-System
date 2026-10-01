import React, { useMemo } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from 'recharts';
import { Activity, AlertCircle } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import type { RollingAnomalyPoint } from '../../types/metrics';

interface AnomalyTimelineProps {
  data: RollingAnomalyPoint[];
  activeInterface: string | null;
  isMonitoring: boolean;
  currentScore: number;
  currentSeverity: string;
}

const AnomalyTimelineComponent: React.FC<AnomalyTimelineProps> = ({
  data,
  activeInterface,
  isMonitoring,
  currentScore,
  currentSeverity,
}) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const chartColors = useMemo(() => {
    return {
      grid: isDark ? '#262626' : '#ebebeb',
      axis: isDark ? '#707070' : '#8f8f8f',
      axisLine: isDark ? '#262626' : '#ebebeb',
      line: isDark ? '#3291ff' : '#0070f3',
      unusualLine: isDark ? '#fbbf24' : '#f5a623',
      highLine: isDark ? '#f87171' : '#ee0000',
      tooltipBg: isDark ? '#0a0a0a' : '#ffffff',
      tooltipBorder: isDark ? '#262626' : '#ebebeb',
      tooltipText: isDark ? '#ededed' : '#171717',
      tooltipMuted: isDark ? '#a1a1a1' : '#4d4d4d',
    };
  }, [isDark]);

  const chartData = useMemo(() => {
    return data.map((d) => ({
      time: d.timeLabel || d.timestamp.slice(11, 19),
      score: Number(d.score.toFixed(3)),
      severity: d.severity,
      isAnomaly: d.isAnomaly,
      download: d.download_mbps,
      upload: d.upload_mbps,
    }));
  }, [data]);

  return (
    <div className="bg-card-surface border border-border-subtle rounded-[12px] p-5 flex flex-col shadow-[var(--shadow-whisper)]">
      {/* Chart Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 mb-3 border-b border-border-subtle">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-text-primary tracking-[-0.28px]">
              Real-Time Anomaly Score Timeline
            </h2>
            <span className="text-[11px] font-mono text-text-muted">
              [rolling 50s live]
            </span>
          </div>
          <p className="text-xs text-text-secondary mt-0.5 font-mono">
            Streaming inference on <span className="font-medium text-text-primary">{activeInterface || 'adapter'}</span>
            <span className="text-text-muted ml-1.5 hidden md:inline">(Normalized telemetry 0.00 – 1.00)</span>
          </p>
        </div>

        {/* Threshold Reference Legend */}
        <div className="flex items-center gap-3 text-xs font-mono flex-wrap">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-[2px] bg-[#0070f3]" aria-hidden="true" />
            <span className="text-text-secondary">Normal (&lt;0.6)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-[2px] bg-[#f5a623]" aria-hidden="true" />
            <span className="text-text-secondary">Unusual (&ge;0.6)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-[2px] bg-[#ee0000]" aria-hidden="true" />
            <span className="text-text-secondary">High (&ge;0.8)</span>
          </div>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="w-full h-64 md:h-72 relative">
        {chartData.length === 0 ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-6 bg-elevated-surface/30 rounded-[8px] border border-dashed border-border-subtle">
            <Activity className="w-6 h-6 text-text-muted animate-pulse mb-2" aria-hidden="true" />
            <span className="text-xs font-mono text-text-secondary">
              {isMonitoring
                ? 'Collecting live anomaly evaluation samples…'
                : 'Monitoring is paused. Start collection to stream real-time scores.'}
            </span>
            <span className="text-xs font-mono text-text-muted mt-1">
              Waiting for incoming WebSocket telemetry frames
            </span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 12, right: 12, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="scoreTimelineGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={chartColors.line} stopOpacity={0.25} />
                  <stop offset="100%" stopColor={chartColors.line} stopOpacity={0.0} />
                </linearGradient>
              </defs>

              <CartesianGrid
                strokeDasharray="3 3"
                stroke={chartColors.grid}
                vertical={false}
              />

              <XAxis
                dataKey="time"
                stroke={chartColors.axis}
                fontSize={10}
                tickLine={false}
                axisLine={{ stroke: chartColors.axisLine }}
                interval="preserveStartEnd"
                minTickGap={35}
                fontFamily="Geist Mono, monospace"
              />

              <YAxis
                domain={[0, 1.0]}
                ticks={[0.0, 0.2, 0.4, 0.6, 0.8, 1.0]}
                stroke={chartColors.axis}
                fontSize={10}
                tickLine={false}
                axisLine={{ stroke: chartColors.axisLine }}
                tickFormatter={(v) => v.toFixed(1)}
                fontFamily="Geist Mono, monospace"
              />

              {/* Threshold Indicators */}
              <ReferenceLine
                y={0.6}
                stroke={chartColors.unusualLine}
                strokeDasharray="4 4"
                strokeWidth={1}
                label={{
                  value: 'Unusual (0.60)',
                  position: 'insideTopRight',
                  fill: chartColors.unusualLine,
                  fontSize: 10,
                  fontFamily: 'Geist Mono, monospace',
                }}
              />
              <ReferenceLine
                y={0.8}
                stroke={chartColors.highLine}
                strokeDasharray="4 4"
                strokeWidth={1}
                label={{
                  value: 'High (0.80)',
                  position: 'insideTopRight',
                  fill: chartColors.highLine,
                  fontSize: 10,
                  fontFamily: 'Geist Mono, monospace',
                }}
              />

              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload || !payload.length) return null;
                  const d = payload[0].payload;
                  const isHigh = d.score >= 0.8;
                  const isUnusual = d.score >= 0.6 && !isHigh;

                  return (
                    <div
                      className="rounded-[6px] border shadow-[var(--shadow-floating)] p-2.5 text-xs font-mono space-y-1 z-50"
                      style={{
                        backgroundColor: chartColors.tooltipBg,
                        borderColor: chartColors.tooltipBorder,
                        color: chartColors.tooltipText,
                      }}
                    >
                      <div
                        className="text-[10px] pb-1 border-b flex items-center justify-between gap-4"
                        style={{
                          borderColor: chartColors.tooltipBorder,
                          color: chartColors.tooltipMuted,
                        }}
                      >
                        <span>{d.time}</span>
                        <span
                          className={`px-1.5 py-0.5 rounded-[4px] text-[10px] font-medium ${
                            isHigh
                              ? 'bg-[#ee0000]/10 text-[#ee0000] dark:text-[#f87171]'
                              : isUnusual
                              ? 'bg-[#f5a623]/10 text-[#f5a623]'
                              : 'bg-[#0070f3]/10 text-[#0070f3] dark:text-[#3291ff]'
                          }`}
                        >
                          {d.severity}
                        </span>
                      </div>
                      <div className="flex items-center justify-between gap-4 pt-1">
                        <span style={{ color: chartColors.tooltipMuted }}>Anomaly Score:</span>
                        <span className="font-bold tabular-nums">{d.score.toFixed(3)}</span>
                      </div>
                      <div
                        className="flex items-center justify-between gap-4 text-[11px]"
                        style={{ color: chartColors.tooltipMuted }}
                      >
                        <span>Throughput:</span>
                        <span className="tabular-nums font-medium">↓ {d.download.toFixed(2)} / ↑ {d.upload.toFixed(2)} Mbps</span>
                      </div>
                    </div>
                  );
                }}
              />

              <Area
                type="monotone"
                dataKey="score"
                stroke={chartColors.line}
                strokeWidth={2}
                fill="url(#scoreTimelineGradient)"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Chart Footer Note */}
      <div className="mt-3 pt-2.5 border-t border-border-subtle flex items-center justify-between text-xs text-text-secondary">
        <div className="flex items-center gap-1.5">
          <AlertCircle className="w-3.5 h-3.5 text-[#0070f3]" aria-hidden="true" />
          <span>Scores reflect continuous streaming variance against calibrated baseline parameters</span>
        </div>
        <div className="font-mono text-xs">
          Current: <span className="text-text-primary font-semibold tabular-nums">{currentScore.toFixed(3)}</span> ({currentSeverity})
        </div>
      </div>
    </div>
  );
};

export const AnomalyTimeline = React.memo(AnomalyTimelineComponent);
