import React from 'react';
import type { Severity } from '../../types';

interface SeverityBadgeProps {
  severity: Severity;
  className?: string;
  size?: 'sm' | 'md';
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({ severity, className = '', size = 'md' }) => {
  const sizeClasses = size === 'sm' ? 'px-1.5 py-0.5 text-xs-tech' : 'px-2 py-0.5 text-xs-tech';

  switch (severity) {
    case 'HIGH':
      return (
        <span
          className={`inline-flex items-center gap-1 font-mono font-medium rounded-sm bg-red-950/30 text-status-high border border-status-high/40 ${sizeClasses} ${className}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-status-high animate-pulse" />
          HIGH ALARM
        </span>
      );
    case 'MEDIUM':
      return (
        <span
          className={`inline-flex items-center gap-1 font-mono font-medium rounded-sm bg-orange-950/20 text-status-med border border-status-med/40 ${sizeClasses} ${className}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-status-med" />
          MEDIUM
        </span>
      );
    case 'LOW':
      return (
        <span
          className={`inline-flex items-center gap-1 font-mono font-medium rounded-sm bg-yellow-950/20 text-status-low border border-status-low/40 ${sizeClasses} ${className}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-status-low" />
          LOW
        </span>
      );
    case 'NONE':
    default:
      return (
        <span
          className={`inline-flex items-center gap-1 font-mono font-medium rounded-sm bg-teal-950/20 text-status-ok border border-status-ok/40 ${sizeClasses} ${className}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-status-ok" />
          VERIFIED
        </span>
      );
  }
};

