import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Bell,
  AlertTriangle,
  CheckCircle,
  Info,
  Clock,
  Search,
  RotateCw,
  FlaskConical,
  ShieldCheck,
  X,
  ChevronRight,
  Layers,
  Server,
} from 'lucide-react';
import {
  fetchAlerts,
  fetchAlertSummary,
  acknowledgeAlert,
  resolveAlert,
} from '../../services/alertApi';
import type {
  TopologyAlert,
  TopologyAlertSummaryResponse,
  AlertFilterOptions,
} from '../../types/alert';
import { Spinner } from '../common/Spinner';

interface AlertCenterProps {
  onNotify?: (type: 'success' | 'error' | 'info', message: string) => void;
  onNavigateToDevices?: () => void;
  onNavigateToTopology?: () => void;
}

export const AlertCenter: React.FC<AlertCenterProps> = ({
  onNotify,
  onNavigateToDevices,
  onNavigateToTopology,
}) => {
  const [alerts, setAlerts] = useState<TopologyAlert[]>([]);
  const [summary, setSummary] = useState<TopologyAlertSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [filters, setFilters] = useState<AlertFilterOptions>({
    status: 'all',
    severity: 'all',
    eventType: 'all',
    deviceId: '',
    dataSource: 'all',
    searchQuery: '',
  });

  // Selected Alert for Details Drawer
  const [selectedAlert, setSelectedAlert] = useState<TopologyAlert | null>(null);

  // Modal for Action Confirmation (Acknowledge / Resolve)
  const [actionModal, setActionModal] = useState<{
    type: 'acknowledge' | 'resolve';
    alert: TopologyAlert;
    operator: string;
    note: string;
    isSubmitting: boolean;
  } | null>(null);

  const loadData = useCallback(async (isSilent = false) => {
    if (!isSilent) setIsLoading(true);
    else setIsRefreshing(true);
    setError(null);

    try {
      const isMockParam =
        filters.dataSource === 'mock'
          ? true
          : filters.dataSource === 'actual'
          ? false
          : undefined;

      const [alertsRes, summaryRes] = await Promise.all([
        fetchAlerts({
          status: filters.status !== 'all' ? filters.status : undefined,
          severity: filters.severity !== 'all' ? filters.severity : undefined,
          event_type: filters.eventType !== 'all' ? filters.eventType : undefined,
          device_id: filters.deviceId.trim() || undefined,
          is_mock: isMockParam,
          limit: 100,
        }),
        fetchAlertSummary({
          is_mock: isMockParam,
        }),
      ]);

      setAlerts(alertsRes.alerts);
      setSummary(summaryRes);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to fetch topology alerts';
      setError(message);
      if (onNotify) onNotify('error', message);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [filters.status, filters.severity, filters.eventType, filters.deviceId, filters.dataSource, onNotify]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Client-side search filtering across message, IDs, and local interface
  const filteredAlerts = useMemo(() => {
    if (!filters.searchQuery.trim()) return alerts;
    const q = filters.searchQuery.toLowerCase().trim();
    return alerts.filter(
      (a) =>
        a.id.toLowerCase().includes(q) ||
        a.message.toLowerCase().includes(q) ||
        a.source_device_id.toLowerCase().includes(q) ||
        (a.source_device_name && a.source_device_name.toLowerCase().includes(q)) ||
        (a.remote_device_name && a.remote_device_name.toLowerCase().includes(q)) ||
        (a.remote_chassis_id && a.remote_chassis_id.toLowerCase().includes(q)) ||
        (a.local_interface && a.local_interface.toLowerCase().includes(q)) ||
        a.event_type.toLowerCase().includes(q)
    );
  }, [alerts, filters.searchQuery]);

  const handleOpenActionModal = (alert: TopologyAlert, type: 'acknowledge' | 'resolve') => {
    setActionModal({
      type,
      alert,
      operator: 'Network Operator',
      note: '',
      isSubmitting: false,
    });
  };

  const handleExecuteAction = async () => {
    if (!actionModal) return;
    setActionModal((prev) => (prev ? { ...prev, isSubmitting: true } : null));

    try {
      if (actionModal.type === 'acknowledge') {
        const updated = await acknowledgeAlert(actionModal.alert.id, {
          acknowledged_by: actionModal.operator.trim() || 'Network Operator',
          note: actionModal.note.trim() || undefined,
        });
        if (onNotify) onNotify('success', `Alert ${updated.id} acknowledged`);
      } else {
        const updated = await resolveAlert(actionModal.alert.id, {
          resolved_by: actionModal.operator.trim() || 'Network Operator',
          note: actionModal.note.trim() || undefined,
        });
        if (onNotify) onNotify('success', `Alert ${updated.id} resolved`);
      }

      setActionModal(null);
      if (selectedAlert && selectedAlert.id === actionModal.alert.id) {
        setSelectedAlert(null);
      }
      loadData(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Action failed';
      if (onNotify) onNotify('error', msg);
      setActionModal((prev) => (prev ? { ...prev, isSubmitting: false } : null));
    }
  };

  const formatEventType = (type: string) => {
    switch (type) {
      case 'new_neighbor':
        return 'New Neighbor';
      case 'neighbor_stale':
        return 'Neighbor Stale';
      case 'neighbor_restored':
        return 'Neighbor Restored';
      case 'interface_changed':
        return 'Interface Changed';
      case 'protocol_changed':
        return 'Protocol Changed';
      case 'discovery_failed':
        return 'Discovery Failed';
      case 'discovery_unsupported':
        return 'Discovery Unsupported';
      default:
        return type.replace(/_/g, ' ');
    }
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-red-500/15 text-red-600 dark:text-red-400 border border-red-500/30">
            <AlertTriangle className="w-3 h-3" />
            CRITICAL
          </span>
        );
      case 'warning':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30">
            <AlertTriangle className="w-3 h-3" />
            WARNING
          </span>
        );
      case 'info':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/30">
            <Info className="w-3 h-3" />
            INFO
          </span>
        );
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'open':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
            Open
          </span>
        );
      case 'acknowledged':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
            <Clock className="w-3 h-3 text-amber-500" />
            Acknowledged
          </span>
        );
      case 'resolved':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <CheckCircle className="w-3 h-3 text-emerald-500" />
            Resolved
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-gray-500/10 text-gray-500 border border-gray-500/20">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-text-primary flex items-center gap-2">
            <Bell className="w-5 h-5 text-accent-primary" />
            Topology Alert Center
          </h1>
          <p className="text-xs text-text-muted mt-0.5">
            Read-only layer-2 discovery event monitoring, stale neighbor detection, and lifecycle alerting.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {summary && summary.mock_alerts_count > 0 && (
            <span className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/25">
              <FlaskConical className="w-3.5 h-3.5" />
              SIMULATED ALERTS ACTIVE ({summary.mock_alerts_count})
            </span>
          )}
          {summary && summary.actual_alerts_count > 0 && (
            <span className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25">
              <ShieldCheck className="w-3.5 h-3.5" />
              ACTUAL SNMP ({summary.actual_alerts_count})
            </span>
          )}

          <button
            type="button"
            onClick={() => loadData(true)}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-card-surface border border-border-subtle hover:bg-surface-hover text-text-primary transition-colors disabled:opacity-50 shadow-xs cursor-pointer"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
        <div
          onClick={() => setFilters((prev) => ({ ...prev, status: prev.status === 'open' ? 'all' : 'open' }))}
          className={`p-4 rounded-[10px] bg-card-surface border cursor-pointer transition-all shadow-[var(--shadow-whisper)] ${
            filters.status === 'open'
              ? 'border-red-500 ring-1 ring-red-500/30'
              : 'border-border-subtle hover:border-border-default'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-text-muted">Open Alerts</span>
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-red-500">
            {summary ? summary.open_alerts : '-'}
          </div>
          <span className="text-[11px] text-text-muted mt-1 block">Requires engineer review</span>
        </div>

        <div
          onClick={() =>
            setFilters((prev) => ({
              ...prev,
              status: prev.status === 'acknowledged' ? 'all' : 'acknowledged',
            }))
          }
          className={`p-4 rounded-[10px] bg-card-surface border cursor-pointer transition-all shadow-[var(--shadow-whisper)] ${
            filters.status === 'acknowledged'
              ? 'border-amber-500 ring-1 ring-amber-500/30'
              : 'border-border-subtle hover:border-border-default'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-text-muted">Acknowledged</span>
            <Clock className="w-4 h-4 text-amber-500" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-amber-500">
            {summary ? summary.acknowledged_alerts : '-'}
          </div>
          <span className="text-[11px] text-text-muted mt-1 block">Investigation in progress</span>
        </div>

        <div
          onClick={() =>
            setFilters((prev) => ({
              ...prev,
              status: prev.status === 'resolved' ? 'all' : 'resolved',
            }))
          }
          className={`p-4 rounded-[10px] bg-card-surface border cursor-pointer transition-all shadow-[var(--shadow-whisper)] ${
            filters.status === 'resolved'
              ? 'border-emerald-500 ring-1 ring-emerald-500/30'
              : 'border-border-subtle hover:border-border-default'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-text-muted">Resolved History</span>
            <CheckCircle className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-emerald-500">
            {summary ? summary.resolved_alerts : '-'}
          </div>
          <span className="text-[11px] text-text-muted mt-1 block">Preserved audit trail</span>
        </div>

        <div
          onClick={() =>
            setFilters((prev) => ({
              ...prev,
              severity: prev.severity === 'critical' ? 'all' : 'critical',
            }))
          }
          className={`p-4 rounded-[10px] bg-card-surface border cursor-pointer transition-all shadow-[var(--shadow-whisper)] ${
            filters.severity === 'critical'
              ? 'border-red-500 ring-1 ring-red-500/30'
              : 'border-border-subtle hover:border-border-default'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-text-muted">Critical Conditions</span>
            <AlertTriangle className="w-4 h-4 text-red-500" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-text-primary">
            {summary?.by_severity?.['critical'] || 0}
          </div>
          <span className="text-[11px] text-text-muted mt-1 block">Failures & interface shifts</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-3.5 rounded-[12px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)] space-y-3">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          {/* Search Input */}
          <div className="relative flex-1 min-w-[240px]">
            <Search className="w-4 h-4 text-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={filters.searchQuery}
              onChange={(e) => setFilters((prev) => ({ ...prev, searchQuery: e.target.value }))}
              placeholder="Search by device, peer, interface, or alert message..."
              className="w-full pl-9 pr-3 py-1.5 rounded-lg text-xs bg-surface-hover/50 border border-border-subtle text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-accent-primary"
            />
          </div>

          {/* Quick Select Controls */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Status Select */}
            <select
              value={filters.status}
              onChange={(e) => setFilters((prev) => ({ ...prev, status: e.target.value }))}
              className="px-2.5 py-1.5 rounded-lg text-xs bg-card-surface border border-border-subtle text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
            >
              <option value="all">All Statuses</option>
              <option value="open">Open</option>
              <option value="acknowledged">Acknowledged</option>
              <option value="resolved">Resolved</option>
            </select>

            {/* Severity Select */}
            <select
              value={filters.severity}
              onChange={(e) => setFilters((prev) => ({ ...prev, severity: e.target.value }))}
              className="px-2.5 py-1.5 rounded-lg text-xs bg-card-surface border border-border-subtle text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>

            {/* Event Type Select */}
            <select
              value={filters.eventType}
              onChange={(e) => setFilters((prev) => ({ ...prev, eventType: e.target.value }))}
              className="px-2.5 py-1.5 rounded-lg text-xs bg-card-surface border border-border-subtle text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
            >
              <option value="all">All Event Types</option>
              <option value="new_neighbor">New Neighbor</option>
              <option value="neighbor_stale">Neighbor Stale</option>
              <option value="neighbor_restored">Neighbor Restored</option>
              <option value="interface_changed">Interface Changed</option>
              <option value="protocol_changed">Protocol Changed</option>
              <option value="discovery_failed">Discovery Failed</option>
              <option value="discovery_unsupported">Discovery Unsupported</option>
            </select>

            {/* Data Source Filter (Rule 6 compliant) */}
            <select
              value={filters.dataSource}
              onChange={(e) => setFilters((prev) => ({ ...prev, dataSource: e.target.value }))}
              className="px-2.5 py-1.5 rounded-lg text-xs bg-card-surface border border-border-subtle text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
            >
              <option value="all">All Provenance</option>
              <option value="actual">Actual SNMP Only</option>
              <option value="mock">Simulated / Mock Only</option>
            </select>

            {/* Reset Filters Button */}
            {(filters.status !== 'all' ||
              filters.severity !== 'all' ||
              filters.eventType !== 'all' ||
              filters.dataSource !== 'all' ||
              filters.searchQuery) && (
              <button
                type="button"
                onClick={() =>
                  setFilters({
                    status: 'all',
                    severity: 'all',
                    eventType: 'all',
                    deviceId: '',
                    dataSource: 'all',
                    searchQuery: '',
                  })
                }
                className="px-2.5 py-1.5 rounded-lg text-xs text-text-muted hover:text-text-primary transition-colors cursor-pointer"
              >
                Reset
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Alert Table / Content */}
      <div className="rounded-[12px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)] overflow-hidden">
        {isLoading ? (
          <div className="py-20 flex flex-col items-center justify-center gap-3">
            <Spinner className="w-6 h-6 text-accent-primary" />
            <span className="text-xs text-text-muted">Loading topology alerts...</span>
          </div>
        ) : error ? (
          <div className="py-16 px-4 text-center">
            <AlertTriangle className="w-8 h-8 text-red-500 mx-auto mb-2 opacity-80" />
            <h3 className="text-sm font-semibold text-text-primary">Unable to Load Alerts</h3>
            <p className="text-xs text-text-muted max-w-md mx-auto mt-1">{error}</p>
            <button
              onClick={() => loadData()}
              className="mt-3 px-3 py-1.5 rounded-lg text-xs font-medium bg-[#0070f3] text-white hover:bg-[#0070f3]/90 cursor-pointer"
            >
              Retry
            </button>
          </div>
        ) : filteredAlerts.length === 0 ? (
          <div className="py-16 px-4 text-center">
            <CheckCircle className="w-10 h-10 text-emerald-500/60 mx-auto mb-2" />
            <h3 className="text-sm font-semibold text-text-primary">No Matching Topology Alerts</h3>
            <p className="text-xs text-text-muted max-w-sm mx-auto mt-1">
              {alerts.length === 0
                ? 'All topology observations are stable. No new neighbors, link shifts, or unrefreshed advertisement windows.'
                : 'No alerts match the active filter criteria. Try resetting your search or severity filter.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-hover/60 border-b border-border-subtle text-text-muted font-medium uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="py-3 px-4">Severity</th>
                  <th className="py-3 px-4">Event Type</th>
                  <th className="py-3 px-4">Source Device & Interface</th>
                  <th className="py-3 px-4">Remote Peer / Chassis</th>
                  <th className="py-3 px-4">Status & Count</th>
                  <th className="py-3 px-4">Provenance</th>
                  <th className="py-3 px-4">Last Detected</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {filteredAlerts.map((alert) => (
                  <tr
                    key={alert.id}
                    className="hover:bg-surface-hover/40 transition-colors group cursor-pointer"
                    onClick={() => setSelectedAlert(alert)}
                  >
                    {/* Severity */}
                    <td className="py-3 px-4 whitespace-nowrap">
                      {getSeverityBadge(alert.severity)}
                    </td>

                    {/* Event Type */}
                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="font-medium text-text-primary">
                        {formatEventType(alert.event_type)}
                      </div>
                      {alert.protocol && (
                        <span className="text-[10px] text-text-muted uppercase font-mono">
                          {alert.protocol}
                        </span>
                      )}
                    </td>

                    {/* Source Device & Interface */}
                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="font-semibold text-text-primary">
                        {alert.source_device_name || alert.source_device_id}
                      </div>
                      {alert.local_interface ? (
                        <div className="text-[11px] text-text-muted font-mono">
                          {alert.local_interface}
                        </div>
                      ) : (
                        <div className="text-[11px] text-text-muted italic">System level</div>
                      )}
                    </td>

                    {/* Remote Peer */}
                    <td className="py-3 px-4 whitespace-nowrap max-w-[200px] truncate">
                      {alert.remote_device_name || alert.remote_device_id || alert.remote_chassis_id ? (
                        <div>
                          <div className="font-medium text-text-primary truncate">
                            {alert.remote_device_name || alert.remote_device_id || 'Unknown Name'}
                          </div>
                          <div className="text-[10px] text-text-muted font-mono truncate">
                            {alert.remote_chassis_id || alert.remote_port_id || '—'}
                          </div>
                        </div>
                      ) : (
                        <span className="text-text-muted italic">—</span>
                      )}
                    </td>

                    {/* Status & Occurrence Count */}
                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        {getStatusBadge(alert.status)}
                        {alert.occurrence_count > 1 && (
                          <span
                            title={`Deduplicated: occurred ${alert.occurrence_count} times`}
                            className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-surface-hover border border-border-subtle text-text-muted"
                          >
                            ×{alert.occurrence_count}
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Provenance Badge (Rule 6) */}
                    <td className="py-3 px-4 whitespace-nowrap">
                      {alert.is_mock ? (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/25">
                          <FlaskConical className="w-2.5 h-2.5" />
                          MOCK
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25">
                          <ShieldCheck className="w-2.5 h-2.5" />
                          ACTUAL
                        </span>
                      )}
                    </td>

                    {/* Last Detected */}
                    <td className="py-3 px-4 whitespace-nowrap text-text-muted font-mono text-[11px]">
                      {new Date(alert.last_seen_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                      })}
                    </td>

                    {/* Action Buttons */}
                    <td
                      className="py-3 px-4 whitespace-nowrap text-right"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex items-center justify-end gap-1.5">
                        {alert.status === 'open' && (
                          <button
                            type="button"
                            onClick={() => handleOpenActionModal(alert, 'acknowledge')}
                            title="Acknowledge Alert"
                            className="px-2 py-1 rounded text-[11px] font-medium bg-amber-500/10 hover:bg-amber-500/20 text-amber-600 dark:text-amber-400 border border-amber-500/20 transition-colors cursor-pointer"
                          >
                            Acknowledge
                          </button>
                        )}
                        {alert.status !== 'resolved' && (
                          <button
                            type="button"
                            onClick={() => handleOpenActionModal(alert, 'resolve')}
                            title="Resolve Alert"
                            className="px-2 py-1 rounded text-[11px] font-medium bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 transition-colors cursor-pointer"
                          >
                            Resolve
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => setSelectedAlert(alert)}
                          title="Inspect Details"
                          className="p-1 rounded text-text-muted hover:text-text-primary hover:bg-surface-hover transition-colors cursor-pointer"
                        >
                          <ChevronRight className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Event Detail Drawer / Modal */}
      {selectedAlert && (
        <div
          className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex justify-end transition-opacity"
          onClick={() => setSelectedAlert(null)}
        >
          <div
            className="w-full max-w-lg bg-card-surface border-l border-border-subtle h-full overflow-y-auto p-6 shadow-2xl flex flex-col justify-between"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="space-y-5">
              {/* Header */}
              <div className="flex items-start justify-between border-b border-border-subtle pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    {getSeverityBadge(selectedAlert.severity)}
                    {getStatusBadge(selectedAlert.status)}
                    {selectedAlert.is_mock && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/25">
                        SIMULATED
                      </span>
                    )}
                  </div>
                  <h2 className="text-base font-bold text-text-primary mt-2">
                    {formatEventType(selectedAlert.event_type)}
                  </h2>
                  <span className="text-xs text-text-muted font-mono">{selectedAlert.id}</span>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedAlert(null)}
                  className="p-1 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-hover transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Message Banner */}
              <div className="p-3.5 rounded-lg bg-surface-hover/70 border border-border-subtle">
                <span className="text-xs font-semibold text-text-primary block mb-1">
                  Event Explanation
                </span>
                <p className="text-xs text-text-secondary leading-relaxed">
                  {selectedAlert.message}
                </p>
              </div>

              {/* Metadata Grid */}
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-2.5 rounded-lg bg-surface-hover/40 border border-border-subtle">
                  <span className="text-[11px] text-text-muted block">Source Device</span>
                  <span className="font-semibold text-text-primary">
                    {selectedAlert.source_device_name || selectedAlert.source_device_id}
                  </span>
                </div>
                <div className="p-2.5 rounded-lg bg-surface-hover/40 border border-border-subtle">
                  <span className="text-[11px] text-text-muted block">Local Interface</span>
                  <span className="font-mono text-text-primary">
                    {selectedAlert.local_interface || 'N/A'}
                  </span>
                </div>
                <div className="p-2.5 rounded-lg bg-surface-hover/40 border border-border-subtle">
                  <span className="text-[11px] text-text-muted block">Remote Peer / System</span>
                  <span className="font-semibold text-text-primary">
                    {selectedAlert.remote_device_name || selectedAlert.remote_device_id || 'N/A'}
                  </span>
                </div>
                <div className="p-2.5 rounded-lg bg-surface-hover/40 border border-border-subtle">
                  <span className="text-[11px] text-text-muted block">Remote Port / Chassis</span>
                  <span className="font-mono text-text-primary">
                    {selectedAlert.remote_port_id || selectedAlert.remote_chassis_id || 'N/A'}
                  </span>
                </div>
                <div className="p-2.5 rounded-lg bg-surface-hover/40 border border-border-subtle">
                  <span className="text-[11px] text-text-muted block">Protocol</span>
                  <span className="font-mono text-text-primary uppercase">
                    {selectedAlert.protocol || 'N/A'}
                  </span>
                </div>
                <div className="p-2.5 rounded-lg bg-surface-hover/40 border border-border-subtle">
                  <span className="text-[11px] text-text-muted block">Occurrence Count</span>
                  <span className="font-mono text-text-primary">
                    {selectedAlert.occurrence_count} time(s)
                  </span>
                </div>
              </div>

              {/* Lifecycle Timestamps & Audit Log */}
              <div className="space-y-2 border-t border-border-subtle pt-3 text-xs">
                <span className="font-semibold text-text-primary block">Lifecycle Audit Log</span>
                <div className="space-y-1.5 text-text-secondary text-[11px]">
                  <div className="flex justify-between">
                    <span className="text-text-muted">First Detected:</span>
                    <span className="font-mono">
                      {new Date(selectedAlert.first_detected_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-text-muted">Last Seen:</span>
                    <span className="font-mono">
                      {new Date(selectedAlert.last_seen_at).toLocaleString()}
                    </span>
                  </div>
                  {selectedAlert.acknowledged_at && (
                    <div className="flex justify-between border-t border-border-subtle/50 pt-1">
                      <span className="text-text-muted">
                        Acknowledged by {selectedAlert.acknowledged_by}:
                      </span>
                      <span className="font-mono">
                        {new Date(selectedAlert.acknowledged_at).toLocaleString()}
                      </span>
                    </div>
                  )}
                  {selectedAlert.acknowledgement_note && (
                    <div className="p-2 rounded bg-amber-500/10 text-amber-700 dark:text-amber-300 text-[11px] italic">
                      &ldquo;{selectedAlert.acknowledgement_note}&rdquo;
                    </div>
                  )}
                  {selectedAlert.resolved_at && (
                    <div className="flex justify-between border-t border-border-subtle/50 pt-1">
                      <span className="text-text-muted">
                        Resolved by {selectedAlert.resolved_by}:
                      </span>
                      <span className="font-mono">
                        {new Date(selectedAlert.resolved_at).toLocaleString()}
                      </span>
                    </div>
                  )}
                  {selectedAlert.resolution_note && (
                    <div className="p-2 rounded bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 text-[11px] italic">
                      &ldquo;{selectedAlert.resolution_note}&rdquo;
                    </div>
                  )}
                </div>
              </div>

              {/* Details JSON Dump if present */}
              {selectedAlert.details && (
                <div className="space-y-1.5 border-t border-border-subtle pt-3">
                  <span className="text-xs font-semibold text-text-primary">Diagnostic Details</span>
                  <pre className="p-2.5 rounded-lg bg-surface-hover font-mono text-[11px] text-text-secondary overflow-x-auto max-h-40">
                    {(() => {
                      try {
                        return JSON.stringify(JSON.parse(selectedAlert.details), null, 2);
                      } catch {
                        return selectedAlert.details;
                      }
                    })()}
                  </pre>
                </div>
              )}
            </div>

            {/* Drawer Bottom Actions */}
            <div className="border-t border-border-subtle pt-4 mt-6 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                {onNavigateToTopology && (
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedAlert(null);
                      onNavigateToTopology();
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-hover hover:bg-surface-hover/80 text-text-primary border border-border-subtle cursor-pointer"
                  >
                    <Layers className="w-3.5 h-3.5" />
                    <span>View Graph</span>
                  </button>
                )}
                {onNavigateToDevices && (
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedAlert(null);
                      onNavigateToDevices();
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-hover hover:bg-surface-hover/80 text-text-primary border border-border-subtle cursor-pointer"
                  >
                    <Server className="w-3.5 h-3.5" />
                    <span>Devices</span>
                  </button>
                )}
              </div>

              <div className="flex items-center gap-2">
                {selectedAlert.status === 'open' && (
                  <button
                    type="button"
                    onClick={() => handleOpenActionModal(selectedAlert, 'acknowledge')}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-500 hover:bg-amber-600 text-white cursor-pointer transition-colors"
                  >
                    Acknowledge
                  </button>
                )}
                {selectedAlert.status !== 'resolved' && (
                  <button
                    type="button"
                    onClick={() => handleOpenActionModal(selectedAlert, 'resolve')}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-600 hover:bg-emerald-700 text-white cursor-pointer transition-colors"
                  >
                    Resolve Alert
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modal for Acknowledge / Resolve */}
      {actionModal && (
        <div
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4"
          onClick={() => setActionModal(null)}
        >
          <div
            className="w-full max-w-md bg-card-surface border border-border-subtle rounded-xl p-5 shadow-2xl space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div>
              <h3 className="text-sm font-bold text-text-primary capitalize">
                {actionModal.type} Alert: {actionModal.alert.id}
              </h3>
              <p className="text-xs text-text-muted mt-1">
                {actionModal.type === 'acknowledge'
                  ? 'Confirm acknowledgement to notify team members that this condition is being reviewed.'
                  : 'Marking as resolved indicates normal operations have been restored or the change was authorized.'}
              </p>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="text-[11px] font-medium text-text-muted block mb-1">
                  Operator Name / Engineer ID
                </label>
                <input
                  type="text"
                  value={actionModal.operator}
                  onChange={(e) =>
                    setActionModal((prev) => (prev ? { ...prev, operator: e.target.value } : null))
                  }
                  className="w-full px-3 py-1.5 rounded-lg bg-surface-hover/60 border border-border-subtle text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
                />
              </div>

              <div>
                <label className="text-[11px] font-medium text-text-muted block mb-1">
                  Optional Note / Reason
                </label>
                <textarea
                  rows={3}
                  value={actionModal.note}
                  onChange={(e) =>
                    setActionModal((prev) => (prev ? { ...prev, note: e.target.value } : null))
                  }
                  placeholder="e.g. Scheduled patch cable re-routing verified with NOC..."
                  className="w-full px-3 py-1.5 rounded-lg bg-surface-hover/60 border border-border-subtle text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-accent-primary text-xs"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-border-subtle">
              <button
                type="button"
                onClick={() => setActionModal(null)}
                disabled={actionModal.isSubmitting}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-text-muted hover:text-text-primary transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleExecuteAction}
                disabled={actionModal.isSubmitting}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium text-white transition-colors cursor-pointer ${
                  actionModal.type === 'acknowledge'
                    ? 'bg-amber-500 hover:bg-amber-600'
                    : 'bg-emerald-600 hover:bg-emerald-700'
                }`}
              >
                {actionModal.isSubmitting
                  ? 'Saving...'
                  : actionModal.type === 'acknowledge'
                  ? 'Confirm Acknowledgement'
                  : 'Confirm Resolution'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
