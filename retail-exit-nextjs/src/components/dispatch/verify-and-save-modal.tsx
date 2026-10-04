"use client";

import React, { useState } from "react";
import {
  CheckCircle,
  AlertTriangle,
  Package,
  Layers,
  Box,
  Save,
  X,
  FileCheck,
  UserCheck,
  Shield,
  HelpCircle,
} from "lucide-react";
import { safeFetch, formatErrorMessage } from "@/lib/api-client";

interface VerifyAndSaveModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (result: any) => void;
  initialCounts?: {
    packagedBoxes?: number;
    bulkMaterials?: number;
    singleUnits?: number;
  };
  laneId?: string;
}

export default function VerifyAndSaveModal({
  isOpen,
  onClose,
  onSuccess,
  initialCounts = { packagedBoxes: 0, bulkMaterials: 0, singleUnits: 0 },
  laneId = "LANE-01",
}: VerifyAndSaveModalProps) {
  const [selectedLane, setSelectedLane] = useState(laneId);
  const [packagedBoxes, setPackagedBoxes] = useState(initialCounts.packagedBoxes ?? 0);
  const [bulkMaterials, setBulkMaterials] = useState(initialCounts.bulkMaterials ?? 0);
  const [singleUnits, setSingleUnits] = useState(initialCounts.singleUnits ?? 0);
  const [badgeId, setBadgeId] = useState("OPERATOR-01");
  const [overrideReason, setOverrideReason] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [commitResult, setCommitResult] = useState<any | null>(null);

  if (!isOpen) return null;

  const initialTotal =
    (initialCounts.packagedBoxes ?? 0) +
    (initialCounts.bulkMaterials ?? 0) +
    (initialCounts.singleUnits ?? 0);

  const currentTotal = packagedBoxes + bulkMaterials + singleUnits;
  const isOverridden = currentTotal !== initialTotal;

  const handleCommit = async () => {
    if (isOverridden && !overrideReason.trim()) {
      setErrorMsg("Please provide an override reason for manually adjusting detected counts.");
      return;
    }

    setSubmitting(true);
    setErrorMsg(null);

    try {
      const res = await safeFetch("/api/dispatch/verify-and-save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          laneId: selectedLane,
          packagedBoxesCount: Number(packagedBoxes),
          bulkMaterialsCount: Number(bulkMaterials),
          singleUnitsCount: Number(singleUnits),
          verifierEmployeeId: badgeId || "OPERATOR",
          overrideReason: isOverridden ? overrideReason : null,
          notes: notes || null,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setCommitResult(data);
        if (onSuccess) onSuccess(data);
      } else {
        const err = await res.json();
        setErrorMsg(formatErrorMessage(err.detail || err.message || "Failed to commit verification"));
      }
    } catch (err: any) {
      setErrorMsg(formatErrorMessage(err.message || "Network error communicating with dispatch API"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl max-w-xl w-full p-6 shadow-2xl space-y-5">
        {/* Header */}
        <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
          <div>
            <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
              <FileCheck size={20} className="text-[#38BDF8]" /> Human Verify-and-Save Workflow (Part DD.3)
            </h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5 font-mono">
              Post-session categorized item confirmation and forensic audit ledger commit
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-[var(--text-secondary)] hover:text-white p-1 rounded-md transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {commitResult ? (
          <div className="space-y-4 py-2">
            <div className="p-4 rounded-xl bg-[#4FD1B3]/10 border border-[#4FD1B3]/40 space-y-2">
              <div className="flex items-center gap-2 text-[#4FD1B3] font-bold text-base">
                <CheckCircle size={18} /> Verification Committed Successfully!
              </div>
              <p className="text-xs text-[var(--text-secondary)] font-mono">
                Verification Reference ID: <b className="text-[var(--text-primary)]">{commitResult.verificationId}</b>
              </p>
              <div className="grid grid-cols-3 gap-2 pt-2 text-xs font-mono">
                <div className="bg-[var(--bg-canvas)] p-2 rounded border border-[var(--border-hairline)]">
                  <span className="text-[var(--text-secondary)] block">Boxes:</span>
                  <b className="text-[var(--text-primary)]">{commitResult.breakdown?.packagedBoxes}</b>
                </div>
                <div className="bg-[var(--bg-canvas)] p-2 rounded border border-[var(--border-hairline)]">
                  <span className="text-[var(--text-secondary)] block">Bulk:</span>
                  <b className="text-[var(--text-primary)]">{commitResult.breakdown?.bulkMaterials}</b>
                </div>
                <div className="bg-[var(--bg-canvas)] p-2 rounded border border-[var(--border-hairline)]">
                  <span className="text-[var(--text-secondary)] block">Single:</span>
                  <b className="text-[var(--text-primary)]">{commitResult.breakdown?.singleUnits}</b>
                </div>
              </div>
            </div>
            <div className="flex justify-end pt-2">
              <button
                onClick={onClose}
                className="px-5 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-sm font-semibold transition-all"
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4 text-sm">
            {/* Lane & Verifier info */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">
                  EXIT / LOADING BAY LANE
                </label>
                <select
                  value={selectedLane}
                  onChange={(e) => setSelectedLane(e.target.value)}
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] font-mono outline-none text-xs"
                >
                  <option value="LANE-01">Lane 01 (Main Exit)</option>
                  <option value="LANE-02">Lane 02 (Secondary Exit)</option>
                  <option value="LANE-03">Lane 03 (Goods Dispatch)</option>
                  <option value="LANE-04">Lane 04 (Warehouse Loading)</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">
                  VERIFIER BADGE ID
                </label>
                <div className="flex items-center gap-2 bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg px-2.5 py-1.5">
                  <UserCheck size={14} className="text-[#38BDF8]" />
                  <input
                    type="text"
                    value={badgeId}
                    onChange={(e) => setBadgeId(e.target.value)}
                    placeholder="e.g. EMP-9021"
                    className="w-full bg-transparent text-[var(--text-primary)] font-mono outline-none text-xs"
                  />
                </div>
              </div>
            </div>

            {/* Categorized Counts (Part DD.2) */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-mono font-bold text-[var(--text-secondary)]">
                  CATEGORIZED ITEM BREAKDOWN (DD.2)
                </span>
                <span className="text-xs font-mono text-[#38BDF8]">
                  Total: {currentTotal} unit(s)
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {/* Packaged Boxes */}
                <div className="bg-[var(--bg-canvas)] p-3 rounded-lg border border-[var(--border-hairline)] space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-[var(--text-primary)]">
                    <Package size={14} className="text-[#38BDF8]" /> Packaged Boxes
                  </div>
                  <p className="text-[10px] text-[var(--text-secondary)] leading-tight">
                    Cartons, cases & shipping boxes
                  </p>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min={0}
                      value={packagedBoxes}
                      onChange={(e) => setPackagedBoxes(Math.max(0, parseInt(e.target.value) || 0))}
                      className="w-full bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded px-2.5 py-1.5 text-center font-mono text-base font-bold text-[var(--text-primary)] outline-none"
                    />
                  </div>
                </div>

                {/* Bulk Materials */}
                <div className="bg-[var(--bg-canvas)] p-3 rounded-lg border border-[var(--border-hairline)] space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-[var(--text-primary)]">
                    <Layers size={14} className="text-[#E8A33D]" /> Bulk Materials
                  </div>
                  <p className="text-[10px] text-[var(--text-secondary)] leading-tight">
                    Lumber, pipes, rebar & sacks
                  </p>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min={0}
                      value={bulkMaterials}
                      onChange={(e) => setBulkMaterials(Math.max(0, parseInt(e.target.value) || 0))}
                      className="w-full bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded px-2.5 py-1.5 text-center font-mono text-base font-bold text-[var(--text-primary)] outline-none"
                    />
                  </div>
                </div>

                {/* Single Units */}
                <div className="bg-[var(--bg-canvas)] p-3 rounded-lg border border-[var(--border-hairline)] space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-[var(--text-primary)]">
                    <Box size={14} className="text-[#4FD1B3]" /> Single Units
                  </div>
                  <p className="text-[10px] text-[var(--text-secondary)] leading-tight">
                    Unboxed loose items & tools
                  </p>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min={0}
                      value={singleUnits}
                      onChange={(e) => setSingleUnits(Math.max(0, parseInt(e.target.value) || 0))}
                      className="w-full bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded px-2.5 py-1.5 text-center font-mono text-base font-bold text-[var(--text-primary)] outline-none"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Override Reason (Required if count adjusted) */}
            {isOverridden && (
              <div className="p-3 bg-[#E8A33D]/10 border border-[#E8A33D]/40 rounded-lg space-y-1.5">
                <label className="block text-xs font-mono font-bold text-[#E8A33D] flex items-center gap-1.5">
                  <AlertTriangle size={13} /> MANUAL OVERRIDE REASON (REQUIRED)
                </label>
                <select
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded p-2 text-xs text-[var(--text-primary)] outline-none"
                >
                  <option value="">-- Select Audit Justification --</option>
                  <option value="Damaged Carton Unloaded">Damaged Carton Unloaded / Set Aside</option>
                  <option value="Pallet Restacked Manually">Pallet Restacked Manually Before Exit</option>
                  <option value="Visual Manual Audit Recount">Visual Manual Audit Recount Verified by Supervisor</option>
                  <option value="Manifest Correction Underway">Manifest Discrepancy Correction Underway</option>
                  <option value="Other Authorized Exception">Other Authorized Exception</option>
                </select>
              </div>
            )}

            {/* Notes */}
            <div>
              <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">
                SUPERVISOR AUDIT NOTES (OPTIONAL)
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Optional notes regarding pallet integrity, seal tags, or carrier details..."
                rows={2}
                className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-xs text-[var(--text-primary)] outline-none"
              />
            </div>

            {/* Error Banner */}
            {errorMsg && (
              <div className="p-3 bg-[#E5484D]/10 border border-[#E5484D]/40 text-[#E5484D] rounded-lg text-xs font-mono flex items-center gap-2">
                <AlertTriangle size={14} /> {errorMsg}
              </div>
            )}

            {/* Actions */}
            <div className="flex justify-between items-center pt-2 border-t border-[var(--border-hairline)]">
              <button
                onClick={onClose}
                className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-lg text-sm font-medium transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCommit}
                disabled={submitting}
                className="px-5 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-sm font-semibold flex items-center gap-2 shadow-lg shadow-blue-900/30 transition-all disabled:opacity-50"
              >
                <Save size={15} /> {submitting ? "Committing Audit..." : "Confirm & Commit"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
