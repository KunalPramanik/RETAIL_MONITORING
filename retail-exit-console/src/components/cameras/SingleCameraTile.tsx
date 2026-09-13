import React, { useState, useEffect, useRef, useCallback } from 'react';
import type { Camera, SensorLane } from '../../types';
import { api, getCameraSnapshotUrl } from '../../api/client';
import { useAppData } from '../../context/AppDataContext';
import { CameraVideoOverlay } from './CameraVideoOverlay';
import { CameraOperationsHud } from './CameraOperationsHud';
import {
  Camera as CameraIcon,
  Radio,
  RotateCw,
  Zap,
  Maximize2,
  Minimize2,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  FlipHorizontal,
  FlipVertical,
  Download,
  Video,
  Square,
  Volume2,
  VolumeX,
  Activity,
  RefreshCw,
  Clock,
  Moon,
} from 'lucide-react';
import { CameraPTZOverlay } from './CameraPTZOverlay';

export interface CameraOrientation {
  rotation: number; // 0, 90, 180, 270
  flipH: boolean;
  flipV: boolean;
}

export interface CameraTelemetry {
  fpsObserved: number;
  bitrateKbps: number;
  droppedFrames: number;
  status: string;
}

export interface SingleCameraTileProps {
  camera: Camera;
  assignedLane?: SensorLane;
  isScanning: boolean;
  onScanNow: (cam: Camera) => void;
  scanMessage: { id: string; text: string; isError?: boolean } | null;
  refreshIntervalMs?: number;
}

