import React from 'react';
import type { ExitEvent } from '../../types';
import { SeverityBadge } from '../common/SeverityBadge';
import { VerdictBadge } from '../common/VerdictBadge';
import { ChevronRight } from 'lucide-react';
import { useAppData } from '../../context/AppDataContext';

interface EventRowProps {
  event: ExitEvent;
  isSelected?: boolean;
  onSelect?: () => void;
}

export const EventRow: React.FC<EventRowProps> = ({ event, isSelected, onSelect }) => {
  const { employees } = useAppData();
  const employee = employees.find((e) => e.employeeId === event.employeeId);

  // Border severity class
  const borderSeverityClass = {
    NONE: 'border-l-sev-ok',
    LOW: 'border-l-sev-low',
    MEDIUM: 'border-l-sev-med',
    HIGH: 'border-l-sev-high',
  }[event.severity];

  const timeFormatted = new Date(event.timestamp).toLocaleTimeString('en-IN', {
    hour12: true,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  return (
    <tr
      tabIndex={0}
      role="button"
      aria-label={`Exit Event ${event.eventId} on lane ${event.laneId} with verdict ${event.verdict}`}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect?.();
        }
      }}
      className={`group cursor-pointer transition-colors border-b border-hairline/60 focus:outline-none focus-visible:ring-1 focus-visible:ring-amber ${borderSeverityClass} ${
        isSelected ? 'bg-panel-raised font-medium' : 'hover:bg-panel-raised/50 bg-panel'
      }`}
    >
      {/* Time */}
      <td className="py-2.5 px-3 font-mono text-xs-tech text-text-sec whitespace-nowrap">
        {timeFormatted}
      </td>

      {/* Lane */}
      <td className="py-2.5 px-3 font-mono text-xs-tech text-text-pri font-medium whitespace-nowrap">
        {event.laneId}
      </td>

      {/* Employee */}
      <td className="py-2.5 px-3 text-xs-tech text-text-sec whitespace-nowrap">
        {employee ? (
          <span className="flex items-center gap-1.5">
            <span className="text-text-pri">{employee.name}</span>
            {employee.mismatchCount30d >= 3 && (
              <span className="px-1 py-0.2 rounded text-[10px] font-mono bg-status-high/20 text-status-high font-bold" title="Repeat mismatch history (>=3 in 30d)">
                FLAG
              </span>
            )}
          </span>
        ) : (
          <span className="text-text-sec italic">Unassigned</span>
        )}
      </td>

      {/* Cases */}
      <td className="py-2.5 px-3 font-mono text-xs-tech text-right text-text-pri whitespace-nowrap">
        {event.casesDetected} <span className="text-[11px] text-text-sec">cs</span>
      </td>

      {/* Units */}
      <td className="py-2.5 px-3 font-mono text-xs-tech text-right text-mono-val font-semibold whitespace-nowrap">
        {event.consensusUnits} <span className="text-[11px] text-text-sec font-normal">ea</span>
      </td>

      {/* Delta */}
      <td className="py-2.5 px-3 font-mono text-xs-tech text-right whitespace-nowrap">
        {event.deltaUnits !== undefined ? (
          event.deltaUnits === 0 ? (
            <span className="text-text-sec">0</span>
          ) : (
            <span className={`font-bold ${event.deltaUnits > 4 ? 'text-status-high' : 'text-status-med'}`}>
              +{event.deltaUnits}
            </span>
          )
        ) : (
          <span className="text-text-sec">-</span>
        )}
      </td>

      {/* Verdict */}
      <td className="py-2.5 px-3 whitespace-nowrap">
        <VerdictBadge verdict={event.verdict} />
      </td>

      {/* Severity */}
      <td className="py-2.5 px-3 whitespace-nowrap">
        <SeverityBadge severity={event.severity} size="sm" />
      </td>

      {/* Action / Arrow */}
      <td className="py-2.5 px-2 text-right whitespace-nowrap">
        <ChevronRight
          className={`w-4 h-4 transition-transform ${
            isSelected ? 'text-amber translate-x-0.5' : 'text-text-sec/40 group-hover:text-text-sec'
          }`}
        />
      </td>
    </tr>
  );
};

