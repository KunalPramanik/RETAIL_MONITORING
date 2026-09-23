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
      case 'cyan':
        return {
          stroke: '#00D4FF',
          fill: 'rgba(0, 212, 255, 0.12)',
          bg: '#0A2533',
          text: '#00D4FF',
          border: 'rgba(0, 212, 255, 0.4)',
        };
      case 'fire':
        return {
          stroke: '#FF3D00',
          fill: 'rgba(255, 61, 0, 0.22)',
          bg: '#3A0D00',
          text: '#FF6E40',
          border: 'rgba(255, 61, 0, 0.7)',
        };
      case 'suspicious':
        return {
          stroke: '#E0245E',
          fill: 'rgba(224, 36, 94, 0.20)',
          bg: '#380B1E',
          text: '#FF5C93',
          border: 'rgba(224, 36, 94, 0.7)',
        };
      case 'ppe_ok':
        return {
          stroke: '#00E676',
          fill: 'rgba(0, 230, 118, 0.15)',
          bg: '#0A331A',
          text: '#00E676',
          border: 'rgba(0, 230, 118, 0.6)',
        };
      case 'ppe_violation':
        return {
          stroke: '#FF9100',
          fill: 'rgba(255, 145, 0, 0.20)',
          bg: '#3B2000',
          text: '#FFB74D',
          border: 'rgba(255, 145, 0, 0.7)',
        };
      case 'defect':
        return {
          stroke: '#D946EF', // Fuchsia / Magenta alert
          fill: 'rgba(217, 70, 239, 0.22)',
          bg: '#380B38',
          text: '#F0ABFC',
          border: 'rgba(217, 70, 239, 0.8)',
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

  // Pre-calculate collision-free layout for all detection boxes and labels
  const placedTags: { x: number; y: number; w: number; h: number }[] = [];

  const computedItems = currentBoxes.map((det) => {
    const rawBx = det.box[0];
    const rawBy = det.box[1];
    const rawBw = det.box[2];
    const rawBh = det.box[3];

    // Clamp bounding box coordinates strictly inside the frame boundaries
    const bx = Math.max(1, Math.min(rawBx, fWidth - 10));
    const by = Math.max(1, Math.min(rawBy, fHeight - 10));
    const bw = Math.max(6, Math.min(rawBw, fWidth - bx - 2));
    const bh = Math.max(6, Math.min(rawBh, fHeight - by - 2));

    const effectiveColor = det.type === 'PERSON_UNMATCHED' && det.color === 'red' ? 'cyan' : det.color;
    const tokens = getColorTokens(effectiveColor);
    const isStatic = det.type === 'STATIC_IMAGE';
    const isDoorway = det.type === 'DOORWAY';

    // Refine label display: clean prefixes and format percentage
    let displayLabel = (det.label || '')
      .replace(/^Item:\s*/i, '')
      .replace(/\(Folded\)/i, '')
      .replace(/\s*\((\d+)%\)$/, ' · $1%');

    // Simplify compound category names (e.g., "Doorway / Exit Door" -> "Doorway", "Clock / Wall Item" -> "Clock")
    if (displayLabel.includes(' / ') && !displayLabel.startsWith('Known:')) {
      displayLabel = displayLabel.replace(/ \/ [^·]+/, '');
    }
    displayLabel = displayLabel.trim();

    // Check for identity sub-label (Section 25 Person Identity Discipline)
    const subLabel =
      det.sub_label ||
      det.subLabel ||
      (det.type === 'PERSON_UNMATCHED' ? 'Match: No confirmed database match' : undefined);

    const tagHeight = subLabel ? 36 : 22;
    const approxCharWidth = 7.8;
    const maxChars = Math.max(displayLabel.length, subLabel ? subLabel.length * 0.8 : 0);
    const tagWidth = Math.max(68, Math.ceil(maxChars * approxCharWidth + 18));

    let candidate = { x: 0, y: 0, w: tagWidth, h: tagHeight };

    if (isDoorway) {
      // Architectural doorways dock their badge cleanly inside the top-left corner
      candidate.x = Math.max(4, Math.min(bx + 8, fWidth - tagWidth - 6));
      candidate.y = Math.max(4, Math.min(by + 8, fHeight - tagHeight - 6));
    } else {
      // Preferred tag position: above bounding box
      let tagX = Math.max(4, Math.min(bx, fWidth - tagWidth - 6));
      let tagY = by - tagHeight - 3;

      // If above goes out of frame, place below the bounding box
      if (tagY < 4) {
        tagY = Math.min(fHeight - tagHeight - 4, by + bh + 4);
      }

      const checkOverlap = (rect: { x: number; y: number; w: number; h: number }) => {
        return placedTags.some(
          (p) => !(rect.x + rect.w < p.x || p.x + p.w < rect.x || rect.y + rect.h < p.y || p.y + p.h < rect.y)
        );
      };

      candidate = { x: tagX, y: tagY, w: tagWidth, h: tagHeight };

      if (checkOverlap(candidate)) {
        // Try below the bounding box
        const belowY = Math.min(fHeight - tagHeight - 4, by + bh + 4);
        const belowCandidate = { x: tagX, y: belowY, w: tagWidth, h: tagHeight };
        if (!checkOverlap(belowCandidate)) {
          candidate = belowCandidate;
        } else {
          // Inside the top border
          const insideY = Math.min(fHeight - tagHeight - 4, by + 4);
          candidate = { x: tagX, y: insideY, w: tagWidth, h: tagHeight };
        }
      }

      candidate.x = Math.max(4, Math.min(candidate.x, fWidth - tagWidth - 4));
      candidate.y = Math.max(4, Math.min(candidate.y, fHeight - tagHeight - 4));
    }

    placedTags.push(candidate);

    return {
      bx,
      by,
      bw,
      bh,
      tagX: candidate.x,
      tagY: candidate.y,
      tagWidth,
      tagHeight,
      displayLabel,
      subLabel,
      tokens,
      isStatic,
      isDoorway,
      det,
    };
  });

  // Aggregated live per-class counts for multi-object counting overlay (Part P.1 & V6)
  const classCounts = currentBoxes.reduce<Record<string, number>>((acc, box) => {
    let label = (box.label || box.type)
      .replace(/^Item:\s*/i, '')
      .replace(/\(Folded\)/i, '')
      .replace(/\s*\((\d+)%\)$/, '')
      .trim();
    if (label.includes(' / ') && !label.startsWith('Known:')) {
      label = label.replace(/ \/ [^·]+/, '');
    }
    const typeUpper = (box.type || '').toUpperCase();
    if (typeUpper === 'PERSON_UNMATCHED') {
      label = 'Unknown Person';
    } else if (typeUpper === 'PERSON_MATCHED' || label.startsWith('Known:')) {
      label = 'Verified Person';
    } else if (typeUpper === 'STATIC_IMAGE') {
      label = 'Static Image';
    } else if (typeUpper === 'BOOKSHELF' || label.toLowerCase().includes('bookshelf')) {
      label = 'Bookshelf';
    } else if (typeUpper === 'BOOK' || label.toLowerCase() === 'book') {
      label = 'Books';
    } else if (typeUpper === 'SMARTPHONE' || label.toLowerCase().includes('smartphone') || label.toLowerCase() === 'cell phone') {
      label = 'Smartphones';
    } else if (typeUpper === 'LAPTOP' || label.toLowerCase() === 'laptop') {
      label = 'Laptops';
    } else if (typeUpper === 'WALL_PICTURE' || label.toLowerCase().includes('wall picture') || label.toLowerCase() === 'picture') {
      label = 'Wall Pictures';
    } else if (typeUpper === 'CLOCK' || label.toLowerCase().includes('clock')) {
      label = 'Clocks';
    } else if (typeUpper === 'DOORWAY' || label.toLowerCase().includes('doorway')) {
      label = 'Doorways';
    } else if (typeUpper === 'BOTTLE' || label.toLowerCase().includes('bottle')) {
      label = 'Bottles';
    } else if (typeUpper === 'KEYBOARD' || label.toLowerCase().includes('keyboard')) {
      label = 'Keyboards';
    } else if (typeUpper === 'MOUSE' || label.toLowerCase().includes('mouse')) {
      label = 'Mice';
    } else if (typeUpper === 'CASE' || label.toLowerCase().startsWith('case:')) {
      label = 'Cases';
    } else if (typeUpper === 'DEFECT_DAMAGE' || box.color === 'defect' || label.toLowerCase().includes('defect')) {
      label = `Defect: ${label.replace(/^(defect|damage)[:\s-]*/i, '')}`;
    }
    acc[label] = (acc[label] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="absolute inset-0 pointer-events-none z-10 overflow-hidden select-none">
      {/* ── 1. SVG Bounding Box Layer ── */}
      <svg
        viewBox={`0 0 ${fWidth} ${fHeight}`}
        preserveAspectRatio="xMidYMid meet"
        className="w-full h-full block"
      >
        {computedItems.map((item, idx) => {
          const { bx, by, bw, bh, tagX, tagY, tagWidth, tagHeight, displayLabel, subLabel, tokens, isStatic, isDoorway, det } = item;

          return (
            <g key={`det-box-${idx}-${det.type}`}>
              {/* Bounding Box Outline */}
              <rect
                x={bx}
                y={by}
                width={bw}
                height={bh}
                stroke={tokens.stroke}
                strokeWidth={isDoorway ? 1.5 : (isStatic ? 1.5 : 2)}
                strokeDasharray={isDoorway ? '6 4' : (tokens.dash || 'none')}
                fill={isDoorway ? 'none' : tokens.fill}
                rx={2}
              />

              {/* Box Corner Accents for surveillance look (Live detections only, excluding doorways) */}
              {!isStatic && !isDoorway && (
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
              {subLabel ? (
                <>
                  <text
                    x={tagX + 8}
                    y={tagY + 12}
                    dominantBaseline="middle"
                    fill={tokens.text}
                    fontSize={10}
                    fontFamily="'IBM Plex Mono', monospace"
                    fontWeight={600}
                    letterSpacing="0.2px"
                  >
                    {displayLabel}
                  </text>
                  <text
                    x={tagX + 8}
                    y={tagY + 25}
                    dominantBaseline="middle"
                    fill={tokens.text}
                    fontSize={8.5}
                    fontFamily="'IBM Plex Mono', monospace"
                    fontWeight={500}
                    opacity={0.85}
                    letterSpacing="0.1px"
                  >
                    {subLabel}
                  </text>
                </>
              ) : (
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
              )}

              {/* Skeletal Pose Keypoints & Kinematic Lines */}
              {det.keypoints && det.connections && (
                <g className="pose-skeleton pointer-events-none">
                  {det.connections.map(([p1, p2], cIdx) => {
                    const pt1 = det.keypoints![p1];
                    const pt2 = det.keypoints![p2];
                    if (!pt1 || !pt2) return null;
                    return (
                      <line
                        key={`bone-${cIdx}`}
                        x1={pt1[0]}
                        y1={pt1[1]}
                        x2={pt2[0]}
                        y2={pt2[1]}
                        stroke={tokens.stroke}
                        strokeWidth={2.5}
                        strokeLinecap="round"
                        opacity={0.85}
                      />
                    );
                  })}
                  {Object.entries(det.keypoints).map(([kName, [kx, ky]]) => (
                    <circle
                      key={`joint-${kName}`}
                      cx={kx}
                      cy={ky}
                      r={3.5}
                      fill="#00E5FF"
                      stroke="#000"
                      strokeWidth={1}
                    />
                  ))}
                </g>
              )}
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

      {/* ── 3. Live Multi-Object Per-Class Counting Overlay (Top-Right, Part P.1) ── */}
      {Object.keys(classCounts).length > 0 && (
        <div className="absolute top-2 right-2 z-20 flex flex-col items-end gap-1 font-mono text-[10px] select-none pointer-events-none">
          <div className="px-2 py-1 bg-black/85 border border-white/10 backdrop-blur-md rounded shadow-lg flex flex-col gap-0.5 min-w-[110px]">
            <div className="text-[9px] text-gray-400 font-semibold tracking-wider border-b border-white/10 pb-0.5 mb-0.5 flex justify-between items-center gap-2">
              <span>ENTITIES</span>
              <span className="text-teal-400 font-bold">{currentBoxes.length}</span>
            </div>
            {Object.entries(classCounts).map(([cls, count]) => (
              <div key={`count-${cls}`} className="flex items-center justify-between gap-3 text-gray-200">
                <span className="truncate max-w-[110px]">{cls}</span>
                <span className="font-bold text-white bg-white/10 px-1 rounded text-[9px]">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── 3b. Active Material Carriers / Movement Attribution HUD (Top-Left) ── */}
      {detectionData?.activeCarriers && detectionData.activeCarriers.length > 0 && (
        <div className="absolute top-2 left-2 z-20 flex flex-col gap-1 font-mono text-[11px] select-none pointer-events-none max-w-sm">
          {detectionData.activeCarriers.map((carrier, cIdx) => (
            <div
              key={`carrier-${cIdx}`}
              className="px-2.5 py-1 bg-black/90 border border-cyan/40 backdrop-blur-md rounded shadow-lg flex items-center gap-2 text-white"
            >
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                carrier.direction === 'ENTRY'
                  ? 'bg-emerald-950/80 border border-emerald-500/50 text-emerald-400'
                  : 'bg-amber-950/80 border border-amber-500/50 text-amber'
              }`}>
                {carrier.direction}
              </span>
              <span className="font-semibold text-cyan truncate max-w-[120px]">{carrier.personName}:</span>
              <span className="text-gray-300 truncate">
                {Object.entries(carrier.materials).map(([m, q]) => `${q}x ${m.split(' (')[0].split(' / ')[0]}`).join(', ')}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── 3c. Store Material Inventory Counter Bar (Bottom-Center) ── */}
      {detectionData?.materialCounts && Object.keys(detectionData.materialCounts).length > 0 && (
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-20 flex items-center gap-2 font-mono text-[10px] select-none pointer-events-none">
          <div className="px-3 py-1 bg-black/90 border border-teal-500/40 backdrop-blur-md rounded shadow-xl flex items-center gap-2.5 text-white">
            <span className="text-teal-400 font-bold tracking-wider">STORE INVENTORY:</span>
            {Object.entries(detectionData.materialCounts).map(([mat, count], mIdx) => (
              <React.Fragment key={`mat-hud-${mIdx}`}>
                {mIdx > 0 && <span className="w-px h-2.5 bg-white/20" />}
                <span className="flex items-center gap-1">
                  <span className="text-gray-300 truncate max-w-[130px]">{mat.split(' (')[0].split(' / ')[0]}</span>
                  <span className="font-bold text-teal-300 bg-white/10 px-1 rounded">{count}</span>
                </span>
              </React.Fragment>
            ))}
          </div>
        </div>
      )}

      {/* ── 4. Real-Time Occupancy & Footfall Analytics HUD (Bottom-Left) ── */}
      {detectionData && (detectionData.occupancy !== undefined || detectionData.totalFootfallIn !== undefined) && (
        <div className="absolute bottom-2 left-2 z-20 flex items-center gap-2 font-mono text-[11px] select-none pointer-events-none">
          <div className="px-2.5 py-1 bg-black/85 border border-white/10 backdrop-blur-md rounded flex items-center gap-3 text-white shadow-lg">
            <span className="flex items-center gap-1">
              <span className="text-gray-400">OCCUPANCY:</span>
              <span className="font-bold text-teal-400">{detectionData.occupancy ?? 0}</span>
            </span>
            <span className="w-px h-3 bg-white/20" />
            <span className="flex items-center gap-1">
              <span className="text-gray-400">IN:</span>
              <span className="font-bold text-emerald-400">{detectionData.totalFootfallIn ?? 0}</span>
            </span>
            <span className="w-px h-3 bg-white/20" />
            <span className="flex items-center gap-1">
              <span className="text-gray-400">OUT:</span>
              <span className="font-bold text-rose-400">{detectionData.totalFootfallOut ?? 0}</span>
            </span>
            {detectionData.uniqueVisitors !== undefined && detectionData.uniqueVisitors > 0 && (
              <>
                <span className="w-px h-3 bg-white/20" />
                <span className="flex items-center gap-1">
                  <span className="text-gray-400">VISITORS:</span>
                  <span className="font-bold text-sky-400">{detectionData.uniqueVisitors}</span>
                </span>
              </>
            )}
            {detectionData.crowdDensity && (
              <>
                <span className="w-px h-3 bg-white/20" />
                <span className={`text-[10px] px-1.5 py-0.5 rounded border font-semibold ${
                  detectionData.crowdDensity === 'HIGH' || detectionData.crowdDensity === 'OVERCROWDED'
                    ? 'bg-rose-950/60 border-rose-500/40 text-rose-400'
                    : detectionData.crowdDensity === 'MODERATE'
                    ? 'bg-amber-950/60 border-amber-500/40 text-amber-400'
                    : 'bg-white/10 border-white/10 text-gray-300'
                }`}>
                  {detectionData.crowdDensity}
                </span>
              </>
            )}
            {detectionData.trackingFidelity && detectionData.trackingFidelity !== 'OPTIMAL' && (
              <>
                <span className="w-px h-3 bg-white/20" />
                <span className={`text-[10px] px-1.5 py-0.5 rounded border font-semibold ${
                  detectionData.trackingFidelity === 'OCCLUDED'
                    ? 'bg-rose-950/60 border-rose-500/40 text-rose-400'
                    : 'bg-amber-950/60 border-amber-500/40 text-amber-400'
                }`}>
                  {detectionData.trackingFidelity}
                </span>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

