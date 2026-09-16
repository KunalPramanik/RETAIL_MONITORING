import React, { useState } from 'react';
import type { Camera, SensorLane } from '../../types';
import { api } from '../../api/client';
import {
  Camera as CameraIcon,
  LayoutGrid,
  Grid2X2,
  Maximize,
  RefreshCw,
  Clock,
  Plus,
  Radio,
} from 'lucide-react';
import { SingleCameraTile } from './SingleCameraTile';
import { AddCameraModal } from './AddCameraModal';

interface LiveCameraFeedTileProps {
  cameras: Camera[];
  lanes: SensorLane[];
  onScanSuccess?: () => void;
}

type LayoutMode = 'auto' | 'quad' | 'grid3' | 'focus';

export const LiveCameraFeedTile: React.FC<LiveCameraFeedTileProps> = ({
  cameras,
  lanes,
  onScanSuccess,
}) => {
  const [scanningCamId, setScanningCamId] = useState<string | null>(null);
  const [scanMessage, setScanMessage] = useState<{ id: string; text: string; isError?: boolean } | null>(
    null
  );
  const [layoutMode, setLayoutMode] = useState<LayoutMode>('auto');
  const [focusedCamId, setFocusedCamId] = useState<string | null>(null);
  const [refreshIntervalMs, setRefreshIntervalMs] = useState<number>(2500);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [forceRefreshKey, setForceRefreshKey] = useState<number>(Date.now());

  // Robust deduplication: prevent duplicate tiles by cameraId and physical endpoint
  const activeCameras = React.useMemo(() => {
    const seenIds = new Set<string>();
    const seenEndpoints = new Set<string>();
    const result: Camera[] = [];

    for (const c of cameras) {
      if (c.removedAt || seenIds.has(c.cameraId)) continue;
      seenIds.add(c.cameraId);

      const endpoint = (c.streamUrl || `${c.ipAddress || ''}:${c.rtspPath || ''}`).trim().toLowerCase();
      if (endpoint && endpoint !== ':' && endpoint !== 'webcam:' && endpoint !== '0:' && endpoint !== '1:') {
        if (seenEndpoints.has(endpoint)) continue;
        seenEndpoints.add(endpoint);
      }
      result.push(c);
    }
    return result;
  }, [cameras]);

  // Default focus camera to first online or first available
  const effectiveFocusId =
    focusedCamId && activeCameras.some((c) => c.cameraId === focusedCamId)
      ? focusedCamId
      : activeCameras[0]?.cameraId || null;

  const handleScanNow = async (cam: Camera) => {
    setScanningCamId(cam.cameraId);
    setScanMessage(null);
    try {
      const data = await api.scanCameraNow(cam.cameraId);
      if (data.success) {
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

  const handleRefreshAll = () => {
    setForceRefreshKey(Date.now());
  };

  if (activeCameras.length === 0) {
    return (
      <div className="bg-panel border border-hairline rounded-sm p-6 space-y-4 text-center">
        <div className="w-12 h-12 mx-auto rounded-full bg-panel-raised border border-hairline flex items-center justify-center text-amber">
          <CameraIcon className="w-6 h-6" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-text-pri">No Surveillance Cameras Registered</h3>
          <p className="text-xs text-text-sec mt-1 max-w-md mx-auto">
            Pair your physical IP camera, local webcam, or RTSP stream to activate real-time visual loss-prevention.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setIsAddModalOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-amber hover:bg-amber/90 text-black text-xs-tech font-bold rounded-sm transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add Surveillance Camera
        </button>
        <AddCameraModal
          isOpen={isAddModalOpen}
          onClose={() => setIsAddModalOpen(false)}
        />
      </div>
    );
  }

  // Determine grid CSS classes
  const getGridClasses = () => {
    if (layoutMode === 'focus') return 'grid grid-cols-1';
    if (layoutMode === 'quad') return 'grid grid-cols-1 md:grid-cols-2 gap-4';
    if (layoutMode === 'grid3') return 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4';
    // Auto
    if (activeCameras.length === 1) return 'grid grid-cols-1';
    if (activeCameras.length === 2) return 'grid grid-cols-1 md:grid-cols-2 gap-4';
    return 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4';
  };

  const displayedCameras =
    layoutMode === 'focus'
      ? activeCameras.filter((c) => c.cameraId === effectiveFocusId)
      : activeCameras;

  return (
    <div className="bg-panel border border-hairline rounded-sm p-4 space-y-3">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-hairline pb-2.5">
        <div className="flex items-center gap-2">
          <CameraIcon className="w-4 h-4 text-amber" />
          <h2 className="text-xs-tech font-bold text-text-pri uppercase tracking-wider">
            Live Surveillance Portal Streams & Optical Inspection
          </h2>
          <span className="font-mono text-[11px] text-text-sec">
            ({activeCameras.filter((c) => c.status === 'ONLINE').length}/{activeCameras.length} Online)
          </span>
        </div>

        {/* Video Wall Toolbar */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Refresh Interval Selector */}
          <div className="flex items-center gap-1 bg-canvas border border-hairline rounded-sm px-2 py-1 text-[11px] font-mono text-text-sec">
            <Clock className="w-3 h-3 text-text-sec" />
            <select
              value={refreshIntervalMs}
              onChange={(e) => setRefreshIntervalMs(Number(e.target.value))}
              className="bg-transparent border-none text-text-pri text-[11px] focus:outline-none cursor-pointer"
              title="Camera snapshot refresh rate"
            >
              <option value={1000}>1s (Fast)</option>
              <option value={2500}>2.5s (Normal)</option>
              <option value={5000}>5s (Eco)</option>
              <option value={0}>Paused</option>
            </select>
          </div>

          {/* Refresh All Button */}
          <button
            type="button"
            onClick={handleRefreshAll}
            className="p-1.5 bg-canvas border border-hairline hover:border-amber/50 rounded-sm text-text-sec hover:text-amber transition-colors"
            title="Refresh all camera frames now"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>

          {/* Layout Mode Selector */}
          <div className="flex items-center bg-canvas border border-hairline rounded-sm p-0.5">
            <button
              type="button"
              onClick={() => setLayoutMode('auto')}
              className={`px-2 py-1 text-[11px] font-mono rounded-sm transition-colors ${
                layoutMode === 'auto'
                  ? 'bg-panel-raised text-amber font-semibold shadow-xs'
                  : 'text-text-sec hover:text-text-pri'
              }`}
              title="Automatic responsive grid"
            >
              Auto
            </button>
            <button
              type="button"
              onClick={() => setLayoutMode('quad')}
              className={`p-1 rounded-sm transition-colors ${
                layoutMode === 'quad'
                  ? 'bg-panel-raised text-amber font-semibold shadow-xs'
                  : 'text-text-sec hover:text-text-pri'
              }`}
              title="2x2 Quad View"
            >
              <Grid2X2 className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setLayoutMode('grid3')}
              className={`p-1 rounded-sm transition-colors ${
                layoutMode === 'grid3'
                  ? 'bg-panel-raised text-amber font-semibold shadow-xs'
                  : 'text-text-sec hover:text-text-pri'
              }`}
              title="3x3 Fleet View"
            >
              <LayoutGrid className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setLayoutMode('focus')}
              className={`p-1 rounded-sm transition-colors ${
                layoutMode === 'focus'
                  ? 'bg-panel-raised text-amber font-semibold shadow-xs'
                  : 'text-text-sec hover:text-text-pri'
              }`}
              title="Single Camera Focus Mode"
            >
              <Maximize className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Add Camera Button */}
          <button
            type="button"
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center gap-1.5 px-2.5 py-1 bg-amber/10 border border-amber/50 hover:bg-amber/20 text-amber text-xs-tech font-semibold rounded-sm transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Camera
          </button>
        </div>
      </div>

      {/* Focus Mode Camera Switcher Tabs */}
      {layoutMode === 'focus' && activeCameras.length > 1 && (
        <div className="flex items-center gap-2 overflow-x-auto pb-1 border-b border-hairline/60">
          <span className="text-[11px] font-mono text-text-sec uppercase">Active Feed:</span>
          {activeCameras.map((cam) => {
            const isSelected = cam.cameraId === effectiveFocusId;
            return (
              <button
                key={cam.cameraId}
                type="button"
                onClick={() => setFocusedCamId(cam.cameraId)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-sm text-xs-tech font-mono transition-colors ${
                  isSelected
                    ? 'bg-amber text-black font-bold'
                    : 'bg-panel-raised border border-hairline text-text-sec hover:text-text-pri'
                }`}
              >
                <Radio className={`w-3 h-3 ${isSelected ? 'text-black animate-pulse' : 'text-text-sec'}`} />
                <span>{cam.label || cam.cameraId}</span>
                <span className={`text-[9px] px-1 py-0.2 rounded ${
                  isSelected ? 'bg-black/20 text-black' : 'bg-canvas text-text-sec'
                }`}>
                  {cam.status}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {/* Camera Grid / Feed Display */}
      <div className={getGridClasses()}>
        {displayedCameras.map((cam) => {
          const assignedLane = lanes.find((l) => l.laneId === cam.laneId);
          return (
            <SingleCameraTile
              key={`${cam.cameraId}_${forceRefreshKey}`}
              camera={cam}
              assignedLane={assignedLane}
              isScanning={scanningCamId === cam.cameraId}
              onScanNow={handleScanNow}
              scanMessage={scanMessage}
              refreshIntervalMs={refreshIntervalMs}
            />
          );
        })}
      </div>

      {/* Add Camera Modal */}
      <AddCameraModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
      />
    </div>
  );
};
