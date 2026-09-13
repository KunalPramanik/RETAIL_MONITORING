import React, { useState, useMemo, useEffect } from 'react';
import { useAppData } from '../context/AppDataContext';
import { EventRow } from '../components/events/EventRow';
import { EventDetailPanel } from '../components/events/EventDetailPanel';
import { Search, Download, Layers, X } from 'lucide-react';
import type { Verdict, Severity, ExitEvent, Product } from '../types';

export const EventsView: React.FC = () => {
  const {
    events,
    lanes,
    selectedEventId,
    setSelectedEventId,
    selectedEvent,
    products,
    isLoading,
    injectSimulatedScenario,
  } = useAppData();

  const [searchQuery, setSearchQuery] = useState(() => {
    return typeof window !== 'undefined' ? sessionStorage.getItem('secops_events_search') || '' : '';
  });
  const [laneFilter, setLaneFilter] = useState(() => {
    return typeof window !== 'undefined' ? sessionStorage.getItem('secops_events_lane') || 'ALL' : 'ALL';
  });
  const [verdictFilter, setVerdictFilter] = useState<'ALL' | Verdict>(() => {
    return typeof window !== 'undefined' ? (sessionStorage.getItem('secops_events_verdict') as any) || 'ALL' : 'ALL';
  });
  const [severityFilter, setSeverityFilter] = useState<'ALL' | Severity>(() => {
    return typeof window !== 'undefined' ? (sessionStorage.getItem('secops_events_severity') as any) || 'ALL' : 'ALL';
  });

  // Sync active filters to sessionStorage
  useEffect(() => {
    try {
      sessionStorage.setItem('secops_events_search', searchQuery);
      sessionStorage.setItem('secops_events_lane', laneFilter);
      sessionStorage.setItem('secops_events_verdict', verdictFilter);
      sessionStorage.setItem('secops_events_severity', severityFilter);
    } catch {
      // ignore storage quota errors
    }
  }, [searchQuery, laneFilter, verdictFilter, severityFilter]);

  // Filtered Events
  const filteredEvents = useMemo(() => {
    return events.filter((ev: ExitEvent) => {
      // Lane filter
      if (laneFilter !== 'ALL' && ev.laneId !== laneFilter) return false;
      // Verdict filter
      if (verdictFilter !== 'ALL' && ev.verdict !== verdictFilter) return false;
      // Severity filter
      if (severityFilter !== 'ALL' && ev.severity !== severityFilter) return false;
      // Search query (matches eventId, employeeId, lane, or product SKU/name)
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesEventId = ev.eventId.toLowerCase().includes(q);
        const matchesLane = ev.laneId.toLowerCase().includes(q);
        const matchesEmployee = ev.employeeId?.toLowerCase().includes(q) || false;
        const matchesProducts = ev.lineItems.some((item) => {
          const prod = products.find((p: Product) => p.productId === item.productId);
          return (
            prod?.name.toLowerCase().includes(q) ||
            prod?.skuCode.toLowerCase().includes(q) ||
            false
          );
        });
        return matchesEventId || matchesLane || matchesEmployee || matchesProducts;
      }
      return true;
    });
  }, [events, laneFilter, verdictFilter, severityFilter, searchQuery, products]);

  // Export to CSV
  const handleExportCsv = () => {
    const headers = [
      'Event ID',
      'Timestamp',
      'Lane ID',
      'Employee ID',
      'Cases Detected',
      'Consensus Units',
      'Declared Units',
      'Delta Units',
      'Verdict',
      'Severity',
      'Vision Count',
      'RFID Count',
      'Weight (kg)',
    ];

    const rows = filteredEvents.map((e: ExitEvent) => [
      e.eventId,
      e.timestamp,
      e.laneId,
      e.employeeId || 'N/A',
      e.casesDetected,
      e.consensusUnits,
      e.declaredUnits ?? 'N/A',
      e.deltaUnits ?? 0,
      e.verdict,
      e.severity,
      e.visionCount,
      e.rfidCount,
      e.weightKg,
    ]);

    const csvContent =
      'data:text/csv;charset=utf-8,' +
      [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `exit_events_audit_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="p-4 space-y-4">
      {/* Header and Search Filters */}
      <div className="p-4 bg-panel border border-hairline rounded-sm space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-base-tech font-semibold text-text-pri flex items-center gap-2">
              <Layers className="w-5 h-5 text-amber" />
              Exit Event Audit Log & Forensic Archive
            </h1>
            <p className="text-xs-tech text-text-sec mt-0.5">
              Historical ledger of all egress line crossings with sensor consensus breakdowns and video audits.
            </p>
          </div>

          <button
            onClick={handleExportCsv}
            disabled={filteredEvents.length === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-panel-raised border border-hairline hover:bg-hairline/40 rounded-sm text-xs-tech text-text-pri font-medium transition-colors disabled:opacity-40"
          >
            <Download className="w-3.5 h-3.5 text-amber" />
            Export Audit CSV
          </button>
        </div>

        {/* Filter Controls Bar */}
        <div className="flex flex-wrap items-center gap-2.5 pt-2 border-t border-hairline">
          {/* Search Input */}
          <div className="relative flex-1 min-w-[200px]">
            <Search className="w-3.5 h-3.5 text-text-sec absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search by event ID, lane, badge, or SKU..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-7 py-1.5 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri placeholder:text-text-sec/60 focus-visible:outline-2 focus-visible:outline-amber"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2 top-2 text-text-sec hover:text-text-pri"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Lane Filter */}
          <select
            value={laneFilter}
            onChange={(e) => setLaneFilter(e.target.value)}
            className="px-3 py-1.5 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
          >
            <option value="ALL">All Portals ({lanes.length} total)</option>
            {lanes.map((l) => (
              <option key={l.laneId} value={l.laneId}>
                {l.name} ({l.location})
              </option>
            ))}
          </select>

          {/* Verdict Filter */}
          <select
            value={verdictFilter}
            onChange={(e) => setVerdictFilter(e.target.value as 'ALL' | Verdict)}
            className="px-3 py-1.5 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
          >
            <option value="ALL">All Verdicts (PASS & MISMATCH)</option>
            <option value="PASS">Verdict: PASS Only</option>
            <option value="MISMATCH">Verdict: MISMATCH Only</option>
          </select>

          {/* Severity Filter */}
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value as 'ALL' | Severity)}
            className="px-3 py-1.5 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
          >
            <option value="ALL">All Severities</option>
            <option value="HIGH">HIGH Severity</option>
            <option value="MEDIUM">MEDIUM Severity</option>
            <option value="LOW">LOW Severity</option>
            <option value="NONE">NONE (Clean Pass)</option>
          </select>
        </div>
      </div>

      {/* Main Content Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Events Table Column */}
        <div className="lg:col-span-7 bg-panel border border-hairline rounded-sm overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-hairline bg-panel-raised flex items-center justify-between">
            <span className="text-xs-tech font-semibold text-text-pri">
              Filtered Events
            </span>
            <span className="font-mono text-xs-tech text-text-sec">
              Showing {filteredEvents.length} of {events.length}
            </span>
          </div>

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
                  <th className="py-2 px-2"></th>
                </tr>
              </thead>
              <tbody>
                {isLoading && events.length === 0 ? (
                  Array.from({ length: 6 }).map((_, idx) => (
                    <tr key={`skel-${idx}`} className="border-b border-hairline animate-pulse">
                      <td className="py-3 px-3"><div className="h-3 w-16 bg-hairline/60 rounded" /></td>
                      <td className="py-3 px-3"><div className="h-3 w-20 bg-hairline/60 rounded" /></td>
                      <td className="py-3 px-3"><div className="h-3 w-28 bg-hairline/60 rounded" /></td>
                      <td className="py-3 px-3 text-right"><div className="h-3 w-8 bg-hairline/60 rounded ml-auto" /></td>
                      <td className="py-3 px-3 text-right"><div className="h-3 w-10 bg-hairline/60 rounded ml-auto" /></td>
                      <td className="py-3 px-3 text-right"><div className="h-3 w-8 bg-hairline/60 rounded ml-auto" /></td>
                      <td className="py-3 px-3"><div className="h-4 w-14 bg-hairline/60 rounded" /></td>
                      <td className="py-3 px-3"><div className="h-4 w-12 bg-hairline/60 rounded" /></td>
                      <td className="py-3 px-2"></td>
                    </tr>
                  ))
                ) : filteredEvents.length > 0 ? (
                  filteredEvents.map((ev: ExitEvent) => (
                    <EventRow
                      key={ev.eventId}
                      event={ev}
                      isSelected={selectedEventId === ev.eventId}
                      onSelect={() => setSelectedEventId(ev.eventId)}
                    />
                  ))
                ) : events.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-16 text-center text-xs-tech text-text-sec">
                      <div className="flex flex-col items-center justify-center gap-2 max-w-sm mx-auto">
                        <Layers className="w-8 h-8 text-amber/60" />
                        <span className="text-text-pri font-semibold text-sm-tech">No Exit Events Logged</span>
                        <span className="text-xs-tech text-text-sec">
                          Live camera feeds and edge sensors will log exit traversals in real time. You can also inject a simulated test traversal.
                        </span>
                        <button
                          type="button"
                          onClick={() => injectSimulatedScenario('CLEAN_PASS')}
                          className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber hover:bg-amber/90 text-black text-xs-tech font-bold rounded-sm transition-colors cursor-pointer"
                        >
                          Inject Test Traversal (Clean Pass)
                        </button>
                      </div>
                    </td>
                  </tr>
                ) : (
                  <tr>
                    <td colSpan={9} className="py-12 text-center text-xs-tech text-text-sec">
                      <div className="flex flex-col items-center justify-center gap-2">
                        <span>No events matched the selected search criteria.</span>
                        <button
                          type="button"
                          onClick={() => {
                            setSearchQuery('');
                            setLaneFilter('ALL');
                            setVerdictFilter('ALL');
                            setSeverityFilter('ALL');
                          }}
                          className="px-3 py-1 bg-panel-raised hover:bg-hairline text-text-pri border border-hairline text-xs-tech rounded-sm transition-colors cursor-pointer"
                        >
                          Clear Active Filters
                        </button>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Selected Event Detail Column */}
        <div className="lg:col-span-5">
          {selectedEvent ? (
            <EventDetailPanel event={selectedEvent} />
          ) : (
            <div className="p-8 bg-panel border border-hairline rounded-sm text-center text-text-sec">
              Select an event row to inspect forensic evidence and math breakdown.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