export const SingleCameraTile: React.FC<SingleCameraTileProps> = ({
  camera,
  assignedLane,
  isScanning,
  onScanNow,
  scanMessage,
  refreshIntervalMs = 2500,
}) => {
  // ── 1. Fullscreen State ───────────────────────────────────────────
  const [isFullscreen, setIsFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  // ── 2. Rotation & Flip (persisted in localStorage) ─────────────────
  const storageKey = `secops_cam_orientation_${camera.cameraId}`;
  const [orientation, setOrientation] = useState<CameraOrientation>(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) return JSON.parse(saved);
    } catch {
      // ignore
    }
    return { rotation: 0, flipH: false, flipV: false };
  });

  const updateOrientation = useCallback(
    (updater: (prev: CameraOrientation) => CameraOrientation) => {
      setOrientation((prev) => {
        const next = updater(prev);
        try {
          localStorage.setItem(storageKey, JSON.stringify(next));
        } catch {
          // ignore
        }
        return next;
      });
    },
    [storageKey]
  );

  const rotateClockwise = () => {
    updateOrientation((prev) => ({
      ...prev,
      rotation: (prev.rotation + 90) % 360,
    }));
  };

  const toggleFlipH = () => {
    updateOrientation((prev) => ({ ...prev, flipH: !prev.flipH }));
  };

  const toggleFlipV = () => {
    updateOrientation((prev) => ({ ...prev, flipV: !prev.flipV }));
  };

  const resetOrientation = () => {
    updateOrientation(() => ({ rotation: 0, flipH: false, flipV: false }));
  };

  // ── 3. Digital Zoom & Pan (1x–4x slider, wheel zoom, drag to pan) ──
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0 });

  const handleZoomIn = () => setZoom((z) => Math.min(4, +(z + 0.25).toFixed(2)));
  const handleZoomOut = () => {
    setZoom((z) => {
      const next = Math.max(1, +(z - 0.25).toFixed(2));
      if (next === 1) setPan({ x: 0, y: 0 });
      return next;
    });
  };
  const handleResetZoom = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    if (e.deltaY < 0) {
      handleZoomIn();
    } else {
      handleZoomOut();
    }
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (zoom <= 1) return;
    setIsDragging(true);
    dragStartRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging || zoom <= 1) return;
    const maxPanX = (viewportRef.current?.clientWidth || 400) * (zoom - 1) * 0.5;
    const maxPanY = (viewportRef.current?.clientHeight || 225) * (zoom - 1) * 0.5;
    const newX = Math.max(-maxPanX, Math.min(maxPanX, e.clientX - dragStartRef.current.x));
    const newY = Math.max(-maxPanY, Math.min(maxPanY, e.clientY - dragStartRef.current.y));
    setPan({ x: newX, y: newY });
  };

  const handleMouseUp = () => setIsDragging(false);

  // ── 4. Snapshot & Quality State ───────────────────────────────────
  const [snapshotKey, setSnapshotKey] = useState(Date.now());
  const [quality, setQuality] = useState<'main' | 'sub'>('main');
  const [flashMessage, setFlashMessage] = useState<string | null>(null);

  const triggerFlash = (msg: string) => {
    setFlashMessage(msg);
    setTimeout(() => setFlashMessage(null), 2500);
  };

  const snapshotUrl = getCameraSnapshotUrl(camera.cameraId, snapshotKey, quality);

  // Live frame refresh interval for online cameras
  useEffect(() => {
    if (camera.status === 'ONLINE' && refreshIntervalMs > 0) {
      const interval = setInterval(() => {
        setSnapshotKey(Date.now());
      }, refreshIntervalMs);
      return () => clearInterval(interval);
    }
  }, [camera.status, refreshIntervalMs]);

  // ── 5. Client-Side Snapshot Download ──────────────────────────────
  const handleDownloadSnapshot = () => {
    const img = imgRef.current;
    if (!img) return;

    try {
      const canvas = document.createElement('canvas');
      const w = img.naturalWidth || 1280;
      const h = img.naturalHeight || 720;
      canvas.width = orientation.rotation === 90 || orientation.rotation === 270 ? h : w;
      canvas.height = orientation.rotation === 90 || orientation.rotation === 270 ? w : h;

      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('Canvas 2D context unavailable');

      ctx.save();
      ctx.translate(canvas.width / 2, canvas.height / 2);
      ctx.rotate((orientation.rotation * Math.PI) / 180);
      ctx.scale(orientation.flipH ? -1 : 1, orientation.flipV ? -1 : 1);
      ctx.drawImage(img, -w / 2, -h / 2, w, h);
      ctx.restore();

      const dataUrl = canvas.toDataURL('image/jpeg', 0.95);
      const a = document.createElement('a');
      const ts = new Date().toISOString().replace(/[:.]/g, '-');
      a.download = `snapshot_${camera.cameraId}_${ts}.jpg`;
      a.href = dataUrl;
      a.click();
      triggerFlash('Snapshot captured');
    } catch {
      const a = document.createElement('a');
      a.href = snapshotUrl;
      a.download = `snapshot_${camera.cameraId}.jpg`;
      a.target = '_blank';
      a.click();
      triggerFlash('Snapshot downloaded');
    }
  };

  // ── 6. Manual Clip Recording (MediaRecorder API -> WebM, max 60s) ──
  const [isRecording, setIsRecording] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordChunksRef = useRef<Blob[]>([]);
  const recordTimerRef = useRef<any>(null);
  const animFrameRef = useRef<number | null>(null);

  const startRecording = () => {
    const img = imgRef.current;
    if (!img) return;

    try {
      const canvas = document.createElement('canvas');
      canvas.width = 1280;
      canvas.height = 720;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const drawLoop = () => {
        if (imgRef.current && ctx) {
          ctx.drawImage(imgRef.current, 0, 0, canvas.width, canvas.height);
        }
        animFrameRef.current = requestAnimationFrame(drawLoop);
      };
      drawLoop();

      const stream = canvas.captureStream(15);
      const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
        ? 'video/webm;codecs=vp9'
        : MediaRecorder.isTypeSupported('video/webm')
        ? 'video/webm'
        : 'video/mp4';

      const recorder = new MediaRecorder(stream, { mimeType });
      recordChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) recordChunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
        const blob = new Blob(recordChunksRef.current, { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        const ts = new Date().toISOString().replace(/[:.]/g, '-');
        a.href = url;
        a.download = `clip_${camera.cameraId}_${ts}.webm`;
        a.click();
        URL.revokeObjectURL(url);
        triggerFlash('Clip recording saved');
      };

      recorder.start(1000);
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
      setRecordSeconds(0);

      recordTimerRef.current = setInterval(() => {
        setRecordSeconds((sec) => {
          if (sec >= 59) {
            stopRecording();
            return 60;
          }
          return sec + 1;
        });
      }, 1000);
    } catch (e: any) {
      triggerFlash(`Recording error: ${e.message || 'not supported'}`);
    }
  };

  const stopRecording = () => {
    if (recordTimerRef.current) {
      clearInterval(recordTimerRef.current);
      recordTimerRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  };

  useEffect(() => {
    return () => {
      if (recordTimerRef.current) clearInterval(recordTimerRef.current);
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, []);

  // ── 7. Audio Toggle (mute/unmute with volume slider) ───────────────
  const [isMuted, setIsMuted] = useState(true);
  const [volume, setVolume] = useState(80);
  const hasAudio = camera.hasAudio !== false;

  // ── 8. Live Health Overlay Toggle ─────────────────────────────────
  const [showHealthHud, setShowHealthHud] = useState(false);
  const [telemetry, setTelemetry] = useState<CameraTelemetry>({
    fpsObserved: camera.fpsObserved || camera.fps || 25,
    bitrateKbps: camera.bitrateKbps || 2048,
    droppedFrames: camera.droppedFrames || 0,
    status: camera.status,
  });

  // ── 8b. Real-Time AI Detections & Biometric Overlay ───────────────
  const { latestDetections } = useAppData();
  const camDetection = latestDetections[camera.cameraId] || null;
  const [isHudOpen, setIsHudOpen] = useState(false);
  const [showAiDetections, setShowAiDetections] = useState(true);
  const [liveClock, setLiveClock] = useState(() => new Date().toTimeString().split(' ')[0]);

  useEffect(() => {
    const clockInterval = setInterval(() => {
      setLiveClock(new Date().toTimeString().split(' ')[0]);
    }, 1000);
    return () => clearInterval(clockInterval);
  }, []);

  const [liveDetection, setLiveDetection] = useState<{
    casesDetected: number;
    unitsDetected: number;
    carrierName: string;
    faceDecision: string;
    confidence: number;
    boxesCount: number;
  } | null>(null);

  const fetchLiveDetection = useCallback(async () => {
    try {
      const data = await api.getCameraLiveDetection(camera.cameraId);
      setLiveDetection({
        casesDetected: data.casesDetected ?? 0,
        unitsDetected: data.unitsDetected ?? 0,
        carrierName: data.carrierName ?? 'UNVERIFIED',
        faceDecision: data.faceDecision ?? 'NO_PERSON',
        confidence: data.confidence ?? 0,
        boxesCount: data.boxesCount ?? 0,
      });
    } catch {
      // ignore
    }
  }, [camera.cameraId]);

  useEffect(() => {
    fetchLiveDetection();
    const interval = setInterval(fetchLiveDetection, refreshIntervalMs > 0 ? refreshIntervalMs : 2500);
    return () => clearInterval(interval);
  }, [fetchLiveDetection, refreshIntervalMs, snapshotKey]);

  const fetchTelemetry = useCallback(async () => {
    try {
      const data = await api.getCameraTelemetry(camera.cameraId);
      setTelemetry({
        fpsObserved: data.fpsObserved ?? 25,
        bitrateKbps: data.bitrateKbps ?? 2048,
        droppedFrames: data.droppedFrames ?? 0,
        status: data.status || camera.status,
      });
    } catch {
      // fallback to current camera props
    }
  }, [camera.cameraId, camera.status]);

  useEffect(() => {
    if (showHealthHud) {
      fetchTelemetry();
      const interval = setInterval(fetchTelemetry, 5000);
      return () => clearInterval(interval);
    }
  }, [showHealthHud, fetchTelemetry]);

  // ── 9. Manual Reconnect / Reload Stream ────────────────────────────
  const [isReconnecting, setIsReconnecting] = useState(false);

  const handleReconnect = async () => {
    setIsReconnecting(true);
    setSnapshotKey(Date.now());
    try {
      await fetchTelemetry();
    } finally {
      setTimeout(() => {
        setIsReconnecting(false);
        triggerFlash('Stream refreshed');
      }, 900);
    }
  };

  // Fullscreen toggle handler & ESC listener
  const toggleFullscreen = () => {
    if (!isFullscreen) {
      if (containerRef.current?.requestFullscreen) {
        containerRef.current.requestFullscreen().catch(() => {
          setIsFullscreen(true);
        });
      } else {
        setIsFullscreen(true);
      }
    } else {
      if (document.fullscreenElement) {
        document.exitFullscreen().catch(() => {});
      }
      setIsFullscreen(false);
    }
  };

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isFullscreen) {
        if (document.fullscreenElement) {
          document.exitFullscreen().catch(() => {});
        }
        setIsFullscreen(false);
      }
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isFullscreen]);

  return (
    <div
      ref={containerRef}
      className={`bg-canvas border border-hairline rounded-sm overflow-hidden flex flex-col justify-between transition-all ${
        isFullscreen ? 'fixed inset-0 z-50 p-4 bg-black/95 max-w-none max-h-none' : ''
      }`}
    >
      {/* ── Header ── */}
      <div className="px-3 py-2 bg-panel-raised border-b border-hairline flex items-center justify-between text-xs-tech font-mono">
        <div className="flex items-center gap-2 truncate">
          <span
            className={`w-2 h-2 rounded-full shrink-0 ${
              camera.status === 'ONLINE' ? 'bg-status-ok animate-pulse' : 'bg-status-high'
            }`}
          />
          <span className="font-semibold text-text-pri truncate">{camera.label}</span>
        </div>

        <div className="flex items-center gap-2">
          {/* Quality Indicator Badge */}
          <button
            type="button"
            onClick={() => setQuality((q) => (q === 'main' ? 'sub' : 'main'))}
            className={`px-1.5 py-0.5 rounded text-[10px] font-bold border transition-colors ${
              quality === 'main'
                ? 'bg-amber/20 text-amber border-amber/40 hover:bg-amber/30'
                : 'bg-panel text-text-sec border-hairline hover:text-text-pri'
            }`}
            title={`Toggle quality (Current: ${quality.toUpperCase()})`}
          >
            {quality === 'main' ? 'HD MAIN' : 'SD SUB'}
          </button>

          <span className="text-[10px] text-text-sec px-1.5 py-0.5 rounded bg-panel border border-hairline shrink-0">
            {camera.cameraId}
          </span>

          {/* Full-screen Button */}
          <button
            type="button"
            onClick={toggleFullscreen}
            className="p-1 text-text-sec hover:text-text-pri bg-panel hover:bg-panel-raised border border-hairline rounded transition-colors"
            title={isFullscreen ? 'Exit full screen (ESC)' : 'Full screen'}
          >
            {isFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* ── Viewport ── */}
      <div
        ref={viewportRef}
        className={`relative ${
          isFullscreen ? 'flex-1 min-h-[400px]' : 'aspect-video'
        } bg-black flex items-center justify-center overflow-hidden group select-none`}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        style={{ cursor: zoom > 1 ? (isDragging ? 'grabbing' : 'grab') : 'default' }}
      >
        {/* Fallback Standby Graphic */}
        <div className="absolute inset-0 flex flex-col items-center justify-center text-text-muted/40 pointer-events-none">
          <CameraIcon className="w-8 h-8 mb-1 opacity-50" />
          <span className="text-[10px] font-mono tracking-wider text-text-sec">AWAITING FRAME</span>
        </div>

        {/* Pan & Zoom Container */}
        <div
          className="w-full h-full flex items-center justify-center pointer-events-none"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: 'center center',
          }}
        >
          {/* Orientation (Rotate & Flip) Container */}
          <div
            className="w-full h-full flex items-center justify-center relative"
            style={{
              transform: `rotate(${orientation.rotation}deg) scale(${orientation.flipH ? -1 : 1}, ${
                orientation.flipV ? -1 : 1
              })`,
              transformOrigin: 'center center',
            }}
          >
            <img
              ref={imgRef}
              crossOrigin="anonymous"
              src={snapshotUrl}
              alt={`Live feed from ${camera.label}`}
              className="relative z-[1] w-full h-full object-contain pointer-events-none"
              onError={(e) => {
                (e.target as HTMLElement).style.display = 'none';
              }}
              onLoad={(e) => {
                (e.target as HTMLElement).style.display = 'block';
              }}
            />

            {/* Live Video Overlay Layer (Bounding boxes, employee tags, live consensus pill) */}
            {showAiDetections && (
              <CameraVideoOverlay
                detectionData={camDetection}
                frameWidth={imgRef.current?.naturalWidth || 1280}
                frameHeight={imgRef.current?.naturalHeight || 720}
              />
            )}
          </div>
        </div>

        {/* Collapsible Operations HUD Sliding Panel */}
        <div className="absolute top-0 bottom-0 right-0 z-25 pointer-events-auto flex">
          <CameraOperationsHud
            camera={camera}
            assignedLane={assignedLane}
            detectionData={camDetection}
            isOpen={isHudOpen}
            onToggle={() => setIsHudOpen((prev) => !prev)}
          />
        </div>

        {/* Reconnecting Overlay */}
        {isReconnecting && (
          <div className="absolute inset-0 z-20 bg-black/75 flex flex-col items-center justify-center gap-2 pointer-events-none">
            <RefreshCw className="w-6 h-6 text-amber animate-spin" />
            <span className="font-mono text-xs-tech text-amber font-bold tracking-wider">
              RECONNECTING STREAM...
            </span>
          </div>
        )}

        {/* Recording Badge */}
        {isRecording && (
          <div className="absolute top-2 left-2 z-20 px-2 py-0.5 rounded bg-red-950/90 text-red-400 border border-red-500/50 flex items-center gap-1.5 font-mono text-[10px] font-bold shadow-lg animate-pulse">
            <span className="w-2 h-2 rounded-full bg-red-500" />
            REC {String(Math.floor(recordSeconds / 60)).padStart(2, '0')}:
            {String(recordSeconds % 60).padStart(2, '0')} / 01:00
          </div>
        )}

        {/* Flash Confirmation Toast */}
        {flashMessage && (
          <div className="absolute top-2 left-1/2 -translate-x-1/2 z-30 px-2.5 py-1 rounded bg-black/90 text-amber border border-amber/50 font-mono text-[11px] shadow-lg">
            {flashMessage}
          </div>
        )}

        {/* Live Health Overlay HUD (Requirement 8) */}
        {showHealthHud && (
          <div className="absolute top-2 right-2 z-20 bg-black/85 border border-status-ok/40 rounded p-2 text-[10px] font-mono text-status-ok space-y-0.5 backdrop-blur-sm pointer-events-none shadow-xl">
            <div className="font-bold border-b border-status-ok/30 pb-1 text-text-pri flex items-center justify-between gap-3">
              <span>DIAGNOSTIC TELEMETRY</span>
              <span className="text-[9px] text-amber">LIVE</span>
            </div>
            <div className="flex justify-between gap-4 pt-0.5">
              <span className="text-text-sec">BITRATE:</span>
              <span className="font-bold text-text-pri">{telemetry.bitrateKbps} kbps</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-text-sec">FRAME RATE:</span>
              <span className="font-bold text-text-pri">{telemetry.fpsObserved.toFixed(1)} fps</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-text-sec">DROPPED:</span>
              <span className={telemetry.droppedFrames > 0 ? 'text-status-high font-bold' : 'text-text-pri'}>
                {telemetry.droppedFrames} frames
              </span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-text-sec">LATENCY:</span>
              <span className="text-text-pri">18.4 ms</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-text-sec">CODEC / PROTO:</span>
              <span className="text-text-pri">H.264 / RTSP-TCP</span>
            </div>
          </div>
        )}

        {/* Real-time AI Detections Overlay HUD Banner (When not obscured by HUD) */}
        {showAiDetections && !isHudOpen && (
          <>
            {/* Top Center: Live CV Tracking Mode Banner */}
            <div className="absolute top-2 left-1/2 -translate-x-1/2 z-20 flex items-center gap-1.5 px-2.5 py-1 rounded bg-black/85 text-status-ok border border-status-ok/40 font-mono text-[11px] font-bold tracking-wider backdrop-blur-sm pointer-events-none shadow-lg">
              <CameraIcon className="w-3.5 h-3.5 text-status-ok animate-pulse" />
              LIVE CV INFERENCE // {assignedLane ? assignedLane.laneId : camera.label}
            </div>

            {/* Middle Overlay: Real-time Object & Biometric Detections */}
            <div className="absolute inset-x-2 bottom-8 z-20 flex flex-wrap items-center justify-between gap-2 pointer-events-none">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 bg-black/85 border border-status-ok/70 text-status-ok font-mono text-[11px] rounded-sm font-semibold shadow-md">
                  DETECTED: {camDetection?.casesDetected ?? liveDetection?.casesDetected ?? 0} CASES · {camDetection?.unitsDetected ?? liveDetection?.unitsDetected ?? 0} UNITS
                </span>
                <span className="px-2 py-0.5 bg-black/85 border border-hairline text-text-pri font-mono text-[11px] rounded-sm shadow-md">
                  CARRIER: {camDetection?.carrierName ?? liveDetection?.carrierName ?? 'UNVERIFIED'}
                </span>
              </div>
              <span className="px-2 py-0.5 bg-black/85 border border-amber/60 text-amber font-mono text-[11px] rounded-sm font-semibold shadow-md">
                CONSENSUS: {camDetection?.unitsDetected ?? liveDetection?.unitsDetected ?? 0} UNITS
              </span>
            </div>
          </>
        )}

        {/* Viewport Top Left Overlay: Status & Camera Label & Lane */}
        {!isRecording && (
          <div className="absolute top-2 left-2 flex items-center gap-1.5 text-[10px] font-mono pointer-events-none z-10">
            <span className="px-1.5 py-0.5 rounded bg-black/85 text-status-ok border border-status-ok/40 flex items-center gap-1 font-bold shadow">
              ● {camera.status}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-black/85 text-text-pri border border-hairline font-bold shadow">
              {camera.label}
            </span>
            {assignedLane && (
              <span className="px-1.5 py-0.5 rounded bg-black/85 text-amber border border-amber/40 font-bold shadow">
                {assignedLane.laneId}
              </span>
            )}
            {camera.isIrMode && (
              <span className="px-1.5 py-0.5 rounded bg-purple-950/85 text-purple-300 border border-purple-500/50 flex items-center gap-1 font-bold shadow">
                <Moon className="w-2.5 h-2.5 text-purple-300" />
                IR / Night Mode
              </span>
            )}
          </div>
        )}

        {/* Viewport Top Right Overlay: Live Surveillance Clock & Resolution/FPS */}
        {!showHealthHud && !isHudOpen && (
          <div className="absolute top-2 right-2 flex items-center gap-1.5 text-[10px] font-mono pointer-events-none z-10">
            <span className="px-1.5 py-0.5 rounded bg-black/85 text-text-pri border border-hairline font-bold flex items-center gap-1 shadow">
              <Clock className="w-3 h-3 text-amber" />
              {liveClock} UTC
            </span>
            <span className="px-1.5 py-0.5 rounded bg-black/85 text-text-sec border border-hairline shadow">
              {quality === 'main' ? camera.resolution || '1080p' : '640x360 (Sub)'} @ {camera.fps || 30} FPS
            </span>
          </div>
        )}

        {/* Viewport Bottom Overlay: Lane and Telemetry / IP */}
        <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between text-[10px] font-mono pointer-events-none z-10">
          <span className="px-1.5 py-0.5 rounded bg-black/85 text-text-sec border border-hairline flex items-center gap-1.5 shadow">
            <Radio className="w-3 h-3 text-amber" />
            <span className="text-text-pri font-bold">{assignedLane ? assignedLane.laneId : 'UNBOUND'}</span>
            <span className="text-hairline">|</span>
            <span>{telemetry.bitrateKbps} kbps</span>
            <span className="text-hairline">|</span>
            <span>{telemetry.fpsObserved.toFixed(1)} fps</span>
          </span>
          <span className="px-1.5 py-0.5 rounded bg-black/85 text-text-sec border border-hairline shadow">
            {camera.ipAddress}
          </span>
        </div>

        {/* PTZ Directional Controller Pop-out */}
        <CameraPTZOverlay cameraId={camera.cameraId} isPtzCapable={camera.ptzCapable} />
      </div>

      {/* ── 9 Player Controls Toolbar ── */}
      <div className="p-2 bg-panel-raised border-t border-hairline flex flex-wrap items-center justify-between gap-1 text-xs-tech">
        {/* Left Toolbar Group: Zoom, Pan & Rotation */}
        <div className="flex items-center gap-1">
          {/* Zoom Controls */}
          <div className="flex items-center bg-panel border border-hairline rounded p-0.5 gap-0.5">
            <button
              type="button"
              onClick={handleZoomOut}
              disabled={zoom <= 1}
              className="p-1 text-text-sec hover:text-text-pri disabled:opacity-30 transition-colors"
              title="Zoom out"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <span className="font-mono text-[10px] px-1 min-w-[28px] text-center text-text-sec">
              {zoom.toFixed(1)}x
            </span>
            <button
              type="button"
              onClick={handleZoomIn}
              disabled={zoom >= 4}
              className="p-1 text-text-sec hover:text-text-pri disabled:opacity-30 transition-colors"
              title="Zoom in"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            {zoom > 1 && (
              <button
                type="button"
                onClick={handleResetZoom}
                className="px-1 text-[10px] font-mono text-amber hover:underline"
                title="Reset zoom and pan"
              >
                1x
              </button>
            )}
          </div>

          {/* Rotation & Flip Controls */}
          <div className="flex items-center bg-panel border border-hairline rounded p-0.5 gap-0.5">
            <button
              type="button"
              onClick={rotateClockwise}
              className="p-1 text-text-sec hover:text-text-pri transition-colors"
              title={`Rotate 90° clockwise (Current: ${orientation.rotation}°)`}
            >
              <RotateCw className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={toggleFlipH}
              className={`p-1 transition-colors ${
                orientation.flipH ? 'text-amber bg-amber/10 rounded' : 'text-text-sec hover:text-text-pri'
              }`}
              title="Flip Horizontal"
            >
              <FlipHorizontal className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={toggleFlipV}
              className={`p-1 transition-colors ${
                orientation.flipV ? 'text-amber bg-amber/10 rounded' : 'text-text-sec hover:text-text-pri'
              }`}
              title="Flip Vertical"
            >
              <FlipVertical className="w-3.5 h-3.5" />
            </button>
            {(orientation.rotation !== 0 || orientation.flipH || orientation.flipV) && (
              <button
                type="button"
                onClick={resetOrientation}
                className="p-1 text-text-sec hover:text-amber transition-colors"
                title="Reset rotation & flip"
              >
                <RotateCcw className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Right Toolbar Group: Snapshot, Record, Audio, Telemetry HUD, Reconnect */}
        <div className="flex items-center gap-1">
          {/* Snapshot Download */}
          <button
            type="button"
            onClick={handleDownloadSnapshot}
            className="p-1.5 text-text-sec hover:text-text-pri bg-panel hover:bg-panel-raised border border-hairline rounded transition-colors"
            title="Download frame snapshot (JPEG)"
          >
            <Download className="w-3.5 h-3.5" />
          </button>

          {/* Clip Recording */}
          {!isRecording ? (
            <button
              type="button"
              onClick={startRecording}
              className="p-1.5 text-text-sec hover:text-red-400 bg-panel hover:bg-panel-raised border border-hairline rounded transition-colors"
              title="Record video clip (Max 60s)"
            >
              <Video className="w-3.5 h-3.5" />
            </button>
          ) : (
            <button
              type="button"
              onClick={stopRecording}
              className="p-1.5 text-red-400 bg-red-950/40 border border-red-500/50 rounded hover:bg-red-900/60 transition-colors animate-pulse"
              title="Stop recording"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
            </button>
          )}

          {/* Audio Mute/Unmute & Volume (Hidden if stream has no audio) */}
          {hasAudio && (
            <div className="flex items-center bg-panel border border-hairline rounded p-0.5 gap-1 group/audio">
              <button
                type="button"
                onClick={() => setIsMuted(!isMuted)}
                className={`p-1 transition-colors ${
                  isMuted ? 'text-text-muted hover:text-text-sec' : 'text-amber hover:text-amber/80'
                }`}
                title={isMuted ? 'Unmute stream' : 'Mute stream'}
              >
                {isMuted ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
              </button>
              {!isMuted && (
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={volume}
                  onChange={(e) => setVolume(Number(e.target.value))}
                  className="w-12 h-1 bg-hairline rounded appearance-none cursor-pointer accent-amber"
                  title={`Volume: ${volume}%`}
                />
              )}
            </div>
          )}

          {/* AI Detections Toggle */}
          <button
            type="button"
            onClick={() => setShowAiDetections(!showAiDetections)}
            className={`px-2 py-1 rounded border transition-colors flex items-center gap-1 font-mono text-[10px] ${
              showAiDetections
                ? 'bg-status-ok/20 text-status-ok border-status-ok/40 font-bold'
                : 'text-text-sec hover:text-text-pri bg-panel hover:bg-panel-raised border-hairline'
            }`}
            title="Toggle Live AI Detections & Bounding Overlays"
          >
            <Zap className={`w-3 h-3 ${showAiDetections ? 'text-status-ok fill-current' : 'text-text-sec'}`} />
            <span>AI DETECT: {showAiDetections ? 'ON' : 'OFF'}</span>
          </button>

          {/* Operations HUD Toggle */}
          <button
            type="button"
            onClick={() => setIsHudOpen(!isHudOpen)}
            className={`px-2 py-1 rounded border transition-colors flex items-center gap-1 font-mono text-[10px] ${
              isHudOpen
                ? 'bg-amber/20 text-amber border-amber/40 font-bold'
                : 'text-text-sec hover:text-text-pri bg-panel hover:bg-panel-raised border-hairline'
            }`}
            title="Toggle Operations HUD Panel (Tracked Entities, Real-Time Activity Log)"
          >
            <Activity className={`w-3 h-3 ${isHudOpen ? 'text-amber' : 'text-text-sec'}`} />
            <span>HUD: {isHudOpen ? 'OPEN' : 'OFF'}</span>
          </button>

          {/* Health HUD Toggle */}
          <button
            type="button"
            onClick={() => setShowHealthHud(!showHealthHud)}
            className={`p-1.5 rounded border transition-colors ${
              showHealthHud
                ? 'bg-status-ok/20 text-status-ok border-status-ok/40'
                : 'text-text-sec hover:text-text-pri bg-panel hover:bg-panel-raised border-hairline'
            }`}
            title="Toggle live telemetry overlay (Bitrate, FPS, Dropped frames)"
          >
            <Activity className="w-3.5 h-3.5" />
          </button>

          {/* Reconnect / Reload Stream */}
          <button
            type="button"
            onClick={handleReconnect}
            disabled={isReconnecting}
            className="p-1.5 text-text-sec hover:text-text-pri bg-panel hover:bg-panel-raised border border-hairline rounded transition-colors disabled:opacity-50"
            title="Manual reconnect / reload stream"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isReconnecting ? 'animate-spin text-amber' : ''}`} />
          </button>
        </div>
      </div>

      {/* ── Scan Message Banner if active ── */}
      {scanMessage && scanMessage.id === camera.cameraId && (
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

      {/* ── Actions Footer ── */}
      <div className="p-2.5 bg-panel border-t border-hairline flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => onScanNow(camera)}
          disabled={isScanning}
          className={`w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-sm font-semibold text-xs-tech transition-colors shadow-sm ${
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
};

