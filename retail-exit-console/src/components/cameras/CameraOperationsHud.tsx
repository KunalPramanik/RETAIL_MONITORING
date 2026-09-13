import React from 'react';
import type { Camera, SensorLane, CameraDetectionUpdate } from '../../types';
import {
  Activity,
  ChevronRight,
  ChevronLeft,
  Clock,
  Radio,
  Eye,
  ShieldCheck,
  Tag,
  Image as ImageIcon,
} from 'lucide-react';

interface CameraOperationsHudProps {
  camera: Camera;
  assignedLane?: SensorLane;
  detectionData?: CameraDetectionUpdate | null;
  isOpen: boolean;
  onToggle: () => void;
}

export const CameraOperationsHud: React.FC<CameraOperationsHudProps> = ({
  camera,
  assignedLane,
  detectionData,
  isOpen,
  onToggle,
}) => {
  const zoneLabel = assignedLane
    ? `${assignedLane.name} (${assignedLane.location})`
    : camera.label || 'Unassigned Zone';

  const entityCount = detectionData?.entityCount ?? 0;
  const recentLogs = detectionData?.recentLogs || [];

  const getLogIcon = (type: string) => {
    switch (type) {
      case 'PERSON':
        return <Eye className="w-3 h-3 text-status-ok shrink-0 mt-0.5" />;
      case 'ITEM':
        return <Tag className="w-3 h-3 text-amber shrink-0 mt-0.5" />;
      case 'STATIC':
        return <ImageIcon className="w-3 h-3 text-text-sec shrink-0 mt-0.5" />;
      case 'TRANSACTION':
      default:
        return <ShieldCheck className="w-3 h-3 text-status-ok shrink-0 mt-0.5" />;
    }
  };

  return (
    <div className="relative flex h-full select-none z-20">
      {/* ── Toggle Handle Button ── */}
      <button
        type="button"
        onClick={onToggle}
        className={`absolute top-2 -left-7 z-30 p-1.5 rounded-l bg-panel-raised/95 hover:bg-panel border-y border-l border-hairline text-text-sec hover:text-amber transition-colors shadow-md flex items-center justify-center`}
        title={isOpen ? 'Collapse Operations HUD' : 'Expand Operations HUD'}
      >
        {isOpen ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronLeft className="w-3.5 h-3.5" />}
      </button>

      {/* ── Sliding Panel ── */}
      {isOpen && (
        <div className="w-64 h-full bg-panel/95 backdrop-blur-md border-l border-hairline flex flex-col justify-between text-xs-tech overflow-hidden shadow-2xl transition-all">
          {/* Header */}
          <div className="p-3 border-b border-hairline bg-panel-raised flex items-center justify-between">
            <div className="flex items-center gap-1.5 font-bold text-text-pri uppercase tracking-wider text-[11px]">
              <Activity className="w-3.5 h-3.5 text-amber" />
              Operations HUD
            </div>
            <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold bg-amber/20 text-amber border border-amber/40">
              LIVE
            </span>
          </div>

          {/* Telemetry Summary Cards */}
          <div className="p-3 space-y-2 border-b border-hairline/60 bg-canvas/40">
            {/* Zone / Lane Readout */}
            <div className="space-y-0.5">
              <div className="text-[10px] text-text-sec uppercase tracking-wider font-mono flex items-center gap-1">
                <Radio className="w-3 h-3 text-amber" />
                Assigned Zone
              </div>
              <div className="font-semibold text-text-pri truncate" title={zoneLabel}>
                {zoneLabel}
              </div>
            </div>

            {/* Tracked Entity Count */}
            <div className="flex items-center justify-between pt-1">
              <span className="text-[11px] text-text-sec font-mono">TRACKED ENTITIES:</span>
              <span
                className={`font-mono font-bold px-1.5 py-0.5 rounded text-[11px] ${
                  entityCount > 0
                    ? 'bg-status-ok/20 text-status-ok border border-status-ok/40'
                    : 'bg-panel text-text-sec border border-hairline'
                }`}
              >
                {entityCount} active
              </span>
            </div>

            {/* Units & Cases Detected */}
            {detectionData && (detectionData.unitsDetected || 0) > 0 && (
              <div className="flex items-center justify-between text-[11px] font-mono">
                <span className="text-text-sec">CONSENSUS LOAD:</span>
                <span className="text-amber font-bold">
                  {detectionData.casesDetected ?? 0} CS · {detectionData.unitsDetected ?? 0} UNITS
                </span>
              </div>
            )}
          </div>

          {/* Scrolling Activity Log */}
          <div className="flex-1 flex flex-col overflow-hidden p-3 space-y-2">
            <div className="text-[10px] text-text-sec uppercase font-mono tracking-wider flex items-center justify-between">
              <span>Real-Time Activity Log</span>
              <span className="text-[9px] font-mono text-text-sec">{recentLogs.length} entries</span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-1.5 pr-1 font-mono text-[11px]">
              {recentLogs.length > 0 ? (
                recentLogs.map((log) => (
                  <div
                    key={log.id}
                    className="p-1.5 rounded bg-panel-raised/80 border border-hairline/80 flex items-start gap-2 animate-in fade-in"
                  >
                    {getLogIcon(log.type)}
                    <div className="flex-1 min-w-0">
                      <p className="text-text-pri text-[11px] leading-tight break-words">{log.text}</p>
                      <span className="text-[9px] text-text-sec">{log.timestamp}</span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-center p-4 text-text-sec space-y-1">
                  <Clock className="w-5 h-5 opacity-40 mb-1" />
                  <span className="text-[11px] font-sans">No activity recorded yet</span>
                  <span className="text-[9px] text-text-sec/60">Awaiting person or item traversals</span>
                </div>
              )}
            </div>
          </div>

          {/* Footer Timestamp */}
          <div className="px-3 py-2 bg-panel-raised border-t border-hairline flex items-center justify-between font-mono text-[10px] text-text-sec">
            <span>PORTAL TELEMETRY</span>
            <span className="text-text-pri font-bold">{camera.status}</span>
          </div>
        </div>
      )}
    </div>
  );
};

