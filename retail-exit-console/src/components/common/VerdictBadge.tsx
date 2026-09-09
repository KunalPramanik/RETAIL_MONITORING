import React from 'react';
import type { Verdict } from '../../types';

interface VerdictBadgeProps {
  verdict: Verdict;
  className?: string;
}

export const VerdictBadge: React.FC<VerdictBadgeProps> = ({ verdict, className = '' }) => {
  if (verdict === 'PASS') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm font-mono text-xs-tech font-semibold bg-teal-950/30 text-status-ok border border-status-ok/30 ${className}`}
      >
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
        </svg>
        PASS
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm font-mono text-xs-tech font-semibold bg-red-950/30 text-status-high border border-status-high/40 ${className}`}
    >
      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
      </svg>
      MISMATCH
    </span>
  );
};

