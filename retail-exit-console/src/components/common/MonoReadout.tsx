import React from 'react';

interface MonoReadoutProps {
  value: string | number;
  unit?: string;
  className?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  highlight?: boolean;
}

export const MonoReadout: React.FC<MonoReadoutProps> = ({
  value,
  unit,
  className = '',
  size = 'md',
  highlight = false,
}) => {
  const sizeClass = {
    sm: 'text-xs-tech',
    md: 'text-sm-tech',
    lg: 'text-lg-tech font-medium',
    xl: 'text-xl-tech font-semibold tracking-tight',
  }[size];

  const colorClass = highlight ? 'text-amber' : 'text-mono-val';

  return (
    <span className={`font-mono tabular-nums ${colorClass} ${sizeClass} ${className}`}>
      {value}
      {unit && <span className="ml-1 text-xs-tech text-text-sec font-normal">{unit}</span>}
    </span>
  );
};

