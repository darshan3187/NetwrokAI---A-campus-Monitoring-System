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
import { Activity, ShieldAlert } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import type { SimulationTimelinePoint } from '../../types/simulation';

interface SimulationChartsProps {
  timeline: SimulationTimelinePoint[];
  scenarioName: string;
}

export const SimulationCharts: React.FC<SimulationChartsProps> = ({
  timeline,
  scenarioName,
}) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const chartColors = useMemo(() => {
    return {
      grid: isDark ? '#262626' : '#ebebeb',
      axis: isDark ? '#707070' : '#8f8f8f',
      axisLine: isDark ? '#262626' : '#ebebeb',
      download: isDark ? '#3291ff' : '#0070f3',
      upload: isDark ? '#a78bfa' : '#7928ca',
      score: isDark ? '#fbbf24' : '#f5a623',
      unusualLine: isDark ? '#fbbf24' : '#f5a623',
      highLine: isDark ? '#f87171' : '#ee0000',
      tooltipBg: isDark ? '#0a0a0a' : '#ffffff',
      tooltipBorder: isDark ? '#262626' : '#ebebeb',
      tooltipText: isDark ? '#ededed' : '#171717',
      tooltipMuted: isDark ? '#a1a1a1' : '#4d4d4d',
    };
  }, [isDark]);

  const chartData = useMemo(() => {
    return timeline.map((pt) => ({
      step: `T+${pt.step}s`,
      stepNum: pt.step,
      download: pt.download_mbps,
      upload: pt.upload_mbps,
      packets: pt.packets_per_sec,
      score: pt.predicted_score,
      severity: pt.predicted_severity,
      groundTruth: pt.ground_truth_anomaly,
      expectedSeverity: pt.expected_severity,
      isDetected: pt.is_detected,
      method: pt.detection_method,
      explanation: pt.explanation,
    }));
  }, [timeline]);

  return (
    <div className="space-y-4">
      {/* 1. Synthetic Telemetry Flow Chart */}
      <div className="bg-card-surface border border-border-subtle rounded-[12px] p-5 flex flex-col space-y-3 shadow-[var(--shadow-whisper)]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-border-subtle">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-text-primary" aria-hidden="true" />
            <h3 className="text-sm font-semibold text-text-primary tracking-[-0.28px]">
              Synthetic Telemetry Throughput ({scenarioName})
            </h3>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-[2px]" style={{ backgroundColor: chartColors.download }} aria-hidden="true" />
              <span className="text-text-secondary">Download (Mbps)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-[2px]" style={{ backgroundColor: chartColors.upload }} aria-hidden="true" />
              <span className="text-text-secondary">Upload (Mbps)</span>
            </div>
          </div>
        </div>

        <div className="h-60 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="simDlGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={chartColors.download} stopOpacity={0.25} />
                  <stop offset="95%" stopColor={chartColors.download} stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="simUlGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={chartColors.upload} stopOpacity={0.25} />
                  <stop offset="95%" stopColor={chartColors.upload} stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} vertical={false} />
              <XAxis dataKey="step" stroke={chartColors.axis} fontSize={10} tickLine={false} axisLine={{ stroke: chartColors.axisLine }} fontFamily="Geist Mono, monospace" />
              <YAxis stroke={chartColors.axis} fontSize={10} tickLine={false} axisLine={{ stroke: chartColors.axisLine }} unit="M" fontFamily="Geist Mono, monospace" />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (active && payload && payload.length) {
                    const d = payload[0].payload;
                    return (
                      <div
                        className="rounded-[6px] border p-2.5 shadow-[var(--shadow-floating)] text-xs font-mono space-y-1"
                        style={{
                          backgroundColor: chartColors.tooltipBg,
                          borderColor: chartColors.tooltipBorder,
                          color: chartColors.tooltipText,
                        }}
                      >
                        <div
                          className="font-semibold border-b pb-1 text-[10px]"
                          style={{
                            borderColor: chartColors.tooltipBorder,
                            color: chartColors.tooltipMuted,
                          }}
                        >
                          Step {label} (Synthetic Sample)
                        </div>
                        <div className="flex justify-between gap-4 font-medium" style={{ color: chartColors.download }}>
                          <span>Download:</span>
                          <span className="tabular-nums font-semibold" style={{ color: chartColors.tooltipText }}>{d.download.toFixed(2)} Mbps</span>
                        </div>
                        <div className="flex justify-between gap-4 font-medium" style={{ color: chartColors.upload }}>
                          <span>Upload:</span>
                          <span className="tabular-nums font-semibold" style={{ color: chartColors.tooltipText }}>{d.upload.toFixed(2)} Mbps</span>
                        </div>
                        <div className="flex justify-between gap-4 text-[11px]" style={{ color: chartColors.tooltipMuted }}>
                          <span>Packet Rate:</span>
                          <span className="tabular-nums">{d.packets.toFixed(0)} pkts/s</span>
                        </div>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Area
                type="monotone"
                dataKey="download"
                stroke={chartColors.download}
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#simDlGrad)"
                isAnimationActive={false}
              />
              <Area
                type="monotone"
                dataKey="upload"
                stroke={chartColors.upload}
                strokeWidth={1.8}
                fillOpacity={1}
                fill="url(#simUlGrad)"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 2. Isolation Forest Anomaly Score Timeline */}
      <div className="bg-card-surface border border-border-subtle rounded-[12px] p-5 flex flex-col space-y-3 shadow-[var(--shadow-whisper)]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-border-subtle">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-[#f5a623]" aria-hidden="true" />
            <h3 className="text-sm font-semibold text-text-primary tracking-[-0.28px]">
              Isolation Forest Anomaly Score Inference
            </h3>
          </div>
          <div className="flex items-center gap-3 text-xs font-mono">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-0.5" style={{ backgroundColor: chartColors.unusualLine }} aria-hidden="true" />
              <span className="text-text-secondary">0.60 Unusual Threshold</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-0.5" style={{ backgroundColor: chartColors.highLine }} aria-hidden="true" />
              <span className="text-text-secondary">0.80 High Anomaly</span>
            </div>
          </div>
        </div>

        <div className="h-60 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="scoreSimGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={chartColors.score} stopOpacity={0.25} />
                  <stop offset="95%" stopColor={chartColors.score} stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} vertical={false} />
              <XAxis dataKey="step" stroke={chartColors.axis} fontSize={10} tickLine={false} axisLine={{ stroke: chartColors.axisLine }} fontFamily="Geist Mono, monospace" />
              <YAxis stroke={chartColors.axis} fontSize={10} domain={[0, 1.0]} ticks={[0.0, 0.2, 0.4, 0.6, 0.8, 1.0]} tickLine={false} axisLine={{ stroke: chartColors.axisLine }} fontFamily="Geist Mono, monospace" />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (active && payload && payload.length) {
                    const d = payload[0].payload;
                    return (
                      <div
                        className="rounded-[6px] border p-2.5 shadow-[var(--shadow-floating)] text-xs font-mono space-y-1"
                        style={{
                          backgroundColor: chartColors.tooltipBg,
                          borderColor: chartColors.tooltipBorder,
                          color: chartColors.tooltipText,
                        }}
                      >
                        <div
                          className="font-semibold border-b pb-1 text-[10px]"
                          style={{
                            borderColor: chartColors.tooltipBorder,
                            color: chartColors.tooltipMuted,
                          }}
                        >
                          Step {label}
                        </div>
                        <div className="flex justify-between gap-4">
                          <span style={{ color: chartColors.tooltipMuted }}>Score:</span>
                          <span className="font-bold tabular-nums">{d.score.toFixed(4)}</span>
                        </div>
                        <div className="flex justify-between gap-4">
                          <span style={{ color: chartColors.tooltipMuted }}>Severity:</span>
                          <span className={d.score >= 0.8 ? 'text-[#ee0000] dark:text-[#f87171]' : d.score >= 0.6 ? 'text-[#f5a623]' : 'text-[#0070f3] dark:text-[#3291ff]'}>
                            {d.severity}
                          </span>
                        </div>
                        <div className="flex justify-between gap-4">
                          <span style={{ color: chartColors.tooltipMuted }}>Ground Truth:</span>
                          <span className={d.groundTruth ? 'text-[#ee0000] dark:text-[#f87171] font-semibold' : 'text-[#0070f3] dark:text-[#3291ff]'}>
                            {d.groundTruth ? 'Anomaly' : 'Normal'}
                          </span>
                        </div>
                        <div
                          className="text-[10px] pt-1 border-t max-w-xs leading-tight"
                          style={{
                            borderColor: chartColors.tooltipBorder,
                            color: chartColors.tooltipMuted,
                          }}
                        >
                          {d.explanation}
                        </div>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <ReferenceLine y={0.60} stroke={chartColors.unusualLine} strokeDasharray="3 3" strokeWidth={1.5} />
              <ReferenceLine y={0.80} stroke={chartColors.highLine} strokeDasharray="3 3" strokeWidth={1.5} />
              <Area
                type="monotone"
                dataKey="score"
                stroke={chartColors.score}
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#scoreSimGrad)"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 3. Expected Ground Truth vs Model Prediction Comparison Strip */}
      <div className="bg-card-surface border border-border-subtle rounded-[12px] p-5 space-y-3 shadow-[var(--shadow-whisper)]">
        <div className="flex items-center justify-between pb-2 border-b border-border-subtle">
          <div>
            <h3 className="text-sm font-semibold text-text-primary tracking-[-0.28px]">
              Ground Truth vs Detector Prediction Strip
            </h3>
            <p className="text-xs text-text-secondary mt-0.5">
              Step-by-step alignment between expected scenario labels and actual model inference
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs font-mono">
            <span className="flex items-center gap-1 text-[#0070f3] dark:text-[#3291ff] font-medium"><span className="w-2 h-2 rounded-[2px] bg-[#0070f3]" aria-hidden="true" /> Normal</span>
            <span className="flex items-center gap-1 text-[#f5a623] font-medium"><span className="w-2 h-2 rounded-[2px] bg-[#f5a623]" aria-hidden="true" /> Unusual</span>
            <span className="flex items-center gap-1 text-[#ee0000] dark:text-[#f87171] font-medium"><span className="w-2 h-2 rounded-[2px] bg-[#ee0000]" aria-hidden="true" /> Anomaly</span>
          </div>
        </div>

        {/* Visual Strip Row */}
        <div className="space-y-2">
          {/* Ground Truth Row */}
          <div>
            <div className="text-xs font-mono text-text-muted mb-1 flex items-center justify-between">
              <span>Ground Truth:</span>
              <span className="font-medium text-text-secondary tabular-nums">{timeline.filter(t => t.ground_truth_anomaly).length} Anomalous Steps</span>
            </div>
            <div className="flex h-3.5 w-full rounded-[4px] overflow-hidden gap-[1px] bg-elevated-surface p-0.5 border border-border-subtle">
              {timeline.map((pt) => (
                <div
                  key={`gt-${pt.step}`}
                  className={`flex-1 transition-colors ${
                    pt.ground_truth_anomaly ? 'bg-[#ee0000]' : 'bg-[#0070f3]/40'
                  }`}
                  title={`Step ${pt.step}: Ground Truth = ${pt.ground_truth_anomaly ? 'Anomaly' : 'Normal'}`}
                />
              ))}
            </div>
          </div>

          {/* Model Prediction Row */}
          <div>
            <div className="text-xs font-mono text-text-muted mb-1 flex items-center justify-between">
              <span>Model Prediction:</span>
              <span className="font-medium text-text-secondary tabular-nums">{timeline.filter(t => t.is_detected).length} Detected Steps</span>
            </div>
            <div className="flex h-3.5 w-full rounded-[4px] overflow-hidden gap-[1px] bg-elevated-surface p-0.5 border border-border-subtle">
              {timeline.map((pt) => (
                <div
                  key={`pred-${pt.step}`}
                  className={`flex-1 transition-colors ${
                    pt.predicted_score >= 0.80
                      ? 'bg-[#ee0000]'
                      : pt.predicted_score >= 0.60
                      ? 'bg-[#f5a623]'
                      : 'bg-[#0070f3]/40'
                  }`}
                  title={`Step ${pt.step}: Predicted = ${pt.predicted_severity} (Score: ${pt.predicted_score.toFixed(3)})`}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
