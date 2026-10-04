import React from 'react';
import {
  Activity,
  BarChart3,
  Radio,
  FlaskConical,
  PanelLeftClose,
  PanelLeftOpen,
  Database,
  BookOpen,
  X,
} from 'lucide-react';

export type NavTab =
  | 'overview'
  | 'experiment'
  | 'dataset'
  | 'results'
  | 'live'
  | 'research';

interface SidebarProps {
  currentTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  collapsed,
  onToggleCollapse,
  mobileOpen = false,
  onCloseMobile,
}) => {
  const navItems = [
    { id: 'overview' as NavTab, label: 'Overview', icon: Activity },
    { id: 'dataset' as NavTab, label: 'Dataset', icon: Database },
    { id: 'experiment' as NavTab, label: 'Experiment', icon: FlaskConical },
    { id: 'results' as NavTab, label: 'Results', icon: BarChart3 },
    { id: 'live' as NavTab, label: 'Live Monitor', icon: Radio },
    { id: 'research' as NavTab, label: 'Research / About', icon: BookOpen },
  ];


  const handleSelect = (id: NavTab) => {
    onSelectTab(id);
    if (onCloseMobile) {
      onCloseMobile();
    }
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-xs md:hidden"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 md:z-30 bg-sidebar-bg border-r border-border-subtle transition-[width,transform] duration-150 ease-out flex flex-col ${
          mobileOpen ? 'translate-x-0 w-64' : '-translate-x-full md:translate-x-0'
        } ${collapsed ? 'md:w-16' : 'md:w-60'}`}
      >
        {/* Brand Header */}
        <div className="h-14 flex items-center justify-between px-3.5 border-b border-border-subtle">
          <div className="flex items-center gap-2.5 overflow-hidden">
            {/* Clean Mark */}
            <div className="w-7 h-7 rounded-[6px] bg-[#171717] dark:bg-[#ededed] text-white dark:text-black flex items-center justify-center shrink-0">
              <svg viewBox="0 0 76 65" className="w-3.5 h-3 fill-current" aria-hidden="true">
                <path d="M37.5274 0L75.0548 65H0L37.5274 0Z" />
              </svg>
            </div>
            {(!collapsed || mobileOpen) && (
              <div className="flex items-baseline gap-1.5 overflow-hidden">
                <span className="font-semibold text-sm text-text-primary tracking-[-0.4px]">
                  Network<span className="text-[#0070f3]">AI</span>
                </span>
                <span className="text-[10px] text-text-muted font-mono uppercase tracking-[0.05em]">
                  Research
                </span>
              </div>
            )}
          </div>

          {/* Desktop collapse toggle */}
          <button
            onClick={onToggleCollapse}
            className="hidden md:flex p-1.5 rounded-[6px] hover:bg-elevated-surface text-text-muted hover:text-text-primary transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-text-primary"
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-label="Toggle sidebar collapse"
          >
            {collapsed ? (
              <PanelLeftOpen className="w-4 h-4" aria-hidden="true" />
            ) : (
              <PanelLeftClose className="w-4 h-4" aria-hidden="true" />
            )}
          </button>

          {/* Mobile close button */}
          <button
            onClick={onCloseMobile}
            className="flex md:hidden p-1.5 rounded-[6px] hover:bg-elevated-surface text-text-muted hover:text-text-primary transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-text-primary"
            aria-label="Close menu"
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 py-3 px-2 space-y-1 overflow-y-auto" role="navigation" aria-label="Main Navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => handleSelect(item.id)}
                className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-[6px] text-[13px] font-medium transition-colors group relative cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-text-primary ${
                  isActive
                    ? 'bg-elevated-surface text-text-primary font-semibold'
                    : 'text-text-secondary hover:text-text-primary hover:bg-elevated-surface/70'
                }`}
                title={collapsed && !mobileOpen ? item.label : undefined}
                aria-current={isActive ? 'page' : undefined}
              >
                <Icon
                  className={`w-4 h-4 shrink-0 transition-colors ${
                    isActive ? 'text-text-primary' : 'text-text-muted group-hover:text-text-primary'
                  }`}
                  aria-hidden="true"
                />

                {(!collapsed || mobileOpen) && (
                  <div className="flex-1 flex items-center justify-between overflow-hidden min-w-0">
                    <span className="truncate">{item.label}</span>
                  </div>
                )}
              </button>
            );
          })}
        </nav>

        {/* Minimal Academic Project Footer */}
        <div className="p-3 border-t border-border-subtle text-xs text-text-muted flex items-center justify-between">
          {!collapsed || mobileOpen ? (
            <>
              <span className="text-[11px] text-text-muted font-medium">B.Tech Project</span>
              <div className="flex items-center gap-1.5 text-[11px] text-text-secondary">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#0070f3]" aria-hidden="true" />
                <span className="font-mono text-[11px]">Computer Engineering</span>
              </div>
            </>
          ) : (
            <div className="w-full flex justify-center">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#0070f3]" title="NetworkAI Active" aria-hidden="true" />
            </div>
          )}
        </div>

      </aside>
    </>
  );
};
