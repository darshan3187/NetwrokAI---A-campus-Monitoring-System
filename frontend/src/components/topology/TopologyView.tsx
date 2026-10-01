import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  GitFork,
  AlertCircle,
  RotateCw,
  Server,
  Play,
  FilterX,
} from 'lucide-react';
import { topologyApi } from '../../services/topologyApi';
import { deviceApi } from '../../services/deviceApi';
import type {
  TopologyLink,
  TopologyNode,
  TopologyEdge,
  TopologyFilterOptions,
  TopologyProtocol,
  TopologyLinkStatus,
} from '../../types/topology';
import type { Device } from '../../types/device';
import { TopologySummaryBar } from './TopologySummaryBar';
import { TopologyFiltersBar } from './TopologyFiltersBar';
import { TopologyGraphCanvas } from './TopologyGraphCanvas';
import { TopologyDetailsPanel } from './TopologyDetailsPanel';
import { DeviceDetailModal } from '../devices/DeviceDetailModal';
import { Spinner } from '../common/Spinner';

interface TopologyViewProps {
  onNavigateToDevices?: () => void;
  onNotify?: (type: 'success' | 'error' | 'info', message: string) => void;
}

const DEFAULT_FILTERS: TopologyFilterOptions = {
  building: 'all',
  deviceType: 'all',
  protocol: 'all',
  linkStatus: 'all',
  resolutionState: 'all',
  dataSource: 'all',
  searchQuery: '',
};

