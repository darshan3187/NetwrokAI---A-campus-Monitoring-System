import React from 'react';
import {
  RotateCw,
  GitFork,
  Radio,
  Clock,
  HelpCircle,
  Server,
  ShieldCheck,
  FlaskConical,
} from 'lucide-react';

interface TopologySummaryBarProps {
  totalDevices: number;
  totalLinks: number;
  activeLinks: number;
  staleLinks: number;
  unresolvedCount: number;
  hasMockLinks: boolean;
  hasActualLinks: boolean;
  isRefreshing: boolean;
  onRefresh: () => void;
  lastUpdated: Date | null;
}

export const TopologySummaryBar: React.FC<TopologySummaryBarProps> = ({
  totalDevices,
  totalLinks,
  activeLinks,
  staleLinks,
  unresolvedCount,
  hasMockLinks,
  hasActualLinks,
  isRefreshing,
  onRefresh,
  lastUpdated,
}) => {
  return (
    <div className="flex flex-col gap-4">
      {/* Top Header Row with Refresh and Data Origin */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-text-primary flex items-center gap-2">
            <GitFork className="w-5 h-5 text-accent-primary" />
            Campus Network Topology
          </h1>
          <p className="text-xs text-text-muted mt-0.5">
            Authorized Layer-2 physical & logical interconnects discovered via read-only LLDP (IEEE 802.1AB) and Cisco CDP.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {/* Data Origin Badges */}
          {hasMockLinks && (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/25">
              <FlaskConical className="w-3.5 h-3.5" />
              MOCK FIXTURES ACTIVE
            </span>
          )}
          {hasActualLinks && (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25">
              <ShieldCheck className="w-3.5 h-3.5" />
              AUTHENTICATED SNMP
            </span>
          )}

          {lastUpdated && (
            <span className="text-[11px] text-text-muted hidden sm:inline-block font-mono">
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}

          {/* Refresh Button */}
          <button
            type="button"
            onClick={onRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-card-surface border border-border-subtle hover:bg-surface-hover text-text-primary transition-colors disabled:opacity-50 shadow-xs"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* KPI Stats Cards Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {/* Total Registered Devices */}
        <div className="p-3.5 bg-sidebar-bg border border-border-subtle rounded-xl shadow-xs">
          <div className="flex items-center justify-between text-text-muted text-xs">
            <span>Monitored Nodes</span>
            <Server className="w-4 h-4" />
          </div>
          <div className="text-xl font-bold text-text-primary mt-1">{totalDevices}</div>
          <span className="text-[10px] text-text-muted">Registered campus fleet</span>
        </div>

        {/* Discovered Links */}
        <div className="p-3.5 bg-sidebar-bg border border-border-subtle rounded-xl shadow-xs">
          <div className="flex items-center justify-between text-text-muted text-xs">
            <span>Discovered Links</span>
            <GitFork className="w-4 h-4 text-sky-400" />
          </div>
          <div className="text-xl font-bold text-text-primary mt-1">{totalLinks}</div>
          <span className="text-[10px] text-text-muted">Total interconnects</span>
        </div>

        {/* Active Links */}
        <div className="p-3.5 bg-sidebar-bg border border-border-subtle rounded-xl shadow-xs">
          <div className="flex items-center justify-between text-text-muted text-xs">
            <span>Active Links</span>
            <Radio className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
            {activeLinks}
          </div>
          <span className="text-[10px] text-text-muted">Observed in recent cycle</span>
        </div>

        {/* Stale Links */}
        <div
          className="p-3.5 bg-sidebar-bg border border-border-subtle rounded-xl shadow-xs cursor-help"
          title="Neighbor observation exceeded freshness threshold without a renewal advertisement packet. Indicates lack of recent discovery packets, NOT a confirmed physical disconnection or interface down state."
        >
          <div className="flex items-center justify-between text-text-muted text-xs">
            <span>Stale Observations</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-xl font-bold text-amber-600 dark:text-amber-400 mt-1">
            {staleLinks}
          </div>
          <span className="text-[10px] text-text-muted">Unrefreshed packet window</span>
        </div>

        {/* Unresolved Neighbors */}
        <div
          className="p-3.5 bg-sidebar-bg border border-border-subtle rounded-xl shadow-xs col-span-2 sm:col-span-1 cursor-help"
          title="Remote neighbor discovered via LLDP/CDP whose chassis MAC does not map to any registered device in the campus database."
        >
          <div className="flex items-center justify-between text-text-muted text-xs">
            <span>Unresolved Neighbors</span>
            <HelpCircle className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-xl font-bold text-purple-600 dark:text-purple-400 mt-1">
            {unresolvedCount}
          </div>
          <span className="text-[10px] text-text-muted">External unmanaged devices</span>
        </div>
      </div>
    </div>
  );
};
