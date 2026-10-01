import React from 'react';
import {
  Activity,
  BarChart3,
  Network,
  Radio,
  Settings,
  ShieldAlert,
  FlaskConical,
  PanelLeftClose,
  PanelLeftOpen,
  Server,
  Building2,
  GitFork,
  X,
  Bell,
} from 'lucide-react';

export type NavTab =
  | 'overview'
  | 'campus'
  | 'topology'
  | 'alerts'
  | 'live'
  | 'analytics'
  | 'interfaces'
  | 'devices'
  | 'anomaly'
  | 'simulation'
  | 'settings';

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
    {
      id: 'campus' as NavTab,
      label: 'Campus NOC',
      icon: Building2,
      badge: 'NOC',
    },
    {
      id: 'topology' as NavTab,
      label: 'Topology',
      icon: GitFork,
      badge: 'LLDP',
    },
    {
      id: 'alerts' as NavTab,
      label: 'Alerts',
      icon: Bell,
      badge: 'Events',
    },
    { id: 'live' as NavTab, label: 'Live Stream', icon: Radio },
    { id: 'analytics' as NavTab, label: 'Analytics', icon: BarChart3 },
    { id: 'interfaces' as NavTab, label: 'Interfaces', icon: Network },
    {
      id: 'devices' as NavTab,
      label: 'Devices',
      icon: Server,
      badge: 'Campus',
    },
    {
      id: 'anomaly' as NavTab,
      label: 'AI Anomaly',
      icon: ShieldAlert,
      badge: 'ML',
    },
    {
      id: 'simulation' as NavTab,
      label: 'Simulation Lab',
      icon: FlaskConical,
      badge: 'Lab',
    },
    { id: 'settings' as NavTab, label: 'Settings', icon: Settings },
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
            {/* Iconic Triangle Mark */}
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
                  OBS
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
                    {item.badge && (
                      <span
                        className={`text-[10px] font-mono px-1.5 py-0.2 rounded-[4px] font-medium uppercase tracking-[0.05em] border ${
                          item.id === 'anomaly'
                            ? 'bg-[#0070f3]/10 text-[#0070f3] border-[#0070f3]/25'
                            : item.id === 'campus'
                            ? 'bg-[#0070f3]/10 text-[#0070f3] border-[#0070f3]/25'
                            : item.id === 'devices'
                            ? 'bg-[#50e3c2]/10 text-[#50e3c2] border-[#50e3c2]/25'
                            : 'bg-elevated-surface text-text-secondary border-border-subtle'
                        }`}
                      >
                        {item.badge}
                      </span>
                    )}
                  </div>
                )}
              </button>
            );
          })}
        </nav>

        {/* Minimal Footer */}
        <div className="p-3 border-t border-border-subtle text-xs text-text-muted flex items-center justify-between">
          {!collapsed || mobileOpen ? (
            <>
              <span className="text-[11px] font-mono text-text-faint">Engine v1.0</span>
              <div className="flex items-center gap-1.5 text-[11px] text-text-secondary">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#0070f3]" aria-hidden="true" />
                <span className="font-mono">ONLINE</span>
              </div>
            </>
          ) : (
            <div className="w-full flex justify-center">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#0070f3]" title="Telemetry Engine Online" aria-hidden="true" />
            </div>
          )}
        </div>
      </aside>
    </>
  );
};
