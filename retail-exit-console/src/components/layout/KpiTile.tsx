import React, { useEffect, useState } from 'react';

interface KpiTileProps {
  label: string;
  value: string | number;
  unit?: string;
  subtext?: React.ReactNode;
  statusColor?: 'ok' | 'amber' | 'high' | 'neutral';
  badge?: React.ReactNode;
  onClick?: () => void;
  clickableHint?: string;
}

export const KpiTile: React.FC<KpiTileProps> = ({
  label,
  value,
  unit,
  subtext,
  statusColor = 'neutral',
  badge,
  onClick,
  clickableHint,
}) => {
  const [animating, setAnimating] = useState(false);

  useEffect(() => {
    setAnimating(true);
    const timer = setTimeout(() => setAnimating(false), 260);
    return () => clearTimeout(timer);
  }, [value]);

  const valueColorClass = {
    ok: 'text-status-ok',
    amber: 'text-amber',
    high: 'text-status-high',
    neutral: 'text-mono-val',
  }[statusColor];

  return (
    <div
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => e.key === 'Enter' && onClick() : undefined}
      title={clickableHint || (onClick ? `Open ${label}` : undefined)}
      className={`flex flex-col justify-between px-4 py-3 bg-panel border border-hairline rounded-sm min-w-[170px] flex-1 select-none transition-all ${
        onClick
          ? 'cursor-pointer hover:border-amber/60 hover:bg-panel-raised hover:shadow-sm active:scale-[0.99] group focus-visible:outline-2 focus-visible:outline-amber'
          : ''
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className={`text-xs-tech font-normal truncate ${onClick ? 'text-text-sec group-hover:text-text-pri transition-colors' : 'text-text-sec'}`}>
          {label}
        </span>
        <div className="flex items-center gap-1">
          {badge}
          {onClick && (
            <span className="opacity-0 group-hover:opacity-100 transition-opacity text-[10px] font-mono text-amber ml-0.5">
              ↗
            </span>
          )}
        </div>
      </div>

      <div className="mt-1.5 flex items-baseline gap-1.5 overflow-hidden">
        <div className={`font-mono text-lg-tech font-semibold tracking-tight ${valueColorClass} ${animating ? 'animate-digit-roll' : ''}`}>
          {value}
        </div>
        {unit && <span className="font-mono text-xs-tech text-text-sec">{unit}</span>}
      </div>

      {subtext && (
        <div className="mt-1 text-xs-tech text-text-sec flex items-center gap-1.5">
          {subtext}
        </div>
      )}
    </div>
  );
};


