import React from 'react';
import {
  Radio,
  Play,
  Pause,
  ArrowDownCircle,
  ArrowUpCircle,
  HardDrive,
  Activity,
  Info,
} from 'lucide-react';
import type {
  InterfaceDetail,
  NetworkMetric,
} from '../../types/metrics';
import { MetricCard } from '../dashboard/MetricCard';
import { LiveChart } from '../dashboard/LiveChart';
import { InterfacePanel } from '../dashboard/InterfacePanel';

interface LiveMonitorTabProps {
  metrics: NetworkMetric | null;
  rollingHistory: NetworkMetric[];
  interfaces: InterfaceDetail[];
  activeInterface: string | null;
  isMonitoring: boolean;
  isSwitching: boolean;
  downloadTrend?: number;
  uploadTrend?: number;
  onSelectInterface: (name: string) => void;
  onToggleMonitoring: (start: boolean) => void;
}

export const LiveMonitorTab: React.FC<LiveMonitorTabProps> = ({
  metrics,
  rollingHistory,
  interfaces,
  activeInterface,
  isMonitoring,
  isSwitching,
  downloadTrend,
  uploadTrend,
  onSelectInterface,
  onToggleMonitoring,
}) => {
  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Clean Host Telemetry Banner */}
      <div className="p-4 rounded-[8px] bg-card-surface border border-border-subtle space-y-2">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-[6px] bg-[#0070f3]/10 text-[#0070f3] flex items-center justify-center">
              <Radio className="w-4 h-4" />
            </div>
            <div>
              <h1 className="text-base font-bold text-text-primary tracking-tight">
                Local Host Network Telemetry
              </h1>
              <p className="text-xs text-text-secondary">
                Hardware NIC activity on this workstation via Python <code className="font-mono text-text-primary">psutil</code>.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
              Active Host Telemetry
            </span>
            <button
              onClick={() => onToggleMonitoring(!isMonitoring)}
              className={`px-3 py-1.5 rounded-[6px] text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer ${
                isMonitoring
                  ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400 hover:bg-rose-500/20 border border-rose-500/25'
                  : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/20 border border-emerald-500/25'
              }`}
            >
              {isMonitoring ? (
                <>
                  <Pause className="w-3.5 h-3.5" />
                  <span>Pause Telemetry</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" />
                  <span>Resume Telemetry</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Local scope note */}
        <div className="text-[11px] text-text-muted bg-elevated-surface px-3 py-1.5 rounded-[6px] border border-border-subtle flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Info className="w-3.5 h-3.5 text-[#0070f3] shrink-0" />
            <span>
              <strong>Workstation Scope:</strong> Real-time NIC counters for local throughput monitoring. Offline benchmark evaluations and model training remain isolated from live network streams.
            </span>
          </div>
        </div>
      </div>

      {/* Primary Telemetry Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Download Throughput"
          value={metrics ? metrics.download_mbps : 0}
          unit="Mbps"
          trendValue={downloadTrend}
          icon={ArrowDownCircle}
          accentColor="#0070f3"
          breakdown={
            metrics
              ? `${(metrics.download_mbps / 8).toFixed(2)} MB/s transfer rate`
              : 'Awaiting telemetry tick...'
          }
        />

        <MetricCard
          title="Upload Throughput"
          value={metrics ? metrics.upload_mbps : 0}
          unit="Mbps"
          trendValue={uploadTrend}
          icon={ArrowUpCircle}
          accentColor="#7928ca"
          breakdown={
            metrics
              ? `${(metrics.upload_mbps / 8).toFixed(2)} MB/s transfer rate`
              : 'Awaiting telemetry tick...'
          }
        />

        <MetricCard
          title="Packet Frequency"
          value={
            metrics
              ? Math.round(metrics.packets_sent_per_sec + metrics.packets_received_per_sec)
              : 0
          }
          unit="pkts/s"
          icon={Activity}
          accentColor="#10b981"
          breakdown={
            metrics
              ? `${Math.round(metrics.packets_received_per_sec)} in / ${Math.round(metrics.packets_sent_per_sec)} out`
              : 'Awaiting packet stats...'
          }
        />

        <MetricCard
          title="Session Volume"
          value={metrics ? metrics.session_transferred_mb : 0}
          unit="MB"
          icon={HardDrive}
          accentColor="#94a3b8"
          breakdown="Cumulative session telemetry"
        />
      </div>

      {/* Real-time Streaming Chart & Interface Selector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-8">
          <LiveChart
            data={rollingHistory}
            activeInterface={activeInterface}
            isMonitoring={isMonitoring}
          />
        </div>

        <div className="lg:col-span-4">
          <InterfacePanel
            interfaces={interfaces}
            activeInterface={activeInterface}
            isMonitoring={isMonitoring}
            isSwitching={isSwitching}
            onSelectInterface={onSelectInterface}
            onToggleMonitoring={onToggleMonitoring}
          />
        </div>
      </div>
    </div>
  );
};
