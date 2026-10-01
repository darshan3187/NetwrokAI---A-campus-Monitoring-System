import { useState, useCallback, useEffect, lazy, Suspense } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowDownCircle,
  ArrowUpCircle,
  HardDrive,
  Activity,
  AlertCircle,
  Sliders,
  Sun,
  Moon,
  Laptop,
  CheckCircle2,
  Server,
  Database,
  Radio,
  Plus,
} from 'lucide-react';
import { useNetworkData } from './hooks/useNetworkData';
import { Sidebar } from './components/layout/Sidebar';
import type { NavTab } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { MetricCard } from './components/dashboard/MetricCard';
import { LiveChart } from './components/dashboard/LiveChart';
import { InterfacePanel } from './components/dashboard/InterfacePanel';
import { SystemStatus } from './components/dashboard/SystemStatus';
import { ActivityFeed } from './components/dashboard/ActivityFeed';
import { AnomalyOverview } from './components/dashboard/AnomalyOverview';
import { AnomalyTimeline } from './components/dashboard/AnomalyTimeline';
import { AnomalyEventHistory } from './components/dashboard/AnomalyEventHistory';
import { DeviceInventory } from './components/devices/DeviceInventory';
import { CampusOverview } from './components/devices/CampusOverview';
import { TopologyView } from './components/topology/TopologyView';
import { AlertCenter } from './components/alerts/AlertCenter';
import { CompactAlertSummary } from './components/dashboard/CompactAlertSummary';
import { deviceApi } from './services/deviceApi';
import type { DeviceSummaryResponse } from './types/device';
import { Badge } from './components/common/Badge';
import { ToastContainer } from './components/common/Toast';
import type { ToastMessage } from './components/common/Toast';
import { Spinner } from './components/common/Spinner';
import { useTheme, type ThemeMode } from './context/ThemeContext';

const HistoricalChart = lazy(() =>
  import('./components/dashboard/HistoricalChart').then((m) => ({ default: m.HistoricalChart }))
);
const SimulationLab = lazy(() =>
  import('./components/simulation/SimulationLab').then((m) => ({ default: m.SimulationLab }))
);

