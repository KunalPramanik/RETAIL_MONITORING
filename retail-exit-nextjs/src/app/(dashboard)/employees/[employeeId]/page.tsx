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
} from "lucide-react";
import Link from "next/link";

export default function EmployeeDetailPage() {
  const params = useParams();
  const employeeId = params.employeeId as string;
  const [employee, setEmployee] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);

  useEffect(() => {
    if (!employeeId) return;
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
          setHistory(histData.recentEvents || []);
        }
      } catch (e) {
        console.warn("Failed to fetch employee detail:", e);
      }
    };
    fetchDetail();
  }, [employeeId]);

  return (
    <div className="space-y-6">
      <Link
        href="/employees"
        className="text-xs font-mono text-[#38BDF8] hover:underline flex items-center gap-1.5"
      >
        <ArrowLeft size={14} /> Back to Personnel Roster
      </Link>

      <div className="bg-[var(--bg-panel)] p-6 rounded-xl border border-[var(--border-hairline)] flex justify-between items-center">
        <div>
          <span className="text-xs font-mono text-[var(--text-secondary)]">PERSONNEL DOSSIER //</span>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] mt-1">{employee?.name || employeeId}</h1>
          <div className="flex items-center gap-3 mt-2 text-xs font-mono">
            <span className="px-2 py-0.5 rounded bg-[var(--bg-canvas)] text-[#38BDF8] border border-[var(--border-hairline)]">
              Role: {employee?.role || "STORE_ASSOCIATE"}
            </span>
            <span className="text-[var(--text-secondary)]">
              RFID Badge: <b className="text-[#E8A33D]">{employee?.rfidBadgeId || "BADGE-N/A"}</b>
            </span>
          </div>
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
    </div>
  );
}
