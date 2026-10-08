"use client";

import { safeFetch } from "@/lib/api-client";
import React, { useState, useEffect, useRef } from "react";
import {
  AlertTriangle,
  ShieldAlert,
  CheckCircle,
  Clock,
  UserCheck,
  FileCheck,
  Unlock,
  PenTool,
  RotateCcw,
  RefreshCw,
  Search,
  Filter,
} from "lucide-react";

interface AlertItem {
  alertId: string;
  eventId?: string;
  cameraId?: string;
  alertType: string;
  severity: "HIGH" | "MEDIUM" | "LOW" | "INFO";
  deltaUnits: number;
  createdAt: string;
  status: "OPEN" | "ACKNOWLEDGED" | "RESOLVED";
  resolvedBy?: string;
  resolutionNote?: string;
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [severityFilter, setSeverityFilter] = useState<string>("ALL");

  // Supervisor Signature Modal State (Part CC.3)
  const [resolvingAlert, setResolvingAlert] = useState<AlertItem | null>(null);
  const [resolutionNote, setResolutionNote] = useState("");
  const [supervisorName, setSupervisorName] = useState("Chief Security Officer");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Canvas Signature Pad
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [hasSignature, setHasSignature] = useState(false);

  const fetchAlerts = async () => {
    try {
      setLoading(true);
      const res = await safeFetch("/api/alerts");
      if (res.ok) {
        const data = await res.json();
        // Sort: OPEN first, then HIGH -> MEDIUM -> LOW
        const sorted = data.sort((a: AlertItem, b: AlertItem) => {
          if (a.status === "OPEN" && b.status !== "OPEN") return -1;
          if (b.status === "OPEN" && a.status !== "OPEN") return 1;
          const sevMap: Record<string, number> = { HIGH: 3, MEDIUM: 2, LOW: 1, INFO: 0 };
          return (sevMap[b.severity] || 0) - (sevMap[a.severity] || 0);
        });
        setAlerts(sorted);
      }
    } catch (e) {
      console.warn("Fetch alerts failed:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleAcknowledge = async (alertId: string) => {
    try {
      const res = await safeFetch(`/api/alerts/${alertId}/acknowledge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ acknowledgedBy: "Supervisor" }),
      });
      if (res.ok) fetchAlerts();
    } catch (e) {
      console.warn("Ack error:", e);
    }
  };

  // Canvas Drawing Handlers
  const startDrawing = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    setIsDrawing(true);
    setHasSignature(true);
    const rect = canvas.getBoundingClientRect();
    ctx.beginPath();
    ctx.moveTo(e.clientX - rect.left, e.clientY - rect.top);
  };

  const drawSignature = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const rect = canvas.getBoundingClientRect();
    ctx.lineWidth = 2.5;
    ctx.lineCap = "round";
    ctx.strokeStyle = "#38BDF8"; // Cyan ink
    ctx.lineTo(e.clientX - rect.left, e.clientY - rect.top);
    ctx.stroke();
  };

  const stopDrawing = () => {
    setIsDrawing(false);
  };

  const clearSignature = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setHasSignature(false);
  };

  // Handle Supervisor Signature Resolution (Part CC.3)
  const handleSubmitResolution = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resolvingAlert) return;
    if (!hasSignature) {
      alert("Supervisor digital signature is required before turnstile override!");
      return;
    }
    if (resolutionNote.trim().length < 5) {
      alert("Please provide a detailed loss-prevention resolution note (min 5 chars).");
      return;
    }

    setIsSubmitting(true);
    try {
      // 1. Resolve alert
      const res = await safeFetch(`/api/alerts/${resolvingAlert.alertId}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resolutionNote: resolutionNote.trim(),
          resolvedBy: supervisorName,
        }),
      });

      if (res.ok) {
        // 2. Command turnstile unlock
        await safeFetch("/api/hardware/turnstile/unlock", {
          method: "POST",
        });

        alert("Alert RESOLVED & Turnstile barrier unlocked with legal supervisor signature audit log.");
        setResolvingAlert(null);
        setResolutionNote("");
        clearSignature();
        fetchAlerts();
      } else {
        const err = await res.json();
        alert(err.detail || "Resolution failed");
      }
    } catch (err: any) {
      alert(err.message || "Failed to complete resolution");
    } finally {
      setIsSubmitting(false);
    }
  };

  const filtered = alerts.filter((a) => {
    const matchesStatus = statusFilter === "ALL" || a.status === statusFilter;
    const matchesSeverity = severityFilter === "ALL" || a.severity === severityFilter;
    return matchesStatus && matchesSeverity;
  });

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-[var(--bg-panel)] p-6 rounded-xl border border-[var(--border-hairline)]">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center gap-3">
            <ShieldAlert className="text-[#E5484D]" /> Real-Time Discrepancy & Security Alarms
          </h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">
            Severity-ranked loss-prevention alarms, sensor divergence, inventory mismatches, and Supervisor Signature
            Gate turnstile unlock controls.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchAlerts}
            className="px-3.5 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
          >
            <RefreshCw size={15} /> Refresh Queue
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-[var(--bg-panel)] p-4 rounded-xl border border-[var(--border-hairline)]">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-[var(--text-secondary)]">STATUS:</span>
          {["ALL", "OPEN", "ACKNOWLEDGED", "RESOLVED"].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
                statusFilter === st
                  ? "bg-[#2563EB] text-white font-bold"
                  : "bg-[var(--bg-canvas)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border-hairline)]"
              }`}
            >
              {st}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-[var(--text-secondary)]">SEVERITY:</span>
          {["ALL", "HIGH", "MEDIUM", "LOW"].map((sev) => (
            <button
              key={sev}
              onClick={() => setSeverityFilter(sev)}
              className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
                severityFilter === sev
                  ? "bg-[#2563EB] text-white font-bold"
                  : "bg-[var(--bg-canvas)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border-hairline)]"
              }`}
            >
              {sev}
            </button>
          ))}
        </div>
      </div>

      {/* Alerts Stream List */}
      <div className="space-y-3">
        {filtered.length === 0 && !loading ? (
          <div className="p-12 text-center text-[var(--text-secondary)] bg-[var(--bg-panel)] rounded-xl border border-[var(--border-hairline)]">
            <CheckCircle size={40} className="mx-auto mb-3 text-[#4FD1B3]" />
            <h4 className="text-base font-bold text-[var(--text-primary)]">Zero Active Discrepancies</h4>
            <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-sm mx-auto">
              All exit-bay sensor consensus checks and invoice matches are currently operating within tolerance.
            </p>
          </div>
        ) : (
          filtered.map((item) => {
            const isHigh = item.severity === "HIGH";
            const isMedium = item.severity === "MEDIUM";
            const borderCol = isHigh
              ? "border-[#E5484D] shadow-[0_0_15px_rgba(229,72,77,0.15)]"
              : isMedium
              ? "border-[#F0924A]"
              : "border-[#E8C34D]";
            const pillCol = isHigh
              ? "bg-[#E5484D] text-white"
              : isMedium
              ? "bg-[#F0924A] text-black"
              : "bg-[#E8C34D] text-black";

            return (
              <div
                key={item.alertId}
                className={`p-5 rounded-xl border-l-4 bg-[var(--bg-panel)] border border-[var(--border-hairline)] ${borderCol} flex flex-col md:flex-row justify-between items-start md:items-center gap-4 transition-all`}
              >
                <div className="space-y-1.5 flex-1">
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold uppercase ${pillCol}`}>
                      {item.severity} SEVERITY
                    </span>
                    <span className="font-mono text-xs text-[var(--text-secondary)]">{item.alertId}</span>
                    <span className="font-mono text-xs text-[#38BDF8]">
                      {item.cameraId || item.eventId || "SYSTEM-EVENT"}
                    </span>
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                        item.status === "OPEN"
                          ? "bg-[#E5484D]/20 text-[#E5484D] border border-[#E5484D]/30 animate-pulse"
                          : item.status === "ACKNOWLEDGED"
                          ? "bg-[#E8A33D]/20 text-[#E8A33D] border border-[#E8A33D]/30"
                          : "bg-[#4FD1B3]/20 text-[#4FD1B3] border border-[#4FD1B3]/30"
                      }`}
                    >
                      {item.status}
                    </span>
                  </div>

                  <h3 className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2">
                    {item.alertType.replace(/_/g, " ")}
                    {item.deltaUnits !== 0 && (
                      <span className="text-xs font-mono font-normal text-[#E5484D]">
                        (Variance: {item.deltaUnits > 0 ? `+${item.deltaUnits}` : item.deltaUnits} units)
                      </span>
                    )}
                  </h3>

                  {item.resolutionNote && (
                    <p className="text-xs text-[#B8E3D6] font-mono bg-[var(--bg-canvas)] p-2 rounded border border-[var(--border-hairline)]">
                      Resolution: {item.resolutionNote} — Authorized by {item.resolvedBy}
                    </p>
                  )}

                  <div className="text-xs text-[var(--text-secondary)] font-mono flex items-center gap-2">
                    <Clock size={12} /> {new Date(item.createdAt).toLocaleString()}
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex items-center gap-2 w-full md:w-auto justify-end">
                  {item.status === "OPEN" && (
                    <button
                      onClick={() => handleAcknowledge(item.alertId)}
                      className="px-3 py-1.5 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[#E8A33D] border border-[var(--border-hairline)] rounded-lg text-xs font-mono font-medium transition-colors"
                    >
                      Acknowledge
                    </button>
                  )}

                  {item.status !== "RESOLVED" && (
                    <button
                      onClick={() => {
                        setResolvingAlert(item);
                        setResolutionNote("");
                        clearSignature();
                      }}
                      className="px-4 py-1.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow transition-colors"
                    >
                      <Unlock size={14} /> Resolve & Override Gate
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Supervisor Signature Gate Modal (Part CC.3) */}
      {resolvingAlert && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                <ShieldAlert size={18} className="text-[#E5484D]" /> Supervisor Signature Gate (Part CC.3)
              </h3>
              <button onClick={() => setResolvingAlert(null)} className="text-[var(--text-secondary)] hover:text-white">
                ✕
              </button>
            </div>

            <div className="bg-[var(--bg-canvas)] p-3 rounded-lg border border-[var(--border-hairline)] text-xs font-mono text-[var(--text-secondary)] space-y-1">
              <div>
                Alert Target: <b className="text-[var(--text-primary)]">{resolvingAlert.alertType}</b> (#{resolvingAlert.alertId})
              </div>
              <div>
                Discrepancy Variance: <b className="text-[#E5484D]">{resolvingAlert.deltaUnits} units</b>
              </div>
              <p className="text-[11px] text-[#E8A33D] pt-1">
                Notice: Turnstile will remain mechanically LOCKED until legal digital supervisor signature is recorded
                in immutable audit logs.
              </p>
            </div>

            <form onSubmit={handleSubmitResolution} className="space-y-4 text-sm">
              <div>
                <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">SUPERVISOR / OFFICER NAME *</label>
                <input
                  type="text"
                  required
                  value={supervisorName}
                  onChange={(e) => setSupervisorName(e.target.value)}
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">
                  MANDATORY LOSS-PREVENTION RESOLUTION NOTE *
                </label>
                <textarea
                  required
                  rows={2}
                  value={resolutionNote}
                  onChange={(e) => setResolutionNote(e.target.value)}
                  placeholder="e.g. Verified with store manager. Discrepancy cleared due to promotional sample pack."
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] outline-none text-xs font-mono"
                />
              </div>

              {/* Digital Signature Pad (Part CC.3) */}
              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="text-xs font-mono text-[var(--text-secondary)] flex items-center gap-1.5">
                    <PenTool size={13} className="text-[#38BDF8]" /> DIGITAL SIGNATURE PAD (DRAW WITH MOUSE/PEN) *
                  </label>
                  <button
                    type="button"
                    onClick={clearSignature}
                    className="text-[11px] font-mono text-[var(--text-secondary)] hover:text-[#E5484D] flex items-center gap-1"
                  >
                    <RotateCcw size={11} /> Clear Ink
                  </button>
                </div>
                <div className="border border-[var(--border-hairline)] rounded-lg bg-black overflow-hidden relative cursor-crosshair">
                  <canvas
                    ref={canvasRef}
                    width={450}
                    height={120}
                    onMouseDown={startDrawing}
                    onMouseMove={drawSignature}
                    onMouseUp={stopDrawing}
                    onMouseLeave={stopDrawing}
                    className="w-full h-[120px]"
                  />
                  {!hasSignature && (
                    <div className="absolute inset-0 flex items-center justify-center text-gray-600 font-mono text-xs pointer-events-none">
                      Sign Here to Authorize Gate Unlock
                    </div>
                  )}
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-2 border-t border-[var(--border-hairline)]">
                <button
                  type="button"
                  onClick={() => setResolvingAlert(null)}
                  className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-sm font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || !hasSignature}
                  className="px-5 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-sm font-semibold shadow-lg shadow-blue-900/30 flex items-center gap-2 disabled:opacity-50"
                >
                  <Unlock size={15} /> {isSubmitting ? "Authorizing..." : "Sign & Unlock Turnstile"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
