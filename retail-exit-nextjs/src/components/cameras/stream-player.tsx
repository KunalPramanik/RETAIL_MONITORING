"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import RoiCanvas, { NormalizedPoint } from "./roi-canvas";
import {
  Camera as CameraIcon,
  Maximize2,
  PenTool,
  Trash2,
  RefreshCw,
  Sliders,
  Radio,
  ArrowUpRight,
  ArrowDownLeft,
  Users,
  Package,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  Video,
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
  const [latencyMs, setLatencyMs] = useState(45);
  const [resolution, setResolution] = useState("1920x1080");
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(true);

  // Live Metrics
  const [boxes, setBoxes] = useState<DetectionBox[]>([]);
  const [footfallIn, setFootfallIn] = useState(0);
  const [footfallOut, setFootfallOut] = useState(0);
  const [occupancy, setOccupancy] = useState(0);
  const [casesDetected, setCasesDetected] = useState(0);
  const [unitsDetected, setUnitsDetected] = useState(0);
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

                // Calculate known vs unknown counts
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
      const res = await fetch(`http://localhost:8000/api/cameras/${cameraId}/roi-polygon`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ roiPolygon: points }),
      });
      if (!res.ok) {
        // Also sync to tripwire API if 2 points
        if (points.length === 2) {
          await fetch(`http://localhost:8000/api/tripwire/configs`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              cameraId,
              label: `${cameraName} Exit Boundary`,
              lineCoords: [
                [points[0].x, points[0].y],
                [points[1].x, points[1].y],
              ],
              directionMode: "BIDIRECTIONAL",
              active: true,
            }),
          });
        }
      }
    } catch (err) {
      console.warn("ROI sync error, saved locally:", err);
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

  // Latency Color Helper
  const getLatencyColor = (ms: number) => {
    if (ms < 150) return "text-emerald-400";
    if (ms <= 300) return "text-amber-400";
    return "text-rose-500 animate-pulse";
  };

  // Video Source URL (MJPEG continuous stream from FastAPI)
  const videoSrc = `http://localhost:8000/api/cameras/${cameraId}/stream?raw=true&stream=${streamQuality}`;

  return (
    <div className="flex flex-col bg-gray-950 border border-gray-800 rounded-xl overflow-hidden shadow-2xl transition-all">
      {/* 1. Camera Top Bar */}
      <div className="px-4 py-3 bg-gray-900 border-b border-gray-800 flex justify-between items-center text-xs">
        <div className="flex items-center gap-3">
          <div
            className={`w-2.5 h-2.5 rounded-full ${
              isConnected ? "bg-emerald-500 animate-pulse" : "bg-rose-500"
            }`}
          />
          <span className="font-bold font-mono text-gray-200">{cameraId}</span>
          <span className="text-gray-400 font-sans hidden sm:inline">({cameraName})</span>
          <span className="bg-gray-800 text-gray-400 px-2 py-0.5 rounded font-mono text-[11px]">
            {laneId}
          </span>
        </div>

        {/* 5-Level AI Pipeline Indicators (Part CC.2.1) */}
        <div className="flex items-center gap-1.5 font-mono text-[10px]">
          <span className="px-1.5 py-0.5 rounded bg-blue-950 text-blue-400 border border-blue-900">
            DETECT: ON
          </span>
          <span className="px-1.5 py-0.5 rounded bg-indigo-950 text-indigo-400 border border-indigo-900">
            CLASSIFY: ON
          </span>
          <span className="px-1.5 py-0.5 rounded bg-teal-950 text-teal-400 border border-teal-900">
            LIVENESS: ON
          </span>
          <span className="px-1.5 py-0.5 rounded bg-amber-950 text-amber-400 border border-amber-900">
            MATH: ON
          </span>
          <span className="px-1.5 py-0.5 rounded bg-purple-950 text-purple-400 border border-purple-900">
            TRACK: ON
          </span>
        </div>
      </div>

      {/* 2. Main Video Feed & HUD Area */}
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
          <div className="w-full h-full flex flex-col items-center justify-center bg-gray-950 text-gray-600 font-mono text-xs">
            <Video size={40} className="mb-2 text-gray-700 animate-pulse" />
            <span>CONNECTING RTSP MEDIA SERVER...</span>
            <span className="text-gray-700 text-[10px] mt-1">{cameraIp} (PORT 554)</span>
          </div>
        )}

        {/* HUD Top-Left Stats (Part CC.2.1) */}
        <div className="absolute top-3 left-3 z-30 flex flex-col gap-1 text-[11px] font-mono pointer-events-none">
          <div className="bg-black/75 backdrop-blur-md px-2.5 py-1 rounded border border-gray-800 text-gray-300 flex items-center gap-2">
            <span>{cameraIp}</span>
            <span className="text-gray-600">|</span>
            <span>{resolution}</span>
            <span className="text-gray-600">|</span>
            <span className="text-blue-400">{fps} FPS</span>
            <span className="text-gray-600">|</span>
            <span className={getLatencyColor(latencyMs)}>{latencyMs}ms</span>
          </div>
        </div>

        {/* Live Detected Bounding Boxes HUD (Part CC.2.1) */}
        {!isDrawingRoi &&
          boxes.map((b, i) => {
            const [x, y, w, h] = b.box;
            // Normalize against 1280x720 baseline if pixels provided
            const leftPct = (x / 1280) * 100;
            const topPct = (y / 720) * 100;
            const widthPct = (w / 1280) * 100;
            const heightPct = (h / 720) * 100;

            const isPerson = b.type.includes("PERSON");
            const isMatched = b.type === "PERSON_MATCHED";
            const isDiscrepancy = b.is_discrepancy || b.type.includes("DISCREPANCY") || b.type.includes("SUSPICIOUS");

            const boxBorderColor = isDiscrepancy
              ? "border-rose-500 animate-pulse shadow-rose-900/50 shadow-lg"
              : isMatched
              ? "border-emerald-500"
              : isPerson
              ? "border-blue-500"
              : "border-amber-500";

            const tagBg = isDiscrepancy
              ? "bg-rose-600"
              : isMatched
              ? "bg-emerald-600"
              : isPerson
              ? "bg-blue-600"
              : "bg-amber-600";

            return (
              <div
                key={i}
                className={`absolute border-2 ${boxBorderColor} transition-all duration-150 pointer-events-none`}
                style={{
                  left: `${leftPct}%`,
                  top: `${topPct}%`,
                  width: `${widthPct}%`,
                  height: `${heightPct}%`,
                }}
              >
                {/* HUD Tag Pill */}
                <div
                  className={`absolute -top-6 left-[-2px] ${tagBg} text-white font-mono text-[10px] font-bold px-1.5 py-0.5 rounded-t flex items-center gap-1.5 whitespace-nowrap shadow`}
                >
                  {isMatched && <CheckCircle2 size={11} className="text-emerald-200" />}
                  {isPerson && !isMatched && <HelpCircle size={11} className="text-blue-200" />}
                  {isDiscrepancy && <AlertTriangle size={11} className="text-rose-200 animate-bounce" />}
                  <span>{b.label || b.type}</span>
                  {b.confidence && <span>{Math.round(b.confidence * 100)}%</span>}
                  {b.track_id && <span className="opacity-80">#{b.track_id}</span>}
                </div>

                {/* Vector Direction Indicator */}
                {b.direction && (
                  <div className="absolute bottom-1 right-1 bg-black/80 px-1 py-0.5 rounded text-[9px] font-mono text-emerald-400 flex items-center gap-0.5">
                    {b.direction === "EXIT" ? <ArrowUpRight size={10} /> : <ArrowDownLeft size={10} />}
                    {b.direction}
                  </div>
                )}
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
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 p-3 bg-gray-900/90 border-t border-gray-800 text-xs">
        {/* Footfall IN / OUT */}
        <div className="bg-gray-950 p-2 rounded border border-gray-800 flex items-center justify-between">
          <div>
            <div className="text-[10px] text-gray-500 font-mono flex items-center gap-1">
              <Users size={12} className="text-blue-400" /> FOOTFALL IN/OUT
            </div>
            <div className="text-sm font-bold font-mono mt-0.5 flex gap-2">
              <span className="text-emerald-400">+{footfallIn}</span>
              <span className="text-gray-600">/</span>
              <span className="text-rose-400">-{footfallOut}</span>
            </div>
          </div>
          <div className="text-[10px] text-gray-400 font-mono text-right">
            <span>OCC:</span> <b className="text-white">{occupancy}</b>
          </div>
        </div>

        {/* Inventory Units & Cases */}
        <div className="bg-gray-950 p-2 rounded border border-gray-800 flex items-center justify-between">
          <div>
            <div className="text-[10px] text-gray-500 font-mono flex items-center gap-1">
              <Package size={12} className="text-amber-400" /> PACK COUNTING
            </div>
            <div className="text-sm font-bold font-mono mt-0.5 flex gap-2">
              <span className="text-amber-300">{casesDetected} Cases</span>
              <span className="text-gray-600">|</span>
              <span className="text-white">{unitsDetected} U</span>
            </div>
          </div>
        </div>

        {/* Identity Recognition */}
        <div className="bg-gray-950 p-2 rounded border border-gray-800 flex items-center justify-between">
          <div>
            <div className="text-[10px] text-gray-500 font-mono flex items-center gap-1">
              <ShieldCheck size={12} className="text-emerald-400" /> BIOMETRIC MATCH
            </div>
            <div className="text-sm font-bold font-mono mt-0.5 flex gap-2">
              <span className="text-emerald-400">{knownCount} Known</span>
              <span className="text-gray-600">|</span>
              <span className="text-blue-400">{unknownCount} Guest</span>
            </div>
          </div>
        </div>

        {/* Tripwire Status */}
        <div className="bg-gray-950 p-2 rounded border border-gray-800 flex items-center justify-between">
          <div>
            <div className="text-[10px] text-gray-500 font-mono flex items-center gap-1">
              <Sliders size={12} className="text-purple-400" /> VIRTUAL TRIPWIRE
            </div>
            <div className="text-sm font-bold font-mono mt-0.5">
              {roiPolygon && roiPolygon.length > 0 ? (
                <span className="text-purple-400">ACTIVE ({roiPolygon.length} PTS)</span>
              ) : (
                <span className="text-gray-500">UNCONFIGURED</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 5. Bottom Action Controls Bar (Part CC.2.1) */}
      <div className="px-4 py-2.5 bg-gray-950 border-t border-gray-800 flex flex-wrap justify-between items-center gap-2">
        {/* Left: ROI / Tripwire Editing Controls */}
        <div className="flex items-center gap-2">
          {isDrawingRoi ? (
            <div className="flex items-center gap-2">
              <span className="text-xs text-amber-400 font-mono animate-pulse">
                Click canvas to place points. Double-click to save.
              </span>
              <button
                onClick={() => setIsDrawingRoi(false)}
                className="px-2.5 py-1 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded font-medium"
              >
                Cancel
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsDrawingRoi(true)}
                className="px-3 py-1 text-xs bg-blue-600 hover:bg-blue-500 text-white rounded font-medium flex items-center gap-1.5 shadow transition-colors"
              >
                <PenTool size={13} /> Draw ROI Polygon
              </button>

              {roiPolygon && roiPolygon.length > 0 && (
                <button
                  onClick={handleClearRoi}
                  className="px-2.5 py-1 text-xs bg-gray-900 hover:bg-rose-950 text-gray-400 hover:text-rose-400 border border-gray-800 hover:border-rose-900 rounded flex items-center gap-1 transition-colors"
                >
                  <Trash2 size={13} /> Clear ROI
                </button>
              )}
            </div>
          )}
        </div>

        {/* Right: Stream Quality & Tools */}
        <div className="flex items-center gap-2">
          {/* Quality Toggle */}
          <div className="bg-gray-900 border border-gray-800 p-0.5 rounded flex items-center text-[11px] font-mono">
            <button
              onClick={() => setStreamQuality("main")}
              className={`px-2 py-0.5 rounded transition-colors ${
                streamQuality === "main" ? "bg-blue-600 text-white font-bold" : "text-gray-400"
              }`}
            >
              MAIN (1080p)
            </button>
            <button
              onClick={() => setStreamQuality("sub")}
              className={`px-2 py-0.5 rounded transition-colors ${
                streamQuality === "sub" ? "bg-blue-600 text-white font-bold" : "text-gray-400"
              }`}
            >
              SUB (480p)
            </button>
          </div>

          {/* Fullscreen */}
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
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded transition-colors"
            title="Toggle Fullscreen"
          >
            <Maximize2 size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
