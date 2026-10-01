import React from 'react';
import type { ActivityEvent } from '../../types/metrics';

interface ActivityFeedProps {
  events: ActivityEvent[];
}

export const ActivityFeed: React.FC<ActivityFeedProps> = ({ events }) => {
  const getDot = (type: ActivityEvent['type']) => {
    switch (type) {
      case 'success':
        return <span className="w-1.5 h-1.5 rounded-full bg-[#0070f3] shrink-0" aria-hidden="true" />;
      case 'warning':
        return <span className="w-1.5 h-1.5 rounded-full bg-[#f5a623] shrink-0" aria-hidden="true" />;
      case 'alert':
        return <span className="w-1.5 h-1.5 rounded-full bg-[#ee0000] shrink-0" aria-hidden="true" />;
      default:
        return <span className="w-1.5 h-1.5 rounded-full bg-[#50e3c2] shrink-0" aria-hidden="true" />;
    }
  };

  return (
    <div className="bg-card-surface border border-border-subtle rounded-[12px] p-5 flex flex-col justify-between shadow-[var(--shadow-whisper)]">
      <div className="pb-3 border-b border-border-subtle">
        <h2 className="text-sm font-semibold text-text-primary tracking-[-0.28px]">
          Observability Event Log
        </h2>
        <p className="text-xs text-text-secondary mt-0.5">
          Real-time adapter events, stream connections, and operational triggers
        </p>
      </div>

      <div className="my-2.5 space-y-1.5 max-h-56 overflow-y-auto pr-1">
        {events.length === 0 ? (
          <div className="text-center py-8 text-xs font-mono text-text-muted">
            Awaiting telemetry state transitions…
          </div>
        ) : (
          events.map((event) => (
            <div
              key={event.id}
              className="p-2.5 rounded-[8px] bg-elevated-surface border border-border-subtle flex items-start gap-2.5 text-xs transition-colors hover:border-border-hover"
            >
              <div className="mt-1">{getDot(event.type)}</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-text-primary truncate text-xs">
                    {event.message}
                  </span>
                  <span className="text-[11px] text-text-muted font-mono shrink-0 tabular-nums">
                    {event.timestamp}
                  </span>
                </div>
                {event.details && (
                  <p className="text-xs text-text-secondary mt-0.5 font-mono truncate">
                    {event.details}
                  </p>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      <div className="pt-2 text-xs font-mono text-text-muted flex items-center justify-between border-t border-border-subtle">
        <span>Event Buffer: <span className="tabular-nums font-medium text-text-primary">{events.length}</span></span>
        <span>Auto-logged stream</span>
      </div>
    </div>
  );
};
