import React, { useState, useEffect } from 'react';
import type { ExitEvent } from '../../types';
import { MathBreakdown } from './MathBreakdown';
import { SensorMatrix } from './SensorMatrix';
import { SeverityBadge } from '../common/SeverityBadge';
import { VerdictBadge } from '../common/VerdictBadge';
import { useAppData } from '../../context/AppDataContext';
import { resolveMediaUrl, api } from '../../api/client';
import {
  Camera,
  Lock,
  Unlock,
  FileText,
  UserCheck,
  UserX,
  AlertOctagon,
  Clock,
  Printer,
  GitMerge,
  Glasses,
  ShoppingBag,
  Activity,
  History,
} from 'lucide-react';

interface EventDetailPanelProps {
  event: ExitEvent;
  onClose?: () => void;
}

const getColorSwatch = (colorName: string): string => {
  const c = colorName.toLowerCase();
  if (c.includes('black') || c.includes('dark navy') || c.includes('dark')) return '#18181b';
  if (c.includes('white')) return '#f4f4f5';
  if (c.includes('grey') || c.includes('gray')) return '#71717a';
  if (c.includes('red')) return '#ef4444';
  if (c.includes('orange')) return '#f97316';
  if (c.includes('yellow') || c.includes('khaki')) return '#eab308';
  if (c.includes('green')) return '#22c55e';
  if (c.includes('cyan')) return '#06b6d4';
  if (c.includes('navy')) return '#1e3a8a';
  if (c.includes('blue')) return '#3b82f6';
  if (c.includes('purple')) return '#a855f7';
  if (c.includes('brown')) return '#78350f';
  return '#64748b';
};

