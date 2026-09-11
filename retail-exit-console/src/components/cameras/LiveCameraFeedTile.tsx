import React, { useState } from 'react';
import type { Camera, SensorLane } from '../../types';
import { Camera as CameraIcon } from 'lucide-react';
import { SingleCameraTile } from './SingleCameraTile';

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
  const [scanMessage, setScanMessage] = useState<{ id: string; text: string; isError?: boolean } | null>(
    null
  );

  const activeCameras = cameras.filter((c) => !c.removedAt);

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
          return (
            <SingleCameraTile
              key={cam.cameraId}
              camera={cam}
              assignedLane={assignedLane}
              isScanning={scanningCamId === cam.cameraId}
              onScanNow={handleScanNow}
              scanMessage={scanMessage}
            />
          );
        })}
      </div>
    </div>
  );
};
