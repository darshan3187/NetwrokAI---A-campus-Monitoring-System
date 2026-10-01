import React, { useState, useEffect } from 'react';
import {
  Menu,
  RotateCw,
  Wifi,
  ChevronDown,
  Sun,
  Moon,
  Laptop,
} from 'lucide-react';
import { Badge } from '../common/Badge';
import { useTheme, type ThemeMode } from '../../context/ThemeContext';
import type { ConnectionStatus } from '../../hooks/useWebSocket';
import type { InterfaceDetail } from '../../types/metrics';

interface HeaderProps {
  title: string;
  activeInterface: string | null;
  interfaces: InterfaceDetail[];
  wsStatus: ConnectionStatus;
  isMonitoring: boolean;
  onRefresh: () => void;
  onSelectInterface: (name: string) => void;
  onToggleSidebarMobile: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  title,
  activeInterface,
  interfaces,
  wsStatus,
  isMonitoring,
  onRefresh,
  onSelectInterface,
  onToggleSidebarMobile,
}) => {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [currentTime, setCurrentTime] = useState<string>('');
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [adapterDropdownOpen, setAdapterDropdownOpen] = useState<boolean>(false);
  const [themeDropdownOpen, setThemeDropdownOpen] = useState<boolean>(false);

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setCurrentTime(
        now.toLocaleTimeString('en-US', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        })
      );
    };

    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleRefreshClick = async () => {
    setIsRefreshing(true);
    await onRefresh();
    setTimeout(() => setIsRefreshing(false), 400);
  };

  const wsBadgeVariant = {
    connected: 'success' as const,
    connecting: 'warning' as const,
    disconnected: 'neutral' as const,
    error: 'error' as const,
  }[wsStatus];

  const themeOptions: { mode: ThemeMode; label: string; icon: React.FC<{ className?: string; 'aria-hidden'?: boolean | 'true' | 'false' }> }[] = [
    { mode: 'light', label: 'Light', icon: Sun },
    { mode: 'dark', label: 'Dark', icon: Moon },
    { mode: 'system', label: 'System', icon: Laptop },
  ];

  return (
    <header className="h-14 bg-card-surface/90 backdrop-blur-md border-b border-border-subtle px-4 md:px-6 flex items-center justify-between sticky top-0 z-30 transition-[background-color,border-color]">
      {/* Left: Mobile Toggle & Page Title */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onToggleSidebarMobile}
          className="md:hidden p-1.5 rounded-[6px] text-text-secondary hover:text-text-primary hover:bg-elevated-surface cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-text-primary"
          aria-label="Toggle navigation drawer"
        >
          <Menu className="w-4 h-4" aria-hidden="true" />
        </button>
        <div className="flex items-center gap-2 truncate">
          <span className="text-sm font-semibold text-text-primary tracking-[-0.28px] truncate">
            {title}
          </span>
          <span className="hidden sm:inline text-text-muted text-xs select-none">/</span>
          <span className="hidden sm:inline text-xs text-text-muted font-mono uppercase tracking-[0.05em]">
            Host Telemetry
          </span>
        </div>
      </div>

      {/* Right: Quick Adapter Selector, Theme Toggle, Indicators, Refresh */}
      <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
        {/* Interface Switcher Dropdown */}
        <div className="relative">
          <button
            onClick={() => {
              setAdapterDropdownOpen(!adapterDropdownOpen);
              setThemeDropdownOpen(false);
            }}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-[6px] bg-card-surface border border-border-subtle hover:border-border-hover text-xs text-text-primary transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-text-primary"
            title="Switch Network Interface"
            aria-expanded={adapterDropdownOpen}
            aria-haspopup="listbox"
            aria-label="Select Network Adapter"
          >
            <Wifi className="w-3.5 h-3.5 text-text-muted" aria-hidden="true" />
            <span className="text-xs max-w-[90px] sm:max-w-[120px] truncate font-mono">
              {activeInterface || 'Select Adapter'}
            </span>
            <ChevronDown className="w-3 h-3 text-text-muted" aria-hidden="true" />
          </button>

          {adapterDropdownOpen && (
            <div
              className="absolute right-0 mt-1.5 w-60 rounded-[6px] bg-card-surface border border-border-subtle shadow-[var(--shadow-floating)] py-1 z-50 animate-in fade-in zoom-in-95 duration-100"
              onMouseLeave={() => setAdapterDropdownOpen(false)}
            >
              <div className="px-3 py-1.5 text-[10px] uppercase font-mono tracking-[0.05em] text-text-muted border-b border-border-subtle">
                Network Adapters
              </div>
              <div className="max-h-48 overflow-y-auto py-1">
                {interfaces.map((iface) => (
                  <button
                    key={iface.name}
                    onClick={() => {
                      onSelectInterface(iface.name);
                      setAdapterDropdownOpen(false);
                    }}
                    className={`w-full text-left px-3 py-1.5 text-xs font-mono flex items-center justify-between transition-colors cursor-pointer ${
                      iface.name === activeInterface
                        ? 'bg-elevated-surface text-[#0070f3] font-medium'
                        : 'text-text-secondary hover:bg-elevated-surface hover:text-text-primary'
                    }`}
                  >
                    <span className="truncate">{iface.name}</span>
                    {iface.name === activeInterface && (
                      <span className="w-1.5 h-1.5 rounded-full bg-[#0070f3] shrink-0" aria-hidden="true" />
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Theme Switcher Dropdown */}
        <div className="relative">
          <button
            onClick={() => {
              setThemeDropdownOpen(!themeDropdownOpen);
              setAdapterDropdownOpen(false);
            }}
            className="flex items-center gap-1.5 px-2 py-1 rounded-[6px] bg-card-surface border border-border-subtle hover:border-border-hover text-xs text-text-secondary hover:text-text-primary transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-text-primary"
            title={`Current theme: ${theme} (${resolvedTheme})`}
            aria-label="Change theme"
            aria-expanded={themeDropdownOpen}
            aria-haspopup="menu"
          >
            {resolvedTheme === 'dark' ? (
              <Moon className="w-3.5 h-3.5 text-text-primary" aria-hidden="true" />
            ) : (
              <Sun className="w-3.5 h-3.5 text-text-primary" aria-hidden="true" />
            )}
            <span className="hidden md:inline capitalize text-xs">{theme}</span>
            <ChevronDown className="w-3 h-3 text-text-muted" aria-hidden="true" />
          </button>

          {themeDropdownOpen && (
            <div
              className="absolute right-0 mt-1.5 w-36 rounded-[6px] bg-card-surface border border-border-subtle shadow-[var(--shadow-floating)] py-1 z-50 animate-in fade-in zoom-in-95 duration-100"
              role="menu"
              aria-label="Theme options"
              onMouseLeave={() => setThemeDropdownOpen(false)}
            >
              {themeOptions.map((opt) => {
                const Icon = opt.icon;
                const isSelected = theme === opt.mode;
                return (
                  <button
                    key={opt.mode}
                    onClick={() => {
                      setTheme(opt.mode);
                      setThemeDropdownOpen(false);
                    }}
                    className={`w-full text-left px-3 py-1.5 text-xs flex items-center justify-between transition-colors cursor-pointer ${
                      isSelected
                        ? 'bg-elevated-surface text-text-primary font-medium'
                        : 'text-text-secondary hover:bg-elevated-surface hover:text-text-primary'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <Icon className="w-3.5 h-3.5" aria-hidden="true" />
                      <span>{opt.label}</span>
                    </div>
                    {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-[#0070f3]" aria-hidden="true" />}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Live Monitoring Badge */}
        {isMonitoring ? (
          <Badge variant="success" pulse size="sm">
            LIVE
          </Badge>
        ) : (
          <Badge variant="warning" size="sm">
            PAUSED
          </Badge>
        )}

        {/* WebSocket Stream Status */}
        <div className="hidden sm:block">
          <Badge variant={wsBadgeVariant} size="sm">
            WS {wsStatus.toUpperCase()}
          </Badge>
        </div>

        {/* Monospace Clock */}
        <div className="hidden lg:block text-xs font-mono text-text-muted tabular-nums pl-1 border-l border-border-subtle">
          {currentTime}
        </div>

        {/* Refresh Action */}
        <button
          onClick={handleRefreshClick}
          disabled={isRefreshing}
          className="p-1.5 rounded-[6px] border border-border-subtle text-text-secondary hover:text-text-primary hover:bg-elevated-surface active:scale-95 transition-transform cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-text-primary"
          title="Refresh telemetry"
          aria-label="Refresh telemetry"
        >
          <RotateCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-[#0070f3]' : ''}`} aria-hidden="true" />
        </button>
      </div>
    </header>
  );
};
