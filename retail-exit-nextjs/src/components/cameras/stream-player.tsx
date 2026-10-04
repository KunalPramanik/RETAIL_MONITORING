"use client";

import { safeFetch } from "@/lib/api-client";
import React, { useState, useEffect, useRef } from "react";
import RoiCanvas, { NormalizedPoint } from "./roi-canvas";
import {
  Camera as CameraIcon,
  Maximize2,
  PenTool,
  Trash2,
  Sliders,
  Users,
  Package,
  ShieldCheck,
  Video,
  Eye,
  Compass,
  ChevronUp,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Square,
  X,
} from "lucide-react";

export interface DetectionBox {
  box: [number, number, number, number]; // [x, y, w, h] normalized 0..1 or pixel coords
  type: string;
  label: string;
  confidence: number;
  color?: string;
  entity?: string;
  track_id?: string | number;
  direction?: string;
  matched_employee_id?: string;
  badge_number?: string;
  is_discrepancy?: boolean;
  is_defect?: boolean;
  defect_type?: string;
  polygon?: number[][]; // [x, y] coordinates for OBB / segmentation masks
}

interface StreamPlayerProps {
  cameraId: string;
  cameraName?: string;
  cameraIp?: string;
  streamUrl?: string;
  laneId?: string;
  initialRoi?: NormalizedPoint[] | null;
  onAlertTriggered?: (alert: any) => void;
}

