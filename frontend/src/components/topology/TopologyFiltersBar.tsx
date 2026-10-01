import React from 'react';
import { Search, X, Filter } from 'lucide-react';
import type { TopologyFilterOptions } from '../../types/topology';

interface TopologyFiltersBarProps {
  filters: TopologyFilterOptions;
  availableBuildings: string[];
  onFilterChange: (key: keyof TopologyFilterOptions, value: string) => void;
  onResetFilters: () => void;
  hasActiveFilters: boolean;
  totalFilteredCount: number;
  totalUnfilteredCount: number;
}

export const TopologyFiltersBar: React.FC<TopologyFiltersBarProps> = ({
  filters,
  availableBuildings,
  onFilterChange,
  onResetFilters,
  hasActiveFilters,
  totalFilteredCount,
  totalUnfilteredCount,
}) => {
  return (
    <div className="flex flex-col gap-3 p-4 bg-sidebar-bg border border-border-subtle rounded-xl shadow-xs">
      <div className="flex flex-wrap items-center gap-3">
        {/* Search Input */}
        <div className="relative min-w-[200px] flex-1 max-w-sm">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
          <input
            type="text"
            placeholder="Search device name, IP, interface..."
            value={filters.searchQuery}
            onChange={(e) => onFilterChange('searchQuery', e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-card-surface border border-border-subtle rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary"
          />
          {filters.searchQuery && (
            <button
              type="button"
              onClick={() => onFilterChange('searchQuery', '')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
              aria-label="Clear search"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Building Filter */}
        <select
          value={filters.building}
          onChange={(e) => onFilterChange('building', e.target.value)}
          className="text-xs py-1.5 px-2.5 bg-card-surface border border-border-subtle rounded-lg text-text-primary focus:outline-none focus:border-accent-primary cursor-pointer"
        >
          <option value="all">All Buildings</option>
          {availableBuildings.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>

        {/* Device Type Filter */}
        <select
          value={filters.deviceType}
          onChange={(e) => onFilterChange('deviceType', e.target.value)}
          className="text-xs py-1.5 px-2.5 bg-card-surface border border-border-subtle rounded-lg text-text-primary focus:outline-none focus:border-accent-primary cursor-pointer"
        >
          <option value="all">All Device Types</option>
          <option value="router">Routers</option>
          <option value="switch">Switches</option>
          <option value="access_point">Access Points</option>
          <option value="server">Servers</option>
        </select>

        {/* Protocol Filter */}
        <select
          value={filters.protocol}
          onChange={(e) => onFilterChange('protocol', e.target.value)}
          className="text-xs py-1.5 px-2.5 bg-card-surface border border-border-subtle rounded-lg text-text-primary focus:outline-none focus:border-accent-primary cursor-pointer"
        >
          <option value="all">All Protocols</option>
          <option value="lldp">LLDP Only</option>
          <option value="cdp">CDP Only</option>
        </select>

        {/* Link Status Filter */}
        <select
          value={filters.linkStatus}
          onChange={(e) => onFilterChange('linkStatus', e.target.value)}
          className="text-xs py-1.5 px-2.5 bg-card-surface border border-border-subtle rounded-lg text-text-primary focus:outline-none focus:border-accent-primary cursor-pointer"
        >
          <option value="all">All Statuses</option>
          <option value="active">Active Only</option>
          <option value="stale">Stale Only</option>
        </select>

        {/* Resolution State Filter */}
        <select
          value={filters.resolutionState}
          onChange={(e) => onFilterChange('resolutionState', e.target.value)}
          className="text-xs py-1.5 px-2.5 bg-card-surface border border-border-subtle rounded-lg text-text-primary focus:outline-none focus:border-accent-primary cursor-pointer"
        >
          <option value="all">All Nodes</option>
          <option value="resolved">Resolved Campus Devices</option>
          <option value="unresolved">Unresolved Neighbors</option>
        </select>

        {/* Data Source Filter (Actual SNMP vs Mock) */}
        <select
          value={filters.dataSource}
          onChange={(e) => onFilterChange('dataSource', e.target.value)}
          className="text-xs py-1.5 px-2.5 bg-card-surface border border-border-subtle rounded-lg text-text-primary focus:outline-none focus:border-accent-primary cursor-pointer"
        >
          <option value="all">All Origins (SNMP + Mock)</option>
          <option value="actual">Actual SNMP Only</option>
          <option value="mock">Mock Topology Only</option>
        </select>

        {/* Reset Filters Button */}
        {hasActiveFilters && (
          <button
            type="button"
            onClick={onResetFilters}
            className="flex items-center gap-1 text-xs text-accent-primary hover:text-accent-primary-hover font-medium px-2 py-1 rounded-md hover:bg-accent-primary-soft transition-colors ml-auto"
          >
            <Filter className="w-3.5 h-3.5" />
            Reset ({totalFilteredCount} of {totalUnfilteredCount} links)
          </button>
        )}
      </div>
    </div>
  );
};
