"use client";

import React, { useState, useEffect } from "react";
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

  const fetchEvents = async () => {
    try {
      setLoading(true);
      const res = await fetch("http://localhost:8000/api/events");
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
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-[#1A1E26] p-6 rounded-xl border border-[#2C323D]">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#E7E9EC] flex items-center gap-3">
            <Activity className="text-[#38BDF8]" /> Exit Bay Traversal Event Stream
          </h1>
          <p className="text-[#8B93A1] text-sm mt-1">
            Complete multi-sensor fusion audit trail: YOLOX vision count, RFID tag reads, and weight scale consensus.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchEvents}
            className="px-3.5 py-2 bg-[#20252F] hover:bg-[#2C323D] text-[#E7E9EC] border border-[#2C323D] rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
          >
            <RefreshCw size={15} /> Refresh Stream
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between bg-[#1A1E26] p-4 rounded-xl border border-[#2C323D]">
        <div className="relative flex-1 max-w-md">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#8B93A1]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by event ID or exit lane..."
            className="w-full bg-[#12151A] border border-[#2C323D] rounded-lg pl-10 pr-4 py-2 text-sm text-[#E7E9EC] placeholder-[#8B93A1] outline-none focus:border-[#38BDF8]"
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
                  : "bg-[#12151A] text-[#8B93A1] hover:text-[#E7E9EC] border border-[#2C323D]"
              }`}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      {/* Events Table */}
      <div className="bg-[#1A1E26] border border-[#2C323D] rounded-xl overflow-hidden shadow-xl">
        {filtered.length === 0 && !loading ? (
          <div className="p-12 text-center text-[#8B93A1]">
            <Activity size={40} className="mx-auto mb-3 text-[#2C323D]" />
            <h4 className="text-base font-bold text-[#E7E9EC]">No exit events recorded yet</h4>
            <p className="text-xs text-[#8B93A1] mt-1 max-w-sm mx-auto">
              Real-time exit traversal events will appear here automatically when subjects cross active lane tripwires.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-[#12151A] text-[#8B93A1] text-xs font-mono border-b border-[#2C323D]">
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
              <tbody className="divide-y divide-[#2C323D] text-[#E7E9EC]">
                {filtered.map((item) => (
                  <tr key={item.eventId} className="hover:bg-[#20252F] transition-colors">
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
                    <td className="p-4 font-mono text-xs text-[#E7E9EC]">{item.laneId}</td>
                    <td className="p-4 font-mono text-xs">
                      <span className="text-[#E8A33D] font-bold">{item.casesDetected} Cases</span> /{" "}
                      <span className="text-[#E7E9EC]">{item.unitsDetected} Units</span>
                    </td>
                    <td className="p-4 font-mono font-bold text-[#4FD1B3]">{item.consensusUnits} U</td>
                    <td className="p-4 font-mono text-xs text-[#8B93A1]">
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
                    <td className="p-4 font-mono text-xs text-right text-[#8B93A1]">
                      {new Date(item.timestamp).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