export default function StreamPlayer({
  cameraId,
  cameraName = "Exit Lane Camera",
  cameraIp = "192.168.1.101",
  streamUrl = "",
  laneId = "LANE-01",
  initialRoi = null,
  onAlertTriggered,
}: StreamPlayerProps) {
  const [streamQuality, setStreamQuality] = useState<"main" | "sub">("main");
  const [isDrawingRoi, setIsDrawingRoi] = useState(false);
  const [roiPolygon, setRoiPolygon] = useState<NormalizedPoint[] | null>(initialRoi);
  const [fps, setFps] = useState(30);
  const [latencyMs, setLatencyMs] = useState(42);
  const [resolution, setResolution] = useState("1920x1080");
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(true);
  const [showPtz, setShowPtz] = useState(false);
  const [ptzMoving, setPtzMoving] = useState(false);

  // Live Metrics
  const [boxes, setBoxes] = useState<DetectionBox[]>([]);
  const [footfallIn, setFootfallIn] = useState(0);
  const [footfallOut, setFootfallOut] = useState(0);
  const [occupancy, setOccupancy] = useState(0);
  const [casesDetected, setCasesDetected] = useState(0);
  const [unitsDetected, setUnitsDetected] = useState(1);
  const [knownCount, setKnownCount] = useState(0);
  const [unknownCount, setUnknownCount] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // WebSocket Telemetry Connection to FastAPI Backend
  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimer: NodeJS.Timeout;

    const connectWebSocket = () => {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.hostname || "localhost";
      const wsUrl = `${protocol}//${host}:8000/ws/live`;

      try {
        ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setIsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "detection_update") {
              const payload = data.payload;
              if (!payload.cameraId || payload.cameraId === cameraId) {
                if (payload.boxes) setBoxes(payload.boxes);
                if (payload.totalFootfallIn !== undefined) setFootfallIn(payload.totalFootfallIn);
                if (payload.totalFootfallOut !== undefined) setFootfallOut(payload.totalFootfallOut);
                if (payload.occupancy !== undefined) setOccupancy(payload.occupancy);
                if (payload.casesDetected !== undefined) setCasesDetected(payload.casesDetected);
                if (payload.unitsDetected !== undefined) setUnitsDetected(payload.unitsDetected);

                if (payload.boxes) {
                  let known = 0;
                  let unknown = 0;
                  payload.boxes.forEach((b: any) => {
                    if (b.type === "PERSON_MATCHED") known++;
                    if (b.type === "PERSON_UNMATCHED") unknown++;
                  });
                  setKnownCount(known);
                  setUnknownCount(unknown);
                }
              }
            } else if (data.type === "new_alert" && onAlertTriggered) {
              onAlertTriggered(data.payload);
            }
          } catch (e) {
            // ignore non-json
          }
        };

        ws.onclose = () => {
          setIsConnected(false);
          reconnectTimer = setTimeout(connectWebSocket, 3000);
        };

        ws.onerror = () => {
          setIsConnected(false);
        };
      } catch (err) {
        reconnectTimer = setTimeout(connectWebSocket, 3000);
      }
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) wsRef.current.close();
      clearTimeout(reconnectTimer);
    };
  }, [cameraId, onAlertTriggered]);

  // Handle ROI saving to Backend API
  const handleSaveRoi = async (points: NormalizedPoint[]) => {
    setRoiPolygon(points);
    setIsDrawingRoi(false);
    try {
      await safeFetch(`/api/cameras/${cameraId}/roi-polygon`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ roiPolygon: points }),
      });
    } catch (err) {
      console.warn("ROI sync warning:", err);
    }
  };

  const handleClearRoi = async () => {
    setRoiPolygon(null);
    setIsDrawingRoi(false);
    try {
      await safeFetch(`/api/cameras/${cameraId}/roi-polygon`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ roiPolygon: [] }),
      });
    } catch (err) {
      // offline fallback
    }
  };

  // PTZ Control Handlers
  const handlePtzMove = async (pan: number, tilt: number, zoom: number) => {
    setPtzMoving(true);
    try {
      await safeFetch(`/api/cameras/${cameraId}/ptz/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pan, tilt, zoom, velocity: 1.0 }),
      });
    } catch (e) {
      console.warn("PTZ move failed:", e);
    }
  };

  const handlePtzStop = async () => {
    setPtzMoving(false);
    try {
      await safeFetch(`/api/cameras/${cameraId}/ptz/stop`, {
        method: "POST",
      });
    } catch (e) {
      console.warn("PTZ stop failed:", e);
    }
  };

  const handlePtzPreset = async (presetId: number) => {
    try {
      await safeFetch(`/api/cameras/${cameraId}/ptz/preset/${presetId}`, {
        method: "POST",
      });
    } catch (e) {
      console.warn(`PTZ preset ${presetId} failed:`, e);
    }
  };

  // Video Source URL (continuous stream from FastAPI)
  const videoSrc = `/api/cameras/${cameraId}/stream?raw=true&stream=${streamQuality}`;

  // Helper to match Part P.1 and CC.2 color & styling system
  const getBoxStyle = (b: DetectionBox) => {
    const rawType = (b.type || "").toUpperCase();
    const rawLabel = (b.label || "").toUpperCase();

    if (b.is_discrepancy || b.is_defect || rawType.includes("DEFECT") || rawLabel.includes("DEFECT") || rawType.includes("DISCREPANCY") || rawType.includes("SUSPICIOUS") || rawType.includes("HAZARD")) {
      return { border: "#EF4444", bg: "#EF4444", text: "#FFFFFF" }; // Red
    }
    if (rawType.includes("STATIC") || rawLabel.includes("STATIC ARTIFACT") || rawLabel.includes("IGNORED")) {
      return { border: "#64748B", bg: "#1E293B", text: "#94A3B8" }; // Slate Gray for quarantined static artifacts
    }
    if (rawLabel.includes("SMARTPHONE") || rawLabel.includes("PHONE") || rawLabel.includes("LAPTOP") || rawType.includes("ELECTRONICS")) {
      return { border: "#F97316", bg: "#F97316", text: "#000000" }; // Orange
    }
    if (rawLabel.includes("SHELF") || rawLabel.includes("BOOKCASE") || rawLabel.includes("CAR") || rawLabel.includes("VEHICLE") || rawType.includes("VEHICLE") || rawLabel.includes("DOORWAY")) {
      return { border: "#06B6D4", bg: "#06B6D4", text: "#000000" }; // Cyan
    }
    if (rawType.includes("MATCHED") || rawLabel.includes("AUTHORIZED") || rawLabel.includes("KNOWN")) {
      return { border: "#10B981", bg: "#10B981", text: "#FFFFFF" }; // Confirmed Match (Emerald)
    }
    if (rawType.includes("UNMATCHED") || rawLabel.includes("UNKNOWN") || rawLabel.includes("UNAUTHORIZED")) {
      return { border: "#EF4444", bg: "#DC2626", text: "#FFFFFF" }; // Unknown Person (Red per CC.2)
    }
    // Default retail item styling (Lime Green matching industrial spec)
    return { border: "#84CC16", bg: "#84CC16", text: "#000000" }; // Lime Green
  };

  return (
    <div className="flex flex-col bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl overflow-hidden shadow-lg transition-colors">
      {/* 1. Camera Top Bar */}
      <div className="px-4 py-2.5 bg-[var(--bg-panel-raised)] border-b border-[var(--border-hairline)] flex justify-between items-center text-xs transition-colors">
        <div className="flex items-center gap-3">
          <div
            className={`w-2.5 h-2.5 rounded-full ${
              isConnected ? "bg-[var(--status-ok)] shadow-[0_0_8px_var(--status-ok)]" : "bg-[var(--status-high)]"
            }`}
          />
          <span className="font-bold font-mono text-[var(--text-primary)] tracking-wider">{cameraId}</span>
          <span className="text-[var(--text-muted)] font-sans text-xs hidden sm:inline">{cameraName}</span>
          <span className="bg-[var(--bg-canvas)] text-[var(--data-mono-text)] px-2 py-0.5 rounded font-mono text-[11px] border border-[var(--border-hairline)]">
            {laneId}
          </span>
        </div>

        {/* 5-Level AI Pipeline Status Indicators */}
        <div className="flex items-center gap-1.5 font-mono text-[10px]">
          <span className="px-1.5 py-0.5 rounded bg-[var(--bg-panel)] text-[var(--status-ok)] border border-[var(--border-hairline)]">
            L1:DET
          </span>
          <span className="px-1.5 py-0.5 rounded bg-[var(--bg-panel)] text-[var(--status-ok)] border border-[var(--border-hairline)]">
            L2:CLS
          </span>
          <span className="px-1.5 py-0.5 rounded bg-[var(--bg-panel)] text-[var(--status-ok)] border border-[var(--border-hairline)]">
            L3:LIV
          </span>
          <span className="px-1.5 py-0.5 rounded bg-[var(--bg-panel)] text-[var(--status-ok)] border border-[var(--border-hairline)]">
            L4:MTH
          </span>
          <span className="px-1.5 py-0.5 rounded bg-[var(--bg-panel)] text-[var(--status-ok)] border border-[var(--border-hairline)]">
            L5:TRK
          </span>
        </div>
      </div>

      {/* 2. Main Video Feed & Surveillance CV HUD Area */}
      <div ref={containerRef} className="relative aspect-video bg-black w-full overflow-hidden select-none">
        {/* Continuous Stream Feed or Real-time Fallback */}
        {isStreaming ? (
          <img
            src={videoSrc}
            alt={cameraName}
            onError={() => setIsStreaming(false)}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center bg-[#12151A] text-[#8B93A1] font-mono text-xs">
            <Video size={40} className="mb-2 text-[#2C323D] animate-pulse" />
            <span className="tracking-widest text-[#B8E3D6]">RTSP STREAM MONITOR</span>
            <span className="text-[#8B93A1] text-[10px] mt-1">{cameraIp} (PORT 554)</span>
          </div>
        )}

        {/* SURVEILLANCE CV TOP BANNER (Sleek, Non-Obstructive) */}
        <div className="absolute top-2 left-2 z-30 pointer-events-none">
          <div className="bg-black/75 backdrop-blur-sm px-2.5 py-0.5 rounded border border-yellow-500/30 shadow-lg font-mono text-[10px] font-bold text-[#FACC15] tracking-wider flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>
              SURVEILLANCE CV // ACTIVE // DETECTIONS: {boxes.length} (CASES: {casesDetected} UNITS: {unitsDetected})
            </span>
          </div>
        </div>

        {/* Solid Pinned Badges with CC.2 Strict Bracketed Format & Oriented Polygons */}
        <div className="absolute inset-0 pointer-events-none z-20">
          {/* SVG layer for Oriented Bounding Boxes (OBB) & instance segmentation masks */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none">
            {boxes.map((b, idx) => {
              if (!b.polygon || b.polygon.length < 3) return null;
              const style = getBoxStyle(b);
              const pointsStr = b.polygon
                .map(([x, y]) => {
                  const px = x <= 1.0 ? x * 100 : (x / (resolution.includes("1920") ? 1920 : 1280)) * 100;
                  const py = y <= 1.0 ? y * 100 : (y / (resolution.includes("1080") ? 1080 : 720)) * 100;
                  return `${px}%,${py}%`;
                })
                .join(" ");
              return (
                <polygon
                  key={`poly-${idx}`}
                  points={pointsStr}
                  fill={style.bg}
                  fillOpacity={0.25}
                  stroke={style.border}
                  strokeWidth={2}
                  strokeLinejoin="round"
                />
              );
            })}
          </svg>

          {boxes.map((b, idx) => {
            const rawType = (b.type || "").toUpperCase();
            const rawLabel = (b.label || "").toUpperCase();
            // Suppress phantom Canny wall frames unless it's a quarantined static artifact
            if (rawType === "WALL_PICTURE" && !rawLabel.includes("STATIC ARTIFACT")) {
              return null;
            }

            const style = getBoxStyle(b);
            const leftPct = `${b.box[0] * 100}%`;
            const topPct = `${b.box[1] * 100}%`;
            const widthPct = `${b.box[2] * 100}%`;
            const heightPct = `${b.box[3] * 100}%`;

            // Strict CC.2 Bracketed Label Construction
            let cleanTag = (b.label || "").trim();
            if (!cleanTag.startsWith("[")) {
              const confPct = typeof b.confidence === "number" ? `${(b.confidence * 100).toFixed(0)}%` : "";
              const trackId = b.track_id ? ` ID:${b.track_id}` : ` ID:${idx + 1}`;
              const baseName = cleanTag.replace(/\s*\(\d+%\)/g, "").trim();
              cleanTag = `[${baseName} ${confPct}${trackId}]`;
            }
            const badgePlacement = b.box[1] < 0.08 ? "top-0 left-0" : "-top-5 left-0";

            return (
              <div
                key={idx}
                className="absolute transition-all duration-100 ease-out"
                style={{
                  left: leftPct,
                  top: topPct,
                  width: widthPct,
                  height: heightPct,
                  border: `2px solid ${style.border}`,
                }}
              >
                <div
                  className={`absolute ${badgePlacement} px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider font-mono shadow-md flex items-center gap-1 whitespace-nowrap rounded-sm`}
                  style={{
                    backgroundColor: style.bg,
                    color: style.text,
                  }}
                >
                  <span>{cleanTag}</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Interactive ROI Polygon Layer */}
        <RoiCanvas
          isDrawing={isDrawingRoi}
          existingPolygon={roiPolygon}
          onSave={handleSaveRoi}
          onCancel={() => setIsDrawingRoi(false)}
        />

        {/* PTZ Interactive Overlay Modal */}
        {showPtz && (
          <div className="absolute bottom-3 right-3 z-30 bg-[#12151A]/90 backdrop-blur-md p-3 rounded-xl border border-[#2C323D] shadow-2xl flex flex-col gap-2">
            <div className="flex justify-between items-center pb-1 border-b border-[#2C323D] text-[10px] font-mono text-[#E7E9EC]">
              <span className="font-bold flex items-center gap-1 text-[#38BDF8]">
                <Compass size={12} /> PTZ CONTROLLER
              </span>
              <button onClick={() => setShowPtz(false)} className="text-[#8B93A1] hover:text-white">
                <X size={12} />
              </button>
            </div>

            {/* D-Pad */}
            <div className="grid grid-cols-3 gap-1 w-28 mx-auto">
              <div></div>
              <button
                onMouseDown={() => handlePtzMove(0, 1, 0)}
                onMouseUp={handlePtzStop}
                className="p-1.5 bg-[#20252F] hover:bg-blue-600 text-white rounded flex justify-center items-center transition-colors"
                title="Tilt Up"
              >
                <ChevronUp size={16} />
              </button>
              <div></div>

              <button
                onMouseDown={() => handlePtzMove(-1, 0, 0)}
                onMouseUp={handlePtzStop}
                className="p-1.5 bg-[#20252F] hover:bg-blue-600 text-white rounded flex justify-center items-center transition-colors"
                title="Pan Left"
              >
                <ChevronLeft size={16} />
              </button>
              <button
                onClick={handlePtzStop}
                className="p-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded flex justify-center items-center transition-colors"
                title="Stop Motion"
              >
                <Square size={12} />
              </button>
              <button
                onMouseDown={() => handlePtzMove(1, 0, 0)}
                onMouseUp={handlePtzStop}
                className="p-1.5 bg-[#20252F] hover:bg-blue-600 text-white rounded flex justify-center items-center transition-colors"
                title="Pan Right"
              >
                <ChevronRight size={16} />
              </button>

              <div></div>
              <button
                onMouseDown={() => handlePtzMove(0, -1, 0)}
                onMouseUp={handlePtzStop}
                className="p-1.5 bg-[#20252F] hover:bg-blue-600 text-white rounded flex justify-center items-center transition-colors"
                title="Tilt Down"
              >
                <ChevronDown size={16} />
              </button>
              <div></div>
            </div>

            {/* Zoom Controls */}
            <div className="flex gap-1 pt-1 border-t border-[#2C323D]">
              <button
                onMouseDown={() => handlePtzMove(0, 0, 1)}
                onMouseUp={handlePtzStop}
                className="flex-1 py-1 bg-[#20252F] hover:bg-blue-600 text-white text-[10px] font-mono rounded flex justify-center items-center gap-1 transition-colors"
              >
                <ZoomIn size={12} /> In
              </button>
              <button
                onMouseDown={() => handlePtzMove(0, 0, -1)}
                onMouseUp={handlePtzStop}
                className="flex-1 py-1 bg-[#20252F] hover:bg-blue-600 text-white text-[10px] font-mono rounded flex justify-center items-center gap-1 transition-colors"
              >
                <ZoomOut size={12} /> Out
              </button>
            </div>

            {/* Presets */}
            <div className="grid grid-cols-4 gap-1 text-[9px] font-mono">
              {[1, 2, 3, 4].map((p) => (
                <button
                  key={p}
                  onClick={() => handlePtzPreset(p)}
                  className="py-1 bg-[#20252F] hover:bg-[#38BDF8] hover:text-black text-[#B8E3D6] rounded font-bold transition-colors"
                >
                  P{p}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 4. Live Sensor Verification Strip */}
      <div className="p-2.5 bg-[var(--bg-panel)] grid grid-cols-2 md:grid-cols-4 gap-2 text-xs transition-colors">
        {/* Footfall Counters */}
        <div className="bg-[var(--bg-canvas)] p-2 rounded-lg border border-[var(--border-hairline)] flex flex-col justify-between min-w-0 overflow-hidden transition-colors">
          <div className="text-[10px] text-[var(--text-muted)] font-mono flex items-center gap-1 truncate">
            <Users size={12} className="text-[#38BDF8] shrink-0" />
            <span className="truncate">FOOTFALL (IN/OUT)</span>
          </div>
          <div className="text-xs sm:text-sm font-bold font-mono mt-0.5 truncate">
            <span className="text-[var(--status-ok)]">+{footfallIn}</span>
            <span className="text-[var(--border-hairline)] mx-1">/</span>
            <span className="text-[var(--status-high)]">-{footfallOut}</span>
          </div>
        </div>

        {/* Live Detected Count */}
        <div className="bg-[var(--bg-canvas)] p-2 rounded-lg border border-[var(--border-hairline)] flex flex-col justify-between min-w-0 overflow-hidden transition-colors">
          <div className="text-[10px] text-[var(--text-muted)] font-mono flex items-center gap-1 truncate">
            <Package size={12} className="text-[var(--signal-amber)] shrink-0" />
            <span className="truncate">CASES / UNITS</span>
          </div>
          <div className="text-xs sm:text-sm font-bold font-mono mt-0.5 truncate">
            <span className="text-[var(--text-primary)]">{casesDetected} Cases</span>
            <span className="text-[var(--border-hairline)] mx-1">|</span>
            <span className="text-[var(--status-ok)]">{unitsDetected} U</span>
          </div>
        </div>

        {/* Identity Recognition */}
        <div className="bg-[var(--bg-canvas)] p-2 rounded-lg border border-[var(--border-hairline)] flex flex-col justify-between min-w-0 overflow-hidden transition-colors">
          <div className="text-[10px] text-[var(--text-muted)] font-mono flex items-center gap-1 truncate">
            <ShieldCheck size={12} className="text-[var(--status-ok)] shrink-0" />
            <span className="truncate">BIOMETRIC MATCH</span>
          </div>
          <div className="text-xs sm:text-sm font-bold font-mono mt-0.5 flex items-center gap-1 truncate">
            <span className="text-[var(--status-ok)] whitespace-nowrap">{knownCount} Known</span>
            <span className="text-[var(--border-hairline)]">|</span>
            <span className="text-[#38BDF8] whitespace-nowrap">{unknownCount} Guest</span>
          </div>
        </div>

        {/* Tripwire Status */}
        <div className="bg-[var(--bg-canvas)] p-2 rounded-lg border border-[var(--border-hairline)] flex flex-col justify-between min-w-0 overflow-hidden transition-colors">
          <div className="text-[10px] text-[var(--text-muted)] font-mono flex items-center gap-1 truncate">
            <Sliders size={12} className="text-[#A78BFA] shrink-0" />
            <span className="truncate">VIRTUAL TRIPWIRE</span>
          </div>
          <div className="text-xs sm:text-sm font-bold font-mono mt-0.5 truncate">
            {roiPolygon && roiPolygon.length > 0 ? (
              <span className="text-[#A78BFA] truncate">ACTIVE ({roiPolygon.length} PTS)</span>
            ) : (
              <span className="text-[var(--text-muted)] truncate">UNCONFIGURED</span>
            )}
          </div>
        </div>
      </div>

      {/* 5. Bottom Action Controls Bar */}
      <div className="px-4 py-2 bg-[var(--bg-panel-raised)] border-t border-[var(--border-hairline)] flex flex-wrap justify-between items-center gap-2 transition-colors">
        {/* Left: ROI / Tripwire Editing Controls */}
        <div className="flex items-center gap-2">
          {isDrawingRoi ? (
            <div className="flex items-center gap-2">
              <span className="text-xs text-[var(--signal-amber)] font-mono animate-pulse">
                Click canvas to place points. Double-click to save.
              </span>
              <button
                onClick={() => setIsDrawingRoi(false)}
                className="px-2.5 py-1 text-xs bg-[var(--bg-panel)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded font-medium border border-[var(--border-hairline)]"
              >
                Cancel
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsDrawingRoi(true)}
                className="px-3 py-1 text-xs bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded font-medium flex items-center gap-1.5 shadow transition-colors"
              >
                <PenTool size={13} /> Draw ROI Polygon
              </button>

              <button
                onClick={() => setShowPtz(!showPtz)}
                className={`px-3 py-1 text-xs rounded font-medium flex items-center gap-1.5 border transition-colors ${
                  showPtz
                    ? "bg-[#38BDF8] text-black border-[#38BDF8] font-bold"
                    : "bg-[var(--bg-panel)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border-[var(--border-hairline)]"
                }`}
              >
                <Compass size={13} /> PTZ Controller
              </button>

              {roiPolygon && roiPolygon.length > 0 && (
                <button
                  onClick={handleClearRoi}
                  className="px-2.5 py-1 text-xs bg-[var(--bg-panel)] hover:bg-rose-950 text-[var(--text-muted)] hover:text-[var(--status-high)] border border-[var(--border-hairline)] hover:border-[var(--status-high)] rounded flex items-center gap-1 transition-colors"
                >
                  <Trash2 size={13} /> Clear ROI
                </button>
              )}
            </div>
          )}
        </div>

        {/* Right: Stream Quality & Tools */}
        <div className="flex items-center gap-2">
          <div className="bg-[var(--bg-canvas)] border border-[var(--border-hairline)] p-0.5 rounded flex items-center text-[11px] font-mono">
            <button
              onClick={() => setStreamQuality("main")}
              className={`px-2 py-0.5 rounded transition-colors ${
                streamQuality === "main" ? "bg-[#2563EB] text-white font-bold" : "text-[var(--text-muted)]"
              }`}
            >
              MAIN (1080p)
            </button>
            <button
              onClick={() => setStreamQuality("sub")}
              className={`px-2 py-0.5 rounded transition-colors ${
                streamQuality === "sub" ? "bg-[#2563EB] text-white font-bold" : "text-[var(--text-muted)]"
              }`}
            >
              SUB (480p)
            </button>
          </div>

          <button
            onClick={() => {
              if (containerRef.current) {
                if (document.fullscreenElement) {
                  document.exitFullscreen();
                } else {
                  containerRef.current.requestFullscreen();
                }
              }
            }}
            className="p-1.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-panel-hover)] rounded transition-colors"
            title="Toggle Fullscreen"
          >
            <Maximize2 size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
