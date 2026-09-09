import React, { useState } from 'react';
import {
  LayoutDashboard,
  Layers,
  AlertOctagon,
  Boxes,
  Users,
  FileSpreadsheet,
  FileBarChart,
  Settings,
  Sun,
  Moon,
  Shield,
  Volume2,
  VolumeX,
} from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import { useAppData } from '../../context/AppDataContext';

export type ViewType =
  | 'dashboard'
  | 'events'
  | 'alerts'
  | 'products'
  | 'employees'
  | 'invoices'
  | 'reports'
  | 'settings';

interface NavigationRailProps {
  activeView: ViewType;
  onSelectView: (view: ViewType) => void;
}

interface NavItem {
  id: ViewType;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: number;
  badgeHigh?: boolean;
}

export const NavigationRail: React.FC<NavigationRailProps> = ({ activeView, onSelectView }) => {
  const { theme, toggleTheme } = useTheme();
  const { openAlertsCount, openAlertsBySeverity, settings, updateSettings, testAlarmSound } = useAppData();
  const [isExpanded, setIsExpanded] = useState(false);

  const navItems: NavItem[] = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'events', label: 'Exit Events', icon: Layers },
    {
      id: 'alerts',
      label: 'Active Alerts',
      icon: AlertOctagon,
      badge: openAlertsCount > 0 ? openAlertsCount : undefined,
      badgeHigh: openAlertsBySeverity.high > 0,
    },
    { id: 'products', label: 'Products & Cases', icon: Boxes },
    { id: 'employees', label: 'Employee Roster', icon: Users },
    { id: 'invoices', label: 'OCR Invoices', icon: FileSpreadsheet },
    { id: 'reports', label: 'Daily Reports', icon: FileBarChart },
    { id: 'settings', label: 'System Settings', icon: Settings },
  ];

  return (
    <aside
      onMouseEnter={() => setIsExpanded(true)}
      onMouseLeave={() => setIsExpanded(false)}
      className={`fixed top-0 left-0 bottom-0 z-40 flex flex-col justify-between bg-panel border-r border-hairline transition-all duration-200 ${
        isExpanded ? 'w-56 shadow-2xl' : 'w-16'
      }`}
    >
      {/* Top Brand / System ID */}
      <div>
        <div className="flex items-center gap-3 px-4 py-4 border-b border-hairline overflow-hidden">
          <div className="flex-shrink-0 w-8 h-8 rounded-sm bg-panel-raised border border-hairline flex items-center justify-center text-amber">
            <Shield className="w-5 h-5" />
          </div>
          {isExpanded && (
            <div className="flex flex-col min-w-0 transition-opacity duration-150">
              <span className="font-mono text-xs-tech font-semibold tracking-wider text-text-pri truncate">
                SEC-OPS 2.0
              </span>
              <span className="text-[11px] text-text-sec truncate">Exit Surveillance</span>
            </div>
          )}
        </div>

        {/* Navigation Items */}
        <nav className="p-2 space-y-1 mt-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeView === item.id;

            return (
              <button
                key={item.id}
                onClick={() => onSelectView(item.id)}
                className={`relative flex items-center w-full gap-3 px-3 py-2.5 rounded-sm text-sm-tech transition-colors group ${
                  isActive
                    ? 'bg-panel-raised text-text-pri border-l-2 border-amber font-medium'
                    : 'text-text-sec hover:text-text-pri hover:bg-hairline/30'
                }`}
                title={item.label}
              >
                <Icon
                  className={`w-5 h-5 flex-shrink-0 transition-colors ${
                    isActive ? 'text-amber' : 'text-text-sec group-hover:text-text-pri'
                  }`}
                />

                {isExpanded && (
                  <span className="flex-1 text-left truncate transition-opacity duration-150">
                    {item.label}
                  </span>
                )}

                {/* Open Alert Badge */}
                {item.badge !== undefined && (
                  <span
                    className={`font-mono text-[11px] font-bold px-1.5 py-0.2 rounded-full ${
                      item.badgeHigh
                        ? 'bg-status-high text-black animate-pulse'
                        : 'bg-amber text-black'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom Controls: Audio Mute & Theme Switcher */}
      <div className="p-2 border-t border-hairline space-y-1 bg-panel">
        {/* Audio Alert Toggle */}
        <button
          onClick={() => {
            updateSettings({ audioAlarmEnabled: !settings.audioAlarmEnabled });
            if (!settings.audioAlarmEnabled) testAlarmSound();
          }}
          className="flex items-center w-full gap-3 px-3 py-2 rounded-sm text-xs-tech text-text-sec hover:text-text-pri hover:bg-hairline/30 transition-colors"
          title={settings.audioAlarmEnabled ? 'Alarm Sound: Active' : 'Alarm Sound: Muted'}
        >
          {settings.audioAlarmEnabled ? (
            <Volume2 className="w-4 h-4 text-amber flex-shrink-0" />
          ) : (
            <VolumeX className="w-4 h-4 text-text-sec flex-shrink-0" />
          )}
          {isExpanded && (
            <span className="truncate">
              {settings.audioAlarmEnabled ? 'Siren Enabled' : 'Siren Muted'}
            </span>
          )}
        </button>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="flex items-center w-full gap-3 px-3 py-2 rounded-sm text-xs-tech text-text-sec hover:text-text-pri hover:bg-hairline/30 transition-colors"
          title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
        >
          {theme === 'dark' ? (
            <Sun className="w-4 h-4 text-status-low flex-shrink-0" />
          ) : (
            <Moon className="w-4 h-4 text-text-sec flex-shrink-0" />
          )}
          {isExpanded && (
            <span className="truncate">
              {theme === 'dark' ? 'Light Theme' : 'Dark Theme'}
            </span>
          )}
        </button>
      </div>
    </aside>
  );
};

