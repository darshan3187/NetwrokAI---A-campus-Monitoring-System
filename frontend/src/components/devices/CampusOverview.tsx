import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Building2,
  Server,
  Wifi,
  Layers,
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  AlertTriangle,
  RotateCw,
  Search,
  ChevronRight,
  ChevronDown,
  Info,
  Shield,
  ExternalLink,
  SlidersHorizontal,
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
import { DeviceDetailModal } from './DeviceDetailModal';
import type {
  CampusTelemetrySummary,
  CampusHierarchyResponse,
  CampusTimelineResponse,
  DeviceComparisonResponse,
  CampusDeviceNode,
  Device,
  DeviceType,
  ComputedStatus,
} from '../../types/device';
import { Spinner } from '../common/Spinner';
import { useTheme } from '../../context/ThemeContext';

interface CampusOverviewProps {
  onNavigateToDevices?: () => void;
  onNotify?: (type: 'success' | 'error' | 'info', message: string) => void;
}

export const CampusOverview: React.FC<CampusOverviewProps> = ({
  onNavigateToDevices,
  onNotify,
}) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  // Core Data States
  const [summary, setSummary] = useState<CampusTelemetrySummary | null>(null);
  const [hierarchy, setHierarchy] = useState<CampusHierarchyResponse | null>(null);
  const [timeline, setTimeline] = useState<CampusTimelineResponse | null>(null);
  const [comparison, setComparison] = useState<DeviceComparisonResponse | null>(null);

  // Loading & Error States
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [timelineLoading, setTimelineLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Time Range Selector for Timeline (hours)
  const [selectedHours, setSelectedHours] = useState<number>(1);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);

  // Hierarchy UI States (collapsible nodes)
  const [expandedBuildings, setExpandedBuildings] = useState<Record<string, boolean>>({});
  const [expandedFloors, setExpandedFloors] = useState<Record<string, boolean>>({});
  const [expandedDepts, setExpandedDepts] = useState<Record<string, boolean>>({});

  // Filtering for Hierarchy & Comparison
  const [filterSearch, setFilterSearch] = useState<string>('');
  const [filterBuilding, setFilterBuilding] = useState<string>('all');
  const [filterFloor, setFilterFloor] = useState<string>('all');
  const [filterDept, setFilterDept] = useState<string>('all');
  const [filterType, setFilterType] = useState<string>('all');
  const [filterStatus, setFilterStatus] = useState<string>('all');

  // Active Device Modal State
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState<boolean>(false);

  // Fetch all primary campus metrics
  const fetchCampusData = useCallback(async (isSilent = false) => {
    if (!isSilent) setIsLoading(true);
    else setIsRefreshing(true);
    setError(null);

    try {
      const [sumRes, hierRes, compRes] = await Promise.all([
        deviceApi.getCampusTelemetrySummary(),
        deviceApi.getHierarchy(),
        deviceApi.getComparison(),
      ]);

      setSummary(sumRes);
      setHierarchy(hierRes);
      setComparison(compRes);

      // Auto-expand all buildings on initial load
      if (hierRes && hierRes.buildings.length > 0) {
        setExpandedBuildings((prev) => {
          if (Object.keys(prev).length === 0) {
            const initial: Record<string, boolean> = {};
            hierRes.buildings.forEach((b) => {
              initial[b.building] = true;
            });
            return initial;
          }
          return prev;
        });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to query campus telemetry data';
      setError(msg);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  // Fetch timeline separately (dependent on selected time window)
  const fetchTimelineData = useCallback(async (hours: number) => {
    setTimelineLoading(true);
    try {
      const timelineRes = await deviceApi.getTimeline(hours);
      setTimeline(timelineRes);
    } catch (err: unknown) {
      console.warn('Failed to load campus timeline data:', err);
    } finally {
      setTimelineLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchCampusData();
  }, [fetchCampusData]);

  // Window changes
  useEffect(() => {
    fetchTimelineData(selectedHours);
  }, [selectedHours, fetchTimelineData]);

  // Auto-refresh timer every 10 seconds
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      fetchCampusData(true);
      fetchTimelineData(selectedHours);
    }, 10000);
    return () => clearInterval(interval);
  }, [autoRefresh, selectedHours, fetchCampusData, fetchTimelineData]);

  // Handlers for accordion expansion
  const toggleBuilding = (b: string) => {
    setExpandedBuildings((prev) => ({ ...prev, [b]: !prev[b] }));
  };

  const toggleFloor = (key: string) => {
    setExpandedFloors((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleDept = (key: string) => {
    setExpandedDepts((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  // Open detail modal for a device node or comparison item
  const handleOpenDetail = async (deviceId: string) => {
    try {
      const dev = await deviceApi.getDevice(deviceId);
      setSelectedDevice(dev);
      setIsDetailModalOpen(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve device details';
      onNotify?.('error', msg);
    }
  };

  // Derive distinct buildings, floors, departments for filter select dropdowns
  const filterOptions = useMemo(() => {
    const buildings = new Set<string>();
    const floors = new Set<string>();
    const depts = new Set<string>();

    if (hierarchy?.buildings) {
      hierarchy.buildings.forEach((b) => {
        buildings.add(b.building);
        b.floors.forEach((f) => {
          floors.add(f.floor);
          f.departments.forEach((d) => {
            depts.add(d.department);
          });
        });
      });
    }

    return {
      buildings: Array.from(buildings).sort(),
      floors: Array.from(floors).sort(),
      departments: Array.from(depts).sort(),
    };
  }, [hierarchy]);

  // Filter comparison items
  const filteredComparisonDevices = useMemo(() => {
    if (!comparison?.devices) return [];
    return comparison.devices.filter((dev) => {
      if (filterSearch) {
        const q = filterSearch.toLowerCase();
        const matches =
          dev.name.toLowerCase().includes(q) ||
          dev.ip_address.toLowerCase().includes(q) ||
          dev.building.toLowerCase().includes(q) ||
          dev.department.toLowerCase().includes(q);
        if (!matches) return false;
      }
      if (filterBuilding !== 'all' && dev.building !== filterBuilding) return false;
      if (filterFloor !== 'all' && dev.floor !== filterFloor) return false;
      if (filterDept !== 'all' && dev.department !== filterDept) return false;
      if (filterType !== 'all' && dev.device_type !== filterType) return false;
      if (filterStatus !== 'all' && dev.computed_status !== filterStatus) return false;
      return true;
    });
  }, [comparison, filterSearch, filterBuilding, filterFloor, filterDept, filterType, filterStatus]);

  // Chart styling constants
  const chartColors = {
    grid: isDark ? '#262626' : '#ebebeb',
    axis: isDark ? '#707070' : '#8f8f8f',
    download: isDark ? '#3291ff' : '#0070f3',
    upload: isDark ? '#a78bfa' : '#7928ca',
    devices: isDark ? '#50e3c2' : '#10b981',
    tooltipBg: isDark ? '#141414' : '#ffffff',
    tooltipBorder: isDark ? '#2b2b2b' : '#e5e5e5',
  };

  const chartData = useMemo(() => {
    if (!timeline?.timeline) return [];
    return timeline.timeline.map((pt) => {
      let formattedTime = pt.timestamp;
      try {
        const d = new Date(pt.timestamp);
        formattedTime =
          selectedHours > 24
            ? d.toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
            : d.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit' });
      } catch {
        // fallback
      }
      return {
        time: formattedTime,
        download_mbps: pt.download_mbps,
        upload_mbps: pt.upload_mbps,
        devices: pt.reporting_devices,
      };
    });
  }, [timeline, selectedHours]);

  const renderDeviceTypeIcon = (type: DeviceType) => {
    switch (type) {
      case 'router':
        return <Activity className="w-4 h-4 text-blue-400" />;
      case 'switch':
        return <Layers className="w-4 h-4 text-purple-400" />;
      case 'access_point':
        return <Wifi className="w-4 h-4 text-emerald-400" />;
      case 'server':
        return <Server className="w-4 h-4 text-amber-400" />;
      default:
        return <Server className="w-4 h-4 text-zinc-400" />;
    }
  };

  const renderStatusBadge = (status: ComputedStatus, isStale?: boolean) => {
    switch (status) {
      case 'online':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            ONLINE
          </span>
        );
      case 'unreachable':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-red-500/10 text-red-400 border border-red-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
            UNREACHABLE
          </span>
        );
      case 'stale':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            STALE
          </span>
        );
      case 'maintenance':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-400" />
            MAINTENANCE
          </span>
        );
      case 'unknown':
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-zinc-500/10 text-zinc-400 border border-zinc-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-zinc-400" />
            {isStale ? 'STALE' : 'UNKNOWN'}
          </span>
        );
    }
  };

  const renderMethodBadge = (method: string) => {
    if (method === 'snmp') {
      return (
        <span className="text-[9px] font-mono uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/25">
          SNMP
        </span>
      );
    }
    if (method === 'local_psutil') {
      return (
        <span className="text-[9px] font-mono uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/25">
          LOCAL
        </span>
      );
    }
    return (
      <span className="text-[9px] font-mono uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/25">
        MOCK LAB
      </span>
    );
  };

  // Check if a device matches filter criteria
  const isDeviceVisible = (d: CampusDeviceNode) => {
    if (filterSearch) {
      const q = filterSearch.toLowerCase();
      const match =
        d.name.toLowerCase().includes(q) ||
        d.ip_address.toLowerCase().includes(q) ||
        (d.vendor_model && d.vendor_model.toLowerCase().includes(q));
      if (!match) return false;
    }
    if (filterType !== 'all' && d.device_type !== filterType) return false;
    if (filterStatus !== 'all' && d.computed_status !== filterStatus) return false;
    return true;
  };

  return (
    <div className="space-y-6">
      {/* 1. Header & Honesty Notice */}
      <div className="p-4 sm:p-5 rounded-[12px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)] flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <h2 className="text-base sm:text-lg font-semibold text-text-primary tracking-[-0.3px]">
              Campus Network Operations Center (NOC)
            </h2>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/25 font-medium">
              Phase 3 Integrated
            </span>
          </div>
          <p className="text-xs text-text-secondary mt-1">
            Aggregated cross-campus telemetry across buildings, floors, and departmental network routers, switches, and access points.
          </p>
        </div>

        {/* Controls: Auto-refresh & Manual Refresh */}
        <div className="flex items-center gap-3 shrink-0 flex-wrap">
          <label className="flex items-center gap-2 text-xs text-text-secondary cursor-pointer select-none">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded border-border-subtle text-accent-primary focus:ring-accent-primary w-3.5 h-3.5"
            />
            <span>Auto-refresh (10s)</span>
          </label>

          <button
            onClick={() => {
              fetchCampusData(true);
              fetchTimelineData(selectedHours);
            }}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] bg-elevated-surface border border-border-subtle text-xs font-medium text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>Refresh Telemetry</span>
          </button>
        </div>
      </div>

      {/* 2. Honesty Classification Banner (Separating Local Host vs SNMP vs Mock) */}
      <div className="p-3.5 rounded-[10px] bg-elevated-surface/50 border border-border-subtle flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
        <div className="flex items-start md:items-center gap-2.5">
          <Shield className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5 md:mt-0" />
          <div className="text-text-secondary leading-relaxed">
            <strong className="text-text-primary">Telemetry Integrity Guarantee:</strong> Local host data is retrieved via psutil. Authorized remote devices use read-only SNMP (UDP/161). Simulated hardware is explicitly badged as <code className="text-amber-400 font-mono">MOCK LAB</code> to ensure real campus operations are never misrepresented.
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
            LOCAL PSUTIL
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            REMOTE SNMP
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
            MOCK LAB
          </span>
        </div>
      </div>

      {/* Global Error Banner */}
      {error && (
        <div className="p-3.5 rounded-[10px] bg-red-500/10 border border-red-500/25 text-red-400 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => fetchCampusData()}
            className="underline font-mono cursor-pointer hover:opacity-80"
          >
            Retry
          </button>
        </div>
      )}

      {/* 3. KPI Metrics Grid */}
      {isLoading ? (
        <div className="h-44 flex flex-col items-center justify-center gap-2 rounded-[12px] bg-card-surface border border-border-subtle">
          <Spinner size="md" />
          <span className="text-xs font-mono text-text-secondary">Aggregating campus telemetry metrics…</span>
        </div>
      ) : !summary || summary.total_devices === 0 ? (
        /* Empty State */
        <div className="p-12 rounded-[12px] bg-card-surface border border-border-subtle text-center flex flex-col items-center justify-center shadow-[var(--shadow-whisper)]">
          <div className="w-12 h-12 rounded-full bg-elevated-surface border border-border-subtle flex items-center justify-center mb-3 text-text-muted">
            <Building2 className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-text-primary">
            No Campus Devices Registered
          </h3>
          <p className="text-xs text-text-secondary mt-1 max-w-md">
            To view campus-wide aggregate telemetry, reachability status, and topological hierarchy, register your college routers, switches, and access points.
          </p>
          {onNavigateToDevices && (
            <button
              onClick={onNavigateToDevices}
              className="mt-4 flex items-center gap-1.5 px-4 py-1.5 rounded-[8px] bg-accent-primary hover:bg-accent-primary/90 text-white text-xs font-medium cursor-pointer shadow-xs"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>Go to Device Inventory</span>
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {/* Total Devices */}
            <div className="p-3.5 rounded-[10px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)]">
              <span className="text-[11px] text-text-muted font-medium block">Total Registered</span>
              <div className="mt-1 text-2xl font-bold font-mono text-text-primary">
                {summary.total_devices}
              </div>
              <span className="text-[10px] text-text-muted block mt-1">
                {summary.polling_enabled_count} actively polled
              </span>
            </div>

            {/* Online Devices */}
            <div className="p-3.5 rounded-[10px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)]">
              <span className="text-[11px] text-text-muted font-medium block">Online & Healthy</span>
              <div className="mt-1 text-2xl font-bold font-mono text-emerald-400">
                {summary.online_count}
              </div>
              <span className="text-[10px] text-emerald-400/80 block mt-1">
                Recent successful poll
              </span>
            </div>

            {/* Unreachable Devices */}
            <div className="p-3.5 rounded-[10px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)]">
              <span className="text-[11px] text-text-muted font-medium block">Unreachable</span>
              <div className="mt-1 text-2xl font-bold font-mono text-red-400">
                {summary.unreachable_count}
              </div>
              <span className="text-[10px] text-red-400/80 block mt-1">
                {summary.total_polling_errors} total poll failures
              </span>
            </div>

            {/* Stale / Unknown */}
            <div className="p-3.5 rounded-[10px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)]">
              <span className="text-[11px] text-text-muted font-medium block">Stale / Standby</span>
              <div className="mt-1 text-2xl font-bold font-mono text-amber-400">
                {summary.stale_count + summary.unknown_count}
              </div>
              <span className="text-[10px] text-amber-400/80 block mt-1">
                {summary.stale_count} stale, {summary.unknown_count} unpolled
              </span>
            </div>

            {/* Aggregate Download Throughput */}
            <div className="p-3.5 rounded-[10px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)]">
              <div className="flex items-center justify-between text-[11px] text-text-muted font-medium">
                <span>Aggregate Rx</span>
                <ArrowDownRight className="w-3.5 h-3.5 text-blue-400" />
              </div>
              <div className="mt-1 text-2xl font-bold font-mono text-text-primary">
                {summary.latest_campus_download_mbps.toFixed(2)}
                <span className="text-xs font-normal text-text-muted ml-1">Mbps</span>
              </div>
              <span className="text-[10px] text-text-muted block mt-1">
                Campus fleet download
              </span>
            </div>

            {/* Aggregate Upload Throughput */}
            <div className="p-3.5 rounded-[10px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)]">
              <div className="flex items-center justify-between text-[11px] text-text-muted font-medium">
                <span>Aggregate Tx</span>
                <ArrowUpRight className="w-3.5 h-3.5 text-purple-400" />
              </div>
              <div className="mt-1 text-2xl font-bold font-mono text-text-primary">
                {summary.latest_campus_upload_mbps.toFixed(2)}
                <span className="text-xs font-normal text-text-muted ml-1">Mbps</span>
              </div>
              <span className="text-[10px] text-text-muted block mt-1">
                Campus fleet upload
              </span>
            </div>
          </div>

          {/* 4. Campus-Wide Throughput Timeline */}
          <div className="p-4 sm:p-5 rounded-[12px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)] space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-text-primary tracking-[-0.2px] flex items-center gap-2">
                  <Activity className="w-4 h-4 text-accent-primary" />
                  Campus Fleet Aggregate Throughput Timeline
                </h3>
                <p className="text-xs text-text-muted mt-0.5">
                  Summed download & upload rates across reporting devices without double-counting interface deltas.
                </p>
              </div>

              {/* Range Selector */}
              <div className="flex items-center gap-1 p-0.5 rounded-[6px] bg-elevated-surface border border-border-subtle text-xs self-start sm:self-auto">
                {[
                  { label: '1h', hours: 1 },
                  { label: '6h', hours: 6 },
                  { label: '24h', hours: 24 },
                  { label: '7d', hours: 168 },
                ].map((range) => (
                  <button
                    key={range.hours}
                    onClick={() => setSelectedHours(range.hours)}
                    className={`px-2.5 py-1 rounded-[4px] font-mono transition-colors cursor-pointer ${
                      selectedHours === range.hours
                        ? 'bg-card-surface text-text-primary shadow-xs font-semibold'
                        : 'text-text-secondary hover:text-text-primary'
                    }`}
                  >
                    {range.label}
                  </button>
                ))}
              </div>
            </div>

            {timelineLoading && chartData.length === 0 ? (
              <div className="h-64 flex flex-col items-center justify-center gap-2">
                <Spinner size="md" />
                <span className="text-xs font-mono text-text-muted">Loading timeline samples…</span>
              </div>
            ) : chartData.length === 0 ? (
              <div className="h-64 flex flex-col items-center justify-center text-center p-6 border border-dashed border-border-subtle rounded-[8px]">
                <Activity className="w-8 h-8 text-text-muted mb-2 opacity-50" />
                <h4 className="text-xs font-semibold text-text-primary mb-1">
                  No Historical Campus Telemetry Available
                </h4>
                <p className="text-xs text-text-muted max-w-sm mb-3">
                  Start background polling on registered devices to collect multi-device time-series telemetry.
                </p>
              </div>
            ) : (
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 5, right: 15, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                    <XAxis dataKey="time" stroke={chartColors.axis} fontSize={10} tickLine={false} />
                    <YAxis stroke={chartColors.axis} fontSize={10} tickLine={false} domain={[0, 'auto']} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: chartColors.tooltipBg,
                        borderColor: chartColors.tooltipBorder,
                        borderRadius: '8px',
                        fontSize: '11px',
                        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                      }}
                      formatter={(val: any, name: any) => [
                        `${Number(val ?? 0).toFixed(3)} Mbps`,
                        name === 'download_mbps' ? 'Campus Download' : 'Campus Upload',
                      ]}
                    />
                    <Line
                      type="monotone"
                      dataKey="download_mbps"
                      name="download_mbps"
                      stroke={chartColors.download}
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="upload_mbps"
                      name="upload_mbps"
                      stroke={chartColors.upload}
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            <div className="pt-2 border-t border-border-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[11px] text-text-muted">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-[#0070f3]" />
                  <span>Campus Download (Mbps)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-[#7928ca]" />
                  <span>Campus Upload (Mbps)</span>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <Info className="w-3.5 h-3.5" />
                <span>
                  Samples aggregated into {selectedHours <= 1 ? '1m' : selectedHours <= 6 ? '5m' : '15m'} buckets.
                </span>
              </div>
            </div>
          </div>

          {/* 5. Filters Bar for Hierarchy & Comparison Table */}
          <div className="p-4 rounded-[12px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)] space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-border-subtle">
              <div className="flex items-center gap-2">
                <SlidersHorizontal className="w-4 h-4 text-text-secondary" />
                <span className="text-xs font-semibold text-text-primary tracking-[-0.2px]">
                  Campus Fleet Filters
                </span>
              </div>
              {(filterSearch ||
                filterBuilding !== 'all' ||
                filterFloor !== 'all' ||
                filterDept !== 'all' ||
                filterType !== 'all' ||
                filterStatus !== 'all') && (
                <button
                  onClick={() => {
                    setFilterSearch('');
                    setFilterBuilding('all');
                    setFilterFloor('all');
                    setFilterDept('all');
                    setFilterType('all');
                    setFilterStatus('all');
                  }}
                  className="text-xs text-accent-primary hover:underline font-medium cursor-pointer"
                >
                  Reset all filters
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-2.5">
              {/* Search */}
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-text-muted" />
                <input
                  type="text"
                  placeholder="Search name, IP, model..."
                  value={filterSearch}
                  onChange={(e) => setFilterSearch(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 rounded-[6px] bg-elevated-surface border border-border-subtle text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary"
                />
              </div>

              {/* Building */}
              <div>
                <select
                  value={filterBuilding}
                  onChange={(e) => setFilterBuilding(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-[6px] bg-elevated-surface border border-border-subtle text-xs text-text-primary focus:outline-none focus:border-accent-primary"
                >
                  <option value="all">All Buildings</option>
                  {filterOptions.buildings.map((b) => (
                    <option key={b} value={b}>
                      {b}
                    </option>
                  ))}
                </select>
              </div>

              {/* Floor */}
              <div>
                <select
                  value={filterFloor}
                  onChange={(e) => setFilterFloor(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-[6px] bg-elevated-surface border border-border-subtle text-xs text-text-primary focus:outline-none focus:border-accent-primary"
                >
                  <option value="all">All Floors</option>
                  {filterOptions.floors.map((f) => (
                    <option key={f} value={f}>
                      Floor {f}
                    </option>
                  ))}
                </select>
              </div>

              {/* Department */}
              <div>
                <select
                  value={filterDept}
                  onChange={(e) => setFilterDept(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-[6px] bg-elevated-surface border border-border-subtle text-xs text-text-primary focus:outline-none focus:border-accent-primary"
                >
                  <option value="all">All Departments</option>
                  {filterOptions.departments.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>

              {/* Device Type */}
              <div>
                <select
                  value={filterType}
                  onChange={(e) => setFilterType(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-[6px] bg-elevated-surface border border-border-subtle text-xs text-text-primary focus:outline-none focus:border-accent-primary"
                >
                  <option value="all">All Device Types</option>
                  <option value="router">Router</option>
                  <option value="switch">Switch</option>
                  <option value="access_point">Access Point</option>
                  <option value="server">Server</option>
                  <option value="other">Other</option>
                </select>
              </div>

              {/* Status */}
              <div>
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-[6px] bg-elevated-surface border border-border-subtle text-xs text-text-primary focus:outline-none focus:border-accent-primary"
                >
                  <option value="all">All Statuses</option>
                  <option value="online">Online</option>
                  <option value="unreachable">Unreachable</option>
                  <option value="stale">Stale</option>
                  <option value="unknown">Unknown</option>
                  <option value="maintenance">Maintenance</option>
                </select>
              </div>
            </div>
          </div>

          {/* 6. Campus Topological Hierarchy Explorer */}
          <div className="p-4 sm:p-5 rounded-[12px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)] space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-text-primary tracking-[-0.2px] flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-accent-primary" />
                  Campus Topology Hierarchy (Campus → Building → Floor → Department → Device)
                </h3>
                <p className="text-xs text-text-muted mt-0.5">
                  Expand topological branches to inspect individual network equipment metrics.
                </p>
              </div>
            </div>

            <div className="space-y-3">
              {hierarchy?.buildings.map((bNode) => {
                const bExpanded = !!expandedBuildings[bNode.building];
                // Check if building matches filters
                if (filterBuilding !== 'all' && bNode.building !== filterBuilding) return null;

                return (
                  <div
                    key={bNode.building}
                    className="rounded-[10px] border border-border-subtle bg-elevated-surface/30 overflow-hidden"
                  >
                    {/* Building Level Header */}
                    <button
                      onClick={() => toggleBuilding(bNode.building)}
                      className="w-full px-4 py-3 bg-elevated-surface/80 hover:bg-elevated-surface flex items-center justify-between transition-colors cursor-pointer text-left"
                    >
                      <div className="flex items-center gap-3">
                        {bExpanded ? (
                          <ChevronDown className="w-4 h-4 text-text-muted" />
                        ) : (
                          <ChevronRight className="w-4 h-4 text-text-muted" />
                        )}
                        <Building2 className="w-4 h-4 text-blue-400" />
                        <span className="text-xs font-semibold text-text-primary">
                          {bNode.building}
                        </span>
                        <span className="text-[11px] text-text-muted">
                          ({bNode.total_devices} devices)
                        </span>
                      </div>

                      <div className="flex items-center gap-2">
                        {bNode.online_devices > 0 && (
                          <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full">
                            {bNode.online_devices} Online
                          </span>
                        )}
                        {bNode.unreachable_devices > 0 && (
                          <span className="text-[10px] font-mono text-red-400 bg-red-500/10 px-2 py-0.5 rounded-full">
                            {bNode.unreachable_devices} Unreachable
                          </span>
                        )}
                      </div>
                    </button>

                    {/* Floors inside Building */}
                    {bExpanded && (
                      <div className="p-3 space-y-2 border-t border-border-subtle bg-card-surface/40">
                        {bNode.floors.map((fNode) => {
                          const fKey = `${bNode.building}-F${fNode.floor}`;
                          const fExpanded = expandedFloors[fKey] ?? true;
                          if (filterFloor !== 'all' && fNode.floor !== filterFloor) return null;

                          return (
                            <div
                              key={fKey}
                              className="rounded-[8px] border border-border-subtle bg-elevated-surface/20 overflow-hidden ml-3 sm:ml-5"
                            >
                              {/* Floor Header */}
                              <button
                                onClick={() => toggleFloor(fKey)}
                                className="w-full px-3 py-2 bg-elevated-surface/40 hover:bg-elevated-surface/70 flex items-center justify-between transition-colors cursor-pointer text-left"
                              >
                                <div className="flex items-center gap-2">
                                  {fExpanded ? (
                                    <ChevronDown className="w-3.5 h-3.5 text-text-muted" />
                                  ) : (
                                    <ChevronRight className="w-3.5 h-3.5 text-text-muted" />
                                  )}
                                  <Layers className="w-3.5 h-3.5 text-purple-400" />
                                  <span className="text-xs font-medium text-text-primary">
                                    Floor {fNode.floor}
                                  </span>
                                  <span className="text-[10px] text-text-muted">
                                    ({fNode.total_devices} devices)
                                  </span>
                                </div>
                                <span className="text-[10px] font-mono text-text-muted">
                                  {fNode.departments.length} departments
                                </span>
                              </button>

                              {/* Departments inside Floor */}
                              {fExpanded && (
                                <div className="p-2 space-y-2 border-t border-border-subtle ml-3 sm:ml-4">
                                  {fNode.departments.map((dNode) => {
                                    const dKey = `${fKey}-${dNode.department}`;
                                    const dExpanded = expandedDepts[dKey] ?? true;
                                    if (filterDept !== 'all' && dNode.department !== filterDept) return null;

                                    const visibleDevices = dNode.devices.filter(isDeviceVisible);
                                    if (visibleDevices.length === 0 && (filterSearch || filterType !== 'all' || filterStatus !== 'all')) {
                                      return null;
                                    }

                                    return (
                                      <div
                                        key={dKey}
                                        className="rounded-[6px] border border-border-subtle bg-card-surface/70 overflow-hidden"
                                      >
                                        {/* Department Header */}
                                        <button
                                          onClick={() => toggleDept(dKey)}
                                          className="w-full px-3 py-1.5 bg-elevated-surface/30 hover:bg-elevated-surface/50 flex items-center justify-between transition-colors cursor-pointer text-left"
                                        >
                                          <div className="flex items-center gap-2">
                                            {dExpanded ? (
                                              <ChevronDown className="w-3 h-3 text-text-muted" />
                                            ) : (
                                              <ChevronRight className="w-3 h-3 text-text-muted" />
                                            )}
                                            <span className="text-[11px] font-semibold text-text-primary">
                                              Dept: {dNode.department}
                                            </span>
                                          </div>
                                          <span className="text-[10px] font-mono text-text-muted">
                                            {visibleDevices.length} / {dNode.total_devices} visible
                                          </span>
                                        </button>

                                        {/* Devices Grid in Department */}
                                        {dExpanded && (
                                          <div className="p-2.5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 border-t border-border-subtle">
                                            {visibleDevices.map((dev) => (
                                              <div
                                                key={dev.id}
                                                onClick={() => handleOpenDetail(dev.id)}
                                                className="p-3 rounded-[8px] bg-elevated-surface/50 hover:bg-elevated-surface border border-border-subtle hover:border-border-hover transition-all cursor-pointer space-y-2 group shadow-xs"
                                              >
                                                <div className="flex items-start justify-between gap-2">
                                                  <div className="flex items-center gap-2 min-w-0">
                                                    {renderDeviceTypeIcon(dev.device_type)}
                                                    <span className="text-xs font-semibold text-text-primary truncate group-hover:text-accent-primary transition-colors">
                                                      {dev.name}
                                                    </span>
                                                  </div>
                                                  {renderStatusBadge(dev.computed_status, dev.is_stale)}
                                                </div>

                                                <div className="flex items-center justify-between text-[11px] font-mono text-text-muted">
                                                  <span>{dev.ip_address}</span>
                                                  {renderMethodBadge(dev.collection_method)}
                                                </div>

                                                {/* Live Rates */}
                                                <div className="pt-1.5 border-t border-border-subtle/60 flex items-center justify-between text-[10px]">
                                                  <div className="flex items-center gap-1.5 font-mono">
                                                    <span className="text-blue-400">
                                                      ↓ {dev.latest_download_mbps.toFixed(2)}M
                                                    </span>
                                                    <span className="text-purple-400">
                                                      ↑ {dev.latest_upload_mbps.toFixed(2)}M
                                                    </span>
                                                  </div>

                                                  <span className="text-text-muted">
                                                    {dev.last_poll_at
                                                      ? new Date(dev.last_poll_at).toLocaleTimeString([], {
                                                          hour: '2-digit',
                                                          minute: '2-digit',
                                                        })
                                                      : 'No polls'}
                                                  </span>
                                                </div>
                                              </div>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* 7. Multi-Device Comparison Table */}
          <div className="p-4 sm:p-5 rounded-[12px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)] space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold text-text-primary tracking-[-0.2px] flex items-center gap-2">
                  <Server className="w-4 h-4 text-accent-primary" />
                  Campus Fleet Telemetry Comparison
                </h3>
                <p className="text-xs text-text-muted mt-0.5">
                  Detailed side-by-side comparison of reachability, rates, errors, and polling status across all {comparison?.total_devices ?? 0} campus devices.
                </p>
              </div>
              <span className="text-xs font-mono text-text-muted self-start sm:self-auto">
                Showing {filteredComparisonDevices.length} of {comparison?.total_devices ?? 0} devices
              </span>
            </div>

            {filteredComparisonDevices.length === 0 ? (
              <div className="p-8 text-center text-xs text-text-muted border border-dashed border-border-subtle rounded-[8px]">
                No campus devices match the currently active filter parameters.
              </div>
            ) : (
              <div className="overflow-x-auto rounded-[8px] border border-border-subtle">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-border-subtle bg-elevated-surface text-[11px] font-semibold text-text-secondary">
                      <th className="py-2.5 px-3">Device Identity</th>
                      <th className="py-2.5 px-3">Location</th>
                      <th className="py-2.5 px-3">Type & Source</th>
                      <th className="py-2.5 px-3">Reliable Status</th>
                      <th className="py-2.5 px-3">Polling</th>
                      <th className="py-2.5 px-3 text-right">Throughput (Mbps)</th>
                      <th className="py-2.5 px-3 text-right">Err / Drop</th>
                      <th className="py-2.5 px-3">Last Polled</th>
                      <th className="py-2.5 px-3 text-center">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-subtle text-text-primary">
                    {filteredComparisonDevices.map((d) => (
                      <tr
                        key={d.device_id}
                        className="hover:bg-elevated-surface/40 transition-colors"
                      >
                        {/* Identity */}
                        <td className="py-2.5 px-3">
                          <div className="font-semibold text-text-primary">{d.name}</div>
                          <div className="font-mono text-[10px] text-text-muted">{d.ip_address}</div>
                        </td>

                        {/* Location */}
                        <td className="py-2.5 px-3">
                          <div className="text-text-primary">{d.building}</div>
                          <div className="text-[10px] text-text-muted">
                            Floor {d.floor} • {d.department}
                          </div>
                        </td>

                        {/* Type & Source */}
                        <td className="py-2.5 px-3">
                          <div className="flex items-center gap-1.5 capitalize text-text-secondary">
                            {renderDeviceTypeIcon(d.device_type)}
                            <span>{d.device_type.replace('_', ' ')}</span>
                          </div>
                          <div className="mt-1">{renderMethodBadge(d.collection_method)}</div>
                        </td>

                        {/* Reliable Status */}
                        <td className="py-2.5 px-3">{renderStatusBadge(d.computed_status)}</td>

                        {/* Polling */}
                        <td className="py-2.5 px-3">
                          {d.polling_enabled ? (
                            <span className="text-[10px] font-mono text-emerald-400">ACTIVE</span>
                          ) : (
                            <span className="text-[10px] font-mono text-zinc-400">PAUSED</span>
                          )}
                        </td>

                        {/* Throughput */}
                        <td className="py-2.5 px-3 text-right font-mono">
                          <div className="text-blue-400 font-medium">↓ {d.download_mbps.toFixed(2)}</div>
                          <div className="text-purple-400 text-[10px]">↑ {d.upload_mbps.toFixed(2)}</div>
                        </td>

                        {/* Err / Drop */}
                        <td className="py-2.5 px-3 text-right font-mono text-[11px]">
                          <span className={d.errors > 0 ? 'text-red-400 font-bold' : 'text-text-muted'}>
                            {d.errors}
                          </span>
                          {' / '}
                          <span className={d.discards > 0 ? 'text-amber-400' : 'text-text-muted'}>
                            {d.discards}
                          </span>
                        </td>

                        {/* Last Polled */}
                        <td className="py-2.5 px-3 font-mono text-[10px] text-text-muted">
                          {d.last_poll_at
                            ? new Date(d.last_poll_at).toLocaleTimeString()
                            : 'Never'}
                        </td>

                        {/* Action */}
                        <td className="py-2.5 px-3 text-center">
                          <button
                            onClick={() => handleOpenDetail(d.device_id)}
                            className="px-2.5 py-1 rounded-[6px] bg-elevated-surface hover:bg-elevated-surface/80 border border-border-subtle text-[11px] font-medium text-text-primary transition-colors cursor-pointer"
                          >
                            Inspect
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {/* Device Detail Modal */}
      {selectedDevice && (
        <DeviceDetailModal
          device={selectedDevice}
          isOpen={isDetailModalOpen}
          onClose={() => {
            setIsDetailModalOpen(false);
            setSelectedDevice(null);
          }}
          onDeviceUpdated={(updated) => {
            setSelectedDevice(updated);
            fetchCampusData(true);
          }}
          onNotify={onNotify}
        />
      )}
    </div>
  );
};

export default CampusOverview;
