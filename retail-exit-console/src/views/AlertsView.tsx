import React, { useState } from 'react';
import { useAppData } from '../context/AppDataContext';
import { AlertCard } from '../components/alerts/AlertCard';
import { ResolveAlertModal } from '../components/alerts/ResolveAlertModal';
import type { Alert, Severity } from '../types';
import { AlertOctagon, CheckCircle2, Filter } from 'lucide-react';
import { ExportDropdown } from '../components/common/ExportDropdown';

export const AlertsView: React.FC = () => {
  const { alerts, selectedEvent } = useAppData();
  const [resolvingAlert, setResolvingAlert] = useState<Alert | null>(null);
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED'>('ALL');
  const [severityFilter, setSeverityFilter] = useState<'ALL' | Severity>('ALL');

  // Filter alerts
  const filteredAlerts = alerts.filter((a: Alert) => {
    if (statusFilter !== 'ALL' && a.status !== statusFilter) return false;
    if (severityFilter !== 'ALL' && a.severity !== severityFilter) return false;
    return true;
  });

  // Group alerts by severity
  const highAlerts = filteredAlerts.filter((a: Alert) => a.severity === 'HIGH');
  const mediumAlerts = filteredAlerts.filter((a: Alert) => a.severity === 'MEDIUM');
  const lowAlerts = filteredAlerts.filter((a: Alert) => a.severity === 'LOW');
  const resolvedAlerts = filteredAlerts.filter((a: Alert) => a.status === 'RESOLVED');

  return (
    <div className="p-4 space-y-4">
      {/* Header and Filter Controls */}
      <div className="p-4 bg-panel border border-hairline rounded-sm space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-base-tech font-semibold text-text-pri flex items-center gap-2">
              <AlertOctagon className="w-5 h-5 text-status-high" />
              Loss Prevention Incident & Alarm Queue
            </h1>
            <p className="text-xs-tech text-text-sec mt-0.5">
              Live alert dispatch matrix. High-severity alerts demand supervisor review and mandatory resolution signatures.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="font-mono text-xs-tech text-status-high px-2 py-1 bg-red-950/30 border border-status-high/40 rounded-sm font-semibold">
              {highAlerts.filter((a: Alert) => a.status !== 'RESOLVED').length} Active High
            </span>
            <span className="font-mono text-xs-tech text-amber px-2 py-1 bg-yellow-950/30 border border-status-low/40 rounded-sm font-semibold">
              {mediumAlerts.filter((a: Alert) => a.status !== 'RESOLVED').length + lowAlerts.filter((a: Alert) => a.status !== 'RESOLVED').length} Active Med/Low
            </span>
            <ExportDropdown dataset="alerts" severity={severityFilter} />
          </div>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-hairline">
          <div className="flex items-center gap-1.5 text-xs-tech text-text-sec">
            <Filter className="w-3.5 h-3.5" />
            <span>Filter Status:</span>
          </div>

          <div className="flex items-center gap-1 bg-canvas p-0.5 border border-hairline rounded-sm">
            {(['ALL', 'OPEN', 'ACKNOWLEDGED', 'RESOLVED'] as const).map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-2.5 py-1 text-xs-tech font-medium rounded-sm transition-colors ${
                  statusFilter === st
                    ? 'bg-panel-raised text-text-pri font-semibold border border-hairline'
                    : 'text-text-sec hover:text-text-pri'
                }`}
              >
                {st}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <span className="text-xs-tech text-text-sec">Severity:</span>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value as 'ALL' | Severity)}
              className="px-2.5 py-1 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
            >
              <option value="ALL">All Severities</option>
              <option value="HIGH">High Severity</option>
              <option value="MEDIUM">Medium Severity</option>
              <option value="LOW">Low Severity</option>
            </select>
          </div>
        </div>
      </div>

      {/* Grouped Alert Columns / Sections */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Section 1: HIGH Severity Alarms */}
        <div className="bg-panel border border-status-high/30 rounded-sm overflow-hidden flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 bg-red-950/20 border-b border-status-high/30">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-status-high animate-pulse" />
              <h2 className="text-xs-tech font-bold text-status-high tracking-tight">
                HIGH SEVERITY ALARMS
              </h2>
            </div>
            <span className="font-mono text-xs-tech font-bold text-status-high">
              {highAlerts.length}
            </span>
          </div>

          <div className="p-3 space-y-2.5 overflow-y-auto max-h-[600px] flex-1">
            {highAlerts.length > 0 ? (
              highAlerts.map((alert: Alert) => (
                <AlertCard
                  key={alert.alertId}
                  alert={alert}
                  isSelected={selectedEvent?.eventId === alert.eventId}
                  onResolve={(a: Alert) => setResolvingAlert(a)}
                />
              ))
            ) : (
              <div className="py-12 text-center text-xs-tech text-text-sec">
                No active High severity alarms.
              </div>
            )}
          </div>
        </div>

        {/* Section 2: MEDIUM Severity Alerts */}
        <div className="bg-panel border border-status-med/30 rounded-sm overflow-hidden flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 bg-orange-950/20 border-b border-status-med/30">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-status-med" />
              <h2 className="text-xs-tech font-bold text-status-med tracking-tight">
                MEDIUM SEVERITY DISCREPANCIES
              </h2>
            </div>
            <span className="font-mono text-xs-tech font-bold text-status-med">
              {mediumAlerts.length}
            </span>
          </div>

          <div className="p-3 space-y-2.5 overflow-y-auto max-h-[600px] flex-1">
            {mediumAlerts.length > 0 ? (
              mediumAlerts.map((alert: Alert) => (
                <AlertCard
                  key={alert.alertId}
                  alert={alert}
                  isSelected={selectedEvent?.eventId === alert.eventId}
                  onResolve={(a: Alert) => setResolvingAlert(a)}
                />
              ))
            ) : (
              <div className="py-12 text-center text-xs-tech text-text-sec">
                No active Medium severity alerts.
              </div>
            )}
          </div>
        </div>

        {/* Section 3: LOW Severity / Informational */}
        <div className="bg-panel border border-hairline rounded-sm overflow-hidden flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 bg-panel-raised border-b border-hairline">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-status-low" />
              <h2 className="text-xs-tech font-bold text-status-low tracking-tight">
                LOW SEVERITY / SENSOR NOISE
              </h2>
            </div>
            <span className="font-mono text-xs-tech font-bold text-status-low">
              {lowAlerts.length}
            </span>
          </div>

          <div className="p-3 space-y-2.5 overflow-y-auto max-h-[600px] flex-1">
            {lowAlerts.length > 0 ? (
              lowAlerts.map((alert: Alert) => (
                <AlertCard
                  key={alert.alertId}
                  alert={alert}
                  isSelected={selectedEvent?.eventId === alert.eventId}
                  onResolve={(a: Alert) => setResolvingAlert(a)}
                />
              ))
            ) : (
              <div className="py-12 text-center text-xs-tech text-text-sec">
                No active Low severity notices.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Section 4: Closed / Resolved Incident Audit Trail */}
      <div className="bg-panel border border-hairline rounded-sm overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-hairline bg-panel-raised">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-status-ok" />
            <h3 className="text-xs-tech font-semibold text-text-pri">
              Resolved Incident Audit Ledger ({resolvedAlerts.length} closed)
            </h3>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-hairline bg-canvas/60 text-xs-tech text-text-sec font-normal">
                <th className="py-2 px-3 font-normal">Alert ID</th>
                <th className="py-2 px-3 font-normal">Type</th>
                <th className="py-2 px-3 font-normal">Linked Event</th>
                <th className="py-2 px-3 font-normal">Severity</th>
                <th className="py-2 px-3 font-normal">Resolved By</th>
                <th className="py-2 px-3 font-normal">Investigation / Disposition Notes</th>
              </tr>
            </thead>
            <tbody>
              {resolvedAlerts.length > 0 ? (
                resolvedAlerts.map((ra: Alert) => (
                  <tr key={ra.alertId} className="border-b border-hairline/50 hover:bg-panel-raised/40 text-xs-tech font-mono">
                    <td className="py-2.5 px-3 font-bold text-text-pri">{ra.alertId}</td>
                    <td className="py-2.5 px-3 text-text-sec">{ra.alertType}</td>
                    <td className="py-2.5 px-3 text-amber font-semibold">{ra.eventId}</td>
                    <td className="py-2.5 px-3 font-sans">
                      <span className="px-1.5 py-0.5 rounded text-[11px] bg-hairline/40 text-text-sec">
                        {ra.severity}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-sans text-text-pri font-medium">
                      {ra.resolvedBy || 'Supervisor'}
                    </td>
                    <td className="py-2.5 px-3 font-sans text-text-sec text-[12px] max-w-[450px] truncate" title={ra.resolutionNote}>
                      {ra.resolutionNote || 'Resolved with standard signoff.'}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-xs-tech text-text-sec">
                    No resolved incidents logged yet today.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Resolution Modal */}
      <ResolveAlertModal
        alert={resolvingAlert}
        isOpen={!!resolvingAlert}
        onClose={() => setResolvingAlert(null)}
      />
    </div>
  );
};

