import React from 'react';
import type { ExitEvent } from '../../types';
import { MathBreakdown } from './MathBreakdown';
import { SensorMatrix } from './SensorMatrix';
import { SeverityBadge } from '../common/SeverityBadge';
import { VerdictBadge } from '../common/VerdictBadge';
import { useAppData } from '../../context/AppDataContext';
import {
  Camera,
  Lock,
  Unlock,
  FileText,
  UserCheck,
  AlertOctagon,
  Clock,
  Printer,
} from 'lucide-react';

interface EventDetailPanelProps {
  event: ExitEvent;
  onClose?: () => void;
}

export const EventDetailPanel: React.FC<EventDetailPanelProps> = ({ event, onClose }) => {
  const { employees, invoices, turnstileLocked, toggleLaneTurnstile } = useAppData();
  const employee = employees.find((e) => e.employeeId === event.employeeId);
  const invoice = invoices.find((i) => i.invoiceId === event.invoiceId);
  const isLocked = turnstileLocked[event.laneId] || false;

  const formattedDateTime = new Date(event.timestamp).toLocaleString('en-IN', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  });

  const handlePrintDossier = () => {
    window.print();
  };

  return (
    <div className="bg-panel border border-hairline rounded-sm flex flex-col h-full overflow-hidden">
      {/* Panel Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-hairline bg-panel-raised">
        <div className="flex items-center gap-2.5">
          <span className="font-mono text-xs-tech font-bold text-amber">
            {event.eventId}
          </span>
          <span className="text-hairline">|</span>
          <span className="font-mono text-xs-tech text-text-pri font-medium">{event.laneId}</span>
          <VerdictBadge verdict={event.verdict} />
          <SeverityBadge severity={event.severity} size="sm" />
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handlePrintDossier}
            className="p-1 rounded-sm text-text-sec hover:text-text-pri hover:bg-hairline/40 transition-colors"
            title="Print Incident Record"
          >
            <Printer className="w-4 h-4" />
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="text-xs-tech px-2 py-0.5 rounded-sm bg-hairline/40 text-text-sec hover:text-text-pri"
            >
              Close
            </button>
          )}
        </div>
      </div>

      {/* Panel Body */}
      <div className="p-4 space-y-4 overflow-y-auto flex-1">
        {/* Real CCTV Camera Snapshot Display */}
        <div className="relative aspect-video w-full bg-black rounded-sm border border-hairline overflow-hidden flex flex-col justify-between p-3 group">
          {/* Real Snapshot Image if available */}
          {event.snapshotUrl ? (
            <img
              src={
                event.snapshotUrl.startsWith('http')
                  ? event.snapshotUrl
                  : `http://127.0.0.1:8000${event.snapshotUrl}`
              }
              alt={`Exit Event Snapshot ${event.eventId}`}
              className="absolute inset-0 w-full h-full object-cover z-0"
              onError={(e) => {
                (e.target as HTMLElement).style.display = 'none';
              }}
            />
          ) : null}

          {/* CCTV Overlay Top Bar */}
          <div className="relative z-10 flex items-center justify-between text-[11px] font-mono text-status-ok bg-black/75 backdrop-blur-[2px] px-2.5 py-1.5 rounded-sm border border-hairline/40">
            <span className="flex items-center gap-1.5 font-bold">
              <Camera className="w-3.5 h-3.5 text-status-ok animate-pulse" />
              RECORDED FRAME // {event.laneId}
            </span>
            <span className="flex items-center gap-1 text-text-sec">
              <Clock className="w-3 h-3" />
              {formattedDateTime}
            </span>
          </div>

          {/* Middle Overlay (Carrier Biometrics & Detections) */}
          <div className="relative z-10 flex-1 flex flex-col justify-end p-2 pointer-events-none">
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-2 py-0.5 bg-black/80 border border-status-ok/60 text-status-ok font-mono text-[11px] rounded-sm font-semibold">
                DETECTED: {event.casesDetected} CASES · {event.unitsDetected} UNITS
              </span>

              {employee ? (
                <div className="flex items-center gap-1.5 bg-black/80 border border-hairline px-2 py-0.5 rounded-sm text-[11px] font-mono">
                  <UserCheck className="w-3.5 h-3.5 text-status-ok" />
                  <span className="text-text-sec">CARRIER:</span>
                  <span className="text-text-pri font-medium">{employee.name}</span>
                  <span className="text-status-ok">({employee.rfidBadgeId})</span>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 bg-black/80 border border-hairline px-2 py-0.5 rounded-sm text-[11px] font-mono text-text-sec">
                  <UserCheck className="w-3.5 h-3.5 text-text-sec" />
                  <span>CARRIER: UNVERIFIED</span>
                </div>
              )}
            </div>
          </div>

          {/* CCTV Overlay Bottom Bar */}
          <div className="relative z-10 flex items-center justify-between text-[10px] font-mono text-text-sec bg-black/75 px-2.5 py-1 rounded-sm border border-hairline/40">
            <span>VISION CONFIDENCE: 95% · 1080p</span>
            <span className="text-amber font-semibold">CONSENSUS: {event.consensusUnits} UNITS</span>
          </div>
        </div>

        {/* Section: Packaging Arithmetic Breakdown */}
        <MathBreakdown event={event} />

        {/* Section: Three-Channel Sensor Agreement */}
        <SensorMatrix event={event} />

        {/* Section: Linked Invoice & Operator Notes */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {/* Invoice Card */}
          <div className="p-3 bg-panel-raised border border-hairline rounded-sm space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs-tech font-semibold text-text-pri">
              <FileText className="w-3.5 h-3.5 text-amber" />
              OCR Document Audit
            </div>
            {invoice ? (
              <div className="text-xs-tech space-y-1">
                <div className="font-mono text-text-pri">{invoice.invoiceNumber}</div>
                <div className="text-text-sec text-[11px]">{invoice.carrierName}</div>
                <div className="flex items-center justify-between pt-1 border-t border-hairline/60 font-mono text-[11px]">
                  <span className="text-text-sec">Declared Units:</span>
                  <span className="text-text-pri font-bold">{invoice.declaredTotalUnits}</span>
                </div>
                <div className="flex items-center justify-between font-mono text-[11px]">
                  <span className="text-text-sec">OCR Confidence:</span>
                  <span className="text-status-ok font-semibold">{invoice.ocrConfidence}%</span>
                </div>
              </div>
            ) : (
              <div className="text-xs-tech text-text-sec italic py-2">
                No formal outbound manifest attached to this portal crossing.
              </div>
            )}
          </div>

          {/* Turnstile / Security Interlock Control */}
          <div className="p-3 bg-panel-raised border border-hairline rounded-sm space-y-2 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs-tech font-semibold text-text-pri flex items-center gap-1.5">
                  <AlertOctagon className="w-3.5 h-3.5 text-amber" />
                  Portal Physical Interlock
                </span>
                <span
                  className={`font-mono text-[11px] font-bold px-1.5 py-0.5 rounded ${
                    isLocked ? 'bg-status-high/20 text-status-high' : 'bg-status-ok/20 text-status-ok'
                  }`}
                >
                  {isLocked ? 'LOCKED / ENGAGED' : 'ARMED / OPEN'}
                </span>
              </div>
              <p className="text-[11px] text-text-sec mt-1">
                {isLocked
                  ? 'Physical turnstile magnetic drop-bar engaged. Operator manual release required.'
                  : 'Turnstile gate operating normally with optical cross-trip detection.'}
              </p>
            </div>

            <button
              onClick={() => toggleLaneTurnstile(event.laneId)}
              className={`flex items-center justify-center gap-2 w-full py-1.5 text-xs-tech font-semibold rounded-sm border transition-colors ${
                isLocked
                  ? 'bg-status-ok/20 hover:bg-status-ok/30 text-status-ok border-status-ok/40'
                  : 'bg-status-high/20 hover:bg-status-high/30 text-status-high border-status-high/40'
              }`}
            >
              {isLocked ? (
                <>
                  <Unlock className="w-3.5 h-3.5" />
                  Release Portal Lock
                </>
              ) : (
                <>
                  <Lock className="w-3.5 h-3.5" />
                  Emergency Lock Turnstile
                </>
              )}
            </button>
          </div>
        </div>

        {/* Operator Investigation Notes */}
        {event.notes && (
          <div className="p-3 bg-canvas border border-hairline rounded-sm">
            <span className="text-[11px] font-semibold text-text-sec uppercase tracking-wider block mb-1">
              Automated Forensic Note
            </span>
            <p className="text-xs-tech text-text-pri leading-relaxed max-w-[78ch]">{event.notes}</p>
          </div>
        )}
      </div>
    </div>
  );
};

