"use client";

import { safeFetch, getWsUrl } from "@/lib/api-client";
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
  History,
  Image as ImageIcon,
  CheckCircle,
  XCircle,
  RefreshCw,
  Download,
  AlertCircle,
  Check,
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

interface DetectionHistoryItem {
  detectionId: string;
  eventId?: string;
  cameraId: string;
  cameraLabel?: string;
  timestamp: string;
  eventType: string;
  objectClass: string;
  quantity: number;
  confidence: number;
  bbox?: number[];
  direction: string;
  personIdentity: string;
  verificationStatus: string;
  snapshotUrl?: string;
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
  const [unitsDetected, setUnitsDetected] = useState(0);
  const [knownCount, setKnownCount] = useState(0);
  const [unknownCount, setUnknownCount] = useState(0);

  // Snapshot & History State
  const [latestSnapshotUrl, setLatestSnapshotUrl] = useState<string | null>(null);
  const [showSnapshotModal, setShowSnapshotModal] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [historyItems, setHistoryItems] = useState<DetectionHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [scanMessage, setScanMessage] = useState<string | null>(null);
  const [snapshotKey, setSnapshotKey] = useState(Date.now());
  const [suggestedGateLine, setSuggestedGateLine] = useState<NormalizedPoint[] | null>(null);
  const [suggestingLine, setSuggestingLine] = useState(false);
  const [snapshotFailed, setSnapshotFailed] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // 1. Fetch Dynamic Camera Stats from Database/Worker API
  const fetchCameraStats = async () => {
    try {
      const res = await safeFetch(`/api/cameras/${cameraId}/stats`);
      if (res.ok) {
        const data = await res.json();
        if (data.footfallIn !== undefined) setFootfallIn(data.footfallIn);
        if (data.footfallOut !== undefined) setFootfallOut(data.footfallOut);
        if (data.occupancy !== undefined) setOccupancy(data.occupancy);
        if (data.casesDetected !== undefined) setCasesDetected(data.casesDetected);
        if (data.unitsDetected !== undefined) setUnitsDetected(data.unitsDetected);
        if (data.knownCount !== undefined) setKnownCount(data.knownCount);
        if (data.unknownCount !== undefined) setUnknownCount(data.unknownCount);
        if (data.roiPolygon && Array.isArray(data.roiPolygon) && data.roiPolygon.length > 0) {
          setRoiPolygon(data.roiPolygon);
        }
        if (data.latestSnapshotUrl) {
          setLatestSnapshotUrl(data.latestSnapshotUrl);
        }
      }
    } catch (err) {
      console.debug("Failed to fetch camera stats:", err);
    }
  };

  // 2. Fetch Camera Detection History from DB
  const fetchCameraHistory = async () => {
    try {
      setHistoryLoading(true);
      const res = await safeFetch(`/api/cameras/${cameraId}/history?limit=30`);
      if (res.ok) {
        const data = await res.json();
        setHistoryItems(data);
      }
    } catch (err) {
      console.warn("Failed to load camera history:", err);
    } finally {
      setHistoryLoading(false);
    }
  };

