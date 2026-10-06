"use client";

import React, { useState, useEffect } from "react";
import {
  FileText,
  Download,
  Calendar,
  RefreshCw,
  TrendingUp,
  ShieldAlert,
  CheckCircle,
  FileSpreadsheet,
  AlertTriangle,
  Layers,
  BarChart3,
} from "lucide-react";
import { safeFetch } from "@/lib/api-client";

interface ReportMetrics {
  totalThroughputUnits: number;
  totalDispatchedValue: number;
  consensusParityRate: number;
  totalDiscrepancyUnits: number;
  estimatedShrinkageValue: number;
  highSeverityCount: number;
}

interface ReportViolation {
  eventId: string;
  laneId: string;
  employeeId: string;
  consensusUnits: number;
  declaredUnits: number;
  deltaUnits: number;
  severity: string;
  notes: string;
}

interface DailyReportResponse {
  reportId: string;
  date: string;
  storeCode: string;
  generatedAt: string;
  status: string;
  metrics: ReportMetrics;
  violations: ReportViolation[];
}

export default function ReportsPage() {
  const [reportDate, setReportDate] = useState(new Date().toISOString().split("T")[0]);
  const [reportData, setReportData] = useState<DailyReportResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchReport = async () => {
    setLoading(true);
    try {
      const res = await safeFetch(`/api/reports/daily?date=${reportDate}`);
      if (res.ok) {
        const data = await res.json();
        setReportData(data);
      }
    } catch (err) {
      console.warn("Failed to fetch daily report:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReport();
  }, [reportDate]);

  const metrics = reportData?.metrics;

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-[var(--bg-panel)] p-6 rounded-xl border border-[var(--border-hairline)] shadow-sm">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center gap-3">
            <FileText className="text-[#38BDF8]" /> Daily Loss-Prevention Audit Digest
          </h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">
            Automated multi-tab compliance reporting: live verified throughput, shrinkage delta logs, and consensus fusion audit trails.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg px-3 py-1.5 text-xs font-mono text-[var(--text-primary)]">
            <Calendar size={14} className="text-[#38BDF8]" />
            <input
              type="date"
              value={reportDate}
              onChange={(e) => setReportDate(e.target.value)}
              className="bg-transparent text-[var(--text-primary)] outline-none"
            />
          </div>
          <button
            onClick={fetchReport}
            className="p-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-lg transition-colors"
            title="Refresh Report Data"
          >
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
          </button>
          <button
            onClick={() => {
              const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "";
              window.open(`${apiBaseUrl}/api/reports/export/xlsx?start_date=${reportDate}&end_date=${reportDate}`, "_blank");
            }}
            className="px-3.5 py-2 bg-[#10B981] hover:bg-[#059669] text-white rounded-lg text-sm font-semibold flex items-center gap-2 shadow-lg shadow-emerald-900/30 transition-all font-mono"
            title="Export Multi-Tab Audit Workbook (.xlsx)"
          >
            <FileSpreadsheet size={16} /> Export Excel (.xlsx)
          </button>
          <button
            onClick={() => {
              const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "";
              window.open(`${apiBaseUrl}/api/reports/daily?date=${reportDate}`, "_blank");
            }}
            className="px-3.5 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-sm font-semibold flex items-center gap-2 shadow-lg shadow-blue-900/30 transition-all"
            title="Download Daily Compliance Digest"
          >
            <Download size={15} /> Download PDF / JSON
          </button>
        </div>
      </div>

      {/* KPI Highlights for the Selected Date */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[var(--bg-panel)] p-5 rounded-xl border border-[var(--border-hairline)] space-y-1">
          <span className="text-xs font-mono text-[var(--text-secondary)] flex items-center gap-1.5">
            <CheckCircle size={13} className="text-[#4FD1B3]" /> VERIFIED DISPATCH VALUE
          </span>
          <h3 className="text-2xl font-bold font-mono text-[#4FD1B3]">
            {loading ? "..." : `$${(metrics?.totalDispatchedValue || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          </h3>
          <p className="text-[11px] text-[var(--text-secondary)]">
            Across {metrics?.totalThroughputUnits || 0} reconciled merchandise units
          </p>
        </div>

        <div className="bg-[var(--bg-panel)] p-5 rounded-xl border border-[var(--border-hairline)] space-y-1">
          <span className="text-xs font-mono text-[var(--text-secondary)] flex items-center gap-1.5">
            <ShieldAlert size={13} className="text-[#E8A33D]" /> PREVENTED SHRINKAGE VALUE
          </span>
          <h3 className="text-2xl font-bold font-mono text-[#E8A33D]">
            {loading ? "..." : `$${(metrics?.estimatedShrinkageValue || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          </h3>
          <p className="text-[11px] text-[var(--text-secondary)]">
            {metrics?.totalDiscrepancyUnits || 0} discrepancy unit(s) intercepted
          </p>
        </div>

        <div className="bg-[var(--bg-panel)] p-5 rounded-xl border border-[var(--border-hairline)] space-y-1">
          <span className="text-xs font-mono text-[var(--text-secondary)] flex items-center gap-1.5">
            <TrendingUp size={13} className="text-[#38BDF8]" /> CONSENSUS FUSION PARITY
          </span>
          <h3 className="text-2xl font-bold font-mono text-[#38BDF8]">
            {loading ? "..." : `${metrics?.consensusParityRate !== undefined ? metrics.consensusParityRate : 100}%`}
          </h3>
          <p className="text-[11px] text-[var(--text-secondary)]">
            Vision, RFID & Weight sensor agreement
          </p>
        </div>

        <div className="bg-[var(--bg-panel)] p-5 rounded-xl border border-[var(--border-hairline)] space-y-1">
          <span className="text-xs font-mono text-[var(--text-secondary)] flex items-center gap-1.5">
            <AlertTriangle size={13} className="text-[#E5484D]" /> HIGH SEVERITY ALERTS
          </span>
          <h3 className="text-2xl font-bold font-mono text-[#E5484D]">
            {loading ? "..." : metrics?.highSeverityCount || 0}
          </h3>
          <p className="text-[11px] text-[var(--text-secondary)]">
            Turnstile auto-interventions executed
          </p>
        </div>
      </div>

      {/* Discrepancy & Violation Audit Table */}
      <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl overflow-hidden shadow-sm">
        <div className="p-5 border-b border-[var(--border-hairline)] flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
          <div>
            <h2 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
              <Layers size={18} className="text-[#38BDF8]" /> Exit Discrepancy & Mismatch Audit Log
            </h2>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              Forensic record of unverified goods, unauthorized carriers, or weight sensor delta triggers for date: {reportDate}
            </p>
          </div>
          <button
            onClick={() => {
              const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "";
              window.open(`${apiBaseUrl}/api/reports/export/csv?dataset=events`, "_blank");
            }}
            className="px-3 py-1.5 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded text-xs font-mono flex items-center gap-1.5 transition-colors"
          >
            <Download size={13} /> Export CSV
          </button>
        </div>

        {loading ? (
          <div className="p-12 text-center text-[var(--text-secondary)] font-mono text-xs">
            Loading live compliance logs...
          </div>
        ) : !reportData?.violations || reportData.violations.length === 0 ? (
          <div className="p-12 text-center text-[var(--text-secondary)]">
            <CheckCircle size={40} className="mx-auto mb-3 text-[#4FD1B3]/60" />
            <h4 className="text-base font-bold text-[var(--text-primary)]">All Exit Events Fully Reconciled</h4>
            <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-sm mx-auto">
              Zero unverified merchandise movements or sensor mismatches recorded for {reportDate}.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-[var(--bg-canvas)] text-[var(--text-secondary)] text-xs font-mono border-b border-[var(--border-hairline)]">
                <tr>
                  <th className="p-4">SEVERITY</th>
                  <th className="p-4">EVENT ID</th>
                  <th className="p-4">LANE ID</th>
                  <th className="p-4">EMPLOYEE ID</th>
                  <th className="p-4">CONSENSUS / DECLARED</th>
                  <th className="p-4">DELTA UNITS</th>
                  <th className="p-4">AUDIT NOTES</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
                {reportData.violations.map((violation) => (
                  <tr key={violation.eventId} className="hover:bg-[var(--bg-panel-raised)] transition-colors">
                    <td className="p-4">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-mono font-semibold ${
                          violation.severity === "HIGH"
                            ? "bg-[#E5484D]/20 text-[#E5484D] border border-[#E5484D]/40"
                            : violation.severity === "MEDIUM"
                            ? "bg-[#E8A33D]/20 text-[#E8A33D] border border-[#E8A33D]/40"
                            : "bg-[#38BDF8]/20 text-[#38BDF8] border border-[#38BDF8]/40"
                        }`}
                      >
                        {violation.severity}
                      </span>
                    </td>
                    <td className="p-4 font-mono text-xs text-[var(--text-primary)]">{violation.eventId}</td>
                    <td className="p-4 font-mono text-xs text-[#38BDF8]">{violation.laneId}</td>
                    <td className="p-4 font-mono text-xs text-[var(--text-secondary)]">{violation.employeeId}</td>
                    <td className="p-4 font-mono text-xs">
                      {violation.consensusUnits} vs {violation.declaredUnits} units
                    </td>
                    <td className="p-4 font-mono text-xs text-[#E5484D] font-bold">
                      +{violation.deltaUnits}
                    </td>
                    <td className="p-4 text-xs text-[var(--text-secondary)] max-w-xs truncate">
                      {violation.notes || "Sensor variance detected at exit boundary"}
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

