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
          stroke: 'var(--text-secondary, #8B93A1)', // Subtle secondary text/slate outline
          fill: 'rgba(139, 147, 161, 0.08)',
          bg: 'var(--bg-panel-raised, #20252F)',
          text: 'var(--text-primary, #E7E9EC)',
          border: 'var(--border-hairline, #2C323D)',
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
          const rawBx = det.box[0];
          const rawBy = det.box[1];
          const rawBw = det.box[2];
          const rawBh = det.box[3];

          // Clamp bounding box coordinates strictly inside the frame boundaries
          const bx = Math.max(1, Math.min(rawBx, fWidth - 10));
          const by = Math.max(1, Math.min(rawBy, fHeight - 10));
          const bw = Math.max(6, Math.min(rawBw, fWidth - bx - 2));
          const bh = Math.max(6, Math.min(rawBh, fHeight - by - 2));

          const tokens = getColorTokens(det.color);
          const isStatic = det.type === 'STATIC_IMAGE';

          // Refine label display to prevent label truncation
          const displayLabel = (det.label || '')
            .replace(/^Item:\s*/i, '')
            .replace(/\s*\((\d+)%\)$/, ' · $1%');

          const tagHeight = 22;
          const approxCharWidth = 8.5;
          const tagWidth = Math.max(70, Math.ceil(displayLabel.length * approxCharWidth + 20));
          // Clamp tagX so the tag pill and text never overflow the right or left edge of the SVG viewbox
          const tagX = Math.max(4, Math.min(bx, fWidth - tagWidth - 6));
          const tagY = (by - tagHeight - 3) >= 4 ? (by - tagHeight - 3) : Math.min(fHeight - tagHeight - 4, by + bh + 4);

          return (
            <g key={`det-box-${idx}-${det.type}`}>
              {/* Bounding Box Outline */}
              <rect
                x={bx}
                y={by}
                width={bw}
                height={bh}
                stroke={tokens.stroke}
                strokeWidth={isStatic ? 1.5 : 2}
                strokeDasharray={tokens.dash || 'none'}
                fill={tokens.fill}
                rx={2}
              />

              {/* Box Corner Accents for surveillance look (Live detections only) */}
              {!isStatic && (
                <>
                  {/* Top-Left Corner */}
                  <line x1={bx} y1={by} x2={bx + Math.min(12, bw * 0.25)} y2={by} stroke={tokens.stroke} strokeWidth={3} />
                  <line x1={bx} y1={by} x2={bx} y2={by + Math.min(12, bh * 0.25)} stroke={tokens.stroke} strokeWidth={3} />
                  {/* Top-Right Corner */}
                  <line x1={bx + bw} y1={by} x2={bx + bw - Math.min(12, bw * 0.25)} y2={by} stroke={tokens.stroke} strokeWidth={3} />
                  <line x1={bx + bw} y1={by} x2={bx + bw} y2={by + Math.min(12, bh * 0.25)} stroke={tokens.stroke} strokeWidth={3} />
                  {/* Bottom-Left Corner */}
                  <line x1={bx} y1={by + bh} x2={bx + Math.min(12, bw * 0.25)} y2={by + bh} stroke={tokens.stroke} strokeWidth={3} />
                  <line x1={bx} y1={by + bh} x2={bx} y2={by + bh - Math.min(12, bh * 0.25)} stroke={tokens.stroke} strokeWidth={3} />
                  {/* Bottom-Right Corner */}
                  <line x1={bx + bw} y1={by + bh} x2={bx + bw - Math.min(12, bw * 0.25)} y2={by + bh} stroke={tokens.stroke} strokeWidth={3} />
                  <line x1={bx + bw} y1={by + bh} x2={bx + bw} y2={by + bh - Math.min(12, bh * 0.25)} stroke={tokens.stroke} strokeWidth={3} />
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
                x={tagX + 8}
                y={tagY + tagHeight / 2 + 0.5}
                dominantBaseline="middle"
                fill={tokens.text}
                fontSize={11}
                fontFamily="'IBM Plex Mono', monospace"
                fontWeight={600}
                letterSpacing="0.2px"
              >
                {displayLabel}
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