  // 3. Operator Detection Verification Action
  const handleVerifyDetection = async (
    detectionId: string,
    status: "APPROVED" | "REJECTED" | "CORRECT"
  ) => {
    try {
      const res = await safeFetch(`/api/cameras/detections/${detectionId}/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ verificationStatus: status }),
      });
      if (res.ok) {
        setHistoryItems((prev) =>
          prev.map((item) =>
            item.detectionId === detectionId
              ? { ...item, verificationStatus: status }
              : item
          )
        );
      }
    } catch (err) {
      console.warn("Verification failed:", err);
    }
  };

  // 4. Manual Scan Now Trigger
  const handleScanNow = async () => {
    try {
      setIsScanning(true);
      setScanMessage("Triggering AI frame scan...");
      const res = await safeFetch(`/api/cameras/${cameraId}/scan-now`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setScanMessage(`Scan complete: ${data.verdict || "INSPECTED"}`);
        setSnapshotKey(Date.now());
        await fetchCameraStats();
        setTimeout(() => setScanMessage(null), 3500);
      } else {
        setScanMessage("Scan failed - edge stream unreachable");
        setTimeout(() => setScanMessage(null), 3000);
      }
    } catch (err) {
      setScanMessage("Scan request failed");
      setTimeout(() => setScanMessage(null), 3000);
    } finally {
      setIsScanning(false);
    }
  };

  // 5. Initial stats fetch and periodic polling fallback
  useEffect(() => {
    fetchCameraStats();
    const statsTimer = setInterval(fetchCameraStats, 10000);
    return () => clearInterval(statsTimer);
  }, [cameraId]);

  // 6. WebSocket Telemetry Connection to FastAPI Backend
  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimer: NodeJS.Timeout;
    let pingTimer: NodeJS.Timeout;

    const connectWebSocket = () => {
      let wsUrl = getWsUrl("/ws/live");
      try {
        const token =
          typeof window !== "undefined"
            ? localStorage.getItem("secops_token") || sessionStorage.getItem("secops_token")
            : null;
        if (token) {
          wsUrl += `?token=${encodeURIComponent(token)}`;
        }
      } catch (_) {}

      try {
        ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setIsConnected(true);
          // Keepalive ping every 10s to satisfy backend idle timeout watchdog
          pingTimer = setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
              ws.send("ping");
            }
          }, 10000);
        };

        ws.onmessage = (event) => {
          try {
            if (event.data === "pong") return;
            const data = JSON.parse(event.data);
            if (data.type === "pong") return;

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
          clearInterval(pingTimer);
          reconnectTimer = setTimeout(connectWebSocket, 4000);
        };

        ws.onerror = () => {
          setIsConnected(false);
        };
      } catch (err) {
        reconnectTimer = setTimeout(connectWebSocket, 4000);
      }
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) wsRef.current.close();
      clearTimeout(reconnectTimer);
      clearInterval(pingTimer);
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
      await fetchCameraStats();
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
      await fetchCameraStats();
    } catch (err) {
      // offline fallback
    }
  };

  const handleSuggestGateLine = async () => {
    setSuggestingLine(true);
    try {
      const res = await safeFetch(`/api/cameras/${cameraId}/suggest-gate-line`);
      if (res.ok) {
        const data = await res.json();
        if (data.suggestedLine && Array.isArray(data.suggestedLine)) {
          setSuggestedGateLine(data.suggestedLine);
          setRoiPolygon(data.suggestedLine);
        }
      }
    } catch (err) {
      console.warn("Gate line suggestion error:", err);
    } finally {
      setSuggestingLine(false);
    }
  };

  const handleAcceptGateLine = async () => {
    if (!suggestedGateLine) return;
    try {
      await safeFetch(`/api/cameras/${cameraId}/save-gate-line`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ line: suggestedGateLine }),
      });
      setSuggestedGateLine(null);
      await fetchCameraStats();
    } catch (err) {
      console.warn("Gate line save error:", err);
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
  const currentSnapshotUrl = `/api/cameras/${cameraId}/snapshot?t=${snapshotKey}`;

  // Helper to match Part P.1 and CC.2 color & styling system
  const getBoxStyle = (b: DetectionBox) => {
    const rawType = (b.type || "").toUpperCase();
    const rawLabel = (b.label || "").toUpperCase();

    if (
      b.is_discrepancy ||
      b.is_defect ||
      rawType.includes("DEFECT") ||
      rawLabel.includes("DEFECT") ||
      rawType.includes("DISCREPANCY") ||
      rawType.includes("SUSPICIOUS") ||
      rawType.includes("HAZARD")
    ) {
      return { border: "#EF4444", bg: "#EF4444", text: "#FFFFFF" }; // Red
    }
    if (
      rawType.includes("STATIC") ||
      rawLabel.includes("STATIC ARTIFACT") ||
      rawLabel.includes("IGNORED")
    ) {
      return { border: "#64748B", bg: "#1E293B", text: "#94A3B8" }; // Slate Gray
    }
    if (
      rawLabel.includes("SMARTPHONE") ||
      rawLabel.includes("PHONE") ||
      rawLabel.includes("LAPTOP") ||
      rawType.includes("ELECTRONICS")
    ) {
      return { border: "#F97316", bg: "#F97316", text: "#000000" }; // Orange
    }
    if (
      rawLabel.includes("SHELF") ||
      rawLabel.includes("BOOKCASE") ||
      rawLabel.includes("CAR") ||
      rawLabel.includes("VEHICLE") ||
      rawType.includes("VEHICLE") ||
      rawLabel.includes("DOORWAY")
    ) {
      return { border: "#06B6D4", bg: "#06B6D4", text: "#000000" }; // Cyan
    }
    if (
      rawType.includes("MATCHED") ||
      rawLabel.includes("AUTHORIZED") ||
      rawLabel.includes("KNOWN")
    ) {
      return { border: "#10B981", bg: "#10B981", text: "#FFFFFF" }; // Confirmed Match (Emerald)
    }
    if (
      rawType.includes("UNMATCHED") ||
      rawLabel.includes("UNKNOWN") ||
      rawLabel.includes("UNAUTHORIZED")
    ) {
      return { border: "#EF4444", bg: "#DC2626", text: "#FFFFFF" }; // Unknown Person
    }
    // Default retail item styling (Lime Green matching industrial spec)
    return { border: "#84CC16", bg: "#84CC16", text: "#000000" };
  };

  return (
    <div className="flex flex-col bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl overflow-hidden shadow-lg transition-colors">
      {/* 1. Camera Top Bar */}
      <div className="px-4 py-2.5 bg-[var(--bg-panel-raised)] border-b border-[var(--border-hairline)] flex justify-between items-center text-xs transition-colors">
        <div className="flex items-center gap-3">
          <div
            className={`w-2.5 h-2.5 rounded-full ${
              isConnected
                ? "bg-[var(--status-ok)] shadow-[0_0_8px_var(--status-ok)]"
                : "bg-[var(--status-high)]"
            }`}
          />
          <span className="font-bold font-mono text-[var(--text-primary)] tracking-wider">
            {cameraId}
          </span>
          <span className="text-[var(--text-muted)] font-sans text-xs hidden sm:inline">
            {cameraName}
          </span>
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
      <div
        ref={containerRef}
        className="relative aspect-video bg-black w-full overflow-hidden select-none"
      >
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
            <span className="text-[#8B93A1] text-[10px] mt-1">
              {cameraIp} (PORT 554)
            </span>
          </div>
        )}

        {/* SURVEILLANCE CV TOP BANNER */}
        <div className="absolute top-2 left-2 z-30 pointer-events-none">
          <div className="bg-black/75 backdrop-blur-sm px-2.5 py-0.5 rounded border border-yellow-500/30 shadow-lg font-mono text-[10px] font-bold text-[#FACC15] tracking-wider flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>
              SURVEILLANCE CV // ACTIVE // DETECTIONS: {boxes.length} (CASES: {casesDetected} UNITS:{" "}
              {unitsDetected})
            </span>
          </div>
        </div>

        {/* Temporary Scan Message Toast */}
        {scanMessage && (
          <div className="absolute top-2 right-2 z-40 bg-black/85 backdrop-blur-md px-3 py-1.5 rounded-lg border border-[#38BDF8] text-[#38BDF8] font-mono text-xs flex items-center gap-2 shadow-xl animate-fade-in">
            <RefreshCw size={13} className="animate-spin text-[#38BDF8]" />
            <span>{scanMessage}</span>
          </div>
        )}

        {/* Solid Pinned Badges with CC.2 Strict Bracketed Format & Oriented Polygons */}
        <div className="absolute inset-0 pointer-events-none z-20">
          <svg className="absolute inset-0 w-full h-full pointer-events-none">
            {boxes.map((b, idx) => {
              if (!b.polygon || b.polygon.length < 3) return null;
              const style = getBoxStyle(b);
              const pointsStr = b.polygon
                .map(([x, y]) => {
                  const px =
                    x <= 1.0
                      ? x * 100
                      : (x / (resolution.includes("1920") ? 1920 : 1280)) * 100;
                  const py =
                    y <= 1.0
                      ? y * 100
                      : (y / (resolution.includes("1080") ? 1080 : 720)) * 100;
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
            if (rawType === "WALL_PICTURE" && !rawLabel.includes("STATIC ARTIFACT")) {
              return null;
            }

            const style = getBoxStyle(b);
            const leftPct = `${b.box[0] * 100}%`;
            const topPct = `${b.box[1] * 100}%`;
            const widthPct = `${b.box[2] * 100}%`;
            const heightPct = `${b.box[3] * 100}%`;

            let cleanTag = (b.label || "").trim();
            if (!cleanTag.startsWith("[")) {
              const confPct =
                typeof b.confidence === "number"
                  ? `${(b.confidence * 100).toFixed(0)}%`
                  : "";
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
              <button
                onClick={() => setShowPtz(false)}
                className="text-[#8B93A1] hover:text-white"
              >
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

      {/* 3. Live Sensor Verification Strip (Dynamic DB & WebSocket Driven) */}
      <div className="p-2.5 bg-[var(--bg-panel)] grid grid-cols-2 md:grid-cols-4 gap-2 text-xs transition-colors">
        {/* Footfall Counters */}
        <div
          onClick={() => {
            fetchCameraHistory();
            setShowHistoryModal(true);
          }}
          className="bg-[var(--bg-canvas)] p-2 rounded-lg border border-[var(--border-hairline)] flex flex-col justify-between min-w-0 overflow-hidden cursor-pointer hover:border-[#38BDF8] transition-colors"
          title="Click to view full traversal history"
        >
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
        <div
          onClick={() => {
            fetchCameraHistory();
            setShowHistoryModal(true);
          }}
          className="bg-[var(--bg-canvas)] p-2 rounded-lg border border-[var(--border-hairline)] flex flex-col justify-between min-w-0 overflow-hidden cursor-pointer hover:border-[var(--signal-amber)] transition-colors"
          title="Click to view detected items history"
        >
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
        <div
          onClick={() => {
            fetchCameraHistory();
            setShowHistoryModal(true);
          }}
          className="bg-[var(--bg-canvas)] p-2 rounded-lg border border-[var(--border-hairline)] flex flex-col justify-between min-w-0 overflow-hidden cursor-pointer hover:border-[#10B981] transition-colors"
          title="Click to view biometric match log"
        >
          <div className="text-[10px] text-[var(--text-muted)] font-mono flex items-center gap-1 truncate">
            <ShieldCheck size={12} className="text-[var(--status-ok)] shrink-0" />
            <span className="truncate">BIOMETRIC MATCH</span>
          </div>
          <div className="text-xs sm:text-sm font-bold font-mono mt-0.5 flex items-center gap-1 truncate">
            <span className="text-[var(--status-ok)] whitespace-nowrap">
              {knownCount} Known
            </span>
            <span className="text-[var(--border-hairline)]">|</span>
            <span className="text-[#38BDF8] whitespace-nowrap">
              {unknownCount} Guest
            </span>
          </div>
        </div>

        {/* Tripwire Status */}
        <div
          onClick={() => setIsDrawingRoi(true)}
          className="bg-[var(--bg-canvas)] p-2 rounded-lg border border-[var(--border-hairline)] flex flex-col justify-between min-w-0 overflow-hidden cursor-pointer hover:border-[#A78BFA] transition-colors"
          title="Click to configure Virtual Tripwire ROI"
        >
          <div className="text-[10px] text-[var(--text-muted)] font-mono flex items-center gap-1 truncate">
            <Sliders size={12} className="text-[#A78BFA] shrink-0" />
            <span className="truncate">VIRTUAL TRIPWIRE</span>
          </div>
          <div className="text-xs sm:text-sm font-bold font-mono mt-0.5 truncate">
            {roiPolygon && roiPolygon.length > 0 ? (
              <span className="text-[#A78BFA] truncate">
                ACTIVE ({roiPolygon.length} PTS)
              </span>
            ) : (
              <span className="text-[var(--text-muted)] truncate">UNCONFIGURED</span>
            )}
          </div>
        </div>
      </div>

      {/* 4. Bottom Action Controls Bar (All Buttons Operational) */}
      <div className="px-4 py-2 bg-[var(--bg-panel-raised)] border-t border-[var(--border-hairline)] flex flex-wrap justify-between items-center gap-2 transition-colors">
        {/* Left: ROI / Tripwire Editing Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          {suggestedGateLine ? (
            <div className="flex items-center gap-1.5 bg-blue-950/80 border border-blue-700/80 px-2.5 py-1 rounded-lg text-xs font-mono">
              <span className="text-[#38BDF8] font-bold">AI Gate Line:</span>
              <button
                onClick={handleAcceptGateLine}
                className="px-2 py-0.5 bg-[#10B981] hover:bg-[#059669] text-white rounded text-[11px] font-bold transition-colors"
              >
                ACCEPT
              </button>
              <button
                onClick={() => {
                  setIsDrawingRoi(true);
                  setSuggestedGateLine(null);
                }}
                className="px-2 py-0.5 bg-[var(--bg-panel)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded text-[11px] border border-[var(--border-hairline)] transition-colors"
              >
                ADJUST
              </button>
              <button
                onClick={() => {
                  handleClearRoi();
                  setIsDrawingRoi(true);
                  setSuggestedGateLine(null);
                }}
                className="px-2 py-0.5 bg-[var(--bg-panel)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded text-[11px] border border-[var(--border-hairline)] transition-colors"
              >
                REDRAW
              </button>
              <button
                onClick={() => {
                  setSuggestedGateLine(null);
                  handleClearRoi();
                }}
                className="px-1.5 py-0.5 text-[var(--text-muted)] hover:text-white text-[11px]"
              >
                Cancel
              </button>
            </div>
          ) : isDrawingRoi ? (
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
            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={handleSuggestGateLine}
                disabled={suggestingLine}
                className="px-2.5 py-1 text-xs bg-[var(--bg-panel)] hover:bg-[var(--bg-panel-hover)] text-[#A78BFA] border border-[#A78BFA]/40 rounded font-medium flex items-center gap-1.5 transition-colors"
              >
                <Sliders size={12} className={suggestingLine ? "animate-spin" : ""} />
                AI Suggest Gate Line
              </button>

              <button
                onClick={() => setIsDrawingRoi(true)}
                className="px-3 py-1 text-xs bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded font-medium flex items-center gap-1.5 shadow transition-colors"
              >
                <PenTool size={13} /> Draw Line / ROI
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

              {/* View Snapshot Button */}
              <button
                onClick={() => {
                  setSnapshotFailed(false);
                  setSnapshotKey(Date.now());
                  setShowSnapshotModal(true);
                }}
                className="px-3 py-1 text-xs bg-[var(--bg-panel)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded font-medium flex items-center gap-1.5 transition-colors"
              >
                <CameraIcon size={13} className="text-[#38BDF8]" /> View Snapshot
              </button>

              {/* View History Button */}
              <button
                onClick={() => {
                  fetchCameraHistory();
                  setShowHistoryModal(true);
                }}
                className="px-3 py-1 text-xs bg-[var(--bg-panel)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded font-medium flex items-center gap-1.5 transition-colors"
              >
                <History size={13} className="text-[#E8A33D]" /> Detection History
              </button>

              {/* Scan Now Edge Trigger */}
              <button
                onClick={handleScanNow}
                disabled={isScanning}
                className="px-3 py-1 text-xs bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded font-medium flex items-center gap-1.5 transition-colors shadow"
              >
                <Eye size={13} /> {isScanning ? "Scanning..." : "Scan Now"}
              </button>
            </div>
          )}
        </div>

        {/* Right: Stream Quality & Tools */}
        <div className="flex items-center gap-2">
          <div className="bg-[var(--bg-canvas)] border border-[var(--border-hairline)] p-0.5 rounded flex items-center text-[11px] font-mono">
            <button
              onClick={() => setStreamQuality("main")}
              className={`px-2 py-0.5 rounded transition-colors ${
                streamQuality === "main"
                  ? "bg-[#2563EB] text-white font-bold"
                  : "text-[var(--text-muted)]"
              }`}
            >
              MAIN (1080p)
            </button>
            <button
              onClick={() => setStreamQuality("sub")}
              className={`px-2 py-0.5 rounded transition-colors ${
                streamQuality === "sub"
                  ? "bg-[#2563EB] text-white font-bold"
                  : "text-[var(--text-muted)]"
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

      {/* Snapshot Modal */}
      {showSnapshotModal && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-2xl max-w-3xl w-full p-5 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <div className="flex items-center gap-2 font-mono text-sm font-bold text-[var(--text-primary)]">
                <CameraIcon size={18} className="text-[#38BDF8]" />
                <span>
                  Camera Snapshot — {cameraId} ({cameraName})
                </span>
              </div>
              <button
                onClick={() => setShowSnapshotModal(false)}
                className="p-1 text-[var(--text-secondary)] hover:text-white rounded"
              >
                <X size={18} />
              </button>
            </div>

            <div className="relative aspect-video bg-neutral-900 rounded-lg overflow-hidden border border-[var(--border-hairline)] flex items-center justify-center">
              {snapshotFailed ? (
                <div className="flex flex-col items-center justify-center p-6 text-center space-y-2">
                  <div className="p-3 rounded-full bg-neutral-800 text-neutral-400">
                    <CameraIcon size={28} />
                  </div>
                  <div className="text-sm font-mono font-bold text-neutral-200">Snapshot Unavailable</div>
                  <p className="text-xs text-neutral-400 max-w-sm">
                    No visual evidence frame was recorded for this camera or the stream was in standby.
                  </p>
                </div>
              ) : (
                <img
                  src={currentSnapshotUrl}
                  alt={`Snapshot from ${cameraId}`}
                  className="w-full h-full object-contain"
                  onError={() => setSnapshotFailed(true)}
                />
              )}
            </div>

            <div className="flex flex-wrap justify-between items-center gap-3 pt-2 text-xs font-mono text-[var(--text-secondary)]">
              <div>
                IP: <span className="text-[var(--text-primary)]">{cameraIp}</span> |
                Status: <span className="text-[var(--status-ok)]">ONLINE</span> | Lane:{" "}
                <span className="text-[#38BDF8]">{laneId}</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setSnapshotKey(Date.now())}
                  className="px-3 py-1.5 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-lg flex items-center gap-1.5 transition-colors"
                >
                  <RefreshCw size={13} /> Refresh Frame
                </button>
                <a
                  href={`/api/cameras/${cameraId}/snapshot?download=1`}
                  download={`snapshot_${cameraId}.jpg`}
                  className="px-3 py-1.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg flex items-center gap-1.5 shadow transition-colors"
                >
                  <Download size={13} /> Download JPEG
                </a>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Detection History Modal */}
      {showHistoryModal && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-2xl max-w-4xl w-full max-h-[85vh] flex flex-col p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <div className="flex items-center gap-2 font-mono text-base font-bold text-[var(--text-primary)]">
                <History size={20} className="text-[#E8A33D]" />
                <span>Camera Detection & Traversal History — {cameraId}</span>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={fetchCameraHistory}
                  disabled={historyLoading}
                  className="p-1.5 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-secondary)] hover:text-white rounded border border-[var(--border-hairline)] transition-colors"
                  title="Refresh History"
                >
                  <RefreshCw size={14} className={historyLoading ? "animate-spin" : ""} />
                </button>
                <button
                  onClick={() => setShowHistoryModal(false)}
                  className="p-1 text-[var(--text-secondary)] hover:text-white rounded"
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {historyLoading && historyItems.length === 0 ? (
                <div className="py-12 text-center text-xs font-mono text-[var(--text-secondary)] flex flex-col items-center gap-2">
                  <RefreshCw size={24} className="animate-spin text-[#38BDF8]" />
                  <span>Loading detection history from database...</span>
                </div>
              ) : historyItems.length === 0 ? (
                <div className="py-12 text-center text-xs font-mono text-[var(--text-secondary)]">
                  No detection records found for this camera today.
                </div>
              ) : (
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-[var(--bg-canvas)] text-[var(--text-secondary)] border-b border-[var(--border-hairline)]">
                    <tr>
                      <th className="p-2.5">TIMESTAMP</th>
                      <th className="p-2.5">EVENT</th>
                      <th className="p-2.5">ITEM / DETECTED OBJECT</th>
                      <th className="p-2.5">DIR</th>
                      <th className="p-2.5">IDENTITY</th>
                      <th className="p-2.5">CONF</th>
                      <th className="p-2.5">STATUS</th>
                      <th className="p-2.5 text-right">OPERATOR VERIFY</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
                    {historyItems.map((item) => (
                      <tr
                        key={item.detectionId}
                        className="hover:bg-[var(--bg-panel-raised)] transition-colors"
                      >
                        <td className="p-2.5 text-[var(--text-secondary)] whitespace-nowrap">
                          {new Date(item.timestamp).toLocaleTimeString()}
                        </td>
                        <td className="p-2.5 font-bold text-[#38BDF8]">
                          {item.eventType}
                        </td>
                        <td className="p-2.5">
                          <span className="font-semibold text-[var(--text-primary)]">
                            {item.objectClass}
                          </span>
                          <span className="text-[var(--text-secondary)] ml-1">
                            (x{item.quantity})
                          </span>
                        </td>
                        <td className="p-2.5">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              item.direction === "EXIT"
                                ? "bg-rose-950 text-rose-300 border border-rose-800"
                                : "bg-emerald-950 text-emerald-300 border border-emerald-800"
                            }`}
                          >
                            {item.direction}
                          </span>
                        </td>
                        <td className="p-2.5 text-[var(--text-secondary)]">
                          {item.personIdentity}
                        </td>
                        <td className="p-2.5 text-[#E8A33D]">
                          {(item.confidence * 100).toFixed(1)}%
                        </td>
                        <td className="p-2.5">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              item.verificationStatus === "APPROVED" ||
                              item.verificationStatus === "CORRECT"
                                ? "bg-emerald-900/60 text-emerald-300 border border-emerald-700"
                                : "bg-amber-900/60 text-amber-300 border border-amber-700"
                            }`}
                          >
                            {item.verificationStatus}
                          </span>
                        </td>
                        <td className="p-2.5 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() =>
                                handleVerifyDetection(item.detectionId, "APPROVED")
                              }
                              className="p-1 bg-emerald-900/50 hover:bg-emerald-800 text-emerald-300 rounded border border-emerald-700 transition-colors"
                              title="Approve / Mark Correct"
                            >
                              <Check size={12} />
                            </button>
                            <button
                              onClick={() =>
                                handleVerifyDetection(item.detectionId, "REJECTED")
                              }
                              className="p-1 bg-rose-900/50 hover:bg-rose-800 text-rose-300 rounded border border-rose-700 transition-colors"
                              title="Reject / Disagree"
                            >
                              <X size={12} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="flex justify-end pt-3 border-t border-[var(--border-hairline)]">
              <button
                onClick={() => setShowHistoryModal(false)}
                className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-xs font-semibold"
              >
                Close History
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
