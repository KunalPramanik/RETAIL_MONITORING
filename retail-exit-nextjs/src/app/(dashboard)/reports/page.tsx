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
} from "lucide-react";

export default function ReportsPage() {
  const [reportDate, setReportDate] = useState(new Date().toISOString().split("T")[0]);

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-[#1A1E26] p-6 rounded-xl border border-[#2C323D]">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#E7E9EC] flex items-center gap-3">
            <FileText className="text-[#38BDF8]" /> Daily Loss-Prevention Audit Digest
          </h1>
          <p className="text-[#8B93A1] text-sm mt-1">
            Automated PDF and Excel compliance reports: dispatched inventory value, discrepancy logs, and shrinkage trends.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="date"
            value={reportDate}
            onChange={(e) => setReportDate(e.target.value)}
            className="bg-[#12151A] border border-[#2C323D] rounded-lg px-3 py-1.5 text-xs font-mono text-[#E7E9EC] outline-none"
          />
          <button
            onClick={() => {
              window.open(`http://localhost:8000/api/reports/daily?date=${reportDate}`, "_blank");
            }}
            className="px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-sm font-semibold flex items-center gap-2 shadow-lg shadow-blue-900/30 transition-all"
          >
            <Download size={15} /> Download PDF Digest
          </button>
        </div>
      </div>

      {/* KPI Highlights for the Day */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-[#1A1E26] p-5 rounded-xl border border-[#2C323D] space-y-1">
          <span className="text-xs font-mono text-[#8B93A1]">VERIFIED DISPATCH VALUE</span>
          <h3 className="text-2xl font-bold font-mono text-[#4FD1B3]">$48,290.00</h3>
          <p className="text-[11px] text-[#8B93A1]">Across 100% audited exit transactions</p>
        </div>
        <div className="bg-[#1A1E26] p-5 rounded-xl border border-[#2C323D] space-y-1">
          <span className="text-xs font-mono text-[#8B93A1]">PREVENTED SHRINKAGE VALUE</span>
          <h3 className="text-2xl font-bold font-mono text-[#E8A33D]">$1,420.50</h3>
          <p className="text-[11px] text-[#8B93A1]">Intercepted via turnstile lock gates</p>
        </div>
        <div className="bg-[#1A1E26] p-5 rounded-xl border border-[#2C323D] space-y-1">
          <span className="text-xs font-mono text-[#8B93A1]">CONSENSUS FUSION ACCURACY</span>
          <h3 className="text-2xl font-bold font-mono text-[#38BDF8]">98.7%</h3>
          <p className="text-[11px] text-[#8B93A1]">Vision + RFID + Weight agreement</p>
        </div>
      </div>
    </div>
  );
}
