import React, { useState } from 'react';
import type { Camera, SensorLane } from '../../types';
import { Camera as CameraIcon, Radio, RotateCw, Zap } from 'lucide-react';

interface LiveCameraFeedTileProps {
  cameras: Camera[];
  lanes: SensorLane[];
  onScanSuccess?: () => void;
}

export const LiveCameraFeedTile: React.FC<LiveCameraFeedTileProps> = ({
  cameras,
  lanes,
  onScanSuccess,
}) => {
  const [scanningCamId, setScanningCamId] = useState<string | null>(null);
  const [scanMessage, setScanMessage] = useState<{ id: string; text: string; isError?: boolean } | null>(null);
  const [snapshotKeys, setSnapshotKeys] = useState<Record<string, number>>({});

  const activeCameras = cameras.filter((c) => !c.removedAt);

  const refreshCameraSnapshot = (cameraId: string) => {
    setSnapshotKeys((prev) => ({ ...prev, [cameraId]: Date.now() }));
  };

  const handleScanNow = async (cam: Camera) => {
    setScanningCamId(cam.cameraId);
    setScanMessage(null);
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/cameras/${cam.cameraId}/scan-now`, {
        method: 'POST',
      });
      const data = await res.json();
      if (res.ok) {
        setScanMessage({
          id: cam.cameraId,
          text: `Inference executed: ${data.unitsDetected} units (${data.casesDetected} cases) · Verdict: ${data.verdict}`,
        });
        refreshCameraSnapshot(cam.cameraId);
        if (onScanSuccess) onScanSuccess();
      } else {
        setScanMessage({
          id: cam.cameraId,
          text: data.detail || 'Scan failed',
          isError: true,
        });
      }
    } catch (e: any) {
      setScanMessage({
        id: cam.cameraId,
        text: e.message || 'Connection error triggering camera scan',
        isError: true,
      });
    } finally {
      setScanningCamId(null);
    }
  };

  if (activeCameras.length === 0) {
    return null;
  }

  return (
    <div className="bg-panel border border-hairline rounded-sm p-4 space-y-3">
      <div className="flex items-center justify-between border-b border-hairline pb-2.5">
        <div className="flex items-center gap-2">
          <CameraIcon className="w-4 h-4 text-amber" />
          <h2 className="text-xs-tech font-bold text-text-pri uppercase tracking-wider">
            Live Surveillance Portal Streams & Optical Inspection
          </h2>
          <span className="font-mono text-[11px] text-text-sec">
            ({activeCameras.filter((c) => c.status === 'ONLINE').length}/{activeCameras.length} Online)
          </span>
        </div>
        <span className="font-mono text-[10px] text-status-ok flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-status-ok animate-pulse" />
          REAL-TIME CV RUNNER ACTIVE
        </span>
      </div>

      {/* Camera Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {activeCameras.map((cam) => {
          const assignedLane = lanes.find((l) => l.laneId === cam.laneId);
          const isScanning = scanningCamId === cam.cameraId;
          const key = snapshotKeys[cam.cameraId] || 0;
          const snapshotUrl = `http://127.0.0.1:8000/snapshots/preview_${cam.cameraId}.jpg?t=${key}`;

          return (
            <div
              key={cam.cameraId}
              className="bg-canvas border border-hairline rounded-sm overflow-hidden flex flex-col justify-between"
            >
              {/* Camera Header */}
              <div className="px-3 py-2 bg-panel-raised border-b border-hairline flex items-center justify-between text-xs-tech font-mono">
                <div className="flex items-center gap-2 truncate">
                  <span
                    className={`w-2 h-2 rounded-full shrink-0 ${
                      cam.status === 'ONLINE' ? 'bg-status-ok animate-pulse' : 'bg-status-high'
                    }`}
                  />
                  <span className="font-semibold text-text-pri truncate">{cam.label}</span>
                </div>
                <span className="text-[10px] text-text-sec px-1.5 py-0.5 rounded bg-panel border border-hairline shrink-0">
                  {cam.cameraId}
                </span>
              </div>

              {/* Video / Snapshot Viewport */}
              <div className="relative aspect-video bg-black flex items-center justify-center overflow-hidden group">
                {/* Fallback Standby Graphic */}
                <div className="absolute inset-0 flex flex-col items-center justify-center text-text-muted/40 pointer-events-none">
                  <CameraIcon className="w-8 h-8 mb-1 opacity-50" />
                  <span className="text-[10px] font-mono tracking-wider text-text-sec">AWAITING FRAME</span>
                </div>

                <img
                  src={snapshotUrl}
                  alt={`Live feed from ${cam.label}`}
                  className="relative z-[1] w-full h-full object-cover"
                  onError={(e) => {
                    // Hide broken image frame if snapshot file does not exist yet
                    (e.target as HTMLElement).style.display = 'none';
                  }}
                  onLoad={(e) => {
                    (e.target as HTMLElement).style.display = 'block';
                  }}
                />

                {/* Viewport Top Overlay */}
                <div className="absolute top-2 left-2 right-2 flex items-center justify-between text-[10px] font-mono pointer-events-none">
                  <span className="px-1.5 py-0.5 rounded bg-black/80 text-status-ok border border-status-ok/30 flex items-center gap-1">
                    ● {cam.status}
                  </span>
                  <span className="px-1.5 py-0.5 rounded bg-black/80 text-text-sec border border-hairline">
                    {cam.resolution || '1080p'} @ {cam.fps || 30} FPS
                  </span>
                </div>

                {/* Viewport Bottom Overlay */}
                <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between text-[10px] font-mono pointer-events-none">
                  <span className="px-1.5 py-0.5 rounded bg-black/80 text-text-pri border border-hairline flex items-center gap-1">
                    <Radio className="w-3 h-3 text-amber" />
                    {assignedLane ? assignedLane.laneId : 'UNBOUND'}
                  </span>
                  <span className="px-1.5 py-0.5 rounded bg-black/80 text-text-sec border border-hairline">
                    {cam.ipAddress}
                  </span>
                </div>
              </div>

              {/* Scan Message Banner if active */}
              {scanMessage && scanMessage.id === cam.cameraId && (
                <div
                  className={`px-3 py-1.5 text-[11px] font-mono border-t ${
                    scanMessage.isError
                      ? 'bg-red-950/30 border-status-high/40 text-status-high'
                      : 'bg-teal-950/30 border-status-ok/40 text-status-ok'
                  }`}
                >
                  {scanMessage.text}
                </div>
              )}

              {/* Actions Footer */}
              <div className="p-2.5 bg-panel border-t border-hairline flex items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={() => refreshCameraSnapshot(cam.cameraId)}
                  className="p-1.5 text-text-sec hover:text-text-pri bg-canvas border border-hairline rounded-sm transition-colors"
                  title="Refresh snapshot frame"
                >
                  <RotateCw className="w-3.5 h-3.5" />
                </button>

                <button
                  type="button"
                  onClick={() => handleScanNow(cam)}
                  disabled={isScanning}
                  className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-sm font-semibold text-xs-tech transition-colors shadow-sm ${
                    isScanning
                      ? 'bg-amber/50 text-black cursor-wait'
                      : 'bg-amber hover:bg-amber/90 text-black'
                  }`}
                >
                  <Zap className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} />
                  {isScanning ? 'Running CV & Face Scan...' : '⚡ Scan Camera Traversal Now'}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
