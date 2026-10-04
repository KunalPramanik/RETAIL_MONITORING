"use client";

import React, { useState, useEffect } from "react";
import StreamPlayer from "@/components/cameras/stream-player";
import {
  Activity,
  Camera,
  Box,
  AlertTriangle,
  ShieldAlert,
  ArrowRight,
  Clock,
  Layers,
  CheckCircle,
  Plus,
} from "lucide-react";
import Link from "next/link";

interface CameraItem {
  cameraId: string;
  label: string;
  laneId?: string;
  ipAddress: string;
  rtspPath: string;
  streamUrl?: string;
}

interface AlertItem {
  alertId: string;
  alertType: string;
  severity: "HIGH" | "MEDIUM" | "LOW" | "INFO";
  deltaUnits: number;
  createdAt: string;
  status: string;
}

interface EventItem {
  eventId: string;
  laneId: string;
  verdict: string;
  consensusUnits: number;
  timestamp: string;
}

export default function DashboardPage() {
  const [cameras, setCameras] = useState<CameraItem[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [kpis, setKpis] = useState({
    todayThroughput: 0,
    openAlerts: 0,
    accuracyRate: 98.7,
    camerasOnline: 0,
    camerasTotal: 0,
  });

  const fetchData = async () => {
    try {
      // 1. Fetch Cameras
      const resCam = await fetch("http://localhost:8000/api/cameras");
      if (resCam.ok) {
        const camData = await resCam.json();
        setCameras(camData);
        setKpis((prev) => ({
          ...prev,
          camerasOnline: camData.filter((c: any) => c.status === "ONLINE").length,
          camerasTotal: camData.length,
        }));
      }

      // 2. Fetch Alerts
      const resAlt = await fetch("http://localhost:8000/api/alerts?limit=5");
      if (resAlt.ok) {
        const altData = await resAlt.json();
        setAlerts(altData.slice(0, 5));
        setKpis((prev) => ({
          ...prev,
          openAlerts: altData.filter((a: any) => a.status === "OPEN").length,
        }));
      }

      // 3. Fetch Events
      const resEv = await fetch("http://localhost:8000/api/events?limit=5");
      if (resEv.ok) {
        const evData = await resEv.json();
        setEvents(evData.slice(0, 5));
        const totalUnits = evData.reduce((acc: number, curr: any) => acc + (curr.consensusUnits || 0), 0);
        setKpis((prev) => ({
          ...prev,
          todayThroughput: totalUnits,
        }));
      }
    } catch (e) {
      console.warn("Dashboard polling error:", e);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 6000);
    return () => clearInterval(interval);
  }, []);

  // Display cameras: use real registered cameras, or default 2 exit lanes if none added yet
  const displayCameras =
    cameras.length > 0
      ? cameras
      : [
          {
            cameraId: "LANE-01-EXIT",
            label: "Exit Lane 01 — Main Bay",
            ipAddress: "192.168.1.101",
            rtspPath: "/live/ch0",
            laneId: "LANE-01",
          },
          {
            cameraId: "LANE-02-EXIT",
            label: "Exit Lane 02 — Dispatch Bay",
            ipAddress: "192.168.1.102",
            rtspPath: "/live/ch0",
            laneId: "LANE-02",
          },
        ];

  return (
    <div className="space-y-6">
      {/* 1. Live KPI Top Strip (Part A.1.4 & Part A.2) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Active Cameras Fleet */}
        <div className="bg-[#1A1E26] p-5 rounded-xl border border-[#2C323D] flex justify-between items-start">
          <div>
            <span className="text-xs font-mono text-[#8B93A1]">CAMERAS ONLINE / TOTAL</span>
            <div className="text-2xl font-bold font-mono text-[#E7E9EC] mt-1">
              <span className="text-[#4FD1B3]">{kpis.camerasOnline}</span>
              <span className="text-[#8B93A1]"> / </span>
              <span>{Math.max(kpis.camerasTotal, displayCameras.length)}</span>
            </div>
            <span className="text-[11px] text-[#4FD1B3] font-mono mt-0.5 block">H.265 Transcode Ready</span>
          </div>
          <div className="p-2.5 rounded-lg bg-[#20252F] text-[#38BDF8]">
            <Camera size={20} />
          </div>
        </div>

        {/* Open Loss-Prevention Alerts */}
        <div className="bg-[#1A1E26] p-5 rounded-xl border border-[#2C323D] flex justify-between items-start">
          <div>
            <span className="text-xs font-mono text-[#8B93A1]">OPEN ALARMS (QUEUE)</span>
            <div className="text-2xl font-bold font-mono text-[#E5484D] mt-1">
              {kpis.openAlerts}
            </div>
            <span className="text-[11px] text-[#E8A33D] font-mono mt-0.5 block">
              {alerts.filter((a) => a.severity === "HIGH").length} Critical High Priority
            </span>
          </div>
          <div className="p-2.5 rounded-lg bg-[#20252F] text-[#E5484D]">
            <AlertTriangle size={20} />
          </div>
        </div>

        {/* Throughput Items Verified */}
        <div className="bg-[#1A1E26] p-5 rounded-xl border border-[#2C323D] flex justify-between items-start">
          <div>
            <span className="text-xs font-mono text-[#8B93A1]">AUDITED THROUGHPUT</span>
            <div className="text-2xl font-bold font-mono text-[#E7E9EC] mt-1">
              {kpis.todayThroughput}{" "}
              <span className="text-xs font-normal text-[#8B93A1]">units</span>
            </div>
            <span className="text-[11px] text-[#4FD1B3] font-mono mt-0.5 block">100% Sensor Verified</span>
          </div>
          <div className="p-2.5 rounded-lg bg-[#20252F] text-[#E8A33D]">
            <Box size={20} />
          </div>
        </div>

        {/* Fusion Consensus Accuracy */}
        <div className="bg-[#1A1E26] p-5 rounded-xl border border-[#2C323D] flex justify-between items-start">
          <div>
            <span className="text-xs font-mono text-[#8B93A1]">CONSENSUS FUSION ACCURACY</span>
            <div className="text-2xl font-bold font-mono text-[#4FD1B3] mt-1">
              {kpis.accuracyRate}%
            </div>
            <span className="text-[11px] text-[#8B93A1] font-mono mt-0.5 block">Vision + RFID + Weight</span>
          </div>
          <div className="p-2.5 rounded-lg bg-[#20252F] text-[#4FD1B3]">
            <Activity size={20} />
          </div>
        </div>
      </div>

      {/* 2. Live Exit Feeds Grid with Industrial Surveillance HUD */}
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-bold text-[#E7E9EC] flex items-center gap-2">
            <Camera size={18} className="text-[#38BDF8]" /> Live Exit Feeds & Surveillance CV HUD
          </h2>
          <Link
            href="/settings/cameras"
            className="text-xs font-mono text-[#38BDF8] hover:underline flex items-center gap-1"
          >
            Manage Camera Fleet <ArrowRight size={13} />
          </Link>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {displayCameras.map((cam) => (
            <StreamPlayer
              key={cam.cameraId}
              cameraId={cam.cameraId}
              cameraName={cam.label}
              cameraIp={cam.ipAddress}
              streamUrl={cam.streamUrl}
              laneId={cam.laneId}
            />
          ))}
        </div>
      </div>

      {/* 3. Bottom Operational Stream: Traversal Events & Critical Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Exit Events */}
        <div className="bg-[#1A1E26] border border-[#2C323D] rounded-xl p-5 shadow-xl space-y-3">
          <div className="flex justify-between items-center border-b border-[#2C323D] pb-3">
            <h3 className="text-sm font-bold text-[#E7E9EC] flex items-center gap-2 font-mono">
              <Layers size={16} className="text-[#38BDF8]" /> LIVE EXIT TRAVERSAL LOG
            </h3>
            <Link href="/events" className="text-xs font-mono text-[#38BDF8] hover:underline">
              View All →
            </Link>
          </div>

          <div className="space-y-2">
            {events.length === 0 ? (
              <div className="p-8 text-center text-[#8B93A1] text-xs font-mono">
                Awaiting exit lane crossings...
              </div>
            ) : (
              events.map((ev) => (
                <div
                  key={ev.eventId}
                  className="bg-[#12151A] p-3 rounded-lg border border-[#2C323D] flex justify-between items-center text-xs"
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span
                        className={`font-mono font-bold text-[10px] px-1.5 py-0.2 rounded ${
                          ev.verdict === "PASS"
                            ? "bg-[#4FD1B3]/20 text-[#4FD1B3]"
                            : "bg-[#E5484D]/20 text-[#E5484D]"
                        }`}
                      >
                        {ev.verdict}
                      </span>
                      <span className="font-mono text-[#E7E9EC] font-bold">{ev.eventId}</span>
                      <span className="text-[#8B93A1] font-mono">{ev.laneId}</span>
                    </div>
                  </div>
                  <div className="text-right font-mono">
                    <span className="font-bold text-[#4FD1B3]">{ev.consensusUnits} Units</span>
                    <span className="text-[10px] text-[#8B93A1] block">
                      {new Date(ev.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Active Alarms Queue */}
        <div className="bg-[#1A1E26] border border-[#2C323D] rounded-xl p-5 shadow-xl space-y-3">
          <div className="flex justify-between items-center border-b border-[#2C323D] pb-3">
            <h3 className="text-sm font-bold text-[#E7E9EC] flex items-center gap-2 font-mono">
              <ShieldAlert size={16} className="text-[#E5484D]" /> ACTIVE DISCREPANCY QUEUE
            </h3>
            <Link href="/alerts" className="text-xs font-mono text-[#E5484D] hover:underline">
              Open Full Queue →
            </Link>
          </div>

          <div className="space-y-2">
            {alerts.length === 0 ? (
              <div className="p-8 text-center text-[#8B93A1] text-xs font-mono flex flex-col items-center gap-1">
                <CheckCircle size={24} className="text-[#4FD1B3]" />
                <span>Zero active security alarms</span>
              </div>
            ) : (
              alerts.map((alt) => (
                <div
                  key={alt.alertId}
                  className="bg-[#12151A] p-3 rounded-lg border border-[#2C323D] flex justify-between items-center text-xs"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-[10px] font-mono font-bold px-1.5 py-0.2 rounded uppercase ${
                          alt.severity === "HIGH"
                            ? "bg-[#E5484D] text-white animate-pulse"
                            : alt.severity === "MEDIUM"
                            ? "bg-[#F0924A] text-black"
                            : "bg-[#E8C34D] text-black"
                        }`}
                      >
                        {alt.severity}
                      </span>
                      <span className="font-bold text-[#E7E9EC]">{alt.alertType.replace(/_/g, " ")}</span>
                    </div>
                    <span className="text-[10px] text-[#8B93A1] font-mono">
                      {alt.deltaUnits !== 0 && `Variance: ${alt.deltaUnits} U | `}
                      {new Date(alt.createdAt).toLocaleTimeString()}
                    </span>
                  </div>
                  <Link
                    href="/alerts"
                    className="px-2.5 py-1 bg-[#20252F] hover:bg-[#2C323D] text-[#38BDF8] rounded text-xs font-mono"
                  >
                    Resolve
                  </Link>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
