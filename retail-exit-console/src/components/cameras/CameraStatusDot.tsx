import React from 'react';
import type { CameraStatus } from '../../types';

interface CameraStatusDotProps {
  status: CameraStatus;
  showLabel?: boolean;
  className?: string;
}

export const CameraStatusDot: React.FC<CameraStatusDotProps> = ({
  status,
  showLabel = false,
  className = '',
}) => {
  const getStatusStyles = () => {
    switch (status) {
      case 'ONLINE':
        return {
          dotBg: 'bg-status-ok',
          textClass: 'text-status-ok',
          label: 'ONLINE',
          pulse: true,
        };
      case 'OFFLINE':
        return {
          dotBg: 'bg-status-high',
          textClass: 'text-status-high font-bold',
          label: 'OFFLINE',
          pulse: false,
        };
      case 'DEGRADED':
        return {
          dotBg: 'bg-status-low',
          textClass: 'text-status-low font-bold',
          label: 'DEGRADED',
          pulse: true,
        };
      case 'PENDING_SETUP':
      default:
        return {
          dotBg: 'bg-text-sec/60',
          textClass: 'text-text-sec',
          label: 'PENDING SETUP',
          pulse: false,
        };
    }
  };

  const config = getStatusStyles();

  return (
    <span className={`inline-flex items-center gap-1.5 font-mono text-[11px] ${className}`}>
      <span className="relative flex h-2 w-2">
        {config.pulse && (
          <span
            className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-60 ${config.dotBg}`}
          />
        )}
        <span className={`relative inline-flex rounded-full h-2 w-2 ${config.dotBg}`} />
      </span>
      {showLabel && <span className={config.textClass}>{config.label}</span>}
    </span>
  );
};

