"use client";

import { safeFetch, getWsUrl } from "@/lib/api-client";
import React, { useState, useEffect } from "react";
import StreamPlayer from "@/components/cameras/stream-player";
import VerifyAndSaveModal from "@/components/dispatch/verify-and-save-modal";
import {
  Activity,
  AlertTriangle,
  Box,
  Camera,
  Layers,
  ArrowRight,
  CheckCircle,
  Plus,
  FileCheck,
  Check,
  Edit2,
  Sliders,
  Eye,
  RefreshCw,
  X,
  ShieldCheck,
  UserCheck,
  FileText,
  Clock,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";

interface LiveDetectionRow {
  detectionId: string;
  cameraId: string;
  cameraLabel: string;
  timestamp: string;
  objectClass: string;
  quantity: number;
  confidence: number;
  personIdentity: string;
  status: string;
  snapshotUrl?: string;
}

interface StockVerificationItem {
  verificationId: string;
  productId: string;
  skuCode: string;
  productName: string;
  cameraId?: string;
  aiProposedCount: number;
  verifiedCount?: number;
  difference?: number;
  status: string;
  verifiedBy?: string;
  correctionReason?: string;
  snapshotUrl?: string;
  modelVersion?: string;
  createdAt?: string;
  verifiedAt?: string;
}

interface MovementMonitorRow {
  movementId: string;
  eventId: string;
  timestamp: string;
  personName: string;
  billNumber: string;
  productName: string;
  skuCode: string;
  authorizedQty: number;
  actualQty: number;
  remainingQty: number;
  progressPct: number;
  status: string;
  verdict: string;
  cameraLabel: string;
  snapshotUrl?: string;
  notes?: string;
}

export default function DashboardPage() {
  const [cameras, setCameras] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [showVerifyModal, setShowVerifyModal] = useState(false);
  const [kpis, setKpis] = useState({
    todayThroughput: 0,
    openAlerts: 0,
    criticalAlerts: 0,
    accuracyRate: 100.0,
    camerasOnline: 0,
    camerasTotal: 0,
  });

  // V8 Addendum: Live Detections, Stock Baseline Verifications & Movement Monitor
  const [liveDetections, setLiveDetections] = useState<LiveDetectionRow[]>([]);
  const [verifications, setVerifications] = useState<StockVerificationItem[]>([]);
  const [movementMonitor, setMovementMonitor] = useState<MovementMonitorRow[]>([]);
  const [previewSnapshot, setPreviewSnapshot] = useState<{ url: string; title: string } | null>(null);

  // Edit Correction Modal State
  const [editingVerif, setEditingVerif] = useState<StockVerificationItem | null>(null);
  const [correctionQty, setCorrectionQty] = useState<number>(0);
  const [correctionReason, setCorrectionReason] = useState("");
  const [submittingCorrection, setSubmittingCorrection] = useState(false);

  const fetchData = async () => {
    try {
      // 1. Fetch Live KPIs directly from database
      const resKpi = await safeFetch("/api/kpis/live");
      if (resKpi.ok) {
        const kData = await resKpi.json();
        setKpis({
          todayThroughput: kData.todayThroughputUnits || 0,
          openAlerts: kData.openAlertsCount || 0,
          criticalAlerts: kData.openAlertsBySeverity?.high || 0,
          accuracyRate:
            kData.consensusAccuracyRate !== undefined
              ? Number(kData.consensusAccuracyRate.toFixed(1))
              : 100.0,
          camerasOnline: kData.camerasOnlineCount || 0,
          camerasTotal: kData.camerasTotalCount || 0,
        });
      }

      // 2. Fetch Cameras Fleet
      const resCam = await safeFetch("/api/cameras");
      if (resCam.ok) {
        const camData = await resCam.json();
        setCameras(camData);
      }

      // 3. Fetch Alerts
      const resAlt = await safeFetch("/api/alerts?limit=5");
      if (resAlt.ok) {
        const altData = await resAlt.json();
        setAlerts(altData.slice(0, 5));
      }

      // 4. Fetch Events
      const resEv = await safeFetch("/api/events?limit=5");
      if (resEv.ok) {
        const evData = await resEv.json();
        setEvents(evData.slice(0, 5));
      }

      // 5. Fetch Live Camera Detections Table (Section 2)
      const resLiveDet = await safeFetch("/api/cameras/detections/live?limit=15");
      if (resLiveDet.ok) {
        const detData = await resLiveDet.json();
        setLiveDetections(detData);
      }

      // 6. Fetch Initial Stock Count Baseline Verifications (Section 5)
      const resVerif = await safeFetch("/api/inventory/verification");
      if (resVerif.ok) {
        const verifData = await resVerif.json();
        setVerifications(verifData);
      }

      // 7. Fetch Movement Monitor (Section 7, 8, 9, 11)
      const resMov = await safeFetch("/api/events/movement-monitor?limit=10");
      if (resMov.ok) {
        const movData = await resMov.json();
        setMovementMonitor(movData);
      }
    } catch (e) {
      console.warn("Dashboard polling warning:", e);
    }
  };

  useEffect(() => {
    fetchData();

    // Real-time WebSocket subscription to /ws/live
    let ws: WebSocket | null = null;
    let reconnectTimeout: any = null;

    const connectWs = () => {
      try {
        const wsUrl = getWsUrl("/ws/live");
        ws = new WebSocket(wsUrl);

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (
              data.type === "new_alert" ||
              data.type === "alert_resolved" ||
              data.type === "exit_event" ||
              data.type === "camera_status_changed" ||
              data.type === "lane_status_changed" ||
              data.type === "detection_update" ||
              data.type === "inventory_update" ||
              data.type === "heartbeat"
            ) {
              fetchData();
            }
          } catch (err) {
            console.debug("WS parse error:", err);
          }
        };

        ws.onclose = () => {
          reconnectTimeout = setTimeout(connectWs, 5000);
        };

        ws.onerror = () => {
          if (ws) ws.close();
        };
      } catch (err) {
        console.debug("WS connection error:", err);
      }
    };

    connectWs();
    const fallbackInterval = setInterval(fetchData, 15000);

    return () => {
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      clearInterval(fallbackInterval);
    };
  }, []);

  // Handle Initial Stock YES Confirmation
  const handleConfirmStock = async (verifId: string, isCorrect: boolean, correctedQty?: number, reason?: string) => {
    try {
      setSubmittingCorrection(true);
      const res = await safeFetch(`/api/inventory/verification/${verifId}/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          is_correct: isCorrect,
          corrected_count: correctedQty,
          reason: reason || (isCorrect ? "Confirmed accurate by operator" : "Recount override"),
          verified_by: "OPERATOR",
        }),
      });

      if (res.ok) {
        setEditingVerif(null);
        await fetchData();
      } else {
        const err = await res.json();
        alert(err.detail || "Verification failed");
      }
    } catch (e: any) {
      alert(e.message || "Request failed");
    } finally {
      setSubmittingCorrection(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 1. Live KPI Top Strip (All Cards Clickable Links per User Feedback) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Active Cameras Fleet -> Navigates to /settings/cameras */}
        <Link
          href="/settings/cameras"
          className="bg-[var(--bg-panel)] p-5 rounded-xl border border-[var(--border-hairline)] flex justify-between items-start shadow-sm transition-all hover:border-[#38BDF8] hover:shadow-md cursor-pointer block group"
          title="Click to manage and inspect camera fleet"
        >
          <div>
            <span className="text-xs font-mono text-[var(--text-muted)] group-hover:text-[#38BDF8] transition-colors">
              CAMERAS ONLINE / TOTAL
            </span>
            <div className="text-2xl font-bold font-mono text-[var(--text-primary)] mt-1">
              <span className="text-[var(--status-ok)]">{kpis.camerasOnline}</span>
              <span className="text-[var(--text-muted)]"> / </span>
              <span>{kpis.camerasTotal}</span>
            </div>
            <span className="text-[11px] text-[var(--status-ok)] font-mono mt-0.5 block flex items-center gap-1">
              Live Edge Stream <ArrowRight size={11} className="inline opacity-0 group-hover:opacity-100 transition-opacity" />
            </span>
          </div>
          <div className="p-2.5 rounded-lg bg-[var(--bg-panel-raised)] text-[#38BDF8] group-hover:bg-blue-900/30 transition-colors">
            <Camera size={20} />
          </div>
        </Link>

        {/* Open Loss-Prevention Alerts -> Navigates to /alerts */}
        <Link
          href="/alerts"
          className="bg-[var(--bg-panel)] p-5 rounded-xl border border-[var(--border-hairline)] flex justify-between items-start shadow-sm transition-all hover:border-rose-500 hover:shadow-md cursor-pointer block group"
          title="Click to view and resolve security alarms queue"
        >
          <div>
            <span className="text-xs font-mono text-[var(--text-muted)] group-hover:text-rose-400 transition-colors">
              OPEN ALARMS (QUEUE)
            </span>
            <div className="text-2xl font-bold font-mono text-[var(--status-high)] mt-1">
              {kpis.openAlerts}
            </div>
            <span className="text-[11px] text-[var(--signal-amber)] font-mono mt-0.5 block flex items-center gap-1">
              {kpis.criticalAlerts} Critical High Priority <ArrowRight size={11} className="inline opacity-0 group-hover:opacity-100 transition-opacity" />
            </span>
          </div>
          <div className="p-2.5 rounded-lg bg-[var(--bg-panel-raised)] text-[var(--status-high)] group-hover:bg-rose-950/40 transition-colors">
            <AlertTriangle size={20} />
          </div>
        </Link>

        {/* Throughput Items Verified -> Navigates to /events */}
        <Link
          href="/events"
          className="bg-[var(--bg-panel)] p-5 rounded-xl border border-[var(--border-hairline)] flex justify-between items-start shadow-sm transition-all hover:border-amber-500 hover:shadow-md cursor-pointer block group"
          title="Click to inspect audited exit event records"
        >
          <div>
            <span className="text-xs font-mono text-[var(--text-muted)] group-hover:text-amber-400 transition-colors">
              AUDITED THROUGHPUT
            </span>
            <div className="text-2xl font-bold font-mono text-[var(--text-primary)] mt-1">
              {kpis.todayThroughput}{" "}
              <span className="text-xs font-normal text-[var(--text-muted)]">units</span>
            </div>
            <span className="text-[11px] text-[var(--status-ok)] font-mono mt-0.5 block flex items-center gap-1">
              100% Sensor Verified <ArrowRight size={11} className="inline opacity-0 group-hover:opacity-100 transition-opacity" />
            </span>
          </div>
          <div className="p-2.5 rounded-lg bg-[var(--bg-panel-raised)] text-[var(--signal-amber)] group-hover:bg-amber-950/40 transition-colors">
            <Box size={20} />
          </div>
        </Link>

        {/* Fusion Consensus Accuracy -> Navigates to /reports */}
        <Link
          href="/reports"
          className="bg-[var(--bg-panel)] p-5 rounded-xl border border-[var(--border-hairline)] flex justify-between items-start shadow-sm transition-all hover:border-emerald-500 hover:shadow-md cursor-pointer block group"
          title="Click to view sensor fusion analytics & reports"
        >
          <div>
            <span className="text-xs font-mono text-[var(--text-muted)] group-hover:text-emerald-400 transition-colors">
              CONSENSUS FUSION ACCURACY
            </span>
            <div className="text-2xl font-bold font-mono text-[var(--status-ok)] mt-1">
              {kpis.accuracyRate}%
            </div>
            <span className="text-[11px] text-[var(--text-muted)] font-mono mt-0.5 block flex items-center gap-1">
              Vision + RFID + Weight <ArrowRight size={11} className="inline opacity-0 group-hover:opacity-100 transition-opacity" />
            </span>
          </div>
          <div className="p-2.5 rounded-lg bg-[var(--bg-panel-raised)] text-[var(--status-ok)] group-hover:bg-emerald-950/40 transition-colors">
            <Activity size={20} />
          </div>
        </Link>
      </div>

      {/* 2. INITIAL STOCK COUNT VERIFICATION WORKFLOW (Section 5 & 18 Addendum) */}
      <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl p-5 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-[var(--border-hairline)] pb-3">
          <div>
            <h2 className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2">
              <Sliders size={18} className="text-[#38BDF8]" /> Initial Stock Baseline Verification Workflow
            </h2>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              Authorized operators review and baseline initial physical inventory scans. Preserves both AI Proposed and Verified counts.
            </p>
          </div>
          <Link href="/products" className="text-xs font-mono text-[#38BDF8] hover:underline flex items-center gap-1">
            Product Catalog &rarr;
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {verifications.slice(0, 6).map((v) => {
            const isPending = v.status === "PENDING_VERIFICATION";
            return (
              <div
                key={v.verificationId}
                className={`p-4 rounded-xl border transition-all ${
                  isPending
                    ? "bg-[var(--bg-canvas)] border-amber-500/40 shadow-sm"
                    : "bg-[var(--bg-canvas)] border-[var(--border-hairline)]"
                }`}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <span className="text-[10px] font-mono font-bold text-[#38BDF8] block">{v.skuCode}</span>
                    <h4 className="text-sm font-bold text-[var(--text-primary)] mt-0.5">{v.productName}</h4>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                      v.status === "VERIFIED_ACCURATE"
                        ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                        : v.status === "CORRECTED"
                        ? "bg-blue-950 text-blue-300 border border-blue-800"
                        : "bg-amber-950 text-amber-300 border border-amber-800 animate-pulse"
                    }`}
                  >
                    {v.status.replace(/_/g, " ")}
                  </span>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-2 text-xs font-mono bg-[var(--bg-panel)] p-2.5 rounded-lg border border-[var(--border-hairline)]">
                  <div>
                    <span className="text-[10px] text-[var(--text-muted)] block">AI PROPOSED COUNT</span>
                    <span className="text-sm font-bold text-[#E8A33D]">{v.aiProposedCount} units</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-[var(--text-muted)] block">VERIFIED STOCK</span>
                    <span className="text-sm font-bold text-[var(--text-primary)]">
                      {v.verifiedCount !== null && v.verifiedCount !== undefined ? `${v.verifiedCount} units` : "Pending Review"}
                    </span>
                  </div>
                </div>

                {isPending ? (
                  <div className="mt-3 pt-3 border-t border-[var(--border-hairline)] space-y-2">
                    <span className="text-[11px] font-mono text-[var(--text-secondary)] block">
                      Is this AI count correct?
                    </span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleConfirmStock(v.verificationId, true)}
                        disabled={submittingCorrection}
                        className="flex-1 py-1.5 bg-[#10B981] hover:bg-[#059669] text-white rounded-lg text-xs font-bold font-mono flex items-center justify-center gap-1 shadow transition-colors"
                      >
                        <Check size={13} /> YES (Accept {v.aiProposedCount})
                      </button>
                      <button
                        onClick={() => {
                          setEditingVerif(v);
                          setCorrectionQty(v.aiProposedCount);
                          setCorrectionReason("Manual physical recount correction");
                        }}
                        className="flex-1 py-1.5 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-xs font-bold font-mono border border-[var(--border-hairline)] flex items-center justify-center gap-1 transition-colors"
                      >
                        <Edit2 size={12} /> NO / EDIT
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="mt-2 text-[10px] font-mono text-[var(--text-muted)] flex justify-between items-center">
                    <span>By: {v.verifiedBy || "Supervisor"}</span>
                    <span>Diff: {v.difference ?? 0} U</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 3. Live Exit Feeds Grid with Industrial Surveillance HUD */}
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
            <Camera size={18} className="text-[#38BDF8]" /> Live Surveillance Feeds & Video HUD
          </h2>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowVerifyModal(true)}
              className="px-3 py-1.5 bg-[#10B981] hover:bg-[#059669] text-white rounded-lg text-xs font-semibold font-mono flex items-center gap-1.5 shadow-md shadow-emerald-900/30 transition-all"
            >
              <FileCheck size={14} /> Verify & Save (DD.3)
            </button>
            <Link
              href="/settings/cameras"
              className="text-xs font-mono text-[#38BDF8] hover:underline flex items-center gap-1"
            >
              Manage Camera Fleet <ArrowRight size={13} />
            </Link>
          </div>
        </div>

        {cameras.length === 0 ? (
          <div className="bg-[var(--bg-panel)] p-12 rounded-xl border border-[var(--border-hairline)] text-center flex flex-col items-center justify-center space-y-3 shadow-sm">
            <div className="p-4 rounded-full bg-[var(--bg-panel-raised)] text-[var(--text-muted)]">
              <Camera size={36} />
            </div>
            <div>
              <h3 className="text-base font-bold text-[var(--text-primary)]">No CCTV Cameras Registered</h3>
              <p className="text-xs text-[var(--text-secondary)] max-w-sm mt-1">
                Connect your IP RTSP surveillance cameras, USB direct devices, or WiFi feeds to enable real-time tracking.
              </p>
            </div>
            <Link
              href="/settings/cameras"
              className="mt-2 px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-bold rounded-lg shadow-md transition-colors flex items-center gap-2"
            >
              <Plus size={14} /> Onboard Camera
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {cameras.map((cam) => (
              <StreamPlayer
                key={cam.cameraId}
                cameraId={cam.cameraId}
                cameraName={cam.label}
                cameraIp={cam.ipAddress}
                streamUrl={cam.streamUrl}
                laneId={cam.laneId}
                initialRoi={cam.roiPolygon || null}
              />
            ))}
          </div>
        )}
      </div>

      {/* 4. REAL-TIME CAMERA DETECTION TABLE (Section 2 & 18 Addendum) */}
      <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl p-5 shadow-sm space-y-3 transition-colors">
        <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
          <div>
            <h3 className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2 font-mono">
              <Eye size={18} className="text-[#38BDF8]" /> Live Real-Time Camera Detection Table
            </h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              Dynamically displays real detected objects from live edge camera streams (Real Camera &rarr; AI Detection &rarr; Tracking &rarr; Database &rarr; Frontend).
            </p>
          </div>
          <button
            onClick={fetchData}
            className="px-2.5 py-1 text-xs font-mono bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-secondary)] hover:text-white rounded border border-[var(--border-hairline)] flex items-center gap-1.5 transition-colors"
          >
            <RefreshCw size={12} /> Refresh
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-[var(--bg-canvas)] text-[var(--text-secondary)] border-b border-[var(--border-hairline)]">
              <tr>
                <th className="p-3">CAMERA</th>
                <th className="p-3">TIME</th>
                <th className="p-3">OBJECT / CLASS</th>
                <th className="p-3 text-right">QUANTITY</th>
                <th className="p-3 text-right">CONFIDENCE</th>
                <th className="p-3">PERSON ASSOCIATION</th>
                <th className="p-3">STATUS</th>
                <th className="p-3 text-right">SNAPSHOT</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
              {liveDetections.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-[var(--text-muted)]">
                    Awaiting camera object detection frames...
                  </td>
                </tr>
              ) : (
                liveDetections.map((row) => (
                  <tr key={row.detectionId} className="hover:bg-[var(--bg-panel-raised)] transition-colors">
                    <td className="p-3 font-bold text-[#38BDF8]">{row.cameraLabel}</td>
                    <td className="p-3 text-[var(--text-secondary)]">{row.timestamp}</td>
                    <td className="p-3 font-semibold text-[var(--text-primary)]">{row.objectClass}</td>
                    <td className="p-3 text-right font-bold text-[#E8A33D]">{row.quantity}</td>
                    <td className="p-3 text-right text-[var(--status-ok)]">{(row.confidence * 100).toFixed(1)}%</td>
                    <td className="p-3 text-[var(--text-secondary)]">{row.personIdentity}</td>
                    <td className="p-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          row.status === "APPROVED"
                            ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                            : "bg-amber-950 text-amber-300 border border-amber-800"
                        }`}
                      >
                        {row.status}
                      </span>
                    </td>
                    <td className="p-3 text-right">
                      <button
                        onClick={() =>
                          setPreviewSnapshot({
                            url: row.snapshotUrl || `/snapshots/preview_${row.cameraId}.jpg`,
                            title: `${row.cameraLabel} — ${row.objectClass} at ${row.timestamp}`,
                          })
                        }
                        className="px-2.5 py-1 bg-[var(--bg-canvas)] hover:bg-[var(--bg-panel-hover)] text-[#38BDF8] rounded border border-[var(--border-hairline)] text-[11px] font-bold transition-colors"
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 5. MOVEMENT MONITOR: AUTHORIZED BILL VS ACTUAL ITEM MOVEMENT (Section 7, 8, 9, 11, 18 Addendum) */}
      <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl p-5 shadow-sm space-y-3 transition-colors">
        <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
          <div>
            <h3 className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2 font-mono">
              <Layers size={18} className="text-[#10B981]" /> Material Movement Monitor & Authorization Comparison
            </h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              Tracks actual physical goods egress against scanned bills/challans (Authorized vs Detected, Progress Counter, and Discrepancy Checks).
            </p>
          </div>
          <Link href="/events" className="text-xs font-mono text-[#38BDF8] hover:underline">
            All Movement Logs &rarr;
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-[var(--bg-canvas)] text-[var(--text-secondary)] border-b border-[var(--border-hairline)]">
              <tr>
                <th className="p-3">TIME</th>
                <th className="p-3">PERSON</th>
                <th className="p-3">BILL ID</th>
                <th className="p-3">PRODUCT</th>
                <th className="p-3 text-right">AUTHORIZED</th>
                <th className="p-3 text-right">TAKEN / ACTUAL</th>
                <th className="p-3">PROGRESS</th>
                <th className="p-3">STATUS</th>
                <th className="p-3 text-right">EVIDENCE</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
              {movementMonitor.length === 0 ? (
                <tr>
                  <td colSpan={9} className="p-8 text-center text-[var(--text-muted)]">
                    No active authorized material dispatches in progress.
                  </td>
                </tr>
              ) : (
                movementMonitor.map((row) => (
                  <tr key={row.movementId} className="hover:bg-[var(--bg-panel-raised)] transition-colors">
                    <td className="p-3 text-[var(--text-secondary)]">{row.timestamp}</td>
                    <td className="p-3 font-bold text-[var(--text-primary)] flex items-center gap-1.5">
                      <UserCheck size={13} className="text-[#38BDF8]" />
                      <span>{row.personName}</span>
                    </td>
                    <td className="p-3 text-[#38BDF8] font-bold">{row.billNumber}</td>
                    <td className="p-3 font-semibold text-[var(--text-primary)]">{row.productName}</td>
                    <td className="p-3 text-right text-[var(--text-secondary)] font-bold">{row.authorizedQty} U</td>
                    <td className="p-3 text-right text-[#E8A33D] font-bold">
                      {row.actualQty} / {row.authorizedQty}
                    </td>
                    <td className="p-3 min-w-[140px]">
                      <div className="space-y-1">
                        <div className="flex justify-between text-[10px] text-[var(--text-muted)]">
                          <span>{row.progressPct}%</span>
                          <span>{row.remainingQty} left</span>
                        </div>
                        <div className="w-full bg-[var(--bg-canvas)] rounded-full h-1.5 border border-[var(--border-hairline)] overflow-hidden">
                          <div
                            className="bg-[#10B981] h-1.5 rounded-full transition-all duration-300"
                            style={{ width: `${Math.min(100, row.progressPct)}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="p-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          row.status === "CORRECT" || row.status === "PASS"
                            ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                            : row.status === "WRONG_ITEM"
                            ? "bg-rose-950 text-rose-300 border border-rose-800"
                            : row.status === "OVER_QUANTITY"
                            ? "bg-amber-950 text-amber-300 border border-amber-800"
                            : "bg-blue-950 text-blue-300 border border-blue-800"
                        }`}
                      >
                        {row.status}
                      </span>
                    </td>
                    <td className="p-3 text-right">
                      <button
                        onClick={() =>
                          setPreviewSnapshot({
                            url: row.snapshotUrl || `/snapshots/preview_CAM-01.jpg`,
                            title: `${row.personName} — ${row.billNumber} (${row.productName})`,
                          })
                        }
                        className="px-2.5 py-1 bg-[var(--bg-canvas)] hover:bg-[var(--bg-panel-hover)] text-[#38BDF8] rounded border border-[var(--border-hairline)] text-[11px] font-bold transition-colors"
                      >
                        Snapshot
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 6. Bottom Operational Stream: Traversal Events & Critical Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Exit Events */}
        <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl p-5 shadow-sm space-y-3 transition-colors">
          <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
            <h3 className="text-sm font-bold text-[var(--text-primary)] flex items-center gap-2 font-mono">
              <Layers size={16} className="text-[#38BDF8]" /> LIVE EXIT TRAVERSAL LOG
            </h3>
            <Link href="/events" className="text-xs font-mono text-[#38BDF8] hover:underline">
              View All →
            </Link>
          </div>

          <div className="space-y-2">
            {events.length === 0 ? (
              <div className="p-8 text-center text-[var(--text-muted)] text-xs font-mono">
                Awaiting exit lane crossings...
              </div>
            ) : (
              events.map((ev) => (
                <div
                  key={ev.eventId}
                  className="bg-[var(--bg-canvas)] p-3 rounded-lg border border-[var(--border-hairline)] flex justify-between items-center text-xs"
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span
                        className={`font-mono font-bold text-[10px] px-1.5 py-0.5 rounded ${
                          ev.verdict === "PASS"
                            ? "bg-[var(--status-ok)]/20 text-[var(--status-ok)]"
                            : "bg-[var(--status-high)]/20 text-[var(--status-high)]"
                        }`}
                      >
                        {ev.verdict}
                      </span>
                      <span className="font-mono text-[var(--text-primary)] font-bold">{ev.eventId}</span>
                      <span className="text-[var(--text-muted)] font-mono">{ev.laneId}</span>
                    </div>
                  </div>
                  <div className="text-right font-mono">
                    <span className="font-bold text-[var(--status-ok)]">{ev.consensusUnits} Units</span>
                    <span className="text-[10px] text-[var(--text-muted)] block">
                      {new Date(ev.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Active Alarms Queue */}
        <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl p-5 shadow-sm space-y-3 transition-colors">
          <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
            <h3 className="text-sm font-bold text-[var(--text-primary)] flex items-center gap-2 font-mono">
              <AlertTriangle size={16} className="text-[var(--status-high)]" /> ACTIVE DISCREPANCY QUEUE
            </h3>
            <Link href="/alerts" className="text-xs font-mono text-[var(--status-high)] hover:underline">
              Open Full Queue →
            </Link>
          </div>

          <div className="space-y-2">
            {alerts.length === 0 ? (
              <div className="p-8 text-center text-[var(--text-muted)] text-xs font-mono flex flex-col items-center gap-1">
                <CheckCircle size={24} className="text-[var(--status-ok)]" />
                <span>Zero active security alarms</span>
              </div>
            ) : (
              alerts.map((alt) => (
                <div
                  key={alt.alertId}
                  className="bg-[var(--bg-canvas)] p-3 rounded-lg border border-[var(--border-hairline)] flex justify-between items-center text-xs"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded uppercase ${
                          alt.severity === "HIGH"
                            ? "bg-[var(--status-high)] text-white animate-pulse"
                            : alt.severity === "MEDIUM"
                            ? "bg-[var(--status-medium)] text-white"
                            : "bg-[var(--status-low)] text-black"
                        }`}
                      >
                        {alt.severity}
                      </span>
                      <span className="font-bold text-[var(--text-primary)]">{alt.alertType.replace(/_/g, " ")}</span>
                    </div>
                    <span className="text-[10px] text-[var(--text-muted)] font-mono">
                      {alt.deltaUnits !== 0 && `Variance: ${alt.deltaUnits} U | `}
                      {new Date(alt.createdAt).toLocaleTimeString()}
                    </span>
                  </div>
                  <Link
                    href="/alerts"
                    className="px-2.5 py-1 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[#38BDF8] rounded text-xs font-mono border border-[var(--border-hairline)]"
                  >
                    Resolve
                  </Link>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Snapshot Preview Modal */}
      {previewSnapshot && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl max-w-3xl w-full p-5 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-sm font-bold font-mono text-[var(--text-primary)] flex items-center gap-2">
                <Camera size={16} className="text-[#38BDF8]" />
                {previewSnapshot.title}
              </h3>
              <button
                onClick={() => setPreviewSnapshot(null)}
                className="text-[var(--text-secondary)] hover:text-white"
              >
                <X size={18} />
              </button>
            </div>
            <div className="relative aspect-video bg-black rounded-lg overflow-hidden border border-[var(--border-hairline)]">
              <img
                src={previewSnapshot.url}
                alt={previewSnapshot.title}
                className="w-full h-full object-contain"
                onError={(e) => {
                  (e.target as HTMLImageElement).src = "/snapshots/preview_CAM-01.jpg";
                }}
              />
            </div>
            <div className="flex justify-end pt-2">
              <button
                onClick={() => setPreviewSnapshot(null)}
                className="px-4 py-1.5 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-xs font-mono"
              >
                Close Frame
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Initial Stock Count Correction Modal */}
      {editingVerif && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2">
                <Edit2 size={16} className="text-[#E8A33D]" /> Correct Stock Count Baseline
              </h3>
              <button
                onClick={() => setEditingVerif(null)}
                className="text-[var(--text-secondary)] hover:text-white"
              >
                <X size={18} />
              </button>
            </div>

            <div className="space-y-3 text-xs font-mono">
              <div className="p-3 bg-[var(--bg-canvas)] rounded-lg border border-[var(--border-hairline)]">
                <div className="text-[var(--text-muted)]">PRODUCT:</div>
                <div className="font-bold text-[var(--text-primary)] text-sm">{editingVerif.productName}</div>
                <div className="text-[var(--text-muted)] mt-1">
                  AI PROPOSED COUNT: <span className="text-[#E8A33D] font-bold">{editingVerif.aiProposedCount} units</span>
                </div>
              </div>

              <div>
                <label className="block text-[var(--text-secondary)] mb-1">ACTUAL PHYSICAL COUNT *</label>
                <input
                  type="number"
                  min="0"
                  value={correctionQty}
                  onChange={(e) => setCorrectionQty(parseInt(e.target.value) || 0)}
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-base font-bold text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div>
                <label className="block text-[var(--text-secondary)] mb-1">CORRECTION REASON / AUDIT NOTE *</label>
                <input
                  type="text"
                  value={correctionReason}
                  onChange={(e) => setCorrectionReason(e.target.value)}
                  placeholder="e.g. Broken packaging pallet, recount override"
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2.5 pt-3 border-t border-[var(--border-hairline)]">
              <button
                onClick={() => setEditingVerif(null)}
                className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-xs font-medium"
              >
                Cancel
              </button>
              <button
                onClick={() =>
                  handleConfirmStock(editingVerif.verificationId, false, correctionQty, correctionReason)
                }
                disabled={submittingCorrection}
                className="px-5 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-xs font-bold shadow-lg shadow-blue-900/30 flex items-center gap-1.5"
              >
                {submittingCorrection ? <RefreshCw size={13} className="animate-spin" /> : <Check size={13} />}
                Save Correction Baseline
              </button>
            </div>
          </div>
        </div>
      )}

      <VerifyAndSaveModal
        isOpen={showVerifyModal}
        onClose={() => setShowVerifyModal(false)}
        onSuccess={() => fetchData()}
      />
    </div>
  );
}
