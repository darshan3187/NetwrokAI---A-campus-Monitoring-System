import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Server,
  Wifi,
  Laptop,
  Layers,
  Cpu,
  Plus,
  Search,
  RotateCw,
  Trash2,
  Edit3,
  X,
  Building2,
  MapPin,
  AlertTriangle,
  LayoutGrid,
  List as ListIcon,
  Activity,
} from 'lucide-react';
import { deviceApi } from '../../services/deviceApi';
import { DeviceDetailModal } from './DeviceDetailModal';
import type {
  Device,
  DeviceType,
  CollectionMethod,
  MonitoringStatus,
  ConnectionStatus,
  DeviceSummaryResponse,
} from '../../types/device';
import { Badge } from '../common/Badge';
import { Spinner } from '../common/Spinner';

interface DeviceInventoryProps {
  onNotify?: (type: 'success' | 'error' | 'info', message: string) => void;
}

export const DeviceInventory: React.FC<DeviceInventoryProps> = ({ onNotify }) => {
  const [devices, setDevices] = useState<Device[]>([]);
  const [summary, setSummary] = useState<DeviceSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Filters
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [selectedDept, setSelectedDept] = useState<string>('all');
  const [selectedBuilding, setSelectedBuilding] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'table' | 'grid'>('table');

  // Modal states
  const [isAddModalOpen, setIsAddModalOpen] = useState<boolean>(false);
  const [editingDevice, setEditingDevice] = useState<Device | null>(null);
  const [deletingDeviceId, setDeletingDeviceId] = useState<string | null>(null);
  const [selectedDetailDevice, setSelectedDetailDevice] = useState<Device | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState<boolean>(false);
  const [formSubmitting, setFormSubmitting] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Form inputs
  const [formId, setFormId] = useState<string>('');
  const [formName, setFormName] = useState<string>('');
  const [formIp, setFormIp] = useState<string>('');
  const [formType, setFormType] = useState<DeviceType>('router');
  const [formBuilding, setFormBuilding] = useState<string>('');
  const [formDept, setFormDept] = useState<string>('');
  const [formFloor, setFormFloor] = useState<string>('');
  const [formLocationDesc, setFormLocationDesc] = useState<string>('');
  const [formVendorModel, setFormVendorModel] = useState<string>('');
  const [formCollectionMethod, setFormCollectionMethod] = useState<CollectionMethod>('manual');
  const [formMonitoringStatus, setFormMonitoringStatus] = useState<MonitoringStatus>('active');
  const [formConnectionStatus, setFormConnectionStatus] = useState<ConnectionStatus>('unknown');

  const fetchDevices = useCallback(async () => {
    try {
      setError(null);
      const [listRes, summaryRes] = await Promise.all([
        deviceApi.getDevices({
          search: searchQuery || undefined,
          device_type: selectedType !== 'all' ? selectedType : undefined,
          department: selectedDept !== 'all' ? selectedDept : undefined,
          building: selectedBuilding !== 'all' ? selectedBuilding : undefined,
          monitoring_status: selectedStatus !== 'all' ? selectedStatus : undefined,
        }),
        deviceApi.getSummary(),
      ]);
      setDevices(listRes.devices);
      setSummary(summaryRes);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load device inventory';
      setError(msg);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [searchQuery, selectedType, selectedDept, selectedBuilding, selectedStatus]);

  useEffect(() => {
    fetchDevices();
  }, [fetchDevices]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await fetchDevices();
  };

  // Distinct lists for dropdown options from summary or loaded devices
  const availableDepts = useMemo(() => {
    if (!summary?.by_department) return [];
    return Object.keys(summary.by_department).sort();
  }, [summary]);

  const availableBuildings = useMemo(() => {
    if (!summary?.by_building) return [];
    return Object.keys(summary.by_building).sort();
  }, [summary]);

  const resetForm = () => {
    setFormId('');
    setFormName('');
    setFormIp('');
    setFormType('router');
    setFormBuilding('');
    setFormDept('');
    setFormFloor('');
    setFormLocationDesc('');
    setFormVendorModel('');
    setFormCollectionMethod('manual');
    setFormMonitoringStatus('active');
    setFormConnectionStatus('unknown');
    setFormError(null);
  };

  const openAddModal = () => {
    resetForm();
    setEditingDevice(null);
    setIsAddModalOpen(true);
  };

  const openEditModal = (dev: Device) => {
    resetForm();
    setEditingDevice(dev);
    setFormId(dev.id);
    setFormName(dev.name);
    setFormIp(dev.ip_address);
    setFormType(dev.device_type);
    setFormBuilding(dev.building);
    setFormDept(dev.department);
    setFormFloor(dev.floor);
    setFormLocationDesc(dev.location_description || '');
    setFormVendorModel(dev.vendor_model || '');
    setFormCollectionMethod(dev.collection_method);
    setFormMonitoringStatus(dev.monitoring_status);
    setFormConnectionStatus(dev.connection_status);
    setIsAddModalOpen(true);
  };

  const handleSaveDevice = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setFormSubmitting(true);

    try {
      if (editingDevice) {
        // Update
        await deviceApi.updateDevice(editingDevice.id, {
          name: formName.trim(),
          ip_address: formIp.trim(),
          device_type: formType,
          building: formBuilding.trim(),
          department: formDept.trim(),
          floor: formFloor.trim(),
          location_description: formLocationDesc.trim() || undefined,
          vendor_model: formVendorModel.trim() || undefined,
          collection_method: formCollectionMethod,
          monitoring_status: formMonitoringStatus,
          connection_status: formConnectionStatus,
        });
        if (onNotify) onNotify('success', `Device "${formName}" updated successfully`);
      } else {
        // Create
        await deviceApi.createDevice({
          id: formId.trim() || undefined,
          name: formName.trim(),
          ip_address: formIp.trim(),
          device_type: formType,
          building: formBuilding.trim(),
          department: formDept.trim(),
          floor: formFloor.trim(),
          location_description: formLocationDesc.trim() || undefined,
          vendor_model: formVendorModel.trim() || undefined,
          collection_method: formCollectionMethod,
          monitoring_status: formMonitoringStatus,
          connection_status: formConnectionStatus,
        });
        if (onNotify) onNotify('success', `Device "${formName}" registered successfully`);
      }
      setIsAddModalOpen(false);
      resetForm();
      await fetchDevices();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Operation failed';
      setFormError(msg);
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleDeleteDevice = async () => {
    if (!deletingDeviceId) return;
    try {
      await deviceApi.deleteDevice(deletingDeviceId);
      if (onNotify) onNotify('info', `Device ${deletingDeviceId} removed from registry`);
      setDeletingDeviceId(null);
      await fetchDevices();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to delete device';
      if (onNotify) onNotify('error', msg);
    }
  };

  const getDeviceIcon = (type: DeviceType) => {
    switch (type) {
      case 'router':
        return <Layers className="w-4 h-4 text-[#0070f3]" aria-hidden="true" />;
      case 'switch':
        return <Layers className="w-4 h-4 text-[#7928ca]" aria-hidden="true" />;
      case 'access_point':
        return <Wifi className="w-4 h-4 text-[#50e3c2]" aria-hidden="true" />;
      case 'server':
        return <Server className="w-4 h-4 text-[#f5a623]" aria-hidden="true" />;
      case 'host':
        return <Laptop className="w-4 h-4 text-[#3291ff]" aria-hidden="true" />;
      default:
        return <Cpu className="w-4 h-4 text-text-muted" aria-hidden="true" />;
    }
  };

  return (
    <div className="space-y-5">
      {/* Top Header & Overview Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-card-surface border border-border-subtle rounded-[12px] p-5 shadow-[var(--shadow-whisper)]">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-semibold text-text-primary tracking-[-0.28px]">
              Campus Multi-Device Registry
            </h1>
            <Badge variant="info" size="sm">
              PHASE 1
            </Badge>
          </div>
          <p className="text-xs text-text-secondary mt-1 max-w-2xl">
            Inventory of authorized campus switches, routers, access points, and servers.
            Telemetry collection uses designated endpoints without storing plaintext credentials.
          </p>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-[6px] border border-border-subtle hover:bg-elevated-surface text-xs text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
            title="Refresh device inventory"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-[#0070f3]' : ''}`} />
            <span>Refresh</span>
          </button>

          <button
            onClick={openAddModal}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-[6px] bg-[#0070f3] hover:bg-[#0070f3]/90 text-white text-xs font-medium shadow-xs transition-colors cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Add Device</span>
          </button>
        </div>
      </div>

      {/* Summary Stat Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
        <div className="p-3.5 rounded-[10px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)] flex flex-col justify-between">
          <span className="text-xs text-text-muted font-medium">Registered Devices</span>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-text-primary">
              {summary ? summary.total_devices : 0}
            </span>
            <span className="text-[11px] font-mono text-text-secondary">total</span>
          </div>
        </div>

        <div className="p-3.5 rounded-[10px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)] flex flex-col justify-between">
          <span className="text-xs text-text-muted font-medium">Monitoring Active</span>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-[#0070f3]">
              {summary ? summary.active_count : 0}
            </span>
            <span className="text-[11px] font-mono text-text-muted">
              / {summary ? summary.total_devices : 0}
            </span>
          </div>
        </div>

        <div className="p-3.5 rounded-[10px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)] flex flex-col justify-between">
          <span className="text-xs text-text-muted font-medium">Connection Status</span>
          <div className="mt-2 flex items-center gap-2">
            <Badge variant="success" size="sm">
              {summary ? summary.online_count : 0} Online
            </Badge>
            <Badge variant="neutral" size="sm">
              {summary ? summary.unknown_count : 0} Standby
            </Badge>
          </div>
        </div>

        <div className="p-3.5 rounded-[10px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)] flex flex-col justify-between">
          <span className="text-xs text-text-muted font-medium">Departments Covered</span>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-text-primary">
              {availableDepts.length}
            </span>
            <span className="text-[11px] font-mono text-text-secondary">depts</span>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-3.5 rounded-[10px] bg-card-surface border border-border-subtle flex flex-wrap items-center justify-between gap-3 shadow-[var(--shadow-whisper)]">
        <div className="flex-1 flex flex-wrap items-center gap-2.5 min-w-[240px]">
          {/* Search Box */}
          <div className="relative min-w-[200px] flex-1 max-w-xs">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by name, IP, department..."
              className="w-full pl-8 pr-3 py-1.5 text-xs rounded-[6px] bg-elevated-surface border border-border-subtle focus:border-[#0070f3] focus:outline-none text-text-primary transition-colors font-mono"
            />
          </div>

          {/* Type Filter */}
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="px-2.5 py-1.5 text-xs rounded-[6px] bg-elevated-surface border border-border-subtle text-text-primary focus:border-[#0070f3] focus:outline-none cursor-pointer"
          >
            <option value="all">All Device Types</option>
            <option value="router">Router</option>
            <option value="switch">Switch</option>
            <option value="access_point">Access Point</option>
            <option value="server">Server</option>
            <option value="host">Host</option>
            <option value="other">Other</option>
          </select>

          {/* Department Filter */}
          {availableDepts.length > 0 && (
            <select
              value={selectedDept}
              onChange={(e) => setSelectedDept(e.target.value)}
              className="px-2.5 py-1.5 text-xs rounded-[6px] bg-elevated-surface border border-border-subtle text-text-primary focus:border-[#0070f3] focus:outline-none cursor-pointer"
            >
              <option value="all">All Departments</option>
              {availableDepts.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          )}

          {/* Building Filter */}
          {availableBuildings.length > 0 && (
            <select
              value={selectedBuilding}
              onChange={(e) => setSelectedBuilding(e.target.value)}
              className="px-2.5 py-1.5 text-xs rounded-[6px] bg-elevated-surface border border-border-subtle text-text-primary focus:border-[#0070f3] focus:outline-none cursor-pointer"
            >
              <option value="all">All Buildings</option>
              {availableBuildings.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
          )}

          {/* Monitoring Status Filter */}
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="px-2.5 py-1.5 text-xs rounded-[6px] bg-elevated-surface border border-border-subtle text-text-primary focus:border-[#0070f3] focus:outline-none cursor-pointer"
          >
            <option value="all">All Statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="maintenance">Maintenance</option>
          </select>
        </div>

        {/* View Toggle */}
        <div className="flex items-center gap-1 border border-border-subtle rounded-[6px] p-0.5 bg-elevated-surface">
          <button
            onClick={() => setViewMode('table')}
            className={`p-1.5 rounded-[4px] cursor-pointer transition-colors ${
              viewMode === 'table' ? 'bg-card-surface text-text-primary shadow-xs' : 'text-text-muted hover:text-text-secondary'
            }`}
            title="Table View"
          >
            <ListIcon className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setViewMode('grid')}
            className={`p-1.5 rounded-[4px] cursor-pointer transition-colors ${
              viewMode === 'grid' ? 'bg-card-surface text-text-primary shadow-xs' : 'text-text-muted hover:text-text-secondary'
            }`}
            title="Grid Card View"
          >
            <LayoutGrid className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main Content Area: Loading, Error, Empty, or List */}
      {isLoading ? (
        <div className="h-64 flex flex-col items-center justify-center gap-3 bg-card-surface border border-border-subtle rounded-[12px]">
          <Spinner size="md" />
          <span className="text-xs font-mono text-text-secondary">Loading registered devices…</span>
        </div>
      ) : error ? (
        <div className="p-6 rounded-[12px] bg-[#ee0000]/10 border border-[#ee0000]/25 flex flex-col items-center justify-center text-center gap-2">
          <AlertTriangle className="w-6 h-6 text-[#ee0000]" />
          <span className="text-xs font-medium text-[#ee0000]">{error}</span>
          <button
            onClick={fetchDevices}
            className="mt-2 px-3 py-1 text-xs font-mono rounded bg-card-surface border border-border-subtle text-text-primary hover:bg-elevated-surface cursor-pointer"
          >
            Retry Query
          </button>
        </div>
      ) : devices.length === 0 ? (
        <div className="p-12 rounded-[12px] bg-card-surface border border-border-subtle text-center flex flex-col items-center justify-center shadow-[var(--shadow-whisper)]">
          <div className="w-12 h-12 rounded-full bg-elevated-surface border border-border-subtle flex items-center justify-center mb-3 text-text-muted">
            <Server className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-text-primary">
            No campus devices have been configured yet.
          </h3>
          <p className="text-xs text-text-secondary mt-1.5 max-w-md">
            Register authorized switches, routers, access points, or servers in this registry to enable multi-device campus monitoring without exposing credentials.
          </p>
          <button
            onClick={openAddModal}
            className="mt-4 flex items-center gap-1.5 px-3.5 py-1.5 rounded-[6px] bg-[#0070f3] hover:bg-[#0070f3]/90 text-white text-xs font-medium shadow-xs transition-colors cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Add First Device</span>
          </button>
        </div>
      ) : viewMode === 'table' ? (
        /* Table View */
        <div className="bg-card-surface border border-border-subtle rounded-[12px] overflow-hidden shadow-[var(--shadow-whisper)]">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-elevated-surface border-b border-border-subtle text-text-muted font-mono text-[11px] uppercase tracking-wider">
                <tr>
                  <th className="py-2.5 px-3.5 font-medium">Device & Model</th>
                  <th className="py-2.5 px-3.5 font-medium">Type</th>
                  <th className="py-2.5 px-3.5 font-medium">Management IP</th>
                  <th className="py-2.5 px-3.5 font-medium">Location</th>
                  <th className="py-2.5 px-3.5 font-medium">Method</th>
                  <th className="py-2.5 px-3.5 font-medium">Monitoring</th>
                  <th className="py-2.5 px-3.5 font-medium">Connection</th>
                  <th className="py-2.5 px-3.5 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle font-sans">
                {devices.map((dev) => (
                  <tr key={dev.id} className="hover:bg-elevated-surface/50 transition-colors">
                    <td className="py-3 px-3.5">
                      <div className="flex items-center gap-2.5">
                        <div className="p-1.5 rounded-[6px] bg-elevated-surface border border-border-subtle shrink-0">
                          {getDeviceIcon(dev.device_type)}
                        </div>
                        <div className="min-w-0">
                          <span className="font-medium text-text-primary block truncate">
                            {dev.name}
                          </span>
                          <span className="text-[11px] font-mono text-text-muted block truncate">
                            {dev.vendor_model || dev.id}
                          </span>
                        </div>
                      </div>
                    </td>

                    <td className="py-3 px-3.5 font-mono text-text-secondary uppercase text-[11px]">
                      {dev.device_type.replace('_', ' ')}
                    </td>

                    <td className="py-3 px-3.5 font-mono text-text-primary text-[11px]">
                      {dev.ip_address}
                    </td>

                    <td className="py-3 px-3.5">
                      <div className="min-w-0">
                        <span className="text-text-primary font-medium block truncate">
                          {dev.building} (Fl. {dev.floor})
                        </span>
                        <span className="text-[11px] text-text-muted block truncate">
                          {dev.department} {dev.location_description ? `• ${dev.location_description}` : ''}
                        </span>
                      </div>
                    </td>

                    <td className="py-3 px-3.5 font-mono text-text-secondary text-[11px]">
                      {dev.collection_method}
                    </td>

                    <td className="py-3 px-3.5">
                      <div className="flex flex-col gap-1 items-start">
                        <Badge
                          variant={
                            dev.monitoring_status === 'active'
                              ? 'success'
                              : dev.monitoring_status === 'maintenance'
                              ? 'warning'
                              : 'neutral'
                          }
                          size="sm"
                        >
                          {dev.monitoring_status.toUpperCase()}
                        </Badge>
                        {dev.polling_enabled ? (
                          <span className="text-[10px] text-emerald-400 font-mono font-medium flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                            POLLING
                          </span>
                        ) : (
                          <span className="text-[10px] text-text-muted font-mono">STANDBY</span>
                        )}
                      </div>
                    </td>

                    <td className="py-3 px-3.5">
                      <Badge
                        variant={
                          dev.reachability === 'reachable'
                            ? 'success'
                            : dev.reachability === 'unreachable'
                            ? 'error'
                            : dev.reachability === 'unsupported'
                            ? 'warning'
                            : dev.connection_status === 'online'
                            ? 'success'
                            : dev.connection_status === 'offline'
                            ? 'error'
                            : 'neutral'
                        }
                        size="sm"
                      >
                        {(dev.reachability || dev.connection_status).toUpperCase()}
                      </Badge>
                    </td>

                    <td className="py-3 px-3.5 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => {
                            setSelectedDetailDevice(dev);
                            setIsDetailModalOpen(true);
                          }}
                          className="p-1 rounded-[4px] text-accent-primary hover:bg-accent-primary/10 transition-colors cursor-pointer"
                          title="View live telemetry & device details"
                        >
                          <Activity className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => openEditModal(dev)}
                          className="p-1 rounded-[4px] text-text-muted hover:text-text-primary hover:bg-elevated-surface transition-colors cursor-pointer"
                          title="Edit device"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => setDeletingDeviceId(dev.id)}
                          className="p-1 rounded-[4px] text-text-muted hover:text-[#ee0000] hover:bg-[#ee0000]/10 transition-colors cursor-pointer"
                          title="Delete device"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* Grid Card View */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {devices.map((dev) => (
            <div
              key={dev.id}
              className="p-4 rounded-[12px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)] flex flex-col justify-between gap-3 hover:border-border-hover transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="p-2 rounded-[8px] bg-elevated-surface border border-border-subtle shrink-0">
                    {getDeviceIcon(dev.device_type)}
                  </div>
                  <div className="min-w-0">
                    <h4 className="font-semibold text-text-primary text-xs truncate">
                      {dev.name}
                    </h4>
                    <span className="text-[11px] font-mono text-text-muted block truncate">
                      {dev.ip_address}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  <button
                    onClick={() => {
                      setSelectedDetailDevice(dev);
                      setIsDetailModalOpen(true);
                    }}
                    className="p-1 text-accent-primary hover:bg-accent-primary/10 rounded cursor-pointer"
                    title="View live telemetry & device details"
                  >
                    <Activity className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => openEditModal(dev)}
                    className="p-1 text-text-muted hover:text-text-primary rounded cursor-pointer"
                    title="Edit"
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => setDeletingDeviceId(dev.id)}
                    className="p-1 text-text-muted hover:text-[#ee0000] rounded cursor-pointer"
                    title="Delete"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              <div className="space-y-1 text-xs border-y border-border-subtle py-2.5">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-text-muted flex items-center gap-1">
                    <Building2 className="w-3 h-3" /> Building:
                  </span>
                  <span className="font-medium text-text-primary">{dev.building} (Fl. {dev.floor})</span>
                </div>
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-text-muted flex items-center gap-1">
                    <MapPin className="w-3 h-3" /> Department:
                  </span>
                  <span className="text-text-secondary truncate max-w-[150px]">{dev.department}</span>
                </div>
                {dev.vendor_model && (
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-text-muted">Vendor/Model:</span>
                    <span className="font-mono text-text-secondary truncate max-w-[150px]">{dev.vendor_model}</span>
                  </div>
                )}
              </div>

              <div className="flex items-center justify-between gap-2 pt-0.5">
                <div className="flex items-center gap-1.5">
                  <Badge
                    variant={
                      dev.monitoring_status === 'active'
                        ? 'success'
                        : dev.monitoring_status === 'maintenance'
                        ? 'warning'
                        : 'neutral'
                    }
                    size="sm"
                  >
                    {dev.monitoring_status.toUpperCase()}
                  </Badge>
                  {dev.polling_enabled && (
                    <span className="text-[10px] text-emerald-400 font-mono flex items-center gap-1 font-medium">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      POLL
                    </span>
                  )}
                </div>

                <Badge
                  variant={
                    dev.reachability === 'reachable'
                      ? 'success'
                      : dev.reachability === 'unreachable'
                      ? 'error'
                      : dev.reachability === 'unsupported'
                      ? 'warning'
                      : 'neutral'
                  }
                  size="sm"
                >
                  {(dev.reachability || dev.connection_status || 'CONFIGURED').toUpperCase()}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add / Edit Device Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-card-surface border border-border-subtle rounded-[12px] shadow-[var(--shadow-floating)] max-w-lg w-full max-h-[90vh] flex flex-col animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="px-5 py-3.5 border-b border-border-subtle flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-text-primary tracking-[-0.28px]">
                  {editingDevice ? 'Edit Campus Device' : 'Register New Campus Device'}
                </h2>
                <p className="text-[11px] text-text-secondary mt-0.5">
                  Phase 1 registry registration. No SNMP or credentials required.
                </p>
              </div>
              <button
                onClick={() => setIsAddModalOpen(false)}
                className="p-1 rounded text-text-muted hover:text-text-primary cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Body / Form */}
            <form onSubmit={handleSaveDevice} className="p-5 overflow-y-auto space-y-3.5 flex-1">
              {formError && (
                <div className="p-2.5 rounded-[6px] bg-[#ee0000]/10 border border-[#ee0000]/25 text-[#ee0000] text-xs">
                  {formError}
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* Device Name */}
                <div>
                  <label className="block text-[11px] font-medium text-text-secondary mb-1">
                    Device Name <span className="text-[#ee0000]">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    placeholder="e.g. Core Switch Turing"
                    className="w-full px-2.5 py-1.5 text-xs rounded-[6px] bg-elevated-surface border border-border-subtle focus:border-[#0070f3] focus:outline-none text-text-primary"
                  />
                </div>

                {/* Management IP */}
                <div>
                  <label className="block text-[11px] font-medium text-text-secondary mb-1">
                    Management IP <span className="text-[#ee0000]">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={formIp}
                    onChange={(e) => setFormIp(e.target.value)}
                    placeholder="e.g. 10.10.1.1 or IPv6"
                    className="w-full px-2.5 py-1.5 text-xs font-mono rounded-[6px] bg-elevated-surface border border-border-subtle focus:border-[#0070f3] focus:outline-none text-text-primary"
                  />
                </div>

                {/* Device Type */}
                <div>
                  <label className="block text-[11px] font-medium text-text-secondary mb-1">
                    Device Category <span className="text-[#ee0000]">*</span>
                  </label>
                  <select
                    value={formType}
                    onChange={(e) => setFormType(e.target.value as DeviceType)}
                    className="w-full px-2.5 py-1.5 text-xs rounded-[6px] bg-elevated-surface border border-border-subtle focus:border-[#0070f3] focus:outline-none text-text-primary cursor-pointer"
                  >
                    <option value="router">Router</option>
                    <option value="switch">Switch</option>
                    <option value="access_point">Access Point</option>
                    <option value="server">Server</option>
                    <option value="host">Host</option>
                    <option value="other">Other</option>
                  </select>
                </div>

                {/* Optional Custom ID */}
                <div>
                  <label className="block text-[11px] font-medium text-text-secondary mb-1">
                    Device ID <span className="text-text-muted font-normal">(Optional)</span>
                  </label>
                  <input
                    type="text"
                    disabled={!!editingDevice}
                    value={formId}
                    onChange={(e) => setFormId(e.target.value)}
                    placeholder="e.g. rtr-core-01"
                    className="w-full px-2.5 py-1.5 text-xs font-mono rounded-[6px] bg-elevated-surface border border-border-subtle focus:border-[#0070f3] focus:outline-none text-text-primary disabled:opacity-50"
                  />
                </div>

                {/* Building */}
                <div>
                  <label className="block text-[11px] font-medium text-text-secondary mb-1">
                    Building <span className="text-[#ee0000]">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={formBuilding}
                    onChange={(e) => setFormBuilding(e.target.value)}
                    placeholder="e.g. Engineering Block"
                    className="w-full px-2.5 py-1.5 text-xs rounded-[6px] bg-elevated-surface border border-border-subtle focus:border-[#0070f3] focus:outline-none text-text-primary"
                  />
                </div>

                {/* Department */}
                <div>
                  <label className="block text-[11px] font-medium text-text-secondary mb-1">
                    Department <span className="text-[#ee0000]">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={formDept}
                    onChange={(e) => setFormDept(e.target.value)}
                    placeholder="e.g. Computer Science"
                    className="w-full px-2.5 py-1.5 text-xs rounded-[6px] bg-elevated-surface border border-border-subtle focus:border-[#0070f3] focus:outline-none text-text-primary"
                  />
                </div>

                {/* Floor */}
                <div>
                  <label className="block text-[11px] font-medium text-text-secondary mb-1">
                    Floor <span className="text-[#ee0000]">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={formFloor}
                    onChange={(e) => setFormFloor(e.target.value)}
                    placeholder="e.g. 1, 2, Ground"
                    className="w-full px-2.5 py-1.5 text-xs rounded-[6px] bg-elevated-surface border border-border-subtle focus:border-[#0070f3] focus:outline-none text-text-primary"
                  />
                </div>

                {/* Vendor / Model */}
                <div>
                  <label className="block text-[11px] font-medium text-text-secondary mb-1">
                    Vendor / Model <span className="text-text-muted font-normal">(Optional)</span>
                  </label>
                  <input
                    type="text"
                    value={formVendorModel}
                    onChange={(e) => setFormVendorModel(e.target.value)}
                    placeholder="e.g. Cisco C9200L"
                    className="w-full px-2.5 py-1.5 text-xs rounded-[6px] bg-elevated-surface border border-border-subtle focus:border-[#0070f3] focus:outline-none text-text-primary"
                  />
                </div>
              </div>

              {/* Location Description */}
              <div>
                <label className="block text-[11px] font-medium text-text-secondary mb-1">
                  Location Description <span className="text-text-muted font-normal">(Optional)</span>
                </label>
                <input
                  type="text"
                  value={formLocationDesc}
                  onChange={(e) => setFormLocationDesc(e.target.value)}
                  placeholder="e.g. Rack 02, Server Room 304"
                  className="w-full px-2.5 py-1.5 text-xs rounded-[6px] bg-elevated-surface border border-border-subtle focus:border-[#0070f3] focus:outline-none text-text-primary"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1 border-t border-border-subtle">
                {/* Collection Method */}
                <div>
                  <label className="block text-[11px] font-medium text-text-secondary mb-1">
                    Collection Method
                  </label>
                  <select
                    value={formCollectionMethod}
                    onChange={(e) => setFormCollectionMethod(e.target.value as CollectionMethod)}
                    className="w-full px-2 py-1.5 text-xs font-mono rounded-[6px] bg-elevated-surface border border-border-subtle focus:border-[#0070f3] focus:outline-none text-text-primary cursor-pointer"
                  >
                    <option value="manual">manual</option>
                    <option value="mock">mock (simulated lab)</option>
                    <option value="local_psutil">local_psutil</option>
                    <option value="snmp">snmp</option>
                    <option value="netflow">netflow</option>
                    <option value="api">api</option>
                  </select>
                </div>

                {/* Monitoring Status */}
                <div>
                  <label className="block text-[11px] font-medium text-text-secondary mb-1">
                    Monitoring Status
                  </label>
                  <select
                    value={formMonitoringStatus}
                    onChange={(e) => setFormMonitoringStatus(e.target.value as MonitoringStatus)}
                    className="w-full px-2 py-1.5 text-xs font-mono rounded-[6px] bg-elevated-surface border border-border-subtle focus:border-[#0070f3] focus:outline-none text-text-primary cursor-pointer"
                  >
                    <option value="active">active</option>
                    <option value="inactive">inactive</option>
                    <option value="maintenance">maintenance</option>
                  </select>
                </div>

                {/* Connection Status */}
                <div>
                  <label className="block text-[11px] font-medium text-text-secondary mb-1">
                    Connection Status
                  </label>
                  <select
                    value={formConnectionStatus}
                    onChange={(e) => setFormConnectionStatus(e.target.value as ConnectionStatus)}
                    className="w-full px-2 py-1.5 text-xs font-mono rounded-[6px] bg-elevated-surface border border-border-subtle focus:border-[#0070f3] focus:outline-none text-text-primary cursor-pointer"
                  >
                    <option value="unknown">unknown</option>
                    <option value="online">online</option>
                    <option value="offline">offline</option>
                  </select>
                </div>
              </div>

              {/* Modal Actions */}
              <div className="pt-3 border-t border-border-subtle flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-3 py-1.5 rounded-[6px] border border-border-subtle hover:bg-elevated-surface text-xs text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={formSubmitting}
                  className="px-3.5 py-1.5 rounded-[6px] bg-[#0070f3] hover:bg-[#0070f3]/90 text-white text-xs font-medium shadow-xs transition-colors cursor-pointer disabled:opacity-50"
                >
                  {formSubmitting ? 'Saving…' : editingDevice ? 'Update Device' : 'Register Device'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deletingDeviceId && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-card-surface border border-border-subtle rounded-[12px] p-5 shadow-[var(--shadow-floating)] max-w-sm w-full space-y-3 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center gap-2 text-[#ee0000]">
              <AlertTriangle className="w-5 h-5 shrink-0" />
              <h3 className="text-sm font-semibold text-text-primary">Confirm Deletion</h3>
            </div>
            <p className="text-xs text-text-secondary">
              Are you sure you want to remove device <span className="font-mono font-medium text-text-primary">{deletingDeviceId}</span> from the campus monitoring registry?
            </p>
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-border-subtle">
              <button
                onClick={() => setDeletingDeviceId(null)}
                className="px-3 py-1.5 rounded-[6px] border border-border-subtle hover:bg-elevated-surface text-xs text-text-secondary hover:text-text-primary cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteDevice}
                className="px-3.5 py-1.5 rounded-[6px] bg-[#ee0000] hover:bg-[#ee0000]/90 text-white text-xs font-medium cursor-pointer"
              >
                Delete Device
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Device Detail & Live Telemetry Modal */}
      {selectedDetailDevice && (
        <DeviceDetailModal
          device={selectedDetailDevice}
          isOpen={isDetailModalOpen}
          onClose={() => {
            setIsDetailModalOpen(false);
            setSelectedDetailDevice(null);
          }}
          onDeviceUpdated={(updated) => {
            setDevices((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
            setSelectedDetailDevice(updated);
          }}
          onNotify={onNotify}
        />
      )}
    </div>
  );
};
