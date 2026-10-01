import React, { useMemo } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import { useTheme } from '../../context/ThemeContext';
import type { NetworkMetric } from '../../types/metrics';

interface LiveChartProps {
  data: NetworkMetric[];
  activeInterface: string | null;
  isMonitoring: boolean;
}

const LiveChartComponent: React.FC<LiveChartProps> = ({
  data,
  activeInterface,
  isMonitoring,
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
      tooltipBg: isDark ? '#0a0a0a' : '#ffffff',
      tooltipBorder: isDark ? '#262626' : '#ebebeb',
      tooltipText: isDark ? '#ededed' : '#171717',
      tooltipMuted: isDark ? '#a1a1a1' : '#4d4d4d',
    };
  }, [isDark]);

  const chartData = useMemo(() => {
    return data.map((d) => {
      let formattedTime = d.timestamp;
      try {
        const date = new Date(d.timestamp);
        if (!isNaN(date.getTime())) {
          formattedTime = date.toLocaleTimeString('en-US', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          });
        }
      } catch {
        // fallback
      }

      return {
        time: formattedTime,
        download: d.download_mbps,
        upload: d.upload_mbps,
        txPackets: d.packets_sent_per_sec,
        rxPackets: d.packets_received_per_sec,
      };
    });
  }, [data]);

  const maxVal = useMemo(() => {
    if (chartData.length === 0) return 1.0;
    const maxNumber = Math.max(...chartData.map((d) => Math.max(d.download, d.upload)));
    return Math.max(0.5, Math.ceil(maxNumber * 1.2 * 10) / 10);
  }, [chartData]);

  const latestSample = chartData.length > 0 ? chartData[chartData.length - 1] : null;

  return (
    <div className="bg-card-surface border border-border-subtle rounded-[12px] p-5 flex flex-col shadow-[var(--shadow-whisper)]">
      {/* Chart Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 mb-3 border-b border-border-subtle">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-text-primary tracking-[-0.28px]">
              Throughput Telemetry
            </h2>
            <span className="text-[11px] font-mono text-text-muted">
              [rolling 30s]
            </span>
          </div>
          <p className="text-xs text-text-secondary mt-0.5 font-mono">
            Active adapter: <span className="font-medium text-text-primary">{activeInterface || 'None'}</span>
          </p>
        </div>

        {/* Minimal Legend with Live Readouts */}
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-[2px]" style={{ backgroundColor: chartColors.download }} aria-hidden="true" />
            <span className="text-text-secondary">Down:</span>
            <span className="text-text-primary font-semibold tabular-nums">
              {latestSample ? latestSample.download.toFixed(3) : '0.000'} Mbps
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-[2px]" style={{ backgroundColor: chartColors.upload }} aria-hidden="true" />
            <span className="text-text-secondary">Up:</span>
            <span className="text-text-primary font-semibold tabular-nums">
              {latestSample ? latestSample.upload.toFixed(3) : '0.000'} Mbps
            </span>
          </div>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="w-full h-64 md:h-72 relative">
        {chartData.length === 0 ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-6 bg-elevated-surface/30 rounded-[8px] border border-dashed border-border-subtle">
            <span className="text-xs text-text-secondary font-mono">
              {isMonitoring
                ? 'Awaiting live stream packet telemetry from host adapter…'
                : 'Telemetry collection paused. Start monitoring to resume streaming.'}
            </span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              margin={{ top: 8, right: 10, left: -20, bottom: 0 }}
            >
              <CartesianGrid
                stroke={chartColors.grid}
                strokeDasharray="2 2"
                vertical={false}
              />
              <XAxis
                dataKey="time"
                stroke={chartColors.axis}
                fontSize={10}
                tickLine={false}
                axisLine={{ stroke: chartColors.axisLine }}
                interval="preserveStartEnd"
                fontFamily="Geist Mono, monospace"
              />
              <YAxis
                stroke={chartColors.axis}
                fontSize={10}
                tickLine={false}
                axisLine={{ stroke: chartColors.axisLine }}
                domain={[0, maxVal]}
                tickFormatter={(val) => `${val}M`}
                fontFamily="Geist Mono, monospace"
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload || !payload.length) return null;
                  const item = payload[0].payload;
                  return (
                    <div
                      className="rounded-[6px] p-2.5 shadow-[var(--shadow-floating)] text-xs font-mono z-50 border"
                      style={{
                        backgroundColor: chartColors.tooltipBg,
                        borderColor: chartColors.tooltipBorder,
                        color: chartColors.tooltipText,
                      }}
                    >
                      <div
                        className="text-[10px] pb-1 mb-1.5 border-b"
                        style={{
                          borderColor: chartColors.tooltipBorder,
                          color: chartColors.tooltipMuted,
                        }}
                      >
                        {item.time}
                      </div>
                      <div className="space-y-1">
                        <div className="flex items-center justify-between gap-4 font-medium" style={{ color: chartColors.download }}>
                          <span>Download:</span>
                          <span className="tabular-nums font-semibold" style={{ color: chartColors.tooltipText }}>
                            {Number(item.download).toFixed(4)} Mbps
                          </span>
                        </div>
                        <div className="flex items-center justify-between gap-4 font-medium" style={{ color: chartColors.upload }}>
                          <span>Upload:</span>
                          <span className="tabular-nums font-semibold" style={{ color: chartColors.tooltipText }}>
                            {Number(item.upload).toFixed(4)} Mbps
                          </span>
                        </div>
                        <div
                          className="pt-1 border-t flex items-center justify-between gap-4 text-[10px]"
                          style={{
                            borderColor: chartColors.tooltipBorder,
                            color: chartColors.tooltipMuted,
                          }}
                        >
                          <span>Packet Rate:</span>
                          <span className="tabular-nums font-medium">
                            {Number(item.txPackets).toFixed(0)} Tx / {Number(item.rxPackets).toFixed(0)} Rx
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                }}
              />
              <Line
                type="monotone"
                dataKey="download"
                stroke={chartColors.download}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3.5, fill: chartColors.download, stroke: chartColors.tooltipBg }}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="upload"
                stroke={chartColors.upload}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3.5, fill: chartColors.upload, stroke: chartColors.tooltipBg }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};

export const LiveChart = React.memo(LiveChartComponent);
