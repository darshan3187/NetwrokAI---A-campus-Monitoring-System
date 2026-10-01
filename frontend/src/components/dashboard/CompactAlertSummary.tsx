import React, { useEffect, useState } from 'react';
import { Bell, AlertTriangle, CheckCircle, ArrowRight, FlaskConical } from 'lucide-react';
import { fetchAlertSummary, fetchAlerts } from '../../services/alertApi';
import type { TopologyAlert, TopologyAlertSummaryResponse } from '../../types/alert';

interface CompactAlertSummaryProps {
  onNavigateToAlerts: () => void;
}

export const CompactAlertSummary: React.FC<CompactAlertSummaryProps> = ({ onNavigateToAlerts }) => {
  const [summary, setSummary] = useState<TopologyAlertSummaryResponse | null>(null);
  const [recentAlert, setRecentAlert] = useState<TopologyAlert | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;

    async function loadAlertSummary() {
      try {
        const [sum, alertsRes] = await Promise.all([
          fetchAlertSummary(),
          fetchAlerts({ status: 'open', limit: 1 }),
        ]);
        if (isMounted) {
          setSummary(sum);
          if (alertsRes.alerts && alertsRes.alerts.length > 0) {
            setRecentAlert(alertsRes.alerts[0]);
          } else {
            setRecentAlert(null);
          }
        }
      } catch {
        // Silently tolerate if alert service is idle
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    loadAlertSummary();
    const interval = setInterval(loadAlertSummary, 30000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  if (isLoading && !summary) {
    return null;
  }

  const openCount = summary?.open_alerts ?? 0;
  const criticalCount = summary?.by_severity?.['critical'] ?? 0;
  const isSimulated = (summary?.mock_alerts_count ?? 0) > 0;

  return (
    <div className="p-4 rounded-[12px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
      <div className="flex items-start sm:items-center gap-3">
        <div
          className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
            openCount > 0
              ? 'bg-red-500/15 text-red-600 dark:text-red-400'
              : 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
          }`}
        >
          {openCount > 0 ? <AlertTriangle className="w-5 h-5" /> : <CheckCircle className="w-5 h-5" />}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h4 className="text-xs font-semibold text-text-primary">
              Topology Change Alerting
            </h4>
            {isSimulated && (
              <span className="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded text-[10px] font-semibold bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                <FlaskConical className="w-2.5 h-2.5" />
                SIMULATED
              </span>
            )}
          </div>
          <p className="text-[11px] text-text-muted mt-0.5">
            {openCount > 0
              ? `${openCount} active condition${openCount > 1 ? 's' : ''} detected (${criticalCount} critical). ${
                  recentAlert ? recentAlert.message : ''
                }`
              : 'All LLDP/CDP neighbor advertisements stable. No unresolved topology changes.'}
          </p>
        </div>
      </div>

      <button
        type="button"
        onClick={onNavigateToAlerts}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-hover hover:bg-surface-hover/80 text-text-primary border border-border-subtle transition-colors shrink-0 cursor-pointer self-start sm:self-auto"
      >
        <Bell className="w-3.5 h-3.5 text-accent-primary" />
        <span>View Alert Center</span>
        <ArrowRight className="w-3.5 h-3.5" />
      </button>
    </div>
  );
};
