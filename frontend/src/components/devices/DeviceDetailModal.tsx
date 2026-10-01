import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  X,
  Activity,
  Play,
  Square,
  RotateCw,
  AlertTriangle,
  CheckCircle2,
  ArrowUpRight,
  ArrowDownRight,
  Info,
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import { deviceApi } from '../../services/deviceApi';
import type {
  Device,
  DeviceTelemetry,
  DeviceHealthResponse,
} from '../../types/device';
import { Spinner } from '../common/Spinner';
import { useTheme } from '../../context/ThemeContext';

interface DeviceDetailModalProps {
  device: Device;
  isOpen: boolean;
  onClose: () => void;
  onDeviceUpdated?: (updated: Device) => void;
  onNotify?: (type: 'success' | 'error' | 'info', message: string) => void;
}

export const DeviceDetailModal: React.FC<DeviceDetailModalProps> = ({
  device,
  isOpen,
  onClose,
  onDeviceUpdated,
  onNotify,
}) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const [currentDevice, setCurrentDevice] = useState<Device>(device);
  const [health, setHealth] = useState<DeviceHealthResponse | null>(null);
  const [telemetryHistory, setTelemetryHistory] = useState<DeviceTelemetry[]>([]);
  const [latestTelemetry, setLatestTelemetry] = useState<DeviceTelemetry | null>(null);
  const [selectedInterface, setSelectedInterface] = useState<string>('all');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isTogglingPoll, setIsTogglingPoll] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Sync prop changes
  useEffect(() => {
    setCurrentDevice(device);
  }, [device]);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      const [healthRes, histRes] = await Promise.all([
        deviceApi.getDeviceHealth(currentDevice.id),
        deviceApi.getTelemetryHistory(
          currentDevice.id,
          50,
          selectedInterface !== 'all' ? selectedInterface : undefined
        ),
      ]);

      setHealth(healthRes);
      // History comes sorted desc; reverse for timeline display
      const records = [...histRes.telemetry].reverse();
      setTelemetryHistory(records);

      if (records.length > 0) {
        setLatestTelemetry(records[records.length - 1]);
      } else {
        setLatestTelemetry(null);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to query telemetry';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [currentDevice.id, selectedInterface]);

  useEffect(() => {
    if (isOpen) {
      setIsLoading(true);
      loadData();
      // Auto-refresh telemetry every 5s while modal is active
      const timer = setInterval(() => {
        loadData();
      }, 5000);
      return () => clearInterval(timer);
    }
  }, [isOpen, loadData]);

  // Distinct interfaces list
  const availableInterfaces = useMemo(() => {
    const set = new Set<string>();
    telemetryHistory.forEach((t) => {
      if (t.interface_name) set.add(t.interface_name);
    });
    return Array.from(set).sort();
  }, [telemetryHistory]);

  const handleToggleMonitoring = async () => {
    setIsTogglingPoll(true);
    try {
      let updated: Device;
      if (currentDevice.polling_enabled) {
        updated = await deviceApi.stopMonitoring(currentDevice.id);
        onNotify?.('info', `Stopped monitoring ${currentDevice.name}`);
      } else {
        updated = await deviceApi.startMonitoring(currentDevice.id);
        onNotify?.('success', `Initiated background polling for ${currentDevice.name}`);
      }
      setCurrentDevice(updated);
      onDeviceUpdated?.(updated);
      // Reload health & telemetry
      await loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to toggle monitoring';
      setError(msg);
      onNotify?.('error', msg);
    } finally {
      setIsTogglingPoll(false);
    }
  };

  if (!isOpen) return null;

  // Honesty Tag styling & text
  const getHonestyBanner = () => {
    if (currentDevice.collection_method === 'local_psutil') {
      return {
        type: 'local',
        title: 'Local Host Telemetry',
        description: 'Captured directly from psutil counters on this local host machine.',
        badge: 'LOCAL HOST',
        color: 'border-blue-500/30 bg-blue-500/5 text-blue-400',
      };
    }
    if (currentDevice.collection_method === 'snmp') {
      return {
        type: 'snmp',
        title: 'Remote Device Telemetry (SNMP v2c/v3)',
        description:
          'Queries authorized network hardware via read-only UDP/161 SNMP MIB-II counters. Requires campus network authorization.',
        badge: 'REMOTE SNMP',
        color: 'border-emerald-500/30 bg-emerald-500/5 text-emerald-400',
      };
    }
    return {
      type: 'mock',
      title: 'Mock / Simulated Hardware Telemetry',
      description:
        'Deterministic simulated telemetry generated in a sandbox lab. Not real live college network traffic.',
      badge: 'MOCK LAB TEST',
      color: 'border-amber-500/30 bg-amber-500/5 text-amber-400',
    };
  };

  const honesty = getHonestyBanner();

  // Colors for chart
  const chartColors = {
    grid: isDark ? '#262626' : '#ebebeb',
    axis: isDark ? '#707070' : '#8f8f8f',
    download: isDark ? '#3291ff' : '#0070f3',
    upload: isDark ? '#a78bfa' : '#7928ca',
    tooltipBg: isDark ? '#141414' : '#ffffff',
    tooltipBorder: isDark ? '#2b2b2b' : '#e5e5e5',
  };

  const chartData = telemetryHistory.map((t) => {
    let timeLabel = t.timestamp;
    try {
      const d = new Date(t.timestamp);
      timeLabel = d.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      // fallback
    }
    return {
      time: timeLabel,
      download_mbps: t.download_mbps,
      upload_mbps: t.upload_mbps,
      packets_sent: t.packets_sent_per_sec,
      packets_recv: t.packets_recv_per_sec,
      interface: t.interface_name,
    };
  });

  const computedStatus = currentDevice.computed_status || (
    currentDevice.reachability === 'reachable' ? 'online' :
    currentDevice.reachability === 'unreachable' ? 'unreachable' :
    currentDevice.monitoring_status === 'maintenance' ? 'maintenance' : 'unknown'
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/70 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="w-full max-w-4xl max-h-[92vh] flex flex-col rounded-[16px] bg-card-surface border border-border-subtle shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="p-4 sm:p-5 border-b border-border-subtle flex items-start justify-between gap-3 shrink-0 bg-elevated-surface/30">
          <div className="flex items-center gap-3 min-w-0">
            <div className="p-2.5 rounded-[10px] bg-elevated-surface border border-border-subtle shrink-0">
              <Activity className="w-5 h-5 text-accent-primary" />
            </div>
            <div className="min-w-0">
              {/* Hierarchy Breadcrumb */}
              <div className="flex items-center gap-1.5 text-[11px] font-mono text-text-muted mb-1 flex-wrap">
                <span>Campus</span>
                <span className="text-border-hover">&gt;</span>
                <span className="text-text-secondary">{currentDevice.building}</span>
                <span className="text-border-hover">&gt;</span>
                <span className="text-text-secondary">Floor {currentDevice.floor}</span>
                <span className="text-border-hover">&gt;</span>
                <span className="text-text-secondary">{currentDevice.department}</span>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-base sm:text-lg font-semibold text-text-primary truncate">
                  {currentDevice.name}
                </h3>
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-elevated-surface text-text-secondary border border-border-subtle">
                  {currentDevice.ip_address}
                </span>

                {/* Reliable Status Badge */}
                <span
                  className={`inline-flex items-center gap-1.5 text-xs font-mono font-medium px-2 py-0.5 rounded-full ${
                    computedStatus === 'online'
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : computedStatus === 'unreachable'
                      ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                      : computedStatus === 'stale'
                      ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                      : computedStatus === 'maintenance'
                      ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                      : 'bg-zinc-500/10 text-zinc-400 border border-zinc-500/20'
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      computedStatus === 'online'
                        ? 'bg-emerald-400 animate-pulse'
                        : computedStatus === 'unreachable'
                        ? 'bg-red-400'
                        : computedStatus === 'stale'
                        ? 'bg-amber-400'
                        : computedStatus === 'maintenance'
                        ? 'bg-purple-400'
                        : 'bg-zinc-400'
                    }`}
                  />
                  {computedStatus.toUpperCase()}
                </span>

                {currentDevice.is_stale && (
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/25">
                    STALE DATA
                  </span>
                )}
              </div>
              <p className="text-xs text-text-muted mt-0.5 truncate">
                {currentDevice.vendor_model ? `${currentDevice.vendor_model} • ` : ''}
                {currentDevice.location_description || `${currentDevice.department} network closet`}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-[6px] text-text-muted hover:text-text-primary hover:bg-elevated-surface transition-colors cursor-pointer shrink-0"
            title="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-4 sm:p-6 overflow-y-auto space-y-5 text-text-primary">
          {/* Honesty Classification Banner */}
          <div className={`p-3.5 rounded-[10px] border flex items-start gap-3 ${honesty.color}`}>
            <Info className="w-4 h-4 shrink-0 mt-0.5" />
            <div className="min-w-0 text-xs">
              <div className="flex items-center gap-2">
                <span className="font-semibold">{honesty.title}</span>
                <span className="text-[10px] uppercase tracking-wider font-mono font-bold px-1.5 py-0.2 rounded bg-black/20">
                  {honesty.badge}
                </span>
              </div>
              <p className="text-text-muted mt-0.5 leading-relaxed">{honesty.description}</p>
            </div>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="p-3 rounded-[8px] bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Polling Controls & Reachability Status Bar */}
          <div className="p-4 rounded-[12px] bg-elevated-surface border border-border-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-text-secondary">Background Polling:</span>
                <span
                  className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full ${
                    currentDevice.polling_enabled
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : 'bg-zinc-500/10 text-zinc-400 border border-zinc-500/20'
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      currentDevice.polling_enabled ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-400'
                    }`}
                  />
                  {currentDevice.polling_enabled ? 'ENABLED' : 'DISABLED'}
                </span>
              </div>
              <div className="flex items-center gap-3 text-[11px] text-text-muted flex-wrap">
                <span>Interval: {currentDevice.polling_interval_seconds || 10}s</span>
                {health?.last_poll_at && (
                  <span>
                    Last Poll: {new Date(health.last_poll_at).toLocaleTimeString()}
                  </span>
                )}
                {health?.last_poll_status && (
                  <span className="capitalize">
                    Status: <strong className="text-text-secondary">{health.last_poll_status}</strong>
                  </span>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleToggleMonitoring}
                disabled={isTogglingPoll}
                className={`px-3.5 py-1.5 rounded-[8px] text-xs font-medium flex items-center gap-2 transition-all cursor-pointer shadow-xs disabled:opacity-50 ${
                  currentDevice.polling_enabled
                    ? 'bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500/20'
                    : 'bg-accent-primary text-white hover:bg-accent-primary/90'
                }`}
              >
                {isTogglingPoll ? (
                  <Spinner size="sm" />
                ) : currentDevice.polling_enabled ? (
                  <>
                    <Square className="w-3.5 h-3.5 fill-current" />
                    Stop Polling
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5 fill-current" />
                    Start Polling
                  </>
                )}
              </button>

              <button
                onClick={loadData}
                disabled={isLoading}
                className="p-1.5 rounded-[8px] bg-card-surface border border-border-subtle text-text-muted hover:text-text-primary transition-colors cursor-pointer"
                title="Refresh metrics now"
              >
                <RotateCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>

          {/* Last Poll Error Banner (if error present) */}
          {health?.last_poll_error && (
            <div className="p-3 rounded-[8px] bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>Poll Warning: {health.last_poll_error}</span>
            </div>
          )}

          {/* Metrics Overview Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 rounded-[10px] bg-card-surface border border-border-subtle">
              <div className="flex items-center justify-between text-text-muted text-[11px] mb-1">
                <span>Download Rate</span>
                <ArrowDownRight className="w-3.5 h-3.5 text-blue-400" />
              </div>
              <div className="text-lg font-bold font-mono text-text-primary">
                {latestTelemetry ? `${latestTelemetry.download_mbps.toFixed(2)}` : '0.00'}
                <span className="text-xs font-normal text-text-muted ml-1">Mbps</span>
              </div>
              <span className="text-[10px] text-text-muted block mt-0.5">
                {latestTelemetry ? `${latestTelemetry.packets_recv_per_sec.toFixed(0)} pkts/s` : '—'}
              </span>
            </div>

            <div className="p-3 rounded-[10px] bg-card-surface border border-border-subtle">
              <div className="flex items-center justify-between text-text-muted text-[11px] mb-1">
                <span>Upload Rate</span>
                <ArrowUpRight className="w-3.5 h-3.5 text-purple-400" />
              </div>
              <div className="text-lg font-bold font-mono text-text-primary">
                {latestTelemetry ? `${latestTelemetry.upload_mbps.toFixed(2)}` : '0.00'}
                <span className="text-xs font-normal text-text-muted ml-1">Mbps</span>
              </div>
              <span className="text-[10px] text-text-muted block mt-0.5">
                {latestTelemetry ? `${latestTelemetry.packets_sent_per_sec.toFixed(0)} pkts/s` : '—'}
              </span>
            </div>

            <div className="p-3 rounded-[10px] bg-card-surface border border-border-subtle">
              <div className="text-text-muted text-[11px] mb-1">Interface State</div>
              <div className="text-sm font-semibold flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span className="capitalize">{latestTelemetry?.oper_status || 'Configured'}</span>
              </div>
              <span className="text-[10px] text-text-muted block mt-1 truncate">
                {latestTelemetry?.interface_name || 'All interfaces'}
              </span>
            </div>

            <div className="p-3 rounded-[10px] bg-card-surface border border-border-subtle">
              <div className="text-text-muted text-[11px] mb-1">Errors / Discards</div>
              <div className="text-sm font-mono font-semibold text-text-primary">
                {latestTelemetry
                  ? `${latestTelemetry.errors_in + latestTelemetry.errors_out} err / ${
                      latestTelemetry.discards_in + latestTelemetry.discards_out
                    } drop`
                  : '0 / 0'}
              </div>
              <span className="text-[10px] text-emerald-400 block mt-1">Normal link health</span>
            </div>
          </div>

          {/* Interface Selector Tabs */}
          {availableInterfaces.length > 1 && (
            <div className="flex items-center gap-2 overflow-x-auto pb-1">
              <span className="text-xs text-text-muted shrink-0">Interface:</span>
              <button
                onClick={() => setSelectedInterface('all')}
                className={`px-2.5 py-1 rounded-[6px] text-xs font-mono transition-colors cursor-pointer ${
                  selectedInterface === 'all'
                    ? 'bg-accent-primary text-white font-medium'
                    : 'bg-elevated-surface text-text-secondary hover:text-text-primary'
                }`}
              >
                All Interfaces
              </button>
              {availableInterfaces.map((iface) => (
                <button
                  key={iface}
                  onClick={() => setSelectedInterface(iface)}
                  className={`px-2.5 py-1 rounded-[6px] text-xs font-mono transition-colors cursor-pointer ${
                    selectedInterface === iface
                      ? 'bg-accent-primary text-white font-medium'
                      : 'bg-elevated-surface text-text-secondary hover:text-text-primary'
                  }`}
                >
                  {iface}
                </button>
              ))}
            </div>
          )}

          {/* Telemetry History Chart */}
          <div className="p-4 rounded-[12px] bg-elevated-surface border border-border-subtle">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-xs font-semibold text-text-primary uppercase tracking-wider">
                Telemetry Throughput History (Last {chartData.length} Samples)
              </h4>
              <div className="flex items-center gap-3 text-[11px]">
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#0070f3]" />
                  <span className="text-text-muted">Download (Mbps)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#7928ca]" />
                  <span className="text-text-muted">Upload (Mbps)</span>
                </div>
              </div>
            </div>

            {isLoading && chartData.length === 0 ? (
              <div className="h-60 flex flex-col items-center justify-center gap-2">
                <Spinner size="md" />
                <span className="text-xs text-text-muted">Querying device telemetry...</span>
              </div>
            ) : chartData.length === 0 ? (
              <div className="h-60 flex flex-col items-center justify-center text-center p-6 border border-dashed border-border-subtle rounded-[8px]">
                <Activity className="w-8 h-8 text-text-muted mb-2 opacity-50" />
                <h5 className="text-xs font-semibold text-text-primary mb-1">
                  No Telemetry Records Collected Yet
                </h5>
                <p className="text-xs text-text-muted max-w-sm mb-3">
                  Background polling is currently inactive for this device. Click &ldquo;Start Polling&rdquo; above
                  to initiate live rate calculations.
                </p>
                {!currentDevice.polling_enabled && (
                  <button
                    onClick={handleToggleMonitoring}
                    className="px-3 py-1.5 rounded-[6px] bg-accent-primary text-white text-xs font-medium cursor-pointer"
                  >
                    Start Polling Now
                  </button>
                )}
              </div>
            ) : (
              <div className="h-60 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                    <XAxis
                      dataKey="time"
                      stroke={chartColors.axis}
                      fontSize={10}
                      tickLine={false}
                    />
                    <YAxis
                      stroke={chartColors.axis}
                      fontSize={10}
                      tickLine={false}
                      domain={[0, 'auto']}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: chartColors.tooltipBg,
                        borderColor: chartColors.tooltipBorder,
                        borderRadius: '8px',
                        fontSize: '11px',
                        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="download_mbps"
                      name="Download Mbps"
                      stroke={chartColors.download}
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="upload_mbps"
                      name="Upload Mbps"
                      stroke={chartColors.upload}
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-3.5 sm:p-4 border-t border-border-subtle bg-elevated-surface/30 flex items-center justify-between text-xs text-text-muted shrink-0">
          <span>Device ID: <code className="font-mono text-text-secondary">{currentDevice.id}</code></span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-[8px] bg-card-surface border border-border-subtle text-text-primary hover:bg-elevated-surface transition-colors cursor-pointer font-medium text-xs"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