export function App() {
  const [currentTab, setCurrentTab] = useState<NavTab>('overview');
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState<boolean>(false);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [campusSummary, setCampusSummary] = useState<DeviceSummaryResponse | null>(null);
  const [sourceMode, setSourceMode] = useState<'localhost' | 'campus'>('localhost');

  const { theme, setTheme, resolvedTheme } = useTheme();

  const addToast = useCallback((type: ToastMessage['type'], message: string) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3500);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const fetchCampusSummary = useCallback(async () => {
    try {
      const summaryData = await deviceApi.getSummary();
      setCampusSummary(summaryData);
    } catch {
      // Fallback silently if service is starting up
    }
  }, []);

  useEffect(() => {
    fetchCampusSummary();
  }, [fetchCampusSummary]);

  const {
    metrics,
    rollingHistory,
    interfaces,
    activeInterface,
    isMonitoring,
    health,
    summary,
    activities,
    isLoading,
    isSwitching,
    error,
    wsStatus,
    downloadTrend,
    uploadTrend,
    selectInterface,
    toggleMonitoring,
    refreshAll,
    // Anomaly engine state & handlers
    anomalySummary,
    anomalyEvents,
    rollingAnomalyHistory,
    isAnomalyLoading,
    anomalyError,
    refreshAnomalies,
  } = useNetworkData();

  const handleRefreshAll = useCallback(async () => {
    await Promise.all([refreshAll(), fetchCampusSummary()]);
  }, [refreshAll, fetchCampusSummary]);

  const handleSelectInterface = async (name: string) => {
    try {
      await selectInterface(name);
      addToast('success', `Switched monitoring adapter to ${name}`);
    } catch {
      addToast('error', `Failed to switch to ${name}`);
    }
  };

  const handleToggleMonitoring = async (start: boolean) => {
    try {
      await toggleMonitoring(start);
      addToast(start ? 'success' : 'info', `Monitoring collection ${start ? 'resumed' : 'paused'}`);
    } catch {
      addToast('error', 'Failed to update monitoring state');
    }
  };

  const getPageTitle = (tab: NavTab): string => {
    switch (tab) {
      case 'overview':
        return 'Network Observability';
      case 'campus':
        return 'Campus Network Operations Center (NOC)';
      case 'live':
        return 'Live Telemetry Stream';
      case 'analytics':
        return 'Traffic Analytics';
      case 'interfaces':
        return 'Network Interfaces';
      case 'devices':
        return 'Campus Device Registry';
      case 'anomaly':
        return 'AI Anomaly Detection';
      case 'simulation':
        return 'Controlled Simulation Lab';
      case 'settings':
        return 'Settings & Diagnostics';
      default:
        return 'NetworkAI';
    }
  };

  const themeCards: { mode: ThemeMode; label: string; desc: string; icon: React.FC<{ className?: string; 'aria-hidden'?: boolean | 'true' | 'false' }> }[] = [
    {
      mode: 'light',
      label: 'Light Mode',
      desc: 'The iconic Geist near-white canvas (#fafafa) with near-black ink typography (#171717).',
      icon: Sun,
    },
    {
      mode: 'dark',
      label: 'Dark Mode',
      desc: 'Stark developer dark theme with elevated charcoal surfaces and high contrast readability.',
      icon: Moon,
    },
    {
      mode: 'system',
      label: 'System Preference',
      desc: 'Automatically synchronizes with your host operating system display mode.',
      icon: Laptop,
    },
  ];

  return (
    <div className="min-h-screen bg-app-bg text-text-primary flex selection:bg-[#0070f3]/20 selection:text-[#0070f3] transition-colors relative">
      {/* Subtle top mesh gradient per DESIGN.md */}
      <div className="absolute top-0 left-0 right-0 h-96 vercel-mesh-gradient pointer-events-none z-0 opacity-70" aria-hidden="true" />

      {/* Sidebar Navigation */}
      <Sidebar
        currentTab={currentTab}
        onSelectTab={(tab) => {
          setCurrentTab(tab);
          setMobileSidebarOpen(false);
        }}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        mobileOpen={mobileSidebarOpen}
        onCloseMobile={() => setMobileSidebarOpen(false)}
      />

      {/* Main Content Area */}
      <div
        className={`flex-1 flex flex-col min-w-0 transition-[margin] duration-150 ease-out z-10 ${
          sidebarCollapsed ? 'md:ml-16' : 'md:ml-60'
        }`}
      >
        <Header
          title={getPageTitle(currentTab)}
          activeInterface={activeInterface}
          interfaces={interfaces}
          wsStatus={wsStatus}
          isMonitoring={isMonitoring}
          onRefresh={handleRefreshAll}
          onSelectInterface={handleSelectInterface}
          onToggleSidebarMobile={() => setMobileSidebarOpen(!mobileSidebarOpen)}
        />

        {/* Global Error Banner */}
        {error && (
          <div className="bg-[#ee0000]/10 border-b border-[#ee0000]/25 px-5 py-2.5 text-xs text-[#ee0000] dark:text-[#f87171] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
              <span>{error}</span>
            </div>
            <button
              onClick={handleRefreshAll}
              className="underline hover:opacity-80 font-medium ml-4 cursor-pointer font-mono"
            >
              Retry
            </button>
          </div>
        )}

        {/* Tab Views */}
        <main className="flex-1 p-4 md:p-6 lg:p-8 space-y-5 max-w-7xl w-full mx-auto">
          {isLoading ? (
            <div className="h-80 flex flex-col items-center justify-center gap-3">
              <Spinner size="md" />
              <p className="text-xs font-mono text-text-secondary">
                Connecting to backend telemetry services…
              </p>
            </div>
          ) : (
            <AnimatePresence mode="wait">
              <motion.div
                key={currentTab}
                initial={{ opacity: 0, y: 3 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15, ease: 'easeOut' }}
                className="space-y-5"
              >
                {/* TAB 1: OVERVIEW */}
                {currentTab === 'overview' && (
                  <>
                    {/* Telemetry Source Switcher / Indicator */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-[12px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)]">
                      <div className="flex items-center gap-2.5">
                        <span className="text-xs font-semibold text-text-primary tracking-[-0.2px]">
                          Telemetry Source:
                        </span>
                        <div className="flex items-center p-0.5 rounded-[6px] bg-elevated-surface border border-border-subtle text-xs">
                          <button
                            onClick={() => setSourceMode('localhost')}
                            className={`flex items-center gap-1.5 px-3 py-1 rounded-[4px] transition-colors cursor-pointer ${
                              sourceMode === 'localhost'
                                ? 'bg-card-surface text-text-primary shadow-xs font-semibold'
                                : 'text-text-secondary hover:text-text-primary'
                            }`}
                          >
                            <span className="w-2 h-2 rounded-full bg-[#0070f3]" aria-hidden="true" />
                            <span>Local Host</span>
                          </button>

                          <button
                            onClick={() => setSourceMode('campus')}
                            className={`flex items-center gap-1.5 px-3 py-1 rounded-[4px] transition-colors cursor-pointer ${
                              sourceMode === 'campus'
                                ? 'bg-card-surface text-text-primary shadow-xs font-semibold'
                                : 'text-text-secondary hover:text-text-primary'
                            }`}
                          >
                            <Server className="w-3.5 h-3.5" aria-hidden="true" />
                            <span>Campus Devices</span>
                            <Badge variant={campusSummary && campusSummary.total_devices > 0 ? 'success' : 'neutral'} size="sm">
                              {campusSummary ? campusSummary.total_devices : 0}
                            </Badge>
                          </button>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 text-[11px] font-mono text-text-muted">
                        {sourceMode === 'localhost' ? (
                          <>
                            <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#0070f3]" />
                            <span>Host adapter ({activeInterface || 'Wi-Fi'}) via psutil collector</span>
                          </>
                        ) : (
                          <>
                            <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#50e3c2]" />
                            <span>Campus multi-device infrastructure registry (Phase 1)</span>
                          </>
                        )}
                      </div>
                    </div>

                    {sourceMode === 'localhost' ? (
                      <>
                        {/* 4 Metric Cards */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
                          <MetricCard
                            title="Download Throughput"
                            value={metrics ? metrics.download_mbps.toFixed(3) : '0.000'}
                            unit="Mbps"
                            icon={ArrowDownCircle}
                            accentColor={resolvedTheme === 'dark' ? '#3291ff' : '#0070f3'}
                            trendValue={downloadTrend}
                          />

                          <MetricCard
                            title="Upload Throughput"
                            value={metrics ? metrics.upload_mbps.toFixed(3) : '0.000'}
                            unit="Mbps"
                            icon={ArrowUpCircle}
                            accentColor={resolvedTheme === 'dark' ? '#a78bfa' : '#7928ca'}
                            trendValue={uploadTrend}
                          />

                          <MetricCard
                            title="Session Volume"
                            value={metrics ? metrics.session_transferred_mb.toFixed(2) : '0.00'}
                            unit="MB"
                            icon={HardDrive}
                            accentColor={resolvedTheme === 'dark' ? '#3291ff' : '#0070f3'}
                            breakdown={
                              metrics
                                ? `Lifetime: ${(
                                    metrics.cumulative_sent_mb + metrics.cumulative_received_mb
                                  ).toFixed(1)} MB`
                                : 'Waiting for packets'
                            }
                          />

                          <MetricCard
                            title="Packet Rate"
                            value={
                              metrics
                                ? (metrics.packets_sent_per_sec + metrics.packets_received_per_sec).toFixed(1)
                                : '0.0'
                            }
                            unit="pkt/s"
                            icon={Activity}
                            accentColor="#f5a623"
                            breakdown={
                              metrics
                                ? `Tx: ${metrics.packets_sent_per_sec.toFixed(0)} | Rx: ${metrics.packets_received_per_sec.toFixed(0)} /s`
                                : 'Waiting for packets'
                            }
                          />
                        </div>

                        {/* Compact Topology Alert Summary */}
                        <CompactAlertSummary onNavigateToAlerts={() => setCurrentTab('alerts')} />

                        {/* Live Throughput Chart */}
                        <LiveChart
                          data={rollingHistory}
                          activeInterface={activeInterface}
                          isMonitoring={isMonitoring}
                        />

                        {/* Network Adapters Panel */}
                        <InterfacePanel
                          interfaces={interfaces}
                          activeInterface={activeInterface}
                          isMonitoring={isMonitoring}
                          isSwitching={isSwitching}
                          onSelectInterface={handleSelectInterface}
                          onToggleMonitoring={handleToggleMonitoring}
                        />

                        {/* Diagnostics & Activity Feed */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                          <SystemStatus
                            health={health}
                            wsStatus={wsStatus}
                            activeInterface={activeInterface}
                            isMonitoring={isMonitoring}
                            campusDeviceCount={campusSummary?.total_devices ?? 0}
                          />
                          <ActivityFeed events={activities} />
                        </div>
                      </>
                    ) : (
                      /* Campus Devices View on Overview */
                      <div className="space-y-4">
                        {(!campusSummary || campusSummary.total_devices === 0) ? (
                          <div className="p-12 rounded-[12px] bg-card-surface border border-border-subtle text-center flex flex-col items-center justify-center shadow-[var(--shadow-whisper)]">
                            <div className="w-12 h-12 rounded-full bg-elevated-surface border border-border-subtle flex items-center justify-center mb-3 text-text-muted">
                              <Server className="w-6 h-6" />
                            </div>
                            <h3 className="text-sm font-semibold text-text-primary">
                              No campus devices have been configured yet.
                            </h3>
                            <p className="text-xs text-text-secondary mt-1.5 max-w-md">
                              Register authorized switches, routers, access points, or servers in the Devices registry to begin monitoring campus infrastructure across college departments.
                            </p>
                            <button
                              onClick={() => setCurrentTab('devices')}
                              className="mt-4 flex items-center gap-1.5 px-3.5 py-1.5 rounded-[6px] bg-[#0070f3] hover:bg-[#0070f3]/90 text-white text-xs font-medium shadow-xs transition-colors cursor-pointer"
                            >
                              <Plus className="w-4 h-4" />
                              <span>Configure Campus Devices</span>
                            </button>
                          </div>
                        ) : (
                          <div className="space-y-4">
                            <div className="p-4 rounded-[12px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                              <div>
                                <h3 className="text-sm font-semibold text-text-primary">
                                  Campus Infrastructure Overview ({campusSummary.total_devices} Devices)
                                </h3>
                                <p className="text-xs text-text-secondary mt-0.5">
                                  Phase 3 Campus NOC is active with logical hierarchy, aggregate throughput, and multi-device comparison.
                                </p>
                              </div>
                              <div className="flex items-center gap-2 shrink-0">
                                <button
                                  onClick={() => setCurrentTab('campus')}
                                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-[6px] bg-[#0070f3] hover:bg-[#0070f3]/90 text-white text-xs font-medium cursor-pointer"
                                >
                                  <span>Open Campus NOC</span>
                                </button>
                                <button
                                  onClick={() => setCurrentTab('devices')}
                                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-[6px] bg-elevated-surface hover:bg-elevated-surface/80 border border-border-subtle text-text-primary text-xs font-medium cursor-pointer"
                                >
                                  <span>Device Inventory</span>
                                </button>
                              </div>
                            </div>

                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
                              <div className="p-3.5 rounded-[10px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)]">
                                <span className="text-xs text-text-muted font-medium">Total Registered</span>
                                <div className="mt-2 text-2xl font-bold font-mono text-text-primary">
                                  {campusSummary.total_devices}
                                </div>
                              </div>
                              <div className="p-3.5 rounded-[10px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)]">
                                <span className="text-xs text-text-muted font-medium">Active Monitoring</span>
                                <div className="mt-2 text-2xl font-bold font-mono text-[#0070f3]">
                                  {campusSummary.active_count}
                                </div>
                              </div>
                              <div className="p-3.5 rounded-[10px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)]">
                                <span className="text-xs text-text-muted font-medium">Online Devices</span>
                                <div className="mt-2 text-2xl font-bold font-mono text-[#50e3c2]">
                                  {campusSummary.online_count}
                                </div>
                              </div>
                              <div className="p-3.5 rounded-[10px] bg-card-surface border border-border-subtle shadow-[var(--shadow-whisper)]">
                                <span className="text-xs text-text-muted font-medium">Departments</span>
                                <div className="mt-2 text-2xl font-bold font-mono text-text-primary">
                                  {Object.keys(campusSummary.by_department).length}
                                </div>
                              </div>
                            </div>

                            {/* Compact Topology Alert Summary */}
                            <CompactAlertSummary onNavigateToAlerts={() => setCurrentTab('alerts')} />
                          </div>
                        )}
                      </div>
                    )}
                  </>
                )}

                {/* TAB: CAMPUS NOC DASHBOARD */}
                {currentTab === 'campus' && (
                  <CampusOverview
                    onNavigateToDevices={() => setCurrentTab('devices')}
                    onNotify={(type, msg) => {
                      addToast(type, msg);
                      fetchCampusSummary();
                    }}
                  />
                )}

                {/* TAB: CAMPUS NETWORK TOPOLOGY */}
                {currentTab === 'topology' && (
                  <TopologyView
                    onNavigateToDevices={() => setCurrentTab('devices')}
                    onNotify={(type, msg) => {
                      addToast(type, msg);
                      fetchCampusSummary();
                    }}
                  />
                )}

                {/* TAB: TOPOLOGY ALERT CENTER (Phase 6) */}
                {currentTab === 'alerts' && (
                  <AlertCenter
                    onNotify={(type, msg) => {
                      addToast(type, msg);
                    }}
                    onNavigateToDevices={() => setCurrentTab('devices')}
                    onNavigateToTopology={() => setCurrentTab('topology')}
                  />
                )}

                {/* TAB 2: LIVE MONITORING */}
                {currentTab === 'live' && (
                  <>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                      <MetricCard
                        title="Live Download Stream"
                        value={metrics ? metrics.download_mbps.toFixed(4) : '0.0000'}
                        unit="Mbps"
                        icon={ArrowDownCircle}
                        accentColor={resolvedTheme === 'dark' ? '#3291ff' : '#0070f3'}
                        trendValue={downloadTrend}
                      />
                      <MetricCard
                        title="Live Upload Stream"
                        value={metrics ? metrics.upload_mbps.toFixed(4) : '0.0000'}
                        unit="Mbps"
                        icon={ArrowUpCircle}
                        accentColor={resolvedTheme === 'dark' ? '#a78bfa' : '#7928ca'}
                        trendValue={uploadTrend}
                      />
                    </div>

                    <LiveChart
                      data={rollingHistory}
                      activeInterface={activeInterface}
                      isMonitoring={isMonitoring}
                    />

                    <InterfacePanel
                      interfaces={interfaces}
                      activeInterface={activeInterface}
                      isMonitoring={isMonitoring}
                      isSwitching={isSwitching}
                      onSelectInterface={handleSelectInterface}
                      onToggleMonitoring={handleToggleMonitoring}
                    />
                  </>
                )}

                {/* TAB 3: TRAFFIC ANALYTICS */}
                {currentTab === 'analytics' && (
                  <Suspense
                    fallback={
                      <div className="py-16 flex flex-col items-center justify-center gap-3">
                        <Spinner size="md" />
                        <span className="text-xs font-mono text-text-secondary">Loading analytics records…</span>
                      </div>
                    }
                  >
                    <HistoricalChart currentInterface={activeInterface} />
                  </Suspense>
                )}

                {/* TAB 4: NETWORK INTERFACES */}
                {currentTab === 'interfaces' && (
                  <>
                    <InterfacePanel
                      interfaces={interfaces}
                      activeInterface={activeInterface}
                      isMonitoring={isMonitoring}
                      isSwitching={isSwitching}
                      onSelectInterface={handleSelectInterface}
                      onToggleMonitoring={handleToggleMonitoring}
                    />
                    <SystemStatus
                      health={health}
                      wsStatus={wsStatus}
                      activeInterface={activeInterface}
                      isMonitoring={isMonitoring}
                      campusDeviceCount={campusSummary?.total_devices ?? 0}
                    />
                  </>
                )}

                {/* TAB: CAMPUS MULTI-DEVICE REGISTRY */}
                {currentTab === 'devices' && (
                  <DeviceInventory
                    onNotify={(type, msg) => {
                      addToast(type, msg);
                      fetchCampusSummary();
                    }}
                  />
                )}

                {/* TAB 5: AI ANOMALY DETECTION ENGINE */}
                {currentTab === 'anomaly' && (
                  <div className="space-y-4">
                    <AnomalyOverview
                      evaluation={metrics?.anomaly || null}
                      summary={anomalySummary}
                      activeInterface={activeInterface}
                      wsStatus={wsStatus}
                      isLoading={isAnomalyLoading}
                      error={anomalyError}
                    />

                    <AnomalyTimeline
                      data={rollingAnomalyHistory}
                      activeInterface={activeInterface}
                      isMonitoring={isMonitoring}
                      currentScore={metrics?.anomaly?.score ?? 0.0}
                      currentSeverity={metrics?.anomaly?.severity ?? 'Normal'}
                    />

                    <AnomalyEventHistory
                      events={anomalyEvents}
                      isLoading={isAnomalyLoading}
                      error={anomalyError}
                      onRefresh={refreshAnomalies}
                    />
                  </div>
                )}

                {/* TAB 6: CONTROLLED SIMULATION LAB */}
                {currentTab === 'simulation' && (
                  <Suspense
                    fallback={
                      <div className="py-16 flex flex-col items-center justify-center gap-3">
                        <Spinner size="md" />
                        <span className="text-xs font-mono text-text-secondary">Initializing simulation lab environment…</span>
                      </div>
                    }
                  >
                    <SimulationLab />
                  </Suspense>
                )}

                {/* TAB 7: SETTINGS & DIAGNOSTICS */}
                {currentTab === 'settings' && (
                  <div className="space-y-5 max-w-4xl mx-auto">
                    {/* Appearance Section */}
                    <div className="bg-card-surface border border-border-subtle rounded-[12px] p-5 shadow-[var(--shadow-whisper)] space-y-4">
                      <div className="pb-3 border-b border-border-subtle">
                        <h2 className="text-sm font-semibold text-text-primary tracking-[-0.28px]">Appearance & Theme</h2>
                        <p className="text-xs text-text-secondary mt-0.5">Customize the visual presentation mode of the NetworkAI observability console</p>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        {themeCards.map((card) => {
                          const Icon = card.icon;
                          const isSelected = theme === card.mode;
                          return (
                            <button
                              key={card.mode}
                              type="button"
                              onClick={() => {
                                setTheme(card.mode);
                                addToast('info', `Switched theme to ${card.label}`);
                              }}
                              className={`p-4 rounded-[12px] border text-left transition-colors cursor-pointer flex flex-col justify-between space-y-3 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-text-primary ${
                                isSelected
                                  ? 'bg-elevated-surface border-text-primary shadow-xs'
                                  : 'bg-card-surface border-border-subtle hover:border-border-hover hover:bg-elevated-surface/50'
                              }`}
                              aria-pressed={isSelected}
                            >
                              <div className="flex items-center justify-between w-full">
                                <div className="p-2 rounded-[6px] bg-card-surface border border-border-subtle text-text-primary">
                                  <Icon className="w-4 h-4" aria-hidden="true" />
                                </div>
                                {isSelected && (
                                  <span className="flex items-center gap-1 text-[11px] font-mono font-semibold text-[#0070f3] dark:text-[#3291ff]">
                                    <CheckCircle2 className="w-3.5 h-3.5" aria-hidden="true" /> Selected
                                  </span>
                                )}
                              </div>
                              <div>
                                <h3 className="text-xs font-semibold text-text-primary">{card.label}</h3>
                                <p className="text-[11px] text-text-secondary mt-1 leading-relaxed">{card.desc}</p>
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* API and WebSocket Configuration */}
                    <div className="bg-card-surface border border-border-subtle rounded-[12px] p-5 shadow-[var(--shadow-whisper)] space-y-4">
                      <div className="pb-3 border-b border-border-subtle flex items-center justify-between">
                        <div>
                          <h2 className="text-sm font-semibold text-text-primary tracking-[-0.28px]">API & Stream Configuration</h2>
                          <p className="text-xs text-text-secondary mt-0.5">Core REST endpoints and streaming socket connectivity</p>
                        </div>
                        <div className="flex items-center gap-1.5 text-xs text-[#0070f3] dark:text-[#3291ff] font-mono font-medium">
                          <span className="w-2 h-2 rounded-full bg-[#0070f3]" aria-hidden="true" />
                          <span>Connected</span>
                        </div>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                        <div className="p-3.5 rounded-[8px] bg-elevated-surface border border-border-subtle">
                          <div className="flex items-center gap-2 text-text-secondary mb-1">
                            <Server className="w-3.5 h-3.5 text-text-muted" aria-hidden="true" />
                            <span className="font-medium">REST API Gateway</span>
                          </div>
                          <div className="font-mono text-text-primary font-medium text-[11px]">http://127.0.0.1:8000</div>
                          <p className="text-[11px] text-text-muted mt-1">Telemetry polling, persistence queries, and simulation execution</p>
                        </div>

                        <div className="p-3.5 rounded-[8px] bg-elevated-surface border border-border-subtle">
                          <div className="flex items-center gap-2 text-text-secondary mb-1">
                            <Radio className="w-3.5 h-3.5 text-text-muted" aria-hidden="true" />
                            <span className="font-medium">WebSocket Live Stream</span>
                          </div>
                          <div className="font-mono text-[#0070f3] dark:text-[#3291ff] font-medium text-[11px]">ws://127.0.0.1:8000/ws/metrics</div>
                          <p className="text-[11px] text-text-muted mt-1">1 Hz full duplex frame broadcast with automatic reconnection</p>
                        </div>
                      </div>
                    </div>

                    {/* Telemetry Cadence & Persistence */}
                    <div className="bg-card-surface border border-border-subtle rounded-[12px] p-5 shadow-[var(--shadow-whisper)] space-y-4">
                      <div className="pb-3 border-b border-border-subtle flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Sliders className="w-4 h-4 text-text-muted" aria-hidden="true" />
                          <h2 className="text-sm font-semibold text-text-primary tracking-[-0.28px]">System Diagnostics & Storage</h2>
                        </div>
                        <span className="text-xs font-mono text-text-muted">Host Agent</span>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                        <div className="p-3.5 rounded-[8px] bg-elevated-surface border border-border-subtle">
                          <div className="flex items-center gap-2 text-text-secondary mb-1">
                            <Database className="w-3.5 h-3.5 text-text-muted" aria-hidden="true" />
                            <span className="font-medium">Persistence Engine</span>
                          </div>
                          <div className="text-text-primary font-mono font-medium text-[11px]">SQLite 3 (WAL Mode)</div>
                          <p className="text-[11px] text-text-muted mt-1">SQLAlchemy ORM with indexing on timestamp and network interface</p>
                        </div>

                        <div className="p-3.5 rounded-[8px] bg-elevated-surface border border-border-subtle">
                          <div className="flex items-center gap-2 text-text-secondary mb-1">
                            <Activity className="w-3.5 h-3.5 text-text-muted" aria-hidden="true" />
                            <span className="font-medium">Sampling Cadence</span>
                          </div>
                          <div className="text-text-primary font-mono font-medium text-[11px]">1.0s Fixed Window</div>
                          <p className="text-[11px] text-text-muted mt-1">Kernel I/O socket counter deltas collected via psutil</p>
                        </div>
                      </div>

                      {summary && (
                        <div className="p-3.5 rounded-[8px] bg-elevated-surface border border-border-subtle space-y-2 font-mono">
                          <div className="text-xs font-semibold text-text-secondary tracking-[0.05em] uppercase text-[10px]">Session Telemetry Aggregates</div>
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs pt-1">
                            <div>
                              <span className="text-text-muted text-[10px] block uppercase">Peak Down</span>
                              <span className="text-[#0070f3] dark:text-[#3291ff] font-semibold tabular-nums">{summary.peak_download_mbps.toFixed(3)} Mbps</span>
                            </div>
                            <div>
                              <span className="text-text-muted text-[10px] block uppercase">Peak Up</span>
                              <span className="text-[#7928ca] dark:text-[#a78bfa] font-semibold tabular-nums">{summary.peak_upload_mbps.toFixed(3)} Mbps</span>
                            </div>
                            <div>
                              <span className="text-text-muted text-[10px] block uppercase">Stored Samples</span>
                              <span className="text-text-primary font-semibold tabular-nums">{summary.total_stored_samples}</span>
                            </div>
                            <div>
                              <span className="text-text-muted text-[10px] block uppercase">Session</span>
                              <span className="text-text-primary font-semibold tabular-nums">{summary.monitoring_duration_seconds}s</span>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </motion.div>
            </AnimatePresence>
          )}
        </main>
      </div>

      {/* Microinteraction Toast Container */}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

export default App;