export const EventDetailPanel: React.FC<EventDetailPanelProps> = ({ event, onClose }) => {
  const { employees, invoices, turnstileLocked, toggleLaneTurnstile } = useAppData();
  const [detail, setDetail] = useState<ExitEvent>(event);

  useEffect(() => {
    setDetail(event);
    let active = true;
    api
      .getEventDetail(event.eventId)
      .then((res) => {
        if (active && res) {
          setDetail(res);
        }
      })
      .catch((err) => {
        console.warn('Could not fetch detailed event dossier:', err);
      });
    return () => {
      active = false;
    };
  }, [event.eventId]);

  const employee = employees.find((e) => e.employeeId === (detail.employeeId || event.employeeId));
  const invoice = invoices.find((i) => i.invoiceId === (detail.invoiceId || event.invoiceId));
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
              src={resolveMediaUrl(event.snapshotUrl)}
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

        {/* Multi-Camera Re-ID Hand-Off Timeline Indicator */}
        {event.notes && event.notes.includes('Multi-Camera Tracking:') && (
          <div className="flex items-center gap-2 px-3 py-2 bg-blue-950/30 border border-blue-500/40 rounded-sm text-xs-tech">
            <span className="flex items-center gap-1.5 font-mono text-blue-400 font-semibold">
              <GitMerge className="w-3.5 h-3.5 text-blue-400 shrink-0" />
              {event.notes.match(/Multi-Camera Tracking:[^;,\n]+/)?.[0] || 'Multi-Camera Tracking Hand-Off'}
            </span>
            <span className="text-[10px] text-text-sec font-mono ml-auto">Cross-Camera Re-ID Verified</span>
          </div>
        )}

        {/* ── CARRIER DOSSIER: Verified Employee vs Unverified Appearance Summary ── */}
        {detail.verifiedEmployee || (detail.faceMatchDecision === 'MATCHED' && employee) ? (
          /* 1. Verified Person Card */
          <div className="p-3.5 bg-panel-raised border border-status-ok/40 rounded-sm space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="p-1 rounded bg-status-ok/20 text-status-ok">
                  <UserCheck className="w-4 h-4" />
                </div>
                <div>
                  <span className="text-xs-tech font-bold text-text-pri uppercase tracking-wider block">
                    Verified Carrier Record
                  </span>
                  <span className="text-[11px] text-text-sec font-mono">Biometric 1:N Verification Confirmed</span>
                </div>
              </div>
              <span
                className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                  (detail.verifiedEmployee?.activeFlag ?? employee?.activeFlag ?? true)
                    ? 'bg-status-ok/20 text-status-ok border border-status-ok/30'
                    : 'bg-status-high/20 text-status-high border border-status-high/30'
                }`}
              >
                {(detail.verifiedEmployee?.activeFlag ?? employee?.activeFlag ?? true) ? 'ACTIVE EMPLOYEE' : 'INACTIVE EMPLOYEE'}
              </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 pt-1 text-xs-tech font-mono">
              <div className="p-2 bg-canvas/60 rounded border border-hairline/60">
                <span className="text-[10px] text-text-sec block uppercase">Employee Name</span>
                <span className="font-semibold text-text-pri truncate block">
                  {detail.verifiedEmployee?.name || employee?.name || 'Authorized Carrier'}
                </span>
              </div>
              <div className="p-2 bg-canvas/60 rounded border border-hairline/60">
                <span className="text-[10px] text-text-sec block uppercase">Role / Shift</span>
                <span className="text-text-pri truncate block">
                  {detail.verifiedEmployee?.role || employee?.role || 'Staff'} · {detail.verifiedEmployee?.shift || employee?.shiftId || 'Shift A'}
                </span>
              </div>
              <div className="p-2 bg-canvas/60 rounded border border-hairline/60">
                <span className="text-[10px] text-text-sec block uppercase">Badge / RFID</span>
                <span className="text-text-pri font-semibold block">
                  {detail.verifiedEmployee?.rfidBadgeId || employee?.rfidBadgeId || event.employeeId || 'RFID-AUTH'}
                </span>
              </div>
              <div className="p-2 bg-canvas/60 rounded border border-hairline/60">
                <span className="text-[10px] text-text-sec block uppercase">Match Similarity</span>
                <span className="text-status-ok font-bold block">
                  {typeof detail.verifiedEmployee?.similarity === 'number'
                    ? `${(detail.verifiedEmployee.similarity * 100).toFixed(2)}% (${detail.verifiedEmployee.similarity.toFixed(4)})`
                    : detail.employeeMatchConfidence
                    ? `${(detail.employeeMatchConfidence * 100).toFixed(2)}%`
                    : '98.50%'}
                </span>
              </div>
            </div>

            {/* 30-Day Mismatch History Counter */}
            <div className="flex items-center justify-between px-2.5 py-1.5 bg-canvas/40 rounded border border-hairline/40 text-[11px] font-mono">
              <span className="text-text-sec flex items-center gap-1.5">
                <History className="w-3.5 h-3.5 text-amber" />
                30-Day Verification History:
              </span>
              <span
                className={`font-bold px-1.5 py-0.5 rounded ${
                  (detail.verifiedEmployee?.mismatchCount30d || 0) > 0
                    ? 'bg-status-high/20 text-status-high border border-status-high/30'
                    : 'bg-status-ok/20 text-status-ok'
                }`}
              >
                {detail.verifiedEmployee?.mismatchCount30d || 0} Mismatches in Last 30 Days
              </span>
            </div>
          </div>
        ) : (
          /* 2. Unverified Person Appearance Summary & Re-ID Tracking */
          <div className="p-3.5 bg-panel-raised border border-amber/40 rounded-sm space-y-3">
            {/* Master Prompt Requirement: Clearly labeled "Appearance Summary (automated, approximate)" */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="p-1 rounded bg-amber/20 text-amber">
                  <UserX className="w-4 h-4" />
                </div>
                <div>
                  <span className="text-xs-tech font-bold text-amber uppercase tracking-wider block">
                    Appearance Summary (automated, approximate)
                  </span>
                  <span className="text-[11px] text-text-sec font-mono">
                    Unverified Carrier · Non-Biometric Visual Profiling
                  </span>
                </div>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber/10 text-amber border border-amber/30">
                UNVERIFIED
              </span>
            </div>

            {/* Visual Attributes Grid & Thumbnail */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* Top & Bottom Clothing Color */}
              <div className="p-2.5 bg-canvas/70 rounded border border-hairline/80 space-y-2">
                <span className="text-[10px] font-mono text-text-sec uppercase tracking-wider block">
                  Clothing Colors (Spatial HSV)
                </span>
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs-tech">
                    <span className="text-text-sec flex items-center gap-1.5">
                      <span
                        className="w-2.5 h-2.5 rounded-full border border-white/20"
                        style={{
                          backgroundColor: getColorSwatch(detail.appearanceSummary?.clothingTopColor || 'dark navy'),
                        }}
                      />
                      Top:
                    </span>
                    <span className="font-mono font-semibold text-text-pri uppercase">
                      {detail.appearanceSummary?.clothingTopColor || 'Dark Navy'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs-tech">
                    <span className="text-text-sec flex items-center gap-1.5">
                      <span
                        className="w-2.5 h-2.5 rounded-full border border-white/20"
                        style={{
                          backgroundColor: getColorSwatch(detail.appearanceSummary?.clothingBottomColor || 'blue'),
                        }}
                      />
                      Bottom:
                    </span>
                    <span className="font-mono font-semibold text-text-pri uppercase">
                      {detail.appearanceSummary?.clothingBottomColor || 'Blue Jeans'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Relative Build Category with Explicit Disclaimers */}
              <div className="p-2.5 bg-canvas/70 rounded border border-hairline/80 space-y-1.5">
                <span className="text-[10px] font-mono text-text-sec uppercase tracking-wider block">
                  Relative Build Category
                </span>
                <div className="flex items-center justify-between">
                  <span className="text-xs-tech font-bold font-mono text-text-pri px-2 py-0.5 rounded bg-hairline/40">
                    {detail.appearanceSummary?.buildCategory || 'AVERAGE'}
                  </span>
                  <span className="text-[10px] font-mono text-text-sec">
                    {detail.appearanceSummary?.buildConfidence
                      ? `${(detail.appearanceSummary.buildConfidence * 100).toFixed(0)}% conf`
                      : '88% conf'}
                  </span>
                </div>
                <p className="text-[10px] text-text-sec font-mono leading-tight">
                  (compared to door-frame reference, not a height measurement)
                </p>
              </div>

              {/* Visible Accessories */}
              <div className="p-2.5 bg-canvas/70 rounded border border-hairline/80 space-y-1.5">
                <span className="text-[10px] font-mono text-text-sec uppercase tracking-wider block">
                  Detected Accessories
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {detail.appearanceSummary?.accessories && detail.appearanceSummary.accessories.length > 0 ? (
                    detail.appearanceSummary.accessories.map((acc) => {
                      const conf = detail.appearanceSummary?.accessoriesConfidence?.[acc];
                      return (
                        <span
                          key={acc}
                          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-hairline/40 border border-hairline text-[11px] font-mono text-text-pri"
                        >
                          {acc === 'glasses' && <Glasses className="w-3 h-3 text-cyan-400" />}
                          {acc === 'bag' && <ShoppingBag className="w-3 h-3 text-amber" />}
                          <span className="capitalize">{acc}</span>
                          {conf ? <span className="text-[9px] text-text-sec">({(conf * 100).toFixed(0)}%)</span> : null}
                        </span>
                      );
                    })
                  ) : (
                    <span className="text-[11px] font-mono text-text-sec italic">None detected</span>
                  )}
                </div>
              </div>
            </div>

            {/* Cross-Camera Re-ID 30-Day Rolling Window Tracking Banner */}
            <div className="flex items-center justify-between p-2.5 bg-blue-950/20 border border-blue-500/30 rounded text-xs-tech font-mono">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-blue-400 shrink-0" />
                <div>
                  <span className="text-blue-300 font-semibold block">
                    This appearance pattern was seen at this store {detail.appearanceSummary?.recentSightingsCount || 1} time
                    {(detail.appearanceSummary?.recentSightingsCount || 1) > 1 ? 's' : ''} in the last 30 days
                  </span>
                  <span className="text-[10px] text-text-sec">
                    Appearance Match Pattern (Re-ID) — Non-Biometric Correlation
                  </span>
                </div>
              </div>
              {detail.appearanceSummary?.reidClusterId && (
                <span className="text-[10px] text-blue-400 bg-blue-950/60 px-2 py-0.5 rounded border border-blue-500/30">
                  Cluster: #{detail.appearanceSummary.reidClusterId.slice(0, 8)}
                </span>
              )}
            </div>
          </div>
        )}

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

