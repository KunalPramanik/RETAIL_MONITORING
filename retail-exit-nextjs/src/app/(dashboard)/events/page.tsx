"use client";

import React, { useState, useEffect } from "react";
import { safeFetch } from "@/lib/api-client";
import VerifyAndSaveModal from "@/components/dispatch/verify-and-save-modal";
import {
  Activity,
  Search,
  RefreshCw,
  Clock,
  CheckCircle,
  AlertTriangle,
  Eye,
  FileSpreadsheet,
  Download,
  FileCheck,
} from "lucide-react";

interface ExitEventItem {
  eventId: string;
  timestamp: string;
  laneId: string;
  casesDetected: number;
  unitsDetected: number;
  consensusUnits: number;
  declaredUnits?: number;
  deltaUnits?: number;
  verdict: "PASS" | "MISMATCH";
  severity: "NONE" | "LOW" | "MEDIUM" | "HIGH";
  snapshotUrl?: string;
  employeeId?: string;
}

export default function EventsPage() {
  const [events, setEvents] = useState<ExitEventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [verdictFilter, setVerdictFilter] = useState("ALL");
  const [selectedEvent, setSelectedEvent] = useState<ExitEventItem | null>(null);
  const [showVerifyModal, setShowVerifyModal] = useState(false);

  const fetchEvents = async () => {
    try {
      setLoading(true);
      const res = await safeFetch("/api/events");
      if (res.ok) {
        const data = await res.json();
        setEvents(data);
      }
    } catch (e) {
      console.warn("Failed to fetch events:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, []);

  const filtered = events.filter((ev) => {
    const matchesVerdict = verdictFilter === "ALL" || ev.verdict === verdictFilter;
    const matchesSearch =
      !search ||
      ev.eventId.toLowerCase().includes(search.toLowerCase()) ||
      ev.laneId.toLowerCase().includes(search.toLowerCase());
    return matchesVerdict && matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-[var(--bg-panel)] p-6 rounded-xl border border-[var(--border-hairline)]">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center gap-3">
            <Activity className="text-[#38BDF8]" /> Exit Bay Traversal Event Stream
          </h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">
            Complete multi-sensor fusion audit trail: YOLOX vision count, RFID tag reads, and weight scale consensus.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowVerifyModal(true)}
            className="px-3.5 py-2 bg-[#10B981] hover:bg-[#059669] text-white rounded-lg text-sm font-semibold flex items-center gap-2 shadow-lg shadow-emerald-900/30 transition-all font-mono"
          >
            <FileCheck size={15} /> Verify & Save (DD.3)
          </button>
          <button
            onClick={fetchEvents}
            className="px-3.5 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
          >
            <RefreshCw size={15} /> Refresh Stream
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between bg-[var(--bg-panel)] p-4 rounded-xl border border-[var(--border-hairline)]">
        <div className="relative flex-1 max-w-md">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by event ID or exit lane..."
            className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg pl-10 pr-4 py-2 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] outline-none focus:border-[#38BDF8]"
          />
        </div>
        <div className="flex items-center gap-2">
          {["ALL", "PASS", "MISMATCH"].map((v) => (
            <button
              key={v}
              onClick={() => setVerdictFilter(v)}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-colors ${
                verdictFilter === v
                  ? "bg-[#2563EB] text-white"
                  : "bg-[var(--bg-canvas)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border-hairline)]"
              }`}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      {/* Events Table */}
      <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl overflow-hidden shadow-xl">
        {filtered.length === 0 && !loading ? (
          <div className="p-12 text-center text-[var(--text-secondary)]">
            <Activity size={40} className="mx-auto mb-3 text-[#2C323D]" />
            <h4 className="text-base font-bold text-[var(--text-primary)]">No exit events recorded yet</h4>
            <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-sm mx-auto">
              Real-time exit traversal events will appear here automatically when subjects cross active lane tripwires.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-[var(--bg-canvas)] text-[var(--text-secondary)] text-xs font-mono border-b border-[var(--border-hairline)]">
                <tr>
                  <th className="p-4">VERDICT</th>
                  <th className="p-4">EVENT ID</th>
                  <th className="p-4">EXIT LANE</th>
                  <th className="p-4">PACK MATH (CASES / UNITS)</th>
                  <th className="p-4">CONSENSUS QTY</th>
                  <th className="p-4">DECLARED QTY</th>
                  <th className="p-4">VARIANCE</th>
                  <th className="p-4 text-right">TIMESTAMP</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
                {filtered.map((item) => (
                  <tr key={item.eventId} className="hover:bg-[var(--bg-panel-raised)] transition-colors">
                    <td className="p-4">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] font-mono font-bold ${
                          item.verdict === "PASS"
                            ? "bg-[#4FD1B3]/15 text-[#4FD1B3] border border-[#4FD1B3]/40"
                            : "bg-[#E5484D]/15 text-[#E5484D] border border-[#E5484D]/40 animate-pulse"
                        }`}
                      >
                        {item.verdict === "PASS" ? <CheckCircle size={12} /> : <AlertTriangle size={12} />}
                        {item.verdict}
                      </span>
                    </td>
                    <td className="p-4 font-mono font-bold text-[#38BDF8]">{item.eventId}</td>
                    <td className="p-4 font-mono text-xs text-[var(--text-primary)]">{item.laneId}</td>
                    <td className="p-4 font-mono text-xs">
                      <span className="text-[#E8A33D] font-bold">{item.casesDetected} Cases</span> /{" "}
                      <span className="text-[var(--text-primary)]">{item.unitsDetected} Units</span>
                    </td>
                    <td className="p-4 font-mono font-bold text-[#4FD1B3]">{item.consensusUnits} U</td>
                    <td className="p-4 font-mono text-xs text-[var(--text-secondary)]">
                      {item.declaredUnits !== undefined ? `${item.declaredUnits} U` : "N/A"}
                    </td>
                    <td className="p-4 font-mono text-xs">
                      {item.deltaUnits ? (
                        <span className={item.deltaUnits > 0 ? "text-[#E5484D] font-bold" : "text-[#E8A33D]"}>
                          {item.deltaUnits > 0 ? `+${item.deltaUnits}` : item.deltaUnits} U
                        </span>
                      ) : (
                        <span className="text-[#4FD1B3]">0</span>
                      )}
                    </td>
                    <td className="p-4 font-mono text-xs text-right text-[var(--text-secondary)]">
                      {new Date(item.timestamp).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <VerifyAndSaveModal
        isOpen={showVerifyModal}
        onClose={() => setShowVerifyModal(false)}
        onSuccess={() => fetchEvents()}
      />
    </div>
  );
}
