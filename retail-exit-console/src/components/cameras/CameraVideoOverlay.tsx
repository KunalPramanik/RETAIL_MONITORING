import React, { useState, useEffect, useRef } from 'react';
import type { DetectionBox, CameraDetectionUpdate } from '../../types';

interface CameraVideoOverlayProps {
  detectionData?: CameraDetectionUpdate | null;
  frameWidth?: number;
  frameHeight?: number;
  ttlMs?: number; // Time-to-live before clearing stale boxes (default: 3500ms)
}

export const CameraVideoOverlay: React.FC<CameraVideoOverlayProps> = ({
  detectionData,
  frameWidth: fallbackWidth = 1280,
  frameHeight: fallbackHeight = 720,
  ttlMs = 3500,
}) => {
  const [currentBoxes, setCurrentBoxes] = useState<DetectionBox[]>([]);
  const [activeTx, setActiveTx] = useState<CameraDetectionUpdate['activeTransaction'] | null>(null);
  const clearTimerRef = useRef<any>(null);

  useEffect(() => {
    if (!detectionData) return;

    // Reset stale timer on incoming detection update
    if (clearTimerRef.current) {
      clearTimeout(clearTimerRef.current);
    }

    setCurrentBoxes(detectionData.boxes || []);
    if (detectionData.activeTransaction) {
      setActiveTx(detectionData.activeTransaction);
    }

    // Auto-clear stale bounding boxes when no detections occur for ttlMs
    clearTimerRef.current = setTimeout(() => {
      setCurrentBoxes([]);
    }, ttlMs);

    return () => {
      if (clearTimerRef.current) clearTimeout(clearTimerRef.current);
    };
  }, [detectionData, ttlMs]);

  const fWidth = detectionData?.frameWidth || fallbackWidth;
  const fHeight = detectionData?.frameHeight || fallbackHeight;

  // Box styling palette adhering strictly to design tokens
  const getColorTokens = (colorType: DetectionBox['color']) => {
    switch (colorType) {
      case 'green':
        return {
          stroke: 'var(--status-ok, #4FD1B3)',
          fill: 'rgba(79, 209, 179, 0.12)',
          bg: '#122c24',
          text: 'var(--status-ok, #4FD1B3)',
          border: 'rgba(79, 209, 179, 0.4)',
        };
      case 'red':
        return {
          stroke: 'var(--status-high, #E5484D)',
          fill: 'rgba(229, 72, 77, 0.12)',
          bg: '#331518',
          text: 'var(--status-high, #E5484D)',
          border: 'rgba(229, 72, 77, 0.4)',
        };
      case 'amber':
        return {
          stroke: 'var(--signal-amber, #E8A33D)',
          fill: 'rgba(232, 163, 61, 0.12)',
          bg: '#332312',
          text: 'var(--signal-amber, #E8A33D)',
          border: 'rgba(232, 163, 61, 0.4)',
        };
      case 'static':
      default:
        return {
          stroke: '#94a3b8', // Subtle slate/cyan low-emphasis outline
          fill: 'rgba(148, 163, 184, 0.08)',
          bg: '#1e293b',
          text: '#cbd5e1',
          border: 'rgba(148, 163, 184, 0.3)',
          dash: '5 3',
        };
    }
  };

  return (
    <div className="absolute inset-0 pointer-events-none z-10 overflow-hidden select-none">
      {/* ── 1. SVG Bounding Box Layer ── */}
      <svg
        viewBox={`0 0 ${fWidth} ${fHeight}`}
        preserveAspectRatio="xMidYMid meet"
        className="w-full h-full block"
      >
        {currentBoxes.map((det, idx) => {
          const [bx, by, bw, bh] = det.box;
          const tokens = getColorTokens(det.color);
          const isStatic = det.type === 'STATIC_IMAGE';

          // Clamp tag positioning within video frame
          const tagHeight = 22;
          const tagY = by - tagHeight > 4 ? by - tagHeight - 2 : by + bh + 4;
          const approxCharWidth = 7.5;
          const tagWidth = Math.max(100, det.label.length * approxCharWidth + 14);
          const tagX = Math.max(4, Math.min(bx, fWidth - tagWidth - 4));

          return (
            <g key={`det-box-${idx}-${det.type}`}>
              {/* Bounding Box Outline */}
              <rect
                x={bx}
                y={by}
                width={Math.max(4, bw)}
                height={Math.max(4, bh)}
                stroke={tokens.stroke}
                strokeWidth={isStatic ? 1.5 : 2}
                strokeDasharray={tokens.dash || 'none'}
                fill={tokens.fill}
                rx={2}
              />

              {/* Box Corner Accents for high-tech surveillance look (Live detections only) */}
              {!isStatic && (
                <>
                  {/* Top-Left Corner */}
                  <line x1={bx} y1={by} x2={bx + Math.min(10, bw * 0.25)} y2={by} stroke={tokens.stroke} strokeWidth={3.5} />
                  <line x1={bx} y1={by} x2={bx} y2={by + Math.min(10, bh * 0.25)} stroke={tokens.stroke} strokeWidth={3.5} />
                  {/* Top-Right Corner */}
                  <line x1={bx + bw} y1={by} x2={bx + bw - Math.min(10, bw * 0.25)} y2={by} stroke={tokens.stroke} strokeWidth={3.5} />
                  <line x1={bx + bw} y1={by} x2={bx + bw} y2={by + Math.min(10, bh * 0.25)} stroke={tokens.stroke} strokeWidth={3.5} />
                  {/* Bottom-Left Corner */}
                  <line x1={bx} y1={by + bh} x2={bx + Math.min(10, bw * 0.25)} y2={by + bh} stroke={tokens.stroke} strokeWidth={3.5} />
                  <line x1={bx} y1={by + bh} x2={bx} y2={by + bh - Math.min(10, bh * 0.25)} stroke={tokens.stroke} strokeWidth={3.5} />
                  {/* Bottom-Right Corner */}
                  <line x1={bx + bw} y1={by + bh} x2={bx + bw - Math.min(10, bw * 0.25)} y2={by + bh} stroke={tokens.stroke} strokeWidth={3.5} />
                  <line x1={bx + bw} y1={by + bh} x2={bx + bw} y2={by + bh - Math.min(10, bh * 0.25)} stroke={tokens.stroke} strokeWidth={3.5} />
                </>
              )}

              {/* Label Tag Background Pill */}
              <rect
                x={tagX}
                y={tagY}
                width={tagWidth}
                height={tagHeight}
                fill={tokens.bg}
                stroke={tokens.border}
                strokeWidth={1}
                rx={3}
              />

              {/* Label Tag Text with Monospace Readout */}
              <text
                x={tagX + 7}
                y={tagY + 15}
                fill={tokens.text}
                fontSize={11.5}
                fontFamily="'IBM Plex Mono', monospace"
                fontWeight={600}
                letterSpacing="0.2px"
              >
                {det.label}
              </text>
            </g>
          );
        })}
      </svg>

      {/* ── 2. Live Compliance / Verdict Tag (Top-Center) ── */}
      {activeTx && (
        <div className="absolute top-2 left-1/2 -translate-x-1/2 z-20 flex items-center gap-2">
          <div
            className={`px-2.5 py-1 rounded-sm border font-mono text-[11px] font-bold tracking-wider backdrop-blur-md shadow-lg flex items-center gap-1.5 transition-colors ${
              activeTx.status === 'CONSENSUS_PENDING'
                ? 'bg-black/90 text-amber border-amber/50 animate-pulse'
                : activeTx.verdict === 'PASS'
                ? 'bg-teal-950/90 text-status-ok border-status-ok/50'
                : 'bg-red-950/90 text-status-high border-status-high/50'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full shrink-0 ${
                activeTx.status === 'CONSENSUS_PENDING'
                  ? 'bg-amber animate-ping'
                  : activeTx.verdict === 'PASS'
                  ? 'bg-status-ok'
                  : 'bg-status-high'
              }`}
            />
            {activeTx.displayText}
          </div>
        </div>
      )}
    </div>
  );
};

