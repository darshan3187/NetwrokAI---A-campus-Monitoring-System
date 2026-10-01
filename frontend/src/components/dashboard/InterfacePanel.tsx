import React from 'react';
import {
  HardDrive,
  Play,
  Square,
  Check,
} from 'lucide-react';
import type { InterfaceDetail } from '../../types/metrics';
import { Spinner } from '../common/Spinner';

interface InterfacePanelProps {
  interfaces: InterfaceDetail[];
  activeInterface: string | null;
  isMonitoring: boolean;
  isSwitching: boolean;
  onSelectInterface: (name: string) => void;
  onToggleMonitoring: (start: boolean) => void;
}

export const InterfacePanel: React.FC<InterfacePanelProps> = ({
  interfaces,
  activeInterface,
  isMonitoring,
  isSwitching,
  onSelectInterface,
  onToggleMonitoring,
}) => {
  const formatBytes = (bytes: number): string => {
    if (bytes >= 1024 * 1024 * 1024) {
      return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
    }
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="bg-card-surface border border-border-subtle rounded-[12px] p-5 relative flex flex-col shadow-[var(--shadow-whisper)]">
      {/* Switching overlay */}
      {isSwitching && (
        <div className="absolute inset-0 bg-card-surface/85 backdrop-blur-xs z-20 rounded-[12px] flex items-center justify-center gap-2">
          <Spinner size="sm" />
          <span className="text-xs font-mono text-text-primary">
            Calibrating adapter counters…
          </span>
        </div>
      )}

      {/* Top Bar with Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 mb-3 border-b border-border-subtle">
        <div>
          <h2 className="text-sm font-semibold text-text-primary tracking-[-0.28px]">
            Network Adapters
          </h2>
          <p className="text-xs text-text-secondary mt-0.5">
            Hardware and virtual network interfaces detected via kernel socket counters
          </p>
        </div>

        {/* Start / Stop Monitoring Buttons */}
        <div className="flex items-center gap-2">
          {isMonitoring ? (
            <button
              onClick={() => onToggleMonitoring(false)}
              className="flex items-center gap-1.5 px-3 py-1 rounded-[6px] bg-[#ee0000]/10 hover:bg-[#ee0000]/15 text-[#ee0000] dark:text-[#f87171] border border-[#ee0000]/25 text-xs font-medium active:scale-95 transition-transform cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#ee0000]"
              title="Pause packet collector"
              aria-label="Pause telemetry collection"
            >
              <Square className="w-3 h-3 fill-current" aria-hidden="true" />
              <span>Pause Collection</span>
            </button>
          ) : (
            <button
              onClick={() => onToggleMonitoring(true)}
              className="flex items-center gap-1.5 px-3 py-1 rounded-[6px] bg-[#0070f3]/10 hover:bg-[#0070f3]/15 text-[#0070f3] dark:text-[#3291ff] border border-[#0070f3]/25 text-xs font-medium active:scale-95 transition-transform cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#0070f3]"
              title="Start packet collector"
              aria-label="Resume telemetry collection"
            >
              <Play className="w-3 h-3 fill-current" aria-hidden="true" />
              <span>Resume Collection</span>
            </button>
          )}
        </div>
      </div>

      {/* Adapter Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
        {interfaces.map((iface) => {
          const isActive = iface.name === activeInterface;
          const totalBytes = iface.bytes_sent + iface.bytes_recv;

          return (
            <button
              key={iface.name}
              type="button"
              onClick={() => !isActive && onSelectInterface(iface.name)}
              className={`p-3.5 rounded-[8px] border transition-colors text-left flex flex-col justify-between cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-text-primary ${
                isActive
                  ? 'bg-elevated-surface border-text-primary/70 shadow-xs'
                  : 'bg-card-surface border-border-subtle hover:border-border-hover hover:bg-elevated-surface/50'
              }`}
              aria-pressed={isActive}
            >
              <div className="flex items-center justify-between gap-2 w-full">
                <div className="flex items-center gap-2 min-w-0">
                  <HardDrive
                    className={`w-3.5 h-3.5 shrink-0 ${
                      isActive ? 'text-text-primary' : 'text-text-muted'
                    }`}
                    aria-hidden="true"
                  />
                  <span
                    className={`text-xs font-mono truncate ${
                      isActive ? 'text-text-primary font-semibold' : 'text-text-secondary'
                    }`}
                  >
                    {iface.name}
                  </span>
                </div>
                {isActive && (
                  <span className="flex items-center gap-1 text-[11px] font-mono text-[#0070f3] shrink-0 font-medium">
                    <Check className="w-3 h-3" aria-hidden="true" /> Active
                  </span>
                )}
              </div>

              {/* Data numbers */}
              <div className="mt-3 pt-2 border-t border-border-subtle flex items-center justify-between text-[11px] font-mono text-text-muted w-full">
                <span>Total: <strong className="text-text-primary font-medium tabular-nums">{formatBytes(totalBytes)}</strong></span>
                <span className="tabular-nums">{(iface.packets_sent + iface.packets_recv).toLocaleString()} pkts</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
