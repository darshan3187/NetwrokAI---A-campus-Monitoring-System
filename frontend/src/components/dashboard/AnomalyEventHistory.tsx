import React, { useState, useMemo } from 'react';
import {
  RotateCw,
  Search,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { Badge } from '../common/Badge';
import type { AnomalyEvent } from '../../types/metrics';

interface AnomalyEventHistoryProps {
  events: AnomalyEvent[];
  isLoading: boolean;
  error: string | null;
  onRefresh: () => Promise<void>;
}

export const AnomalyEventHistory: React.FC<AnomalyEventHistoryProps> = ({
  events,
  isLoading,
  error,
  onRefresh,
}) => {
  const [selectedSeverity, setSelectedSeverity] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [expandedEventId, setExpandedEventId] = useState<number | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const handleRefreshClick = async () => {
    setIsRefreshing(true);
    await onRefresh();
    setTimeout(() => setIsRefreshing(false), 400);
  };

  const filteredEvents = useMemo(() => {
    return events.filter((ev) => {
      if (selectedSeverity !== 'all' && ev.severity.toLowerCase() !== selectedSeverity.toLowerCase()) {
        return false;
      }
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchesIface = ev.interface.toLowerCase().includes(query);
        const matchesExpl = ev.explanation.toLowerCase().includes(query);
        const matchesMethod = ev.detection_method.toLowerCase().includes(query);
        return matchesIface || matchesExpl || matchesMethod;
      }
      return true;
    });
  }, [events, selectedSeverity, searchQuery]);

  const severityBadge = (sev: string) => {
    if (sev.toLowerCase().includes('high')) {
      return <Badge variant="error" size="sm">{sev}</Badge>;
    }
    if (sev.toLowerCase().includes('unusual')) {
      return <Badge variant="warning" size="sm">{sev}</Badge>;
    }
    return <Badge variant="success" size="sm">{sev}</Badge>;
  };

  const toggleExpand = (id: number) => {
    setExpandedEventId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="bg-card-surface border border-border-subtle rounded-[12px] p-5 flex flex-col space-y-4 shadow-[var(--shadow-whisper)]">
      {/* Header and Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border-subtle">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-text-primary tracking-[-0.28px]">
              Persisted Anomaly Event Log
            </h2>
            <span className="text-[11px] font-mono text-text-muted">
              [SQLite: {events.length} records]
            </span>
          </div>
          <p className="text-xs text-text-secondary mt-0.5">
            Confirmed outlier events persisted according to the 10-second cooldown policy
          </p>
        </div>

        {/* Action Buttons & Refresh */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleRefreshClick}
            disabled={isRefreshing || isLoading}
            className="flex items-center gap-1.5 px-3 py-1 rounded-[6px] bg-card-surface border border-border-subtle hover:border-border-hover text-xs text-text-primary transition-colors cursor-pointer disabled:opacity-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-text-primary"
            title="Refresh Persisted Anomalies"
            aria-label="Refresh Persisted Anomalies"
          >
            <RotateCw className={`w-3.5 h-3.5 text-[#0070f3] ${isRefreshing ? 'animate-spin' : ''}`} aria-hidden="true" />
            <span className="hidden sm:inline font-mono">Refresh</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
        {/* Severity Filter Tabs */}
        <div className="flex items-center gap-1 bg-elevated-surface p-1 rounded-[6px] border border-border-subtle w-fit font-mono">
          <button
            onClick={() => setSelectedSeverity('all')}
            className={`px-2.5 py-1 rounded-[4px] text-xs transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-text-primary ${
              selectedSeverity === 'all'
                ? 'bg-card-surface text-text-primary font-semibold shadow-xs'
                : 'text-text-muted hover:text-text-primary'
            }`}
            aria-pressed={selectedSeverity === 'all'}
          >
            All ({events.length})
          </button>
          <button
            onClick={() => setSelectedSeverity('high anomaly')}
            className={`px-2.5 py-1 rounded-[4px] text-xs transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#ee0000] ${
              selectedSeverity === 'high anomaly'
                ? 'bg-[#ee0000]/10 text-[#ee0000] dark:text-[#f87171] font-semibold'
                : 'text-text-muted hover:text-[#ee0000]'
            }`}
            aria-pressed={selectedSeverity === 'high anomaly'}
          >
            High Anomaly ({events.filter((e) => e.severity.toLowerCase().includes('high')).length})
          </button>
          <button
            onClick={() => setSelectedSeverity('unusual traffic')}
            className={`px-2.5 py-1 rounded-[4px] text-xs transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#f5a623] ${
              selectedSeverity === 'unusual traffic'
                ? 'bg-[#f5a623]/10 text-[#f5a623] font-semibold'
                : 'text-text-muted hover:text-[#f5a623]'
            }`}
            aria-pressed={selectedSeverity === 'unusual traffic'}
          >
            Unusual ({events.filter((e) => e.severity.toLowerCase().includes('unusual')).length})
          </button>
        </div>

        {/* Search Input */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-text-muted absolute left-2.5 top-1/2 -translate-y-1/2" aria-hidden="true" />
          <input
            type="text"
            name="anomaly_search"
            autoComplete="off"
            spellCheck={false}
            placeholder="Search interface or explanation…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8 pr-3 py-1.5 rounded-[6px] bg-card-surface border border-border-subtle text-xs text-text-primary placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-text-primary w-full sm:w-64 font-mono"
            aria-label="Search anomaly events"
          />
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-3 rounded-[6px] bg-[#ee0000]/10 border border-[#ee0000]/25 text-[#ee0000] dark:text-[#f87171] text-xs flex items-center justify-between">
          <span>Failed to load anomaly events: {error}</span>
          <button
            onClick={() => onRefresh()}
            className="underline hover:opacity-80 cursor-pointer font-mono"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && events.length === 0 && (
        <div className="space-y-2 py-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-14 rounded-[8px] bg-elevated-surface/60 animate-pulse border border-border-subtle" />
          ))}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && filteredEvents.length === 0 && (
        <div className="py-12 flex flex-col items-center justify-center text-center p-6 bg-elevated-surface/30 rounded-[8px] border border-dashed border-border-subtle">
          <div className="w-10 h-10 rounded-full bg-[#0070f3]/10 border border-[#0070f3]/25 flex items-center justify-center mb-3">
            <CheckCircle2 className="w-5 h-5 text-[#0070f3]" aria-hidden="true" />
          </div>
          <h3 className="text-sm font-semibold text-text-primary tracking-[-0.28px]">
            No Anomaly Events Recorded
          </h3>
          <p className="text-xs text-text-secondary max-w-sm mt-1 leading-relaxed">
            {events.length === 0
              ? 'All streaming network telemetry has remained within normal baseline parameters. Confirmed outliers will be automatically logged here.'
              : 'No anomaly events match the current filter criteria.'}
          </p>
        </div>
      )}

      {/* Events Table / Card List */}
      {!isLoading && filteredEvents.length > 0 && (
        <div className="overflow-x-auto">
          {/* Desktop Table View */}
          <table className="w-full text-left text-xs hidden md:table font-mono">
            <thead>
              <tr className="border-b border-border-subtle text-text-muted uppercase text-[10px] font-semibold tracking-[0.05em]">
                <th className="pb-2.5">Timestamp (UTC)</th>
                <th className="pb-2.5">Interface</th>
                <th className="pb-2.5">Severity</th>
                <th className="pb-2.5 text-right">Score</th>
                <th className="pb-2.5">Detection Method</th>
                <th className="pb-2.5">Explanation</th>
                <th className="pb-2.5 text-center">Inspect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {filteredEvents.map((ev) => {
                const isExpanded = expandedEventId === ev.id;
                const formattedTime = new Date(ev.timestamp).toLocaleString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                  hour12: false,
                });

                return (
                  <React.Fragment key={ev.id}>
                    <tr
                      onClick={() => toggleExpand(ev.id)}
                      className="hover:bg-elevated-surface/60 transition-colors cursor-pointer group"
                    >
                      <td className="py-2.5 text-text-muted text-[11px] whitespace-nowrap">
                        {formattedTime}
                      </td>
                      <td className="py-2.5 text-text-primary font-medium whitespace-nowrap">
                        {ev.interface}
                      </td>
                      <td className="py-2.5 whitespace-nowrap">
                        {severityBadge(ev.severity)}
                      </td>
                      <td className="py-2.5 font-bold text-right tabular-nums whitespace-nowrap text-[#ee0000] dark:text-[#f87171]">
                        {ev.anomaly_score.toFixed(2)}
                      </td>
                      <td className="py-2.5 text-text-muted text-[11px] whitespace-nowrap">
                        {ev.detection_method}
                      </td>
                      <td className="py-2.5 text-text-secondary max-w-xs truncate font-sans text-xs" title={ev.explanation}>
                        {ev.explanation}
                      </td>
                      <td className="py-2.5 text-center text-text-muted group-hover:text-text-primary">
                        {isExpanded ? <ChevronUp className="w-3.5 h-3.5 mx-auto" aria-hidden="true" /> : <ChevronDown className="w-3.5 h-3.5 mx-auto" aria-hidden="true" />}
                      </td>
                    </tr>

                    {/* Expanded Snapshot Drawer */}
                    {isExpanded && (
                      <tr className="bg-elevated-surface/50">
                        <td colSpan={7} className="p-3 text-xs">
                          <div className="space-y-2">
                            <div className="text-xs text-text-secondary flex items-center gap-2 font-mono">
                              <span className="text-[#0070f3] font-semibold uppercase tracking-[0.05em]">SNAPSHOT TELEMETRY:</span>
                              <span className="font-sans">{ev.explanation}</span>
                            </div>

                            {/* Render metric key-values if present */}
                            {ev.metrics_snapshot && Object.keys(ev.metrics_snapshot).length > 0 ? (
                              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-2 pt-1 text-xs font-mono">
                                {Object.entries(ev.metrics_snapshot).map(([k, v]) => (
                                  <div key={k} className="p-2 rounded-[6px] bg-card-surface border border-border-subtle">
                                    <div className="text-text-muted text-[10px] uppercase truncate" title={k}>{k.replace(/_/g, ' ')}</div>
                                    <div className="text-text-primary font-semibold mt-0.5 tabular-nums">
                                      {typeof v === 'number' ? v.toFixed(3) : String(v)}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <div className="text-text-muted italic text-xs font-mono">
                                No metric snapshot dictionary recorded for this event.
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>

          {/* Mobile Card View */}
          <div className="space-y-2.5 md:hidden">
            {filteredEvents.map((ev) => {
              const isExpanded = expandedEventId === ev.id;
              const formattedTime = new Date(ev.timestamp).toLocaleTimeString();

              return (
                <div
                  key={ev.id}
                  onClick={() => toggleExpand(ev.id)}
                  className="p-3.5 rounded-[8px] bg-elevated-surface/50 border border-border-subtle space-y-2 cursor-pointer"
                >
                  <div className="flex items-center justify-between font-mono">
                    <span className="text-xs text-[#0070f3] font-medium">{ev.interface}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold tabular-nums text-[#ee0000] dark:text-[#f87171]">
                        {ev.anomaly_score.toFixed(2)}
                      </span>
                      {severityBadge(ev.severity)}
                    </div>
                  </div>

                  <p className="text-xs text-text-primary leading-relaxed">
                    {ev.explanation}
                  </p>

                  <div className="flex items-center justify-between text-[11px] text-text-muted pt-1 border-t border-border-subtle font-mono">
                    <span>{formattedTime}</span>
                    <span>{ev.detection_method}</span>
                  </div>

                  {isExpanded && ev.metrics_snapshot && Object.keys(ev.metrics_snapshot).length > 0 && (
                    <div className="pt-2 border-t border-border-subtle grid grid-cols-2 gap-1.5 text-xs font-mono">
                      {Object.entries(ev.metrics_snapshot).slice(0, 6).map(([k, v]) => (
                        <div key={k} className="p-1.5 rounded-[4px] bg-card-surface border border-border-subtle">
                          <span className="text-text-muted text-[10px] block truncate">{k}</span>
                          <span className="text-text-primary font-medium tabular-nums">{typeof v === 'number' ? v.toFixed(2) : String(v)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
