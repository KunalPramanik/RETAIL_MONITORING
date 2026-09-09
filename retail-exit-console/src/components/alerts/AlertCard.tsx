import React from 'react';
import type { Alert } from '../../types';
import { SeverityBadge } from '../common/SeverityBadge';
import { useAppData } from '../../context/AppDataContext';
import { Check, User, Clock, ShieldAlert, Camera } from 'lucide-react';

interface AlertCardProps {
  alert: Alert;
  onResolve: (alert: Alert) => void;
  isSelected?: boolean;
}

export const AlertCard: React.FC<AlertCardProps> = ({ alert, onResolve, isSelected }) => {
  const { events, employees, cameras, acknowledgeAlert, setSelectedEventId, latestHighAlertId } = useAppData();

  const linkedEvent = events.find((e) => e.eventId === alert.eventId);
  const linkedCamera = cameras.find((c) => c.cameraId === alert.cameraId);
  const employee = employees.find((e) => e.employeeId === linkedEvent?.employeeId);

  const isNewlyArrivedHigh = alert.severity === 'HIGH' && alert.alertId === latestHighAlertId;

  // Border severity class
  const borderSeverityClass = {
    HIGH: 'border-l-sev-high',
    MEDIUM: 'border-l-sev-med',
    LOW: 'border-l-sev-low',
    NONE: 'border-l-sev-ok',
  }[alert.severity];

  const timeAgo = (isoString: string) => {
    const diffSec = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
    if (diffSec < 60) return `${diffSec}s ago`;
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    return `${Math.floor(diffSec / 3600)}h ago`;
  };

  const causeDescriptions: Record<string, string> = {
    OVER_CARRY: `Exceeded invoice declaration by +${alert.deltaUnits} units.`,
    UNDER_DECLARE: `Carrier declared fewer units than multi-sensor consensus count.`,
    SENSOR_DISAGREEMENT: `RFID gate attenuated vs camera/scale multi-modal reading.`,
    UNAUTHORIZED_ACCESS: `Turnstile unbadged push-through detected without RFID trigger.`,
    INTRUSION: `Directional outflow detected opposite permitted flow vector.`,
    CAMERA_OFFLINE: `Surveillance camera stream timeout: heartbeat missed for > 60s (${linkedCamera?.label || alert.cameraId || 'Camera'}).`,
  };

  const cause = causeDescriptions[alert.alertType] || 'Exit threshold anomaly detected.';

  return (
    <div
      onClick={() => alert.eventId && setSelectedEventId(alert.eventId)}
      className={`relative p-3.5 bg-panel border border-hairline rounded-sm transition-all cursor-pointer ${borderSeverityClass} ${
        isSelected ? 'bg-panel-raised ring-1 ring-amber/50' : 'hover:bg-panel-raised/50'
      } ${isNewlyArrivedHigh ? 'animate-alarm-pulse' : ''}`}
    >
      {/* Top Meta Line */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <SeverityBadge severity={alert.severity} size="sm" />
          <span className="font-mono text-xs-tech font-bold text-text-pri">
            {alert.alertId}
          </span>
          <span className="font-mono text-xs-tech text-text-sec">
            // {linkedEvent?.laneId || linkedCamera?.laneId || (alert.cameraId ? `CAM:${alert.cameraId}` : 'LANE-XX')}
          </span>
        </div>

        <div className="flex items-center gap-1 font-mono text-[11px] text-text-sec">
          <Clock className="w-3 h-3" />
          {timeAgo(alert.createdAt)}
        </div>
      </div>

      {/* Cause description */}
      <div className="mt-2 text-xs-tech text-text-pri font-normal leading-snug">
        {cause}
      </div>

      {/* Employee / Camera / Delta Details */}
      <div className="mt-2.5 pt-2 border-t border-hairline/60 flex items-center justify-between text-xs-tech">
        {alert.alertType === 'CAMERA_OFFLINE' ? (
          <div className="flex items-center gap-1.5 text-status-high">
            <Camera className="w-3.5 h-3.5 text-status-high" />
            <span className="font-mono text-[11px] font-bold">
              {linkedCamera?.label || alert.cameraId || 'Optical Sensor'} (OFFLINE)
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 text-text-sec">
            <User className="w-3.5 h-3.5 text-text-sec" />
            {employee ? (
              <span className="text-text-pri font-medium">
                {employee.name}{' '}
                {employee.mismatchCount30d >= 3 && (
                  <span className="text-status-high font-mono text-[10px] ml-1">
                    ({employee.mismatchCount30d} mismatches)
                  </span>
                )}
              </span>
            ) : (
              <span className="italic text-text-sec">Unassigned Porter</span>
            )}
          </div>
        )}

        {alert.deltaUnits > 0 && (
          <div className="font-mono font-bold text-status-high">
            Δ +{alert.deltaUnits} EA
          </div>
        )}
      </div>

      {/* Status & Action Buttons */}
      <div className="mt-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 font-mono text-[11px]">
          <span className="text-text-sec">STATUS:</span>
          <span
            className={`font-semibold ${
              alert.status === 'RESOLVED'
                ? 'text-status-ok'
                : alert.status === 'ACKNOWLEDGED'
                ? 'text-amber'
                : 'text-status-high'
            }`}
          >
            {alert.status}
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          {alert.status === 'OPEN' && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                acknowledgeAlert(alert.alertId, 'Security Supervisor');
              }}
              className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium rounded-sm border border-hairline bg-canvas hover:bg-hairline/40 text-text-sec hover:text-text-pri transition-colors"
            >
              <Check className="w-3 h-3" />
              Ack
            </button>
          )}

          {alert.status !== 'RESOLVED' && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onResolve(alert);
              }}
              className="flex items-center gap-1 px-2 py-1 text-[11px] font-semibold rounded-sm bg-status-ok/20 hover:bg-status-ok/30 text-status-ok border border-status-ok/40 transition-colors"
            >
              <ShieldAlert className="w-3 h-3" />
              Resolve
            </button>
          )}

          {alert.status === 'RESOLVED' && (
            <span className="font-mono text-[11px] text-text-sec truncate max-w-[140px]" title={alert.resolutionNote}>
              ✓ {alert.resolvedBy || 'Resolved'}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
