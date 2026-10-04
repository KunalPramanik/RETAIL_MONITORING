"use client";

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
} from "lucide-react";

export interface DetectionBox {
  box: [number, number, number, number]; // [x, y, w, h]
  type: string;
  label: string;
  confidence: number;
  color?: string;
  entity?: string;
  track_id?: string | number;
  direction?: string;
  matched_employee_id?: string;
  is_discrepancy?: boolean;
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
      await fetch(`http://localhost:8000/api/cameras/${cameraId}/roi-polygon`, {
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
      await fetch(`http://localhost:8000/api/cameras/${cameraId}/roi-polygon`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ roiPolygon: [] }),
      });
    } catch (err) {
      // offline fallback
    }
  };

  // Video Source URL (continuous stream from FastAPI)
  const videoSrc = `http://localhost:8000/api/cameras/${cameraId}/stream?raw=true&stream=${streamQuality}`;

  // Helper to match the reference image's color styling
  const getBoxStyle = (b: DetectionBox) => {
    const rawType = (b.type || "").toUpperCase();
    const rawLabel = (b.label || "").toUpperCase();

    if (b.is_discrepancy || rawType.includes("DISCREPANCY") || rawType.includes("SUSPICIOUS") || rawType.includes("HAZARD")) {
      return { border: "#EF4444", bg: "#EF4444", text: "#FFFFFF" }; // Red
    }
    if (rawLabel.includes("SMARTPHONE") || rawLabel.includes("PHONE") || rawLabel.includes("LAPTOP") || rawType.includes("ELECTRONICS")) {
      return { border: "#F97316", bg: "#F97316", text: "#000000" }; // Orange
    }
    if (rawLabel.includes("SHELF") || rawLabel.includes("BOOKCASE") || rawLabel.includes("CAR") || rawLabel.includes("VEHICLE") || rawType.includes("VEHICLE")) {
      return { border: "#06B6D4", bg: "#06B6D4", text: "#000000" }; // Cyan
    }
    if (rawType === "STATIC_IMAGE" || rawLabel.includes("STATIC")) {
      return { border: "#6B7280", bg: "#374151", text: "#D1D5DB" }; // Grey
    }
    // Default person / item styling (Lime Green matching user's image)
    return { border: "#84CC16", bg: "#84CC16", text: "#000000" }; // Lime Green
  };

  return (
    <div className="flex flex-col bg-[#1A1E26] border border-[#2C323D] rounded-xl overflow-hidden shadow-2xl transition-all">
      {/* 1. Camera Top Bar */}
      <div className="px-4 py-2.5 bg-[#12151A] border-b border-[#2C323D] flex justify-between items-center text-xs">
        <div className="flex items-center gap-3">
          <div
            className={`w-2.5 h-2.5 rounded-full ${
              isConnected ? "bg-[#4FD1B3] shadow-[0_0_8px_#4FD1B3]" : "bg-[#E5484D]"
            }`}
          />
          <span className="font-bold font-mono text-[#E7E9EC] tracking-wider">{cameraId}</span>
          <span className="text-[#8B93A1] font-sans text-xs hidden sm:inline">{cameraName}</span>
          <span className="bg-[#20252F] text-[#B8E3D6] px-2 py-0.5 rounded font-mono text-[11px] border border-[#2C323D]">
            {laneId}
          </span>
        </div>

        {/* 5-Level AI Pipeline Status Indicators */}
        <div className="flex items-center gap-1.5 font-mono text-[10px]">
          <span className="px-1.5 py-0.5 rounded bg-[#1A2634] text-[#4FD1B3] border border-[#2C323D]">
            L1:DET
          </span>
          <span className="px-1.5 py-0.5 rounded bg-[#1A2634] text-[#4FD1B3] border border-[#2C323D]">
            L2:CLS
          </span>
          <span className="px-1.5 py-0.5 rounded bg-[#1A2634] text-[#4FD1B3] border border-[#2C323D]">
            L3:LIV
          </span>
          <span className="px-1.5 py-0.5 rounded bg-[#1A2634] text-[#4FD1B3] border border-[#2C323D]">
            L4:MTH
          </span>
          <span className="px-1.5 py-0.5 rounded bg-[#1A2634] text-[#4FD1B3] border border-[#2C323D]">
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

        {/* SURVEILLANCE CV TOP BANNER (Exact Match to User Reference Photo) */}
        <div className="absolute top-2 left-2 z-30 pointer-events-none">
          <div className="bg-black px-3 py-1 border border-black shadow-lg font-mono text-[11px] md:text-xs font-bold text-[#FACC15] tracking-widest flex items-center gap-2">
            <span>
              SURVEILLANCE CV // DETECTIONS: {boxes.length} (CASES:{casesDetected} UNITS:{unitsDetected}) // ACTIVE :
            </span>
          </div>
        </div>

        {/* Live Detected Bounding Boxes with Solid Tag Badges (Exact Image Match) */}
        {!isDrawingRoi &&
          boxes.map((b, i) => {
            const [x, y, w, h] = b.box;
            const leftPct = (x / 1280) * 100;
            const topPct = (y / 720) * 100;
            const widthPct = (w / 1280) * 100;
            const heightPct = (h / 720) * 100;

            const style = getBoxStyle(b);
            const confPct = b.confidence ? Math.round(b.confidence * 100) : 90;
            const displayLabel = `${b.label || b.type} ${confPct}%`;

            return (
              <div
                key={i}
                className="absolute transition-all duration-150 pointer-events-none"
                style={{
                  left: `${leftPct}%`,
                  top: `${topPct}%`,
                  width: `${widthPct}%`,
                  height: `${heightPct}%`,
                  border: `2px solid ${style.border}`,
                }}
              >
                {/* Solid Rectangular Label Attached to Box (Image Match) */}
                <div
                  className="absolute -top-[19px] left-[-2px] px-1.5 py-0.5 font-mono text-[10px] md:text-[11px] font-black uppercase tracking-wider whitespace-nowrap shadow"
                  style={{
                    backgroundColor: style.bg,
                    color: style.text,
                  }}
                >
                  {displayLabel}
                </div>
              </div>
            );
          })}

        {/* 3. Interactive ROI / Tripwire Canvas */}
        <RoiCanvas
          width={800}
          height={450}
          isDrawingMode={isDrawingRoi}
          existingPolygon={roiPolygon}
          onPolygonComplete={handleSaveRoi}
          onCancel={() => setIsDrawingRoi(false)}
        />
      </div>

      {/* 4. Real-Time Side-by-Side Counters & Telemetry Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 p-3 bg-[#12151A] border-t border-[#2C323D] text-xs">
        {/* Footfall IN / OUT */}
        <div className="bg-[#1A1E26] p-2.5 rounded-lg border border-[#2C323D] flex items-center justify-between">
          <div>
            <div className="text-[10px] text-[#8B93A1] font-mono flex items-center gap-1">
              <Users size={12} className="text-[#38BDF8]" /> FOOTFALL IN/OUT
            </div>
            <div className="text-sm font-bold font-mono mt-0.5 flex gap-2">
              <span className="text-[#4FD1B3]">+{footfallIn}</span>
              <span className="text-[#8B93A1]">/</span>
              <span className="text-[#E5484D]">-{footfallOut}</span>
            </div>
          </div>
          <div className="text-[10px] text-[#8B93A1] font-mono text-right">
            <span>OCC:</span> <b className="text-[#E7E9EC]">{occupancy}</b>
          </div>
        </div>

        {/* Inventory Units & Cases */}
        <div className="bg-[#1A1E26] p-2.5 rounded-lg border border-[#2C323D] flex items-center justify-between">
          <div>
            <div className="text-[10px] text-[#8B93A1] font-mono flex items-center gap-1">
              <Package size={12} className="text-[#E8A33D]" /> PACK COUNTING
            </div>
            <div className="text-sm font-bold font-mono mt-0.5 flex gap-2">
              <span className="text-[#E8A33D]">{casesDetected} Cases</span>
              <span className="text-[#2C323D]">|</span>
              <span className="text-[#E7E9EC]">{unitsDetected} U</span>
            </div>
          </div>
        </div>

        {/* Identity Recognition */}
        <div className="bg-[#1A1E26] p-2.5 rounded-lg border border-[#2C323D] flex items-center justify-between">
          <div>
            <div className="text-[10px] text-[#8B93A1] font-mono flex items-center gap-1">
              <ShieldCheck size={12} className="text-[#4FD1B3]" /> BIOMETRIC MATCH
            </div>
            <div className="text-sm font-bold font-mono mt-0.5 flex gap-2">
              <span className="text-[#4FD1B3]">{knownCount} Known</span>
              <span className="text-[#2C323D]">|</span>
              <span className="text-[#38BDF8]">{unknownCount} Guest</span>
            </div>
          </div>
        </div>

        {/* Tripwire Status */}
        <div className="bg-[#1A1E26] p-2.5 rounded-lg border border-[#2C323D] flex items-center justify-between">
          <div>
            <div className="text-[10px] text-[#8B93A1] font-mono flex items-center gap-1">
              <Sliders size={12} className="text-[#A78BFA]" /> VIRTUAL TRIPWIRE
            </div>
            <div className="text-sm font-bold font-mono mt-0.5">
              {roiPolygon && roiPolygon.length > 0 ? (
                <span className="text-[#A78BFA]">ACTIVE ({roiPolygon.length} PTS)</span>
              ) : (
                <span className="text-[#8B93A1]">UNCONFIGURED</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 5. Bottom Action Controls Bar */}
      <div className="px-4 py-2 bg-[#1A1E26] border-t border-[#2C323D] flex flex-wrap justify-between items-center gap-2">
        {/* Left: ROI / Tripwire Editing Controls */}
        <div className="flex items-center gap-2">
          {isDrawingRoi ? (
            <div className="flex items-center gap-2">
              <span className="text-xs text-[#E8A33D] font-mono animate-pulse">
                Click canvas to place points. Double-click to save.
              </span>
              <button
                onClick={() => setIsDrawingRoi(false)}
                className="px-2.5 py-1 text-xs bg-[#20252F] hover:bg-[#2C323D] text-[#E7E9EC] rounded font-medium border border-[#2C323D]"
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

              {roiPolygon && roiPolygon.length > 0 && (
                <button
                  onClick={handleClearRoi}
                  className="px-2.5 py-1 text-xs bg-[#1A1E26] hover:bg-[#451A1A] text-[#8B93A1] hover:text-[#E5484D] border border-[#2C323D] hover:border-[#E5484D] rounded flex items-center gap-1 transition-colors"
                >
                  <Trash2 size={13} /> Clear ROI
                </button>
              )}
            </div>
          )}
        </div>

        {/* Right: Stream Quality & Tools */}
        <div className="flex items-center gap-2">
          <div className="bg-[#12151A] border border-[#2C323D] p-0.5 rounded flex items-center text-[11px] font-mono">
            <button
              onClick={() => setStreamQuality("main")}
              className={`px-2 py-0.5 rounded transition-colors ${
                streamQuality === "main" ? "bg-[#2563EB] text-white font-bold" : "text-[#8B93A1]"
              }`}
            >
              MAIN (1080p)
            </button>
            <button
              onClick={() => setStreamQuality("sub")}
              className={`px-2 py-0.5 rounded transition-colors ${
                streamQuality === "sub" ? "bg-[#2563EB] text-white font-bold" : "text-[#8B93A1]"
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
            className="p-1.5 text-[#8B93A1] hover:text-[#E7E9EC] hover:bg-[#20252F] rounded transition-colors"
            title="Toggle Fullscreen"
          >
            <Maximize2 size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
