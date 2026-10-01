import React from 'react';
import {
  Server,
  Database,
  Radio,
  Wifi,
} from 'lucide-react';
import type { HealthResponse } from '../../types/metrics';
import type { ConnectionStatus } from '../../hooks/useWebSocket';
import { Badge } from '../common/Badge';

interface SystemStatusProps {
  health: HealthResponse | null;
  wsStatus: ConnectionStatus;
  activeInterface: string | null;
  isMonitoring: boolean;
  campusDeviceCount?: number;
}

export const SystemStatus: React.FC<SystemStatusProps> = ({
  health,
  wsStatus,
  activeInterface,
  isMonitoring,
  campusDeviceCount = 0,
}) => {
  return (
    <div className="bg-card-surface border border-border-subtle rounded-[12px] p-5 flex flex-col justify-between shadow-[var(--shadow-whisper)]">
      <div className="pb-3 border-b border-border-subtle">
        <h2 className="text-sm font-semibold text-text-primary tracking-[-0.28px]">
          System & Node Diagnostics
        </h2>
        <p className="text-xs text-text-secondary mt-0.5">
          Operational status of API services, persistence layer, and stream sockets
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 my-3">
        {/* API Backend */}
        <div className="p-3 rounded-[8px] bg-elevated-surface border border-border-subtle flex flex-col justify-between gap-2.5 min-w-0">
          <div className="flex items-center gap-1.5 text-xs text-text-secondary min-w-0">
            <Server className="w-3.5 h-3.5 text-text-muted shrink-0" aria-hidden="true" />
            <span className="font-medium truncate">API Gateway</span>
          </div>
          <div className="flex items-center justify-between gap-2 min-w-0">
            <span className="text-[11px] font-mono text-text-muted truncate">FastAPI</span>
            <Badge variant={health?.status === 'ok' ? 'success' : 'error'} size="sm" className="shrink-0">
              {health?.status === 'ok' ? 'ONLINE' : 'OFFLINE'}
            </Badge>
          </div>
        </div>

        {/* Database */}
        <div className="p-3 rounded-[8px] bg-elevated-surface border border-border-subtle flex flex-col justify-between gap-2.5 min-w-0">
          <div className="flex items-center gap-1.5 text-xs text-text-secondary min-w-0">
            <Database className="w-3.5 h-3.5 text-text-muted shrink-0" aria-hidden="true" />
            <span className="font-medium truncate">Persistence</span>
          </div>
          <div className="flex items-center justify-between gap-2 min-w-0">
            <span className="text-[11px] font-mono text-text-muted truncate">SQLite</span>
            <Badge variant={health?.database === 'connected' ? 'success' : 'error'} size="sm" className="shrink-0">
              {health?.database === 'connected' ? 'CONNECTED' : 'DISCONNECTED'}
            </Badge>
          </div>
        </div>

        {/* WebSocket */}
        <div className="p-3 rounded-[8px] bg-elevated-surface border border-border-subtle flex flex-col justify-between gap-2.5 min-w-0">
          <div className="flex items-center gap-1.5 text-xs text-text-secondary min-w-0">
            <Radio className="w-3.5 h-3.5 text-text-muted shrink-0" aria-hidden="true" />
            <span className="font-medium truncate">Live Stream</span>
          </div>
          <div className="flex items-center justify-between gap-2 min-w-0">
            <span className="text-[11px] font-mono text-text-muted truncate">/ws/metrics</span>
            <Badge
              variant={
                wsStatus === 'connected'
                  ? 'success'
                  : wsStatus === 'connecting'
                  ? 'warning'
                  : 'error'
              }
              size="sm"
              className="shrink-0"
            >
              {wsStatus.toUpperCase()}
            </Badge>
          </div>
        </div>

        {/* Collector */}
        <div className="p-3 rounded-[8px] bg-elevated-surface border border-border-subtle flex flex-col justify-between gap-2.5 min-w-0">
          <div className="flex items-center gap-1.5 text-xs text-text-secondary min-w-0">
            <Wifi className="w-3.5 h-3.5 text-text-muted shrink-0" aria-hidden="true" />
            <span className="font-medium truncate">Collector Loop</span>
          </div>
          <div className="flex items-center justify-between gap-2 min-w-0">
            <span className="text-[11px] font-mono text-text-muted truncate">
              {activeInterface || 'None'}
            </span>
            <Badge variant={isMonitoring ? 'success' : 'warning'} size="sm" className="shrink-0">
              {isMonitoring ? 'ACTIVE' : 'PAUSED'}
            </Badge>
          </div>
        </div>
      </div>

      <div className="pt-2.5 text-xs font-mono text-text-muted flex flex-wrap items-center justify-between gap-2 border-t border-border-subtle">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[11px] text-text-secondary">Source:</span>
          <Badge variant="info" size="sm">Local Host (psutil)</Badge>
          <Badge variant="neutral" size="sm">Campus: {campusDeviceCount} configured</Badge>
        </div>
        <span className="tabular-nums">Telemetry cadence: 1.0s</span>
      </div>
    </div>
  );
};
