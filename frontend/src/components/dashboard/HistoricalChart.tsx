import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import {
  RotateCw,
  Database,
} from 'lucide-react';
import { api } from '../../services/api';
import type { NetworkMetric } from '../../types/metrics';
import { Spinner } from '../common/Spinner';
import { useTheme } from '../../context/ThemeContext';

interface HistoricalChartProps {
  currentInterface: string | null;
}

export const HistoricalChart: React.FC<HistoricalChartProps> = ({ currentInterface }) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const [history, setHistory] = useState<NetworkMetric[]>([]);
  const [limit, setLimit] = useState<number>(50);
  const [selectedInterface, setSelectedInterface] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHistoricalData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.getHistory({
        interface: selectedInterface || undefined,
        limit,
      });
      const chronological = [...(res.metrics || [])].reverse();
      setHistory(chronological);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to query historical metrics';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [limit, selectedInterface]);

  useEffect(() => {
    fetchHistoricalData();
  }, [fetchHistoricalData]);

  useEffect(() => {
    if (currentInterface && !selectedInterface) {
      setSelectedInterface(currentInterface);
    }
  }, [currentInterface, selectedInterface]);

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

  const chartData = history.map((item) => {
    let timeLabel = item.timestamp;
    try {
      const date = new Date(item.timestamp);
      if (!isNaN(date.getTime())) {
        timeLabel = date.toLocaleTimeString('en-US', {
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
      id: item.id,
      time: timeLabel,
      download: item.download_mbps,
      upload: item.upload_mbps,
      txPackets: item.packets_sent_per_sec,
      rxPackets: item.packets_received_per_sec,
      sessionMB: item.session_transferred_mb,
      interface: item.interface,
    };
  });

  return (
    <div className="bg-card-surface border border-border-subtle rounded-[12px] p-5 flex flex-col space-y-4 shadow-[var(--shadow-whisper)]">
      {/* Top Header & Range Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border-subtle">
        <div>
          <h2 className="text-sm font-semibold text-text-primary tracking-[-0.28px]">
            Persisted Telemetry History
          </h2>
          <p className="text-xs text-text-secondary mt-0.5">
            Historical samples retrieved from local SQLite database
          </p>
        </div>

        {/* Range Controls */}
        <div className="flex items-center gap-1.5">
          <div className="flex rounded-[6px] border border-border-subtle bg-elevated-surface p-0.5 text-xs font-mono">
            {[25, 50, 100, 250].map((num) => (
              <button
                key={num}
                onClick={() => setLimit(num)}
                className={`px-2.5 py-1 rounded-[4px] text-xs transition-colors cursor-pointer tabular-nums focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-text-primary ${
                  limit === num
                    ? 'bg-card-surface text-text-primary font-semibold shadow-xs'
                    : 'text-text-muted hover:text-text-primary'
                }`}
                aria-pressed={limit === num}
              >
                {num}
              </button>
            ))}
          </div>

          <button
            onClick={fetchHistoricalData}
            disabled={isLoading}
            className="p-1.5 rounded-[6px] border border-border-subtle text-text-secondary hover:text-text-primary hover:bg-elevated-surface active:scale-95 transition-transform cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-text-primary"
            title="Reload SQLite records"
            aria-label="Reload historical records"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-[#0070f3]' : ''}`} aria-hidden="true" />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-[#ee0000]/10 border border-[#ee0000]/25 rounded-[6px] text-xs text-[#ee0000] dark:text-[#f87171] flex items-center justify-between">
          <span>Failed to query database: {error}</span>
          <button onClick={fetchHistoricalData} className="underline hover:opacity-80 cursor-pointer">
            Retry
          </button>
        </div>
      )}

      {/* Historical Area Chart */}
      <div className="w-full h-60 md:h-64 relative">
        {isLoading ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-card-surface/50 rounded-[8px]">
            <Spinner size="sm" className="mb-2" />
            <span className="text-xs font-mono text-text-secondary">Querying historical samples…</span>
          </div>
        ) : chartData.length === 0 ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-elevated-surface/30 rounded-[8px] border border-dashed border-border-subtle text-center p-6">
            <Database className="w-6 h-6 text-text-muted mb-2" aria-hidden="true" />
            <span className="text-xs font-mono text-text-secondary">
              No historical records in database
            </span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 8, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="historyDownloadGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={chartColors.download} stopOpacity={0.25} />
                  <stop offset="95%" stopColor={chartColors.download} stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="historyUploadGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={chartColors.upload} stopOpacity={0.25} />
                  <stop offset="95%" stopColor={chartColors.upload} stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="2 2" stroke={chartColors.grid} vertical={false} />
              <XAxis dataKey="time" stroke={chartColors.axis} fontSize={10} tickLine={false} axisLine={{ stroke: chartColors.axisLine }} fontFamily="Geist Mono, monospace" />
              <YAxis stroke={chartColors.axis} fontSize={10} tickLine={false} axisLine={{ stroke: chartColors.axisLine }} tickFormatter={(v) => `${v}M`} fontFamily="Geist Mono, monospace" />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload || !payload.length) return null;
                  const item = payload[0].payload;
                  return (
                    <div
                      className="rounded-[6px] p-2.5 shadow-[var(--shadow-floating)] text-xs font-mono border"
                      style={{
                        backgroundColor: chartColors.tooltipBg,
                        borderColor: chartColors.tooltipBorder,
                        color: chartColors.tooltipText,
                      }}
                    >
                      <div
                        className="text-[10px] pb-1 mb-1 border-b"
                        style={{
                          borderColor: chartColors.tooltipBorder,
                          color: chartColors.tooltipMuted,
                        }}
                      >
                        {item.time} ({item.interface})
                      </div>
                      <div className="space-y-1">
                        <div className="flex items-center justify-between gap-3 font-medium" style={{ color: chartColors.download }}>
                          <span>Down:</span>
                          <span className="font-semibold tabular-nums" style={{ color: chartColors.tooltipText }}>
                            {item.download.toFixed(4)} Mbps
                          </span>
                        </div>
                        <div className="flex items-center justify-between gap-3 font-medium" style={{ color: chartColors.upload }}>
                          <span>Up:</span>
                          <span className="font-semibold tabular-nums" style={{ color: chartColors.tooltipText }}>
                            {item.upload.toFixed(4)} Mbps
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                }}
              />
              <Area
                type="monotone"
                dataKey="download"
                stroke={chartColors.download}
                strokeWidth={1.5}
                fillOpacity={1}
                fill="url(#historyDownloadGradient)"
              />
              <Area
                type="monotone"
                dataKey="upload"
                stroke={chartColors.upload}
                strokeWidth={1.5}
                fillOpacity={1}
                fill="url(#historyUploadGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Historical Data Table */}
      {chartData.length > 0 && (
        <div className="overflow-x-auto rounded-[8px] border border-border-subtle max-h-56 overflow-y-auto">
          <table className="w-full text-left text-xs font-mono text-text-primary">
            <thead className="bg-elevated-surface text-text-muted uppercase text-[10px] sticky top-0 border-b border-border-subtle font-medium tracking-[0.05em]">
              <tr>
                <th className="py-2 px-3 font-semibold">ID</th>
                <th className="py-2 px-3 font-semibold">Timestamp</th>
                <th className="py-2 px-3 font-semibold">Adapter</th>
                <th className="py-2 px-3 font-semibold">Download</th>
                <th className="py-2 px-3 font-semibold">Upload</th>
                <th className="py-2 px-3 font-semibold">Packets (Tx/Rx)</th>
                <th className="py-2 px-3 font-semibold">Session MB</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle bg-card-surface">
              {chartData.slice().reverse().map((row, idx) => (
                <tr key={row.id ?? `metric-${idx}`} className="hover:bg-elevated-surface/50 transition-colors">
                  <td className="py-1.5 px-3 text-text-muted font-mono">#{row.id}</td>
                  <td className="py-1.5 px-3 text-text-secondary font-mono text-[11px]">{row.time}</td>
                  <td className="py-1.5 px-3 text-[#0070f3] dark:text-[#3291ff] font-medium">{row.interface}</td>
                  <td className="py-1.5 px-3 font-medium tabular-nums">{row.download.toFixed(4)} Mbps</td>
                  <td className="py-1.5 px-3 font-medium tabular-nums">{row.upload.toFixed(4)} Mbps</td>
                  <td className="py-1.5 px-3 text-text-secondary tabular-nums">
                    {row.txPackets.toFixed(0)} / {row.rxPackets.toFixed(0)}
                  </td>
                  <td className="py-1.5 px-3 text-text-secondary tabular-nums">{row.sessionMB.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
