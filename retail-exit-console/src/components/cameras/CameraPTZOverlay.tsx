import React, { useState } from 'react';
import { ChevronUp, ChevronDown, ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Compass, Square, Loader2 } from 'lucide-react';
import { api } from '../../api/client';

interface CameraPTZOverlayProps {
  cameraId: string;
  isPtzCapable?: boolean;
}

export const CameraPTZOverlay: React.FC<CameraPTZOverlayProps> = ({
  cameraId,
  isPtzCapable = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMoving, setIsMoving] = useState(false);
  const [statusText, setStatusText] = useState<string | null>(null);

  if (!isPtzCapable) return null;

  const handleMove = async (pan: number, tilt: number, zoom: number = 0) => {
    setIsMoving(true);
    setStatusText('Moving PTZ...');
    try {
      await api.movePtz(cameraId, pan, tilt, zoom);
    } catch (err: any) {
      setStatusText(err?.message || 'PTZ Error');
    } finally {
      setTimeout(() => {
        setIsMoving(false);
        setStatusText(null);
      }, 600);
    }
  };

  const handleStop = async () => {
    try {
      await api.stopPtz(cameraId);
    } catch {
      // ignore
    } finally {
      setIsMoving(false);
      setStatusText(null);
    }
  };

  const handlePreset = async (presetId: number) => {
    setIsMoving(true);
    setStatusText(`Moving to Preset ${presetId}...`);
    try {
      await api.gotoPtzPreset(cameraId, presetId);
    } catch (err: any) {
      setStatusText(err?.message || 'Preset Error');
    } finally {
      setTimeout(() => {
        setIsMoving(false);
        setStatusText(null);
      }, 700);
    }
  };

  return (
    <div className="absolute bottom-3 left-3 z-30 flex flex-col items-start gap-1">
      {/* Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        title="Toggle PTZ Directional Controller"
        className={`flex items-center gap-1.5 px-2 py-1 rounded-sm text-[11px] font-mono border backdrop-blur-md transition-colors ${
          isOpen
            ? 'bg-amber text-black border-amber font-semibold'
            : 'bg-canvas/80 text-text-pri border-hairline hover:bg-canvas'
        }`}
      >
        <Compass className={`w-3.5 h-3.5 ${isMoving ? 'animate-spin text-status-high' : ''}`} />
        <span>PTZ</span>
        {isMoving && (
          <span className="flex items-center gap-1 text-[10px] text-amber animate-pulse">
            <Loader2 className="w-2.5 h-2.5 animate-spin" /> Moving
          </span>
        )}
      </button>

      {/* Controller Pop-out */}
      {isOpen && (
        <div className="p-2.5 bg-canvas/90 backdrop-blur-md border border-hairline rounded-sm shadow-2xl space-y-2 select-none">
          <div className="flex items-center justify-between text-[10px] font-mono text-text-sec pb-1 border-b border-hairline/60">
            <span>ONVIF PTZ D-PAD</span>
            {statusText && <span className="text-amber truncate max-w-[120px]">{statusText}</span>}
          </div>

          {/* Directional Pad */}
          <div className="grid grid-cols-3 gap-1 w-28 mx-auto">
            <div />
            <button
              onClick={() => handleMove(0, 1.0)}
              title="Tilt Up"
              className="h-8 flex items-center justify-center bg-panel-raised border border-hairline hover:bg-hairline rounded text-text-pri active:scale-95"
            >
              <ChevronUp className="w-4 h-4" />
            </button>
            <div />

            <button
              onClick={() => handleMove(-1.0, 0)}
              title="Pan Left"
              className="h-8 flex items-center justify-center bg-panel-raised border border-hairline hover:bg-hairline rounded text-text-pri active:scale-95"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={handleStop}
              title="Stop Motion"
              className="h-8 flex items-center justify-center bg-red-950/40 border border-red-800/40 hover:bg-red-900/60 rounded text-rose-300 active:scale-95"
            >
              <Square className="w-3 h-3 fill-current" />
            </button>
            <button
              onClick={() => handleMove(1.0, 0)}
              title="Pan Right"
              className="h-8 flex items-center justify-center bg-panel-raised border border-hairline hover:bg-hairline rounded text-text-pri active:scale-95"
            >
              <ChevronRight className="w-4 h-4" />
            </button>

            <div />
            <button
              onClick={() => handleMove(0, -1.0)}
              title="Tilt Down"
              className="h-8 flex items-center justify-center bg-panel-raised border border-hairline hover:bg-hairline rounded text-text-pri active:scale-95"
            >
              <ChevronDown className="w-4 h-4" />
            </button>
            <div />
          </div>

          {/* Zoom Controls */}
          <div className="flex items-center justify-between gap-1 pt-1 border-t border-hairline/60">
            <button
              onClick={() => handleMove(0, 0, 1.0)}
              title="Zoom In"
              className="flex-1 flex items-center justify-center gap-1 py-1 bg-panel-raised border border-hairline hover:bg-hairline rounded text-[10px] text-text-pri"
            >
              <ZoomIn className="w-3 h-3 text-amber" />
              <span>In</span>
            </button>
            <button
              onClick={() => handleMove(0, 0, -1.0)}
              title="Zoom Out"
              className="flex-1 flex items-center justify-center gap-1 py-1 bg-panel-raised border border-hairline hover:bg-hairline rounded text-[10px] text-text-pri"
            >
              <ZoomOut className="w-3 h-3 text-amber" />
              <span>Out</span>
            </button>
          </div>

          {/* Presets 1-4 */}
          <div className="pt-1 border-t border-hairline/60">
            <p className="text-[9px] uppercase font-mono text-text-sec mb-1">Quick Presets</p>
            <div className="grid grid-cols-4 gap-1">
              {[
                { id: 1, label: 'P1', title: 'Preset 1: Lane Overhead Full' },
                { id: 2, label: 'P2', title: 'Preset 2: Pedestal Close-Up' },
                { id: 3, label: 'P3', title: 'Preset 3: Conveyor Face / ID' },
                { id: 4, label: 'P4', title: 'Preset 4: Ambient Wide' },
              ].map((p) => (
                <button
                  key={p.id}
                  onClick={() => handlePreset(p.id)}
                  title={p.title}
                  className="py-0.5 bg-panel border border-hairline hover:bg-amber hover:text-black rounded text-[10px] font-mono text-text-sec font-semibold transition-colors"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

