"use client";

import { safeFetch } from "@/lib/api-client";
import React, { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import {
  Users,
  ArrowLeft,
  ShieldCheck,
  AlertTriangle,
  Clock,
  Layers,
  Key,
  Camera,
  RotateCw,
  CheckCircle,
} from "lucide-react";
import Link from "next/link";

export default function EmployeeDetailPage() {
  const params = useParams();
  const employeeId = params.employeeId as string;
  const [employee, setEmployee] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);

  // 360 Face Add Modal State
  const [show360Modal, setShow360Modal] = useState(false);
  const [files360, setFiles360] = useState<{ [angle: string]: File | null }>({
    front: null,
    left: null,
    right: null,
    up: null,
    down: null,
  });
  const [uploading360, setUploading360] = useState(false);

  const fetchDetail = async () => {
    try {
      const res = await safeFetch(`/api/employees`);
      if (res.ok) {
        const list = await res.json();
        const match = list.find((e: any) => e.employeeId === employeeId);
        if (match) setEmployee(match);
      }
      const resHist = await safeFetch(`/api/employees/${employeeId}/history`);
      if (resHist.ok) {
        const histData = await resHist.json();
        setHistory(histData.events || histData.recentEvents || []);
      }
    } catch (e) {
      console.warn("Failed to fetch employee detail:", e);
    }
  };

  useEffect(() => {
    if (!employeeId) return;
    fetchDetail();
  }, [employeeId]);

  const handleUpload360 = async (e: React.FormEvent) => {
    e.preventDefault();
    const activeFiles = Object.values(files360).filter((f): f is File => f !== null);
    if (activeFiles.length === 0) {
      alert("Please select at least 1 face angle image for 360 enrollment.");
      return;
    }
    setUploading360(true);
    try {
      const data = new FormData();
      activeFiles.forEach((file) => {
        data.append("files", file);
      });

      const res = await safeFetch(`/api/employees/${employeeId}/face-360`, {
        method: "POST",
        body: data,
      });

      if (res.ok) {
        const respData = await res.json();
        alert(respData.message || "360° Multi-Angle Biometric Profile successfully saved!");
        setShow360Modal(false);
        setFiles360({ front: null, left: null, right: null, up: null, down: null });
        fetchDetail();
      } else {
        const err = await res.json();
        alert(err.detail || "360° Face enrollment failed");
      }
    } catch (err: any) {
      alert(err.message || "Upload error");
    } finally {
      setUploading360(false);
    }
  };

  return (
    <div className="space-y-6">
      <Link
        href="/employees"
        className="text-xs font-mono text-[#38BDF8] hover:underline flex items-center gap-1.5"
      >
        <ArrowLeft size={14} /> Back to Personnel Roster
      </Link>

      <div className="bg-[var(--bg-panel)] p-6 rounded-xl border border-[var(--border-hairline)] flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <span className="text-xs font-mono text-[var(--text-secondary)]">PERSONNEL DOSSIER //</span>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] mt-1">{employee?.name || employeeId}</h1>
          <div className="flex flex-wrap items-center gap-3 mt-2 text-xs font-mono">
            <span className="px-2 py-0.5 rounded bg-[var(--bg-canvas)] text-[#38BDF8] border border-[var(--border-hairline)]">
              Role: {employee?.role || "STORE_ASSOCIATE"}
            </span>
            <span className="text-[var(--text-secondary)]">
              RFID Badge: <b className="text-[#E8A33D]">{employee?.rfidBadgeId || "BADGE-N/A"}</b>
            </span>
            <span className="text-[var(--text-secondary)]">
              Code: <b className="text-[#38BDF8]">{employee?.employeeCode || "EMP-AUTO"}</b>
            </span>
            {employee?.hasFaceEnrolled ? (
              <span className="px-2 py-0.5 rounded bg-[#4FD1B3]/10 text-[#4FD1B3] border border-[#4FD1B3]/30 font-bold flex items-center gap-1">
                <ShieldCheck size={13} /> KNOWN STAFF (VERIFIED)
              </span>
            ) : (
              <span className="px-2 py-0.5 rounded bg-[#E5484D]/10 text-[#E5484D] border border-[#E5484D]/30 font-bold flex items-center gap-1">
                <AlertTriangle size={13} /> UNKNOWN (NO FACE ENROLLED)
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShow360Modal(true)}
            className="px-4 py-2 bg-gradient-to-r from-blue-600 to-teal-600 hover:from-blue-500 hover:to-teal-500 text-white rounded-lg text-sm font-semibold flex items-center gap-2 shadow-lg shadow-blue-900/30 font-mono transition-all"
          >
            <RotateCw size={15} /> 360° Face Add
          </button>
        </div>
      </div>

      <div className="bg-[var(--bg-panel)] p-6 rounded-xl border border-[var(--border-hairline)] space-y-4">
        <h3 className="text-sm font-bold text-[var(--text-primary)] font-mono flex items-center gap-2">
          <Layers size={16} className="text-[#38BDF8]" /> RECENT EXIT TRAVERSAL LOGS FOR THIS PERSONNEL
        </h3>
        {history.length === 0 ? (
          <p className="text-xs text-[var(--text-secondary)] font-mono p-4 bg-[var(--bg-canvas)] rounded-lg">
            No historical mismatch records for this employee. Clean compliance record.
          </p>
        ) : (
          <div className="space-y-2">
            {history.map((ev: any, idx: number) => (
              <div
                key={idx}
                className="bg-[var(--bg-canvas)] p-3 rounded-lg border border-[var(--border-hairline)] flex justify-between items-center text-xs font-mono"
              >
                <span>{ev.eventId}</span>
                <span className={ev.verdict === "PASS" ? "text-[#4FD1B3]" : "text-[#E5484D]"}>{ev.verdict}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 360 Multi-Angle Face Biometric Enrollment Modal */}
      {show360Modal && (
        <div className="fixed inset-0 z-[9999] bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="card-3d max-w-xl w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                <RotateCw size={18} className="text-[#38BDF8]" /> 360° Multi-Angle Face Enrollment: {employee?.name}
              </h3>
              <button
                onClick={() => setShow360Modal(false)}
                className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] p-1 rounded-lg transition-colors"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-[var(--text-secondary)]">
              Upload multi-angle portraits (Front, Left Profile, Right Profile, Up, Down) to construct a 360-degree
              512-d ArcFace centroid. This enables omni-directional recognition at retail exit gates under any camera angle.
            </p>

            <form onSubmit={handleUpload360} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {[
                  { key: "front", label: "0° Frontal Face *" },
                  { key: "left", label: "45° Left Profile" },
                  { key: "right", label: "45° Right Profile" },
                  { key: "up", label: "15° Tilted Up" },
                  { key: "down", label: "15° Tilted Down" },
                ].map((slot) => (
                  <div
                    key={slot.key}
                    className="border border-[var(--border-hairline)] hover:border-[#38BDF8] rounded-lg p-3 text-center bg-[var(--bg-canvas)] transition-all flex flex-col justify-between"
                  >
                    <div>
                      <span className="text-[11px] font-mono text-[var(--text-secondary)] font-bold block mb-2">
                        {slot.label}
                      </span>
                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        id={`dossier-slot-${slot.key}`}
                        className="hidden"
                        onChange={(e) => {
                          const f = e.target.files?.[0] || null;
                          setFiles360((prev) => ({ ...prev, [slot.key]: f }));
                        }}
                      />
                      <label
                        htmlFor={`dossier-slot-${slot.key}`}
                        className="cursor-pointer block py-2 border border-dashed border-[var(--border-hairline)] hover:border-[#38BDF8] rounded bg-[var(--bg-panel-raised)]"
                      >
                        <Camera size={18} className="mx-auto text-[#38BDF8] mb-1" />
                        <span className="text-[10px] text-[var(--text-muted)] block truncate px-1">
                          {files360[slot.key]?.name || "Select Image"}
                        </span>
                      </label>
                    </div>
                    {files360[slot.key] && (
                      <span className="text-[10px] text-[#4FD1B3] font-mono font-bold mt-1.5 flex items-center justify-center gap-1">
                        <CheckCircle size={10} /> Loaded
                      </span>
                    )}
                  </div>
                ))}
              </div>

              <div className="flex justify-between items-center text-xs font-mono text-[var(--text-secondary)] pt-2 border-t border-[var(--border-hairline)]">
                <span>
                  Angles Ready:{" "}
                  <b className="text-[#38BDF8]">
                    {Object.values(files360).filter((f) => f !== null).length} / 5
                  </b>
                </span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setShow360Modal(false)}
                    className="px-3.5 py-1.5 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-xs font-medium"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={uploading360 || Object.values(files360).filter((f) => f !== null).length === 0}
                    className="px-4 py-1.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-xs font-semibold shadow-lg shadow-blue-900/30 disabled:opacity-50 flex items-center gap-1.5"
                  >
                    {uploading360 ? "Synthesizing 360 Embeddings..." : "Save 360° Profile"}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
