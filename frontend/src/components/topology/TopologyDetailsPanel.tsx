import React, { useState, useEffect } from 'react';
import {
  X,
  Router,
  Network,
  Wifi,
  Server,
  HelpCircle,
  Play,
  ExternalLink,
  ArrowRightLeft,
} from 'lucide-react';
import type { TopologyNode, TopologyLink, DeviceDiscoveryStatusResponse, TopologyEdge } from '../../types/topology';
import type { Device } from '../../types/device';
import { topologyApi } from '../../services/topologyApi';
import { Spinner } from '../common/Spinner';

interface TopologyDetailsPanelProps {
  selectedNode: TopologyNode | null;
  selectedLink: TopologyLink | null;
  selectedEdge?: TopologyEdge | null;
  onClose: () => void;
  onOpenDeviceModal?: (device: Device) => void;
  onDiscoveryTriggered?: () => void;
  onNotify?: (type: 'success' | 'error' | 'info', message: string) => void;
}

export const TopologyDetailsPanel: React.FC<TopologyDetailsPanelProps> = ({
  selectedNode,
  selectedLink,
  selectedEdge,
  onClose,
  onOpenDeviceModal,
  onDiscoveryTriggered,
  onNotify,
}) => {
  const [discoveryStatus, setDiscoveryStatus] = useState<DeviceDiscoveryStatusResponse | null>(null);
  const [isLoadingStatus, setIsLoadingStatus] = useState<boolean>(false);
  const [isDiscovering, setIsDiscovering] = useState<boolean>(false);

  // Fetch discovery status when a node is selected
  useEffect(() => {
    if (!selectedNode || selectedNode.isUnresolved) {
      setDiscoveryStatus(null);
      return;
    }

    let isMounted = true;
    const fetchStatus = async () => {
      setIsLoadingStatus(true);
      try {
        const res = await topologyApi.getDiscoveryStatus(selectedNode.id);
        if (isMounted) setDiscoveryStatus(res);
      } catch {
        // Device may not have run discovery yet; status will be empty/idle
      } finally {
        if (isMounted) setIsLoadingStatus(false);
      }
    };

    fetchStatus();
    return () => {
      isMounted = false;
    };
  }, [selectedNode]);

  // Handle Trigger Discovery
  const handleTriggerDiscovery = async () => {
    if (!selectedNode || selectedNode.isUnresolved) return;
    setIsDiscovering(true);
    try {
      const res = await topologyApi.triggerDiscovery(selectedNode.id);
      if (res.success || res.status === 'empty' || res.status === 'unsupported') {
        onNotify?.(
          'success',
          `Discovery for ${selectedNode.label}: Found ${res.neighbors_found} neighbors (${res.neighbors_resolved} resolved).`
        );
        // Refresh local status
        const updatedStatus = await topologyApi.getDiscoveryStatus(selectedNode.id);
        setDiscoveryStatus(updatedStatus);
        onDiscoveryTriggered?.();
      } else {
        onNotify?.('error', res.message || 'Discovery attempt failed.');
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Discovery request failed';
      onNotify?.('error', msg);
    } finally {
      setIsDiscovering(false);
    }
  };

  if (!selectedNode && !selectedLink) return null;

  return (
    <aside className="w-full lg:w-96 shrink-0 bg-sidebar-bg border border-border-subtle rounded-xl p-5 flex flex-col gap-4 shadow-sm animate-in fade-in slide-in-from-right-4 duration-150">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border-subtle pb-3">
        <div className="flex items-center gap-2">
          {selectedNode ? (
            selectedNode.isUnresolved ? (
              <HelpCircle className="w-5 h-5 text-purple-400" />
            ) : selectedNode.deviceType === 'router' ? (
              <Router className="w-5 h-5 text-indigo-400" />
            ) : selectedNode.deviceType === 'switch' ? (
              <Network className="w-5 h-5 text-sky-400" />
            ) : selectedNode.deviceType === 'access_point' ? (
              <Wifi className="w-5 h-5 text-emerald-400" />
            ) : (
              <Server className="w-5 h-5 text-amber-400" />
            )
          ) : (
            <ArrowRightLeft className="w-5 h-5 text-sky-400" />
          )}
          <h3 className="font-semibold text-text-primary text-sm">
            {selectedNode ? (selectedNode.isUnresolved ? 'Unresolved Neighbor' : 'Device Inspector') : 'Link Inspector'}
          </h3>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1 text-text-muted hover:text-text-primary hover:bg-surface-hover rounded-md transition-colors"
          aria-label="Close details panel"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* NODE DETAILS VIEW */}
      {selectedNode && (
        <div className="flex flex-col gap-4 text-xs">
          {/* Title & Core Identifiers */}
          <div>
            <div className="text-base font-bold text-text-primary truncate">
              {selectedNode.label}
            </div>
            <div className="font-mono text-text-muted text-[11px] mt-0.5">
              {selectedNode.isUnresolved ? selectedNode.remoteChassisId : selectedNode.ipAddress}
            </div>
          </div>

          {/* Badges Bar */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="px-2 py-0.5 rounded-md font-medium capitalize text-[10px] bg-surface-hover text-text-secondary border border-border-subtle">
              {selectedNode.isUnresolved ? 'Unresolved Node' : selectedNode.deviceType}
            </span>
            {selectedNode.isMock && (
              <span className="px-2 py-0.5 rounded-md font-bold text-[10px] bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                MOCK TOPOLOGY
              </span>
            )}
            <span
              className={`px-2 py-0.5 rounded-md font-medium text-[10px] ${
                selectedNode.computedStatus === 'online'
                  ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                  : selectedNode.computedStatus === 'stale'
                  ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400'
                  : 'bg-neutral-500/15 text-neutral-400'
              }`}
            >
              Status: {selectedNode.computedStatus}
            </span>
          </div>

          {/* Unresolved Explanation Banner */}
          {selectedNode.isUnresolved && (
            <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-900 dark:text-purple-200">
              <div className="font-semibold mb-1 flex items-center gap-1.5">
                <HelpCircle className="w-3.5 h-3.5" />
                External Boundary Neighbor
              </div>
              <p className="text-[11px] leading-relaxed text-purple-800 dark:text-purple-300">
                This device was discovered via LLDP/CDP advertisement frames, but does not match any registered campus inventory record.
              </p>
            </div>
          )}

          {/* Location & Metadata Section */}
          {!selectedNode.isUnresolved && (
            <div className="grid grid-cols-2 gap-2 p-3 rounded-lg bg-elevated-surface border border-border-subtle">
              <div>
                <span className="text-text-muted block text-[10px]">Building</span>
                <span className="font-medium text-text-primary">{selectedNode.building || 'Unassigned'}</span>
              </div>
              <div>
                <span className="text-text-muted block text-[10px]">Floor</span>
                <span className="font-medium text-text-primary">{selectedNode.floor || 'N/A'}</span>
              </div>
              <div>
                <span className="text-text-muted block text-[10px]">Department</span>
                <span className="font-medium text-text-primary">{selectedNode.department || 'N/A'}</span>
              </div>
              <div>
                <span className="text-text-muted block text-[10px]">Topology Degree</span>
                <span className="font-medium text-text-primary">{selectedNode.degree} links</span>
              </div>
            </div>
          )}

          {/* Protocol Capabilities & Status */}
          {!selectedNode.isUnresolved && (
            <div className="p-3 rounded-lg bg-card-surface border border-border-subtle flex flex-col gap-2">
              <span className="font-semibold text-text-primary text-[11px]">
                Link-Layer Capabilities
              </span>
              {isLoadingStatus ? (
                <div className="flex items-center gap-2 text-text-muted py-2">
                  <Spinner size="sm" /> Fetching capability state...
                </div>
              ) : discoveryStatus ? (
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-text-muted">LLDP Support</span>
                    <span
                      className={`font-mono font-medium ${
                        discoveryStatus.lldp_supported ? 'text-emerald-500' : 'text-text-muted'
                      }`}
                    >
                      {discoveryStatus.lldp_supported ? 'Supported' : 'Disabled / N/A'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-text-muted">CDP Support</span>
                    <span
                      className={`font-mono font-medium ${
                        discoveryStatus.cdp_supported ? 'text-emerald-500' : 'text-text-muted'
                      }`}
                    >
                      {discoveryStatus.cdp_supported ? 'Supported' : 'Disabled / N/A'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-text-muted">Last Discovery</span>
                    <span className="font-mono text-text-secondary">
                      {discoveryStatus.last_discovery_at
                        ? new Date(discoveryStatus.last_discovery_at).toLocaleTimeString()
                        : 'Never'}
                    </span>
                  </div>
                  {discoveryStatus.last_error && (
                    <div className="text-[10px] text-rose-500 font-mono mt-1 p-1.5 bg-rose-500/10 rounded border border-rose-500/20">
                      Error: {discoveryStatus.last_error}
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-text-muted text-[11px]">No discovery attempts recorded yet.</div>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-col gap-2 pt-2 border-t border-border-subtle">
            {!selectedNode.isUnresolved && (
              <button
                type="button"
                onClick={handleTriggerDiscovery}
                disabled={isDiscovering}
                className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-semibold bg-accent-primary hover:bg-accent-primary-hover text-white transition-colors disabled:opacity-50"
              >
                {isDiscovering ? (
                  <>
                    <Spinner size="sm" /> Querying Neighbors...
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5 fill-current" /> Run LLDP/CDP Discovery
                  </>
                )}
              </button>
            )}

            {selectedNode.deviceRecord && onOpenDeviceModal && (
              <button
                type="button"
                onClick={() => onOpenDeviceModal(selectedNode.deviceRecord!)}
                className="w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-xs font-medium bg-surface-hover hover:bg-elevated-surface text-text-primary border border-border-subtle transition-colors"
              >
                <ExternalLink className="w-3.5 h-3.5" /> View Device Telemetry History
              </button>
            )}
          </div>
        </div>
      )}

      {/* LINK (EDGE) DETAILS VIEW */}
      {selectedLink && (
        <div className="flex flex-col gap-4 text-xs">
          <div>
            <div className="text-xs font-semibold text-text-muted uppercase tracking-wider">
              {selectedEdge?.isBidirectional ? 'Physical Interconnect (Bidirectional)' : 'Discovered Interconnect (One-Sided)'}
            </div>
            <div className="text-sm font-bold text-text-primary mt-1 flex items-center gap-1.5 flex-wrap">
              <span>{selectedEdge?.sourceDeviceName || selectedLink.source_device_id}</span>
              <span className="text-text-muted">{selectedEdge?.isBidirectional ? '↔' : '→'}</span>
              <span>{selectedEdge?.targetDeviceName || selectedLink.remote_device_id || selectedLink.remote_system_name || selectedLink.remote_chassis_id}</span>
            </div>
          </div>

          {/* Protocol & Verification Badges */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span
              className={`px-2 py-0.5 rounded-md font-bold text-[10px] ${
                selectedEdge?.conflictingProtocols
                  ? 'bg-purple-500/15 text-purple-600 dark:text-purple-400 border border-purple-500/20'
                  : selectedLink.protocol === 'lldp'
                  ? 'bg-sky-500/15 text-sky-600 dark:text-sky-400 border border-sky-500/20'
                  : 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
              }`}
            >
              {selectedEdge?.conflictingProtocols ? 'MIXED PROTOCOL' : selectedLink.protocol.toUpperCase()}
            </span>

            {selectedEdge?.isBidirectional ? (
              <span className="px-2 py-0.5 rounded-md font-medium text-[10px] bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                BIDIRECTIONAL CONFIRMED
              </span>
            ) : (
              <span className="px-2 py-0.5 rounded-md font-medium text-[10px] bg-sky-500/15 text-sky-600 dark:text-sky-400 border border-sky-500/20">
                ONE-SIDED OBSERVATION
              </span>
            )}

            <span
              className={`px-2 py-0.5 rounded-md font-medium text-[10px] ${
                selectedLink.link_status === 'active'
                  ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                  : 'bg-amber-500/15 text-amber-600 dark:text-amber-400'
              }`}
            >
              {selectedLink.link_status.toUpperCase()}
            </span>

            {selectedLink.is_mock ? (
              <span className="px-2 py-0.5 rounded-md font-bold text-[10px] bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                MOCK DATA
              </span>
            ) : (
              <span className="px-2 py-0.5 rounded-md font-bold text-[10px] bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                ACTUAL SNMP
              </span>
            )}
          </div>

          {/* Interface Details */}
          <div className="p-3 rounded-lg bg-elevated-surface border border-border-subtle flex flex-col gap-2.5">
            <div>
              <span className="text-text-muted block text-[10px]">
                {selectedEdge?.sourceDeviceName || selectedLink.source_device_id} Interface
              </span>
              <span className="font-mono font-medium text-text-primary">
                {selectedLink.local_interface}
              </span>
            </div>
            <div>
              <span className="text-text-muted block text-[10px]">
                {selectedEdge?.targetDeviceName || selectedLink.remote_device_id || selectedLink.remote_system_name || 'Remote Peer'} Port ID
              </span>
              <span className="font-mono font-medium text-text-primary">
                {selectedLink.remote_port_id}
              </span>
            </div>
            {selectedLink.remote_port_desc && (
              <div>
                <span className="text-text-muted block text-[10px]">Remote Port Description</span>
                <span className="text-text-secondary text-[11px]">
                  {selectedLink.remote_port_desc}
                </span>
              </div>
            )}

            {selectedEdge?.reciprocalLinkRecord && (
              <div className="pt-2 border-t border-border-subtle text-[11px] text-emerald-600 dark:text-emerald-400">
                ✓ Reciprocal observation confirmed by both endpoint MIB tables.
              </div>
            )}

            {!selectedEdge?.isBidirectional && (
              <div className="pt-2 border-t border-border-subtle text-[11px] text-text-muted leading-relaxed">
                One-sided observation: Discovered via {selectedLink.source_device_id} MIB table. Remote peer has not broadcasted reciprocal advertisement.
              </div>
            )}
          </div>

          {/* Remote Chassis Identifiers */}
          <div className="p-3 rounded-lg bg-card-surface border border-border-subtle flex flex-col gap-1.5 font-mono text-[11px]">
            <div className="flex items-center justify-between">
              <span className="text-text-muted font-sans text-[10px]">Remote Chassis ID</span>
              <span className="text-text-primary">{selectedLink.remote_chassis_id}</span>
            </div>
            {selectedLink.remote_system_name && (
              <div className="flex items-center justify-between">
                <span className="text-text-muted font-sans text-[10px]">Remote System Name</span>
                <span className="text-text-primary truncate max-w-[160px]">
                  {selectedLink.remote_system_name}
                </span>
              </div>
            )}
            <div className="flex items-center justify-between">
              <span className="text-text-muted font-sans text-[10px]">Resolution State</span>
              <span className={selectedLink.resolution_state === 'resolved' ? 'text-emerald-500 font-sans' : 'text-purple-400 font-sans'}>
                {selectedLink.resolution_state === 'resolved' ? 'Resolved Campus Node' : 'Unresolved External Peer'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-text-muted font-sans text-[10px]">Last Observation</span>
              <span className="text-text-secondary">
                {new Date(selectedLink.last_seen_at).toLocaleTimeString()}
              </span>
            </div>
          </div>

          {/* Stale Observation Note */}
          {selectedLink.is_stale && (
            <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-900 dark:text-amber-200 text-[11px] leading-relaxed">
              <span className="font-semibold block mb-0.5">Stale Link Notice</span>
              This observation exceeded the configured freshness threshold without a renewal advertisement. Stale status indicates absence of fresh discovery packets, NOT a confirmed physical link failure or interface down state.
            </div>
          )}

          {/* Unresolved Note */}
          {selectedLink.resolution_state === 'unresolved' && (
            <div className="p-2.5 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-900 dark:text-purple-200 text-[11px] leading-relaxed">
              <span className="font-semibold block mb-0.5">Unresolved Peer Notice</span>
              The remote chassis ID does not map to any registered campus device in the database. Register this device in the Device Inventory to enable full telemetry polling.
            </div>
          )}
        </div>
      )}
    </aside>
  );
};
