import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  RotateCcw,
  Router,
  Network,
  Wifi,
  Server,
  HelpCircle,
  Laptop,
} from 'lucide-react';
import type { TopologyNode, TopologyEdge, TopologyLink } from '../../types/topology';
import { useTheme } from '../../context/ThemeContext';

interface TopologyGraphCanvasProps {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  onSelectNode: (node: TopologyNode | null) => void;
  onSelectEdge: (link: TopologyLink | null, edge?: TopologyEdge | null) => void;
}

const NODE_WIDTH = 150;
const NODE_HEIGHT = 56;

export const TopologyGraphCanvas: React.FC<TopologyGraphCanvasProps> = ({
  nodes,
  edges,
  selectedNodeId,
  selectedEdgeId,
  onSelectNode,
  onSelectEdge,
}) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const containerRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState<boolean>(false);
  const [panStart, setPanStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [draggingNodeId, setDraggingNodeId] = useState<string | null>(null);
  const [nodePositions, setNodePositions] = useState<Record<string, { x: number; y: number }>>({});

  // Node position initialization / layout computation
  useEffect(() => {
    if (nodes.length === 0) {
      setNodePositions({});
      return;
    }

    // Categorize nodes into topological tiers
    const tiers: Record<string, TopologyNode[]> = {
      router: [],
      switch: [],
      endpoint: [], // access_point, server, host, other
      unresolved: [],
    };

    nodes.forEach((node) => {
      if (node.isUnresolved) {
        tiers.unresolved.push(node);
      } else if (node.deviceType === 'router') {
        tiers.router.push(node);
      } else if (node.deviceType === 'switch') {
        tiers.switch.push(node);
      } else {
        tiers.endpoint.push(node);
      }
    });

    const newPos: Record<string, { x: number; y: number }> = {};
    const containerWidth = containerRef.current?.clientWidth || 900;
    const centerX = containerWidth / 2;

    const tierYMap: Record<string, number> = {
      router: 90,
      switch: 260,
      endpoint: 430,
      unresolved: 590,
    };

    const SPACING_X = 220;

    Object.entries(tiers).forEach(([tierName, tierNodes]) => {
      const y = tierYMap[tierName];
      const count = tierNodes.length;
      if (count === 0) return;

      const totalWidth = (count - 1) * SPACING_X;
      const startX = centerX - totalWidth / 2;

      tierNodes.forEach((node, idx) => {
        newPos[node.id] = {
          x: startX + idx * SPACING_X,
          y: y,
        };
      });
    });

    setNodePositions(newPos);
  }, [nodes]);

  // Fit to screen helper
  const handleFitToScreen = useCallback(() => {
    if (nodes.length === 0 || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const positions = Object.values(nodePositions);
    if (positions.length === 0) return;

    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;

    positions.forEach((pos) => {
      minX = Math.min(minX, pos.x - NODE_WIDTH / 2);
      maxX = Math.max(maxX, pos.x + NODE_WIDTH / 2);
      minY = Math.min(minY, pos.y - NODE_HEIGHT / 2);
      maxY = Math.max(maxY, pos.y + NODE_HEIGHT / 2);
    });

    const padding = 100;
    const graphWidth = maxX - minX + padding * 2;
    const graphHeight = maxY - minY + padding * 2;

    const scaleX = rect.width / graphWidth;
    const scaleY = rect.height / graphHeight;
    const newZoom = Math.min(Math.max(Math.min(scaleX, scaleY), 0.4), 1.6);

    const graphCenterX = (minX + maxX) / 2;
    const graphCenterY = (minY + maxY) / 2;

    setZoom(newZoom);
    setPan({
      x: rect.width / 2 - graphCenterX * newZoom,
      y: rect.height / 2 - graphCenterY * newZoom,
    });
  }, [nodes, nodePositions]);

  // Reset zoom & pan
  const handleResetView = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  // Zoom buttons
  const handleZoomIn = () => setZoom((z) => Math.min(z + 0.15, 2.5));
  const handleZoomOut = () => setZoom((z) => Math.max(z - 0.15, 0.35));

  // Wheel zoom
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY * -0.0012;
    setZoom((prevZoom) => {
      const newZoom = Math.min(Math.max(prevZoom + delta, 0.35), 2.5);
      return Number(newZoom.toFixed(2));
    });
  };

  // Pan interaction
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return; // Only left click
    // Check if clicked background canvas
    const target = e.target as HTMLElement;
    if (target.tagName === 'svg' || target.getAttribute('data-canvas-bg') === 'true') {
      setIsPanning(true);
      setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
      onSelectNode(null);
      onSelectEdge(null);
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isPanning) {
      setPan({
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y,
      });
    } else if (draggingNodeId) {
      // Dragging a specific node
      const currentPos = nodePositions[draggingNodeId];
      if (currentPos) {
        setNodePositions((prev) => ({
          ...prev,
          [draggingNodeId]: {
            x: currentPos.x + e.movementX / zoom,
            y: currentPos.y + e.movementY / zoom,
          },
        }));
      }
    }
  };

  const handleMouseUp = () => {
    setIsPanning(false);
    setDraggingNodeId(null);
  };

  // Node Icon Helper
  const renderNodeIcon = (type: string, isUnres: boolean) => {
    if (isUnres) return <HelpCircle className="w-4 h-4 text-purple-400" />;
    switch (type) {
      case 'router':
        return <Router className="w-4 h-4 text-indigo-400" />;
      case 'switch':
        return <Network className="w-4 h-4 text-sky-400" />;
      case 'access_point':
        return <Wifi className="w-4 h-4 text-emerald-400" />;
      case 'server':
        return <Server className="w-4 h-4 text-amber-400" />;
      default:
        return <Laptop className="w-4 h-4 text-slate-400" />;
    }
  };

  // Node Status Indicator Color
  const getStatusColor = (status: string, isUnres: boolean) => {
    if (isUnres) return 'bg-purple-500';
    switch (status) {
      case 'online':
        return 'bg-emerald-500';
      case 'stale':
        return 'bg-amber-500';
      case 'unreachable':
        return 'bg-rose-500';
      default:
        return 'bg-slate-400';
    }
  };

  // Edge lookups with position mapping and multi-link curvature
  const activeEdges = useMemo(() => {
    const positioned = edges
      .map((edge) => {
        const sourcePos = nodePositions[edge.source];
        const targetPos = nodePositions[edge.target];
        if (!sourcePos || !targetPos) return null;
        return {
          ...edge,
          sourcePos,
          targetPos,
        };
      })
      .filter((e): e is NonNullable<typeof e> => e !== null);

    const pairCounts = new Map<string, number>();
    positioned.forEach((edge) => {
      const key = [edge.source, edge.target].sort().join(':::');
      pairCounts.set(key, (pairCounts.get(key) || 0) + 1);
    });

    const pairSeen = new Map<string, number>();
    return positioned.map((edge) => {
      const key = [edge.source, edge.target].sort().join(':::');
      const idx = pairSeen.get(key) || 0;
      pairSeen.set(key, idx + 1);
      return {
        ...edge,
        pairIndex: idx,
        totalInPair: pairCounts.get(key) || 1,
      };
    });
  }, [edges, nodePositions]);

  return (
    <div
      ref={containerRef}
      className="relative w-full h-[600px] lg:h-[680px] bg-sidebar-bg border border-border-subtle rounded-xl overflow-hidden select-none"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onWheel={handleWheel}
      style={{ cursor: isPanning ? 'grabbing' : 'default' }}
    >
      {/* Zoom and Controls Toolbar */}
      <div className="absolute top-4 right-4 z-20 flex items-center gap-1.5 p-1 bg-card-surface/90 backdrop-blur-md border border-border-subtle rounded-lg shadow-sm">
        <button
          type="button"
          onClick={handleZoomIn}
          className="p-1.5 text-text-secondary hover:text-text-primary hover:bg-surface-hover rounded-md transition-colors"
          title="Zoom In"
          aria-label="Zoom In"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={handleZoomOut}
          className="p-1.5 text-text-secondary hover:text-text-primary hover:bg-surface-hover rounded-md transition-colors"
          title="Zoom Out"
          aria-label="Zoom Out"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <div className="w-[1px] h-4 bg-border-subtle" />
        <button
          type="button"
          onClick={handleFitToScreen}
          className="p-1.5 text-text-secondary hover:text-text-primary hover:bg-surface-hover rounded-md transition-colors"
          title="Fit to Screen"
          aria-label="Fit to Screen"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={handleResetView}
          className="p-1.5 text-text-secondary hover:text-text-primary hover:bg-surface-hover rounded-md transition-colors"
          title="Reset View"
          aria-label="Reset View"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
        <span className="text-[11px] font-mono text-text-muted px-1.5 min-w-[40px] text-center">
          {Math.round(zoom * 100)}%
        </span>
      </div>

      {/* Protocol & Status Legend */}
      <div className="absolute bottom-4 left-4 z-20 hidden sm:flex items-center gap-4 px-3 py-2 bg-card-surface/90 backdrop-blur-md border border-border-subtle rounded-lg text-xs shadow-sm">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-0.5 bg-sky-500 rounded-full inline-block" />
          <span className="text-text-secondary font-medium">LLDP Link</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-0.5 bg-emerald-500 rounded-full inline-block" />
          <span className="text-text-secondary font-medium">CDP Link</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-0.5 border-t-2 border-dashed border-amber-500 inline-block" />
          <span className="text-text-secondary font-medium">Stale Link</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm border border-dashed border-purple-400 bg-purple-500/10 inline-block" />
          <span className="text-text-secondary font-medium">Unresolved Node</span>
        </div>
      </div>

      {/* Main SVG Visualization Canvas */}
      <svg
        className="w-full h-full block"
        data-canvas-bg="true"
      >
        <defs>
          {/* Subtle Grid Pattern */}
          <pattern
            id="topo-grid"
            width={32 * zoom}
            height={32 * zoom}
            patternUnits="userSpaceOnUse"
          >
            <circle
              cx="1"
              cy="1"
              r="1"
              fill={isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'}
            />
          </pattern>

          {/* Glow Filters for Selected Elements */}
          <filter id="node-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Background Grid */}
        <rect
          width="100%"
          height="100%"
          fill="url(#topo-grid)"
          data-canvas-bg="true"
        />

        {/* Viewport Transform Group */}
        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          {/* Layer 1: Edges */}
          {activeEdges.map((edge) => {
            const isSelected = selectedEdgeId === edge.id;
            const isLLDP = edge.protocol === 'lldp';
            const isMixed = edge.protocol === 'mixed';
            const strokeColor = isMixed ? '#8b5cf6' : isLLDP ? '#0284c7' : '#059669';
            const darkStrokeColor = isMixed ? '#a78bfa' : isLLDP ? '#38bdf8' : '#34d399';
            const edgeColor = isDark ? darkStrokeColor : strokeColor;

            const x1 = edge.sourcePos.x;
            const y1 = edge.sourcePos.y;
            const x2 = edge.targetPos.x;
            const y2 = edge.targetPos.y;

            const dx = x2 - x1;
            const dy = y2 - y1;
            const len = Math.sqrt(dx * dx + dy * dy) || 1;
            const nx = -dy / len;
            const ny = dx / len;

            // Offset parallel cables between the same pair of nodes
            const offset = edge.totalInPair > 1
              ? (edge.pairIndex - (edge.totalInPair - 1) / 2) * 36
              : 0;

            const midX = (x1 + x2) / 2 + nx * offset;
            const midY = (y1 + y2) / 2 + ny * offset;

            const pathData = offset === 0
              ? `M ${x1} ${y1} L ${x2} ${y2}`
              : `M ${x1} ${y1} Q ${midX} ${midY} ${x2} ${y2}`;

            return (
              <g
                key={`edge-${edge.id}`}
                className="cursor-pointer group"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectEdge(edge.linkRecord, edge);
                  onSelectNode(null);
                }}
              >
                {/* Wide invisible stroke for easy clicking */}
                <path
                  d={pathData}
                  fill="none"
                  stroke="transparent"
                  strokeWidth={20}
                />

                {/* Visible Edge Line */}
                <path
                  d={pathData}
                  fill="none"
                  stroke={isSelected ? '#3b82f6' : edgeColor}
                  strokeWidth={isSelected ? 3.5 : 2}
                  strokeDasharray={edge.isStale ? '6 4' : undefined}
                  className="transition-all duration-150 group-hover:stroke-accent-primary"
                  opacity={edge.isStale ? 0.75 : 0.95}
                />

                {/* Interactive Edge Label Pill */}
                <foreignObject
                  x={midX - 42}
                  y={midY - 10}
                  width={84}
                  height={20}
                  className="pointer-events-none"
                >
                  <div
                    className={`flex items-center justify-center gap-1 h-full px-1.5 rounded-full text-[10px] font-mono border transition-all ${
                      isSelected
                        ? 'bg-blue-600 text-white border-blue-400 font-bold scale-105'
                        : isDark
                        ? 'bg-neutral-900/90 text-neutral-300 border-neutral-700/80'
                        : 'bg-white/95 text-neutral-700 border-neutral-200 shadow-xs'
                    }`}
                  >
                    <span>{edge.protocol.toUpperCase()}</span>
                    <span className="text-[9px] font-sans opacity-70">
                      {edge.isBidirectional ? '↔' : '→'}
                    </span>
                    {edge.isStale && <span className="text-amber-400 font-bold" title="Stale observation">*</span>}
                  </div>
                </foreignObject>
              </g>
            );
          })}

          {/* Layer 2: Nodes */}
          {nodes.map((node) => {
            const pos = nodePositions[node.id];
            if (!pos) return null;

            const isSelected = selectedNodeId === node.id;
            const isUnres = node.isUnresolved;

            const x = pos.x - NODE_WIDTH / 2;
            const y = pos.y - NODE_HEIGHT / 2;

            return (
              <g
                key={`node-${node.id}`}
                transform={`translate(${x}, ${y})`}
                className="cursor-pointer group"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectNode(node);
                  onSelectEdge(null);
                }}
                onMouseDown={(e) => {
                  if (e.button === 0) {
                    e.stopPropagation();
                    setDraggingNodeId(node.id);
                  }
                }}
              >
                {/* Node Box */}
                <rect
                  width={NODE_WIDTH}
                  height={NODE_HEIGHT}
                  rx={8}
                  className={`transition-colors duration-150 ${
                    isSelected
                      ? isDark
                        ? 'fill-neutral-900 stroke-blue-500'
                        : 'fill-white stroke-blue-600'
                      : isUnres
                      ? isDark
                        ? 'fill-purple-950/20 stroke-purple-500/50'
                        : 'fill-purple-50/60 stroke-purple-400/60'
                      : isDark
                      ? 'fill-neutral-900/95 stroke-neutral-800 hover:stroke-neutral-600'
                      : 'fill-white stroke-neutral-200 hover:stroke-neutral-400 shadow-xs'
                  }`}
                  strokeWidth={isSelected ? 2.5 : 1.5}
                  strokeDasharray={isUnres ? '5 3' : undefined}
                  filter={isSelected ? 'url(#node-glow)' : undefined}
                />

                {/* Node Content */}
                <foreignObject width={NODE_WIDTH} height={NODE_HEIGHT} className="pointer-events-none">
                  <div className="flex items-center h-full px-2.5 gap-2.5">
                    {/* Icon container */}
                    <div
                      className={`flex items-center justify-center w-8 h-8 rounded-md shrink-0 ${
                        isUnres
                          ? isDark
                            ? 'bg-purple-900/30'
                            : 'bg-purple-100'
                          : isDark
                          ? 'bg-neutral-800'
                          : 'bg-neutral-100'
                      }`}
                    >
                      {renderNodeIcon(node.deviceType, isUnres)}
                    </div>

                    {/* Label & Details */}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-1">
                        <span className="text-xs font-semibold text-text-primary truncate">
                          {node.label}
                        </span>
                        {/* Status indicator dot */}
                        <span
                          className={`w-1.5 h-1.5 rounded-full shrink-0 ${getStatusColor(
                            node.computedStatus,
                            isUnres
                          )}`}
                          title={`Status: ${node.computedStatus}`}
                        />
                      </div>
                      <div className="text-[10px] text-text-muted truncate font-mono">
                        {isUnres ? 'External / Unmanaged' : node.ipAddress}
                      </div>
                    </div>
                  </div>
                </foreignObject>
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
};