export const TopologyView: React.FC<TopologyViewProps> = ({
  onNavigateToDevices,
  onNotify,
}) => {
  // Primary Data
  const [devices, setDevices] = useState<Device[]>([]);
  const [links, setLinks] = useState<TopologyLink[]>([]);
  const [unresolvedLinks, setUnresolvedLinks] = useState<TopologyLink[]>([]);

  // UI & Loading States
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  // Filter & Selection States
  const [filters, setFilters] = useState<TopologyFilterOptions>(DEFAULT_FILTERS);
  const [selectedNode, setSelectedNode] = useState<TopologyNode | null>(null);
  const [selectedLink, setSelectedLink] = useState<TopologyLink | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<TopologyEdge | null>(null);

  // Device Detail Modal
  const [modalDevice, setModalDevice] = useState<Device | null>(null);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);

  // Load All Topology & Device Data
  const loadTopologyData = useCallback(async (isSilent = false) => {
    if (!isSilent) setIsLoading(true);
    else setIsRefreshing(true);
    setError(null);

    try {
      const [devListRes, linkListRes, unresRes] = await Promise.all([
        deviceApi.getDevices(),
        topologyApi.getLinks({ limit: 500 }),
        topologyApi.getUnresolvedNeighbors(),
      ]);

      setDevices(devListRes.devices || []);
      setLinks(linkListRes.links || []);
      setUnresolvedLinks(unresRes.unresolved_neighbors || []);
      setLastUpdated(new Date());
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load topology data';
      setError(msg);
      onNotify?.('error', msg);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [onNotify]);

  useEffect(() => {
    loadTopologyData();
  }, [loadTopologyData]);

  // Available Buildings for Dropdown Filter
  const availableBuildings = useMemo(() => {
    const bSet = new Set<string>();
    devices.forEach((d) => {
      if (d.building) bSet.add(d.building);
    });
    return Array.from(bSet).sort();
  }, [devices]);

  // Filter Change Handler
  const handleFilterChange = (key: keyof TopologyFilterOptions, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  // Reset Filters Handler
  const handleResetFilters = () => {
    setFilters(DEFAULT_FILTERS);
    setSelectedNode(null);
    setSelectedLink(null);
    setSelectedEdge(null);
  };

  const hasActiveFilters = useMemo(() => {
    return (
      filters.building !== 'all' ||
      filters.deviceType !== 'all' ||
      filters.protocol !== 'all' ||
      filters.linkStatus !== 'all' ||
      filters.resolutionState !== 'all' ||
      filters.dataSource !== 'all' ||
      filters.searchQuery.trim() !== ''
    );
  }, [filters]);

  // Filtered Links
  const filteredLinks = useMemo(() => {
    const q = filters.searchQuery.trim().toLowerCase();
    const deviceMap = new Map(devices.map((d) => [d.id, d]));

    return links.filter((link) => {
      // Protocol Filter
      if (filters.protocol !== 'all' && link.protocol !== filters.protocol) return false;

      // Link Status Filter
      if (filters.linkStatus !== 'all' && link.link_status !== filters.linkStatus) return false;

      // Resolution State Filter
      if (filters.resolutionState !== 'all' && link.resolution_state !== filters.resolutionState) return false;

      // Data Source Filter (Actual SNMP vs Mock)
      if (filters.dataSource === 'actual' && link.is_mock) return false;
      if (filters.dataSource === 'mock' && !link.is_mock) return false;

      // Building Filter (check source or remote device)
      if (filters.building !== 'all') {
        const srcDev = deviceMap.get(link.source_device_id);
        const remDev = link.remote_device_id ? deviceMap.get(link.remote_device_id) : null;
        const matchesSrc = srcDev && srcDev.building === filters.building;
        const matchesRem = remDev && remDev.building === filters.building;
        if (!matchesSrc && !matchesRem) return false;
      }

      // Device Type Filter
      if (filters.deviceType !== 'all') {
        const srcDev = deviceMap.get(link.source_device_id);
        const remDev = link.remote_device_id ? deviceMap.get(link.remote_device_id) : null;
        const matchesSrc = srcDev && srcDev.device_type === filters.deviceType;
        const matchesRem = remDev && remDev.device_type === filters.deviceType;
        if (!matchesSrc && !matchesRem) return false;
      }

      // Search Query Filter
      if (q) {
        const matchSrcId = link.source_device_id.toLowerCase().includes(q);
        const matchRemId = (link.remote_device_id || '').toLowerCase().includes(q);
        const matchChassis = link.remote_chassis_id.toLowerCase().includes(q);
        const matchSysName = (link.remote_system_name || '').toLowerCase().includes(q);
        const matchLocalIf = link.local_interface.toLowerCase().includes(q);
        const matchRemoteIf = link.remote_port_id.toLowerCase().includes(q);

        const srcDev = deviceMap.get(link.source_device_id);
        const matchSrcName = srcDev?.name.toLowerCase().includes(q) || false;
        const matchSrcIp = srcDev?.ip_address.toLowerCase().includes(q) || false;

        if (
          !matchSrcId &&
          !matchRemId &&
          !matchChassis &&
          !matchSysName &&
          !matchLocalIf &&
          !matchRemoteIf &&
          !matchSrcName &&
          !matchSrcIp
        ) {
          return false;
        }
      }

      return true;
    });
  }, [links, devices, filters]);

  // Helper to normalize interface names for reciprocal comparison (e.g. GigabitEthernet0/1 <-> gi0/1)
  const normalizePort = (p: string): string =>
    p.trim().toLowerCase().replace(/^gigabitethernet/i, 'gi').replace(/^fastethernet/i, 'fa').replace(/^tengigabitethernet/i, 'te');

  // Construct Graph Nodes and Edges from filtered links and devices
  const { graphNodes, graphEdges } = useMemo(() => {
    const nodeMap = new Map<string, TopologyNode>();
    const deviceMap = new Map(devices.map((d) => [d.id, d]));

    // 1. Safe Physical Edge Deduplication
    // Consolidate reciprocal directional observations (A->B and B->A) into a single physical edge
    // without mutating original backend records.
    const processedLinkIds = new Set<number>();
    const edges: TopologyEdge[] = [];

    filteredLinks.forEach((link) => {
      if (processedLinkIds.has(link.id)) return;

      let reciprocalLink: TopologyLink | null = null;
      if (link.remote_device_id) {
        reciprocalLink = filteredLinks.find((other) => {
          if (other.id === link.id || processedLinkIds.has(other.id)) return false;
          if (other.source_device_id !== link.remote_device_id) return false;
          if (other.remote_device_id !== link.source_device_id) return false;

          const normLinkLocal = normalizePort(link.local_interface);
          const normLinkRemote = normalizePort(link.remote_port_id);
          const normOtherLocal = normalizePort(other.local_interface);
          const normOtherRemote = normalizePort(other.remote_port_id);

          return normLinkLocal === normOtherRemote && normLinkRemote === normOtherLocal;
        }) || null;
      }

      if (reciprocalLink) {
        processedLinkIds.add(link.id);
        processedLinkIds.add(reciprocalLink.id);

        // Deterministic endpoint ordering for stable edge keys
        const isForward = link.source_device_id <= reciprocalLink.source_device_id;
        const primary = isForward ? link : reciprocalLink;
        const secondary = isForward ? reciprocalLink : link;

        const hasConflictingProtocols = primary.protocol !== secondary.protocol;
        const protocol: TopologyProtocol | 'mixed' = hasConflictingProtocols ? 'mixed' : primary.protocol;

        const bothStale = primary.link_status === 'stale' && secondary.link_status === 'stale';
        const linkStatus: TopologyLinkStatus = bothStale ? 'stale' : 'active';

        const srcDev = deviceMap.get(primary.source_device_id);
        const tgtDev = deviceMap.get(primary.remote_device_id!);

        edges.push({
          id: `edge_bi_${primary.id}_${secondary.id}`,
          source: primary.source_device_id,
          target: primary.remote_device_id!,
          sourceInterface: primary.local_interface,
          targetInterface: primary.remote_port_id,
          protocol,
          linkStatus,
          isStale: bothStale,
          isMock: primary.is_mock || secondary.is_mock,
          resolutionState: 'resolved',
          lastSeenAt: primary.last_seen_at > secondary.last_seen_at ? primary.last_seen_at : secondary.last_seen_at,
          discoveredAt: primary.discovered_at < secondary.discovered_at ? primary.discovered_at : secondary.discovered_at,
          linkRecord: primary,
          isBidirectional: true,
          reciprocalLinkRecord: secondary,
          conflictingProtocols: hasConflictingProtocols,
          sourceDeviceName: srcDev?.name,
          targetDeviceName: tgtDev?.name,
        });
      } else {
        // One-sided observation
        processedLinkIds.add(link.id);
        const targetNodeId = link.remote_device_id || `unres_${link.remote_chassis_id}`;
        const srcDev = deviceMap.get(link.source_device_id);
        const tgtDev = link.remote_device_id ? deviceMap.get(link.remote_device_id) : null;

        edges.push({
          id: `edge_single_${link.id}`,
          source: link.source_device_id,
          target: targetNodeId,
          sourceInterface: link.local_interface,
          targetInterface: link.remote_port_id,
          protocol: link.protocol,
          linkStatus: link.link_status,
          isStale: link.is_stale,
          isMock: link.is_mock,
          resolutionState: link.resolution_state,
          lastSeenAt: link.last_seen_at,
          discoveredAt: link.discovered_at,
          linkRecord: link,
          isBidirectional: false,
          reciprocalLinkRecord: null,
          sourceDeviceName: srcDev?.name,
          targetDeviceName: tgtDev?.name || link.remote_system_name || undefined,
        });
      }
    });

    // 2. Synchronized Node Degree Calculation based on visible physical edges
    const nodeDegreeMap = new Map<string, number>();
    edges.forEach((edge) => {
      nodeDegreeMap.set(edge.source, (nodeDegreeMap.get(edge.source) || 0) + 1);
      nodeDegreeMap.set(edge.target, (nodeDegreeMap.get(edge.target) || 0) + 1);
    });

    // 3. Registered Devices Inclusion: Ensure registered campus devices remain visible
    // even when isolated (degree === 0), respecting active device filters.
    const visibleDevices = devices.filter((d) => {
      if (filters.building !== 'all' && d.building !== filters.building) {
        // Also keep device if it is an endpoint of a visible edge
        return nodeDegreeMap.has(d.id);
      }
      if (filters.deviceType !== 'all' && d.device_type !== filters.deviceType) {
        return nodeDegreeMap.has(d.id);
      }
      if (filters.dataSource === 'actual' && d.collection_method === 'mock') {
        return nodeDegreeMap.has(d.id);
      }
      if (filters.dataSource === 'mock' && d.collection_method !== 'mock') {
        return nodeDegreeMap.has(d.id);
      }
      if (filters.searchQuery) {
        const q = filters.searchQuery.toLowerCase();
        const matches =
          d.name.toLowerCase().includes(q) ||
          d.ip_address.toLowerCase().includes(q) ||
          d.device_type.toLowerCase().includes(q) ||
          (d.building || '').toLowerCase().includes(q);
        return matches || nodeDegreeMap.has(d.id);
      }
      return true;
    });

    visibleDevices.forEach((d) => {
      nodeMap.set(d.id, {
        id: d.id,
        label: d.name,
        ipAddress: d.ip_address,
        deviceType: d.device_type,
        building: d.building,
        floor: d.floor,
        department: d.department,
        isUnresolved: false,
        isMock: d.collection_method === 'mock',
        computedStatus: d.computed_status || 'unknown',
        deviceRecord: d,
        x: 0,
        y: 0,
        degree: nodeDegreeMap.get(d.id) || 0,
      });
    });

    // 4. Add participating unresolved nodes from edges
    edges.forEach((edge) => {
      if (edge.target.startsWith('unres_')) {
        const unresId = edge.target;
        if (!nodeMap.has(unresId)) {
          const l = edge.linkRecord;
          nodeMap.set(unresId, {
            id: unresId,
            label: l.remote_system_name || `External (${l.remote_chassis_id.slice(-5)})`,
            ipAddress: l.remote_chassis_id,
            deviceType: 'unresolved',
            building: 'External',
            floor: 'N/A',
            department: 'External',
            isUnresolved: true,
            isMock: l.is_mock,
            computedStatus: 'unknown',
            remoteChassisId: l.remote_chassis_id,
            remoteSystemDesc: l.remote_system_desc || undefined,
            x: 0,
            y: 0,
            degree: nodeDegreeMap.get(unresId) || 0,
          });
        }
      }
    });

    return {
      graphNodes: Array.from(nodeMap.values()),
      graphEdges: edges,
    };
  }, [filteredLinks, devices, filters]);

  // Check data sources across all links
  const hasMockLinks = useMemo(() => links.some((l) => l.is_mock), [links]);
  const hasActualLinks = useMemo(() => links.some((l) => !l.is_mock), [links]);

  // Active / Stale Link Counts
  const activeLinksCount = useMemo(() => links.filter((l) => l.link_status === 'active').length, [links]);
  const staleLinksCount = useMemo(() => links.filter((l) => l.link_status === 'stale').length, [links]);

  // Handle Quick Discovery Trigger for first device (Empty State Helper)
  const handleTriggerInitialDiscovery = async () => {
    if (devices.length === 0) return;
    const targetDev = devices[0];
    try {
      setIsRefreshing(true);
      const res = await topologyApi.triggerDiscovery(targetDev.id);
      onNotify?.(
        res.success ? 'success' : 'info',
        res.message || `Discovery completed for ${targetDev.name}.`
      );
      await loadTopologyData(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Discovery attempt failed';
      onNotify?.('error', msg);
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Summary KPI Header */}
      <TopologySummaryBar
        totalDevices={devices.length}
        totalLinks={links.length}
        activeLinks={activeLinksCount}
        staleLinks={staleLinksCount}
        unresolvedCount={unresolvedLinks.length}
        hasMockLinks={hasMockLinks}
        hasActualLinks={hasActualLinks}
        isRefreshing={isRefreshing}
        onRefresh={() => loadTopologyData(true)}
        lastUpdated={lastUpdated}
      />

      {/* Filter Toolbar */}
      <TopologyFiltersBar
        filters={filters}
        availableBuildings={availableBuildings}
        onFilterChange={handleFilterChange}
        onResetFilters={handleResetFilters}
        hasActiveFilters={hasActiveFilters}
        totalFilteredCount={filteredLinks.length}
        totalUnfilteredCount={links.length}
      />

      {/* Primary Content View: Loading / Error / Empty / Visualizer */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center p-24 bg-sidebar-bg border border-border-subtle rounded-xl min-h-[450px]">
          <Spinner size="lg" />
          <span className="text-sm text-text-muted mt-3 font-medium">
            Discovering Layer-2 Topology Interconnects...
          </span>
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center p-12 bg-sidebar-bg border border-rose-500/20 rounded-xl text-center">
          <AlertCircle className="w-10 h-10 text-rose-500 mb-2" />
          <h3 className="font-semibold text-text-primary text-base">Topology Service Unavailable</h3>
          <p className="text-xs text-text-muted max-w-md mt-1 mb-4">{error}</p>
          <button
            type="button"
            onClick={() => loadTopologyData()}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-accent-primary hover:bg-accent-primary-hover text-white transition-colors"
          >
            <RotateCw className="w-3.5 h-3.5" /> Retry Connection
          </button>
        </div>
      ) : devices.length === 0 ? (
        /* Empty State 1: No devices in inventory */
        <div className="flex flex-col items-center justify-center p-16 bg-sidebar-bg border border-border-subtle rounded-xl text-center">
          <Server className="w-12 h-12 text-text-muted mb-3" />
          <h3 className="font-semibold text-text-primary text-base">No Monitored Devices Registered</h3>
          <p className="text-xs text-text-muted max-w-md mt-1 mb-5 leading-relaxed">
            NetworkAI requires registered routers and switches before running Layer-2 topology discovery. Add campus devices in the Device Inventory to begin.
          </p>
          {onNavigateToDevices && (
            <button
              type="button"
              onClick={onNavigateToDevices}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-accent-primary hover:bg-accent-primary-hover text-white transition-colors"
            >
              Go to Device Inventory
            </button>
          )}
        </div>
      ) : links.length === 0 ? (
        /* Empty State 2: Devices registered, but no topology links discovered yet */
        <div className="flex flex-col items-center justify-center p-16 bg-sidebar-bg border border-border-subtle rounded-xl text-center">
          <GitFork className="w-12 h-12 text-accent-primary mb-3" />
          <h3 className="font-semibold text-text-primary text-base">No Topology Links Discovered Yet</h3>
          <p className="text-xs text-text-muted max-w-md mt-1 mb-5 leading-relaxed">
            You have {devices.length} registered campus devices, but no neighbor discovery queries have been executed. Run read-only LLDP/CDP discovery on a registered core device to map physical links.
          </p>
          <button
            type="button"
            onClick={handleTriggerInitialDiscovery}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-accent-primary hover:bg-accent-primary-hover text-white transition-colors disabled:opacity-50"
          >
            {isRefreshing ? (
              <>
                <Spinner size="sm" /> Initiating Discovery...
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" /> Run Initial Topology Discovery
              </>
            )}
          </button>
        </div>
      ) : filteredLinks.length === 0 ? (
        /* Empty State 3: Filter matches 0 links */
        <div className="flex flex-col items-center justify-center p-16 bg-sidebar-bg border border-border-subtle rounded-xl text-center">
          <FilterX className="w-10 h-10 text-text-muted mb-2" />
          <h3 className="font-semibold text-text-primary text-base">No Interconnects Match Current Filters</h3>
          <p className="text-xs text-text-muted max-w-md mt-1 mb-4">
            Try adjusting building, protocol, status, or search terms to display discovered links.
          </p>
          <button
            type="button"
            onClick={handleResetFilters}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-card-surface border border-border-subtle hover:bg-surface-hover text-text-primary transition-colors"
          >
            Reset Filters
          </button>
        </div>
      ) : (
        /* Interactive Graph & Details Layout */
        <div className="flex flex-col lg:flex-row gap-5 items-start">
          {/* Main Visualizer SVG Canvas */}
          <div className="flex-1 w-full min-w-0">
            <TopologyGraphCanvas
              nodes={graphNodes}
              edges={graphEdges}
              selectedNodeId={selectedNode ? selectedNode.id : null}
              selectedEdgeId={selectedEdge ? selectedEdge.id : selectedLink ? `edge_single_${selectedLink.id}` : null}
              onSelectNode={(node) => {
                setSelectedNode(node);
                setSelectedLink(null);
                setSelectedEdge(null);
              }}
              onSelectEdge={(link, edge) => {
                setSelectedLink(link);
                setSelectedEdge(edge || null);
                setSelectedNode(null);
              }}
            />
          </div>

          {/* Interactive Inspection Drawer */}
          {(selectedNode || selectedLink) && (
            <TopologyDetailsPanel
              selectedNode={selectedNode}
              selectedLink={selectedLink}
              selectedEdge={selectedEdge}
              onClose={() => {
                setSelectedNode(null);
                setSelectedLink(null);
                setSelectedEdge(null);
              }}
              onOpenDeviceModal={(device) => {
                setModalDevice(device);
                setIsModalOpen(true);
              }}
              onDiscoveryTriggered={() => loadTopologyData(true)}
              onNotify={onNotify}
            />
          )}
        </div>
      )}

      {/* Device Detail History Modal */}
      {modalDevice && (
        <DeviceDetailModal
          device={modalDevice}
          isOpen={isModalOpen}
          onClose={() => {
            setIsModalOpen(false);
            setModalDevice(null);
          }}
          onDeviceUpdated={() => loadTopologyData(true)}
          onNotify={onNotify}
        />
      )}
    </div>
  );
};
