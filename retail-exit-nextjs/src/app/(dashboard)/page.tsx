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
} from "lucide-react";
import Link from "next/link";

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

      // 2. Fetch Cameras
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
    } catch (e) {
      console.warn("Dashboard polling warning:", e);
    }
  };

  useEffect(() => {
    // Initial fetch on mount
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

    // Resilient fallback slow poll (30s) if WebSocket disconnects
    const fallbackInterval = setInterval(fetchData, 30000);

    return () => {
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      clearInterval(fallbackInterval);
    };
  }, []);

  return (
    <div className="space-y-6">
      {/* 1. Live KPI Top Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Active Cameras Fleet */}
        <div className="bg-[var(--bg-panel)] p-5 rounded-xl border border-[var(--border-hairline)] flex justify-between items-start shadow-sm transition-colors">
          <div>
            <span className="text-xs font-mono text-[var(--text-muted)]">CAMERAS ONLINE / TOTAL</span>
            <div className="text-2xl font-bold font-mono text-[var(--text-primary)] mt-1">
              <span className="text-[var(--status-ok)]">{kpis.camerasOnline}</span>
              <span className="text-[var(--text-muted)]"> / </span>
              <span>{kpis.camerasTotal}</span>
            </div>
            <span className="text-[11px] text-[var(--status-ok)] font-mono mt-0.5 block">Live Edge Stream</span>
          </div>
          <div className="p-2.5 rounded-lg bg-[var(--bg-panel-raised)] text-[#38BDF8]">
            <Camera size={20} />
          </div>
        </div>

        {/* Open Loss-Prevention Alerts */}
        <div className="bg-[var(--bg-panel)] p-5 rounded-xl border border-[var(--border-hairline)] flex justify-between items-start shadow-sm transition-colors">
          <div>
            <span className="text-xs font-mono text-[var(--text-muted)]">OPEN ALARMS (QUEUE)</span>
            <div className="text-2xl font-bold font-mono text-[var(--status-high)] mt-1">
              {kpis.openAlerts}
            </div>
            <span className="text-[11px] text-[var(--signal-amber)] font-mono mt-0.5 block">
              {kpis.criticalAlerts} Critical High Priority
            </span>
          </div>
          <div className="p-2.5 rounded-lg bg-[var(--bg-panel-raised)] text-[var(--status-high)]">
            <AlertTriangle size={20} />
          </div>
        </div>

        {/* Throughput Items Verified */}
        <div className="bg-[var(--bg-panel)] p-5 rounded-xl border border-[var(--border-hairline)] flex justify-between items-start shadow-sm transition-colors">
          <div>
            <span className="text-xs font-mono text-[var(--text-muted)]">AUDITED THROUGHPUT</span>
            <div className="text-2xl font-bold font-mono text-[var(--text-primary)] mt-1">
              {kpis.todayThroughput}{" "}
              <span className="text-xs font-normal text-[var(--text-muted)]">units</span>
            </div>
            <span className="text-[11px] text-[var(--status-ok)] font-mono mt-0.5 block">100% Sensor Verified</span>
          </div>
          <div className="p-2.5 rounded-lg bg-[var(--bg-panel-raised)] text-[var(--signal-amber)]">
            <Box size={20} />
          </div>
        </div>

        {/* Fusion Consensus Accuracy */}
        <div className="bg-[var(--bg-panel)] p-5 rounded-xl border border-[var(--border-hairline)] flex justify-between items-start shadow-sm transition-colors">
          <div>
            <span className="text-xs font-mono text-[var(--text-muted)]">CONSENSUS FUSION ACCURACY</span>
            <div className="text-2xl font-bold font-mono text-[var(--status-ok)] mt-1">
              {kpis.accuracyRate}%
            </div>
            <span className="text-[11px] text-[var(--text-muted)] font-mono mt-0.5 block">Vision + RFID + Weight</span>
          </div>
          <div className="p-2.5 rounded-lg bg-[var(--bg-panel-raised)] text-[var(--status-ok)]">
            <Activity size={20} />
          </div>
        </div>
      </div>

      {/* 2. Live Exit Feeds Grid with Industrial Surveillance HUD */}
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
            <Camera size={18} className="text-[#38BDF8]" /> Live Exit Feeds & Surveillance CV HUD
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

      {/* 3. Bottom Operational Stream: Traversal Events & Critical Alerts */}
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
              <AlertTriangle size={16} className="text-[var(--status-high)]]" /> ACTIVE DISCREPANCY QUEUE
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

      <VerifyAndSaveModal
        isOpen={showVerifyModal}
        onClose={() => setShowVerifyModal(false)}
        onSuccess={() => fetchData()}
      />
    </div>
  );
}
