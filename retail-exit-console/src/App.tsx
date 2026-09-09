import React, { useState, useEffect } from 'react';
import { ThemeProvider } from './context/ThemeContext';
import { AppDataProvider, useAppData } from './context/AppDataContext';
import { NavigationRail } from './components/layout/NavigationRail';
import { TopKpiStrip } from './components/layout/TopKpiStrip';
import { SimulatorDrawer } from './components/simulation/SimulatorDrawer';
import { DashboardView } from './views/DashboardView';
import { EventsView } from './views/EventsView';
import { AlertsView } from './views/AlertsView';
import { ProductsView } from './views/ProductsView';
import { EmployeesView } from './views/EmployeesView';
import { InvoicesView } from './views/InvoicesView';
import { ReportsView } from './views/ReportsView';
import { SettingsView } from './views/SettingsView';
import { AlertOctagon, Zap, Lock } from 'lucide-react';

const AppContent: React.FC = () => {
  const [isSimulatorOpen, setIsSimulatorOpen] = useState(false);
  const { activeView, setActiveView, openAlertsBySeverity, turnstileLocked } = useAppData();

  // Keyboard shortcut navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input or textarea
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as HTMLElement)?.tagName)) {
        return;
      }

      if (e.key === 's' || e.key === 'S') {
        setIsSimulatorOpen((prev) => !prev);
      } else if (e.key === '1') {
        setActiveView('dashboard');
      } else if (e.key === '2') {
        setActiveView('events');
      } else if (e.key === '3') {
        setActiveView('alerts');
      } else if (e.key === '4') {
        setActiveView('products');
      } else if (e.key === '5') {
        setActiveView('employees');
      } else if (e.key === '6') {
        setActiveView('invoices');
      } else if (e.key === '7') {
        setActiveView('reports');
      } else if (e.key === '8') {
        setActiveView('settings');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const lockedLanes = Object.entries(turnstileLocked).filter(([, locked]) => locked).map(([lane]) => lane);

  return (
    <div className="min-h-screen bg-canvas text-text-pri flex flex-col font-sans">
      {/* High Severity Emergency Alert Banner */}
      {openAlertsBySeverity.high > 0 && (
        <div className="bg-red-950/80 border-b border-status-high text-status-high px-4 py-2 flex items-center justify-between text-xs-tech font-mono z-50 sticky top-0 backdrop-blur-sm animate-pulse">
          <div className="flex items-center gap-2">
            <AlertOctagon className="w-4 h-4 text-status-high flex-shrink-0" />
            <span className="font-bold tracking-wider">
              EMERGENCY INTERLOCK DISCREPANCY: {openAlertsBySeverity.high} HIGH-SEVERITY ALARM(S) ACTIVE
            </span>
          </div>
          <div className="flex items-center gap-3">
            {lockedLanes.length > 0 && (
              <span className="text-[11px] px-2 py-0.5 rounded bg-black/60 border border-status-high/50 flex items-center gap-1">
                <Lock className="w-3 h-3" />
                Interlock Engaged: {lockedLanes.join(', ')}
              </span>
            )}
            <button
              onClick={() => setActiveView('alerts')}
              className="px-2.5 py-0.5 bg-status-high text-black font-bold rounded-sm hover:bg-status-high/90 transition-colors"
            >
              Inspect Alarm Queue
            </button>
          </div>
        </div>
      )}

      {/* Main Layout Container */}
      <div className="flex flex-1">
        {/* Left Navigation Rail */}
        <NavigationRail activeView={activeView} onSelectView={setActiveView} />

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col ml-16 min-w-0">
          {/* Top Live KPI Strip (shown across monitoring views) */}
          <TopKpiStrip onOpenSimulator={() => setIsSimulatorOpen(true)} />

          {/* Active View Container */}
          <main className="flex-1 overflow-y-auto">
            {activeView === 'dashboard' && <DashboardView />}
            {activeView === 'events' && <EventsView />}
            {activeView === 'alerts' && <AlertsView />}
            {activeView === 'products' && <ProductsView />}
            {activeView === 'employees' && <EmployeesView />}
            {activeView === 'invoices' && <InvoicesView />}
            {activeView === 'reports' && <ReportsView />}
            {activeView === 'settings' && <SettingsView />}
          </main>

          {/* Bottom Industrial Status Bar */}
          <footer className="border-t border-hairline bg-panel px-4 py-2 flex items-center justify-between text-[11px] text-text-sec font-mono">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1.5 text-status-ok">
                <span className="w-1.5 h-1.5 rounded-full bg-status-ok animate-pulse" />
                EDGE CLUSTER: ONLINE (4/4 NODES)
              </span>
              <span className="text-hairline">|</span>
              <span>INFERENCE ENGINE: YOLOv8-RETAIL-PACK (FP16 @ 14ms)</span>
              <span className="text-hairline">|</span>
              <span>SQLITE ACID LOG: SYNCED</span>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => setIsSimulatorOpen(true)}
                className="hover:text-amber transition-colors flex items-center gap-1"
              >
                <Zap className="w-3 h-3 text-amber" />
                Press [S] to Simulate Scenarios
              </button>
              <span className="text-hairline">|</span>
              <span>KEYS: [1-8] NAV</span>
            </div>
          </footer>
        </div>
      </div>

      {/* Interactive Simulation Drawer */}
      <SimulatorDrawer
        isOpen={isSimulatorOpen}
        onClose={() => setIsSimulatorOpen(false)}
      />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <AppDataProvider>
        <AppContent />
      </AppDataProvider>
    </ThemeProvider>
  );
};

export default App;
