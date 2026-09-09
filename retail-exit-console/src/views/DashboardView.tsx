import React, { useState } from 'react';
import { useAppData } from '../context/AppDataContext';
import { EventRow } from '../components/events/EventRow';
import { AlertCard } from '../components/alerts/AlertCard';
import { EventDetailPanel } from '../components/events/EventDetailPanel';
import { ResolveAlertModal } from '../components/alerts/ResolveAlertModal';
import { LiveCameraFeedTile } from '../components/cameras/LiveCameraFeedTile';
import type { Alert, ExitEvent } from '../types';
import { Filter, Layers, AlertOctagon, Radio } from 'lucide-react';

export const DashboardView: React.FC = () => {
  const { events, alerts, lanes, cameras, selectedEventId, setSelectedEventId, selectedEvent, refreshAllData } = useAppData();
  const [resolvingAlert, setResolvingAlert] = useState<Alert | null>(null);
  const [laneFilter, setLaneFilter] = useState<string>('ALL');

  // Filter events by lane if selected
  const filteredEvents = events.filter((ev: ExitEvent) => {
    if (laneFilter === 'ALL') return true;
    return ev.laneId === laneFilter;
  });

  // Sort alerts: HIGH severity sticky on top, then MEDIUM, then LOW, then by creation date
  const sortedAlerts = [...alerts]
    .filter((a: Alert) => a.status === 'OPEN' || a.status === 'ACKNOWLEDGED')
    .sort((a: Alert, b: Alert) => {
      const severityRank: Record<string, number> = { HIGH: 3, MEDIUM: 2, LOW: 1, NONE: 0 };
      const rankDiff = (severityRank[b.severity] || 0) - (severityRank[a.severity] || 0);
      if (rankDiff !== 0) return rankDiff;
      return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
    });

  return (
    <div className="p-4 space-y-4">
      {/* Zero Lanes Banner per Part I */}
      {lanes.length === 0 && (
        <div className="flex items-center justify-between p-3.5 bg-panel-raised border-l-4 border-amber border-hairline rounded-sm">
          <div className="flex items-center gap-2.5">
            <Radio className="w-4 h-4 text-amber animate-pulse" />
            <span className="text-xs-tech text-text-pri font-medium">
              No exit lanes configured. Add your first camera in Settings to begin monitoring.
            </span>
          </div>
          <span className="text-[11px] text-text-sec font-mono">STANDBY MODE</span>
        </div>
      )}

      {/* Live Surveillance Portal Streams & Optical Inspection */}
      <LiveCameraFeedTile
        cameras={cameras}
        lanes={lanes}
        onScanSuccess={refreshAllData}
      />

      {/* Upper Section: 2 Columns (Exit Stream & Active Alerts) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column (7 cols): Exit Event Stream */}
        <div className="lg:col-span-7 flex flex-col bg-panel border border-hairline rounded-sm overflow-hidden min-h-[480px]">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-hairline bg-panel-raised">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-amber" />
              <h2 className="text-xs-tech font-semibold text-text-pri">
                Live Exit Event Stream
              </h2>
              <span className="font-mono text-[11px] text-text-sec">
                ({filteredEvents.length} events logged)
              </span>
            </div>

            {/* Lane Filter dropdown */}
            <div className="flex items-center gap-2">
              <Filter className="w-3.5 h-3.5 text-text-sec" />
              <select
                value={laneFilter}
                onChange={(e) => setLaneFilter(e.target.value)}
                className="px-2 py-1 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
              >
                <option value="ALL">All Exit Portals ({lanes.length} total)</option>
                {lanes.map((l) => (
                  <option key={l.laneId} value={l.laneId}>
                    {l.name} ({l.location})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Event Stream Table */}
          <div className="overflow-x-auto flex-1">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-hairline bg-canvas/60 text-xs-tech text-text-sec font-normal">
                  <th className="py-2 px-3 font-normal">Time</th>
                  <th className="py-2 px-3 font-normal">Portal</th>
                  <th className="py-2 px-3 font-normal">Carrier</th>
                  <th className="py-2 px-3 font-normal text-right">Cases</th>
                  <th className="py-2 px-3 font-normal text-right">Units</th>
                  <th className="py-2 px-3 font-normal text-right">Δ Delta</th>
                  <th className="py-2 px-3 font-normal">Verdict</th>
                  <th className="py-2 px-3 font-normal">Severity</th>
                  <th className="py-2 px-2 text-right"></th>
                </tr>
              </thead>
              <tbody>
                {filteredEvents.length > 0 ? (
                  filteredEvents.map((ev: ExitEvent) => (
                    <EventRow
                      key={ev.eventId}
                      event={ev}
                      isSelected={selectedEventId === ev.eventId}
                      onSelect={() => setSelectedEventId(ev.eventId)}
                    />
                  ))
                ) : (
                  <tr>
                    <td colSpan={9} className="py-16 text-center text-xs-tech text-text-sec">
                      <div className="flex flex-col items-center justify-center gap-1.5">
                        <Layers className="w-6 h-6 text-hairline" />
                        <span className="text-text-pri font-medium">No exit events recorded</span>
                        <span className="text-[11px]">Active camera feeds and edge sensors will populate traversal events in real time.</span>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column (5 cols): Active Alerts Panel */}
        <div className="lg:col-span-5 flex flex-col bg-panel border border-hairline rounded-sm overflow-hidden min-h-[480px]">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-hairline bg-panel-raised">
            <div className="flex items-center gap-2">
              <AlertOctagon className="w-4 h-4 text-status-high" />
              <h2 className="text-xs-tech font-semibold text-text-pri">
                Active Incident Alerts
              </h2>
            </div>
            <div className="flex items-center gap-2">
              <span className="px-1.5 py-0.5 rounded text-[11px] font-mono bg-status-high/15 text-status-high font-semibold border border-status-high/30">
                {sortedAlerts.length} OPEN
              </span>
            </div>
          </div>

          {/* Alerts List */}
          <div className="p-3 space-y-2.5 overflow-y-auto flex-1 max-h-[580px]">
            {sortedAlerts.length > 0 ? (
              sortedAlerts.map((alt: Alert) => (
                <AlertCard
                  key={alt.alertId}
                  alert={alt}
                  onResolve={(a: Alert) => setResolvingAlert(a)}
                />
              ))
            ) : (
              <div className="flex flex-col items-center justify-center py-20 text-center text-text-sec">
                <Radio className="w-8 h-8 text-status-ok mb-2" />
                <span className="text-xs-tech font-medium text-text-pri">All Exit Lanes Nominal</span>
                <span className="text-[11px] mt-0.5">No open discrepancies requiring supervisor intervention.</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Lower Section: Selected Event Detail Inspector */}
      {selectedEvent ? (
        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-xs-tech font-semibold text-text-sec uppercase tracking-wider">
              Selected Exit Telemetry & Forensic Math
            </h3>
            <span className="font-mono text-xs-tech text-amber font-semibold">
              EVENT: {selectedEvent.eventId}
            </span>
          </div>
          <EventDetailPanel event={selectedEvent} />
        </div>
      ) : (
        <div className="p-6 bg-panel border border-hairline rounded-sm text-center text-xs-tech text-text-sec">
          No exit event selected. Traversal telemetry, camera snapshots, and case-to-unit math breakdowns will appear here.
        </div>
      )}

      {/* Resolution Modal */}
      <ResolveAlertModal
        alert={resolvingAlert}
        isOpen={!!resolvingAlert}
        onClose={() => setResolvingAlert(null)}
      />
    </div>
  );
};

