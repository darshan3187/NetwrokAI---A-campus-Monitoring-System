import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNetworkData } from './hooks/useNetworkData';
import { Sidebar, type NavTab } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { ToastContainer, type ToastMessage } from './components/common/Toast';
import { Spinner } from './components/common/Spinner';

// Dedicated Research and Monitoring Views
import { OverviewTab } from './components/research/OverviewTab';
import { ExperimentTab } from './components/research/ExperimentTab';
import { DatasetTab } from './components/research/DatasetTab';
import { ResultsTab } from './components/research/ResultsTab';
import { DocumentationTab } from './components/research/DocumentationTab';
import { LiveMonitorTab } from './components/monitor/LiveMonitorTab';

export function App() {
  const [currentTab, setCurrentTab] = useState<NavTab>('overview');
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState<boolean>(false);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

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

  const {
    metrics,
    rollingHistory,
    interfaces,
    activeInterface,
    isMonitoring,
    isLoading,
    isSwitching,
    error,
    wsStatus,
    downloadTrend,
    uploadTrend,
    selectInterface,
    toggleMonitoring,
    refreshAll,
  } = useNetworkData();

  const handleSelectInterface = async (name: string) => {
    try {
      await selectInterface(name);
      addToast('success', `Switched local host adapter to ${name}`);
    } catch {
      addToast('error', `Failed to switch to ${name}`);
    }
  };

  const handleToggleMonitoring = async (start: boolean) => {
    try {
      await toggleMonitoring(start);
      addToast(start ? 'success' : 'info', `Local monitoring ${start ? 'resumed' : 'paused'}`);
    } catch {
      addToast('error', 'Failed to update monitoring state');
    }
  };

  const getPageTitle = (tab: NavTab): string => {
    switch (tab) {
      case 'overview':
        return 'Overview';
      case 'dataset':
        return 'Dataset';
      case 'experiment':
        return 'Experiment';
      case 'results':
        return 'Results';
      case 'live':
        return 'Live Monitor';
      case 'research':
        return 'Research / About';
      default:
        return 'NetworkAI';
    }
  };

  const getPageSubtitle = (tab: NavTab): string => {
    switch (tab) {
      case 'overview':
        return 'Project Overview & Status';
      case 'dataset':
        return 'NetFlow Dataset Management';
      case 'experiment':
        return 'Model Training & Evaluation';
      case 'results':
        return 'Performance Evaluation & Comparison';
      case 'live':
        return 'Local Host Telemetry';
      case 'research':
        return 'Reference Paper & About';
      default:
        return 'Network Anomaly Detection';
    }
  };

  return (
    <div className="min-h-screen bg-canvas text-text-primary flex transition-colors duration-150">
      {/* Sidebar Navigation (Simplified 6 Tabs) */}
      <Sidebar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        mobileOpen={mobileSidebarOpen}
        onCloseMobile={() => setMobileSidebarOpen(false)}
      />

      {/* Main Content Area */}
      <div
        className={`flex-1 flex flex-col min-w-0 transition-[margin] duration-150 ease-out ${
          sidebarCollapsed ? 'md:ml-16' : 'md:ml-60'
        }`}
      >
        {/* Top Header */}
        <Header
          title={getPageTitle(currentTab)}
          subtitle={getPageSubtitle(currentTab)}
          activeInterface={activeInterface}
          interfaces={interfaces}
          wsStatus={wsStatus}
          isMonitoring={isMonitoring}
          onRefresh={refreshAll}
          onSelectInterface={handleSelectInterface}
          onToggleSidebarMobile={() => setMobileSidebarOpen(true)}
        />

        {/* Dynamic View Container */}
        <main className="flex-1 p-4 md:p-6 overflow-y-auto">
          {isLoading && !metrics ? (
            <div className="py-24 flex flex-col items-center justify-center gap-3">
              <Spinner size="lg" />
              <span className="text-xs font-mono text-text-secondary">
                Initializing NetworkAI platform…
              </span>
            </div>
          ) : error ? (
            <div className="p-4 rounded-[8px] bg-red-500/10 border border-red-500/25 text-red-500 text-xs flex items-center justify-between">
              <span>{error}</span>
              <button
                onClick={refreshAll}
                className="underline hover:opacity-80 font-medium cursor-pointer"
              >
                Retry
              </button>
            </div>
          ) : (
            <AnimatePresence mode="wait">
              <motion.div
                key={currentTab}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                {/* 1. OVERVIEW */}
                {currentTab === 'overview' && (
                  <OverviewTab onNavigate={(tab) => setCurrentTab(tab)} />
                )}

                {/* 2. DATASET */}
                {currentTab === 'dataset' && <DatasetTab />}

                {/* 3. EXPERIMENT */}
                {currentTab === 'experiment' && (
                  <ExperimentTab
                    onNavigateToResults={() => setCurrentTab('results')}
                  />
                )}

                {/* 4. RESULTS & COMPARISON */}
                {currentTab === 'results' && <ResultsTab />}

                {/* 5. LIVE MONITOR */}
                {currentTab === 'live' && (
                  <LiveMonitorTab
                    metrics={metrics}
                    rollingHistory={rollingHistory}
                    interfaces={interfaces}
                    activeInterface={activeInterface}
                    isMonitoring={isMonitoring}
                    isSwitching={isSwitching}
                    downloadTrend={downloadTrend}
                    uploadTrend={uploadTrend}
                    onSelectInterface={handleSelectInterface}
                    onToggleMonitoring={handleToggleMonitoring}
                  />
                )}

                {/* 6. RESEARCH & DOCUMENTATION */}
                {currentTab === 'research' && <DocumentationTab />}
              </motion.div>
            </AnimatePresence>
          )}
        </main>
      </div>

      {/* Global Toast Container */}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

export default App;
