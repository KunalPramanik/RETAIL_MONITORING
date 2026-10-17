"use client";

import React, { useState, useEffect } from "react";
import { safeFetch } from "@/lib/api-client";
import {
  Box,
  Layers,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  Plus,
  Search,
  Filter,
  Check,
  X,
  FileCheck,
  TrendingUp,
  TrendingDown,
  Camera,
  ArrowRight,
  ShieldAlert,
  Upload,
  Eye,
  ScanLine,
} from "lucide-react";

interface VerificationItem {
  verificationId: string;
  productId: string;
  skuCode: string;
  productName: string;
  cameraId: string;
  aiProposedCount: number;
  verifiedCount?: number;
  difference?: number;
  status: "PENDING_VERIFICATION" | "VERIFIED_ACCURATE" | "CORRECTED" | "REJECTED";
  verifiedBy?: string;
  correctionReason?: string;
  snapshotUrl?: string;
  modelVersion?: string;
  createdAt?: string;
  verifiedAt?: string;
}

interface StockItem {
  skuCode: string;
  productName: string;
  category: string;
  packSize: number;
  unitPrice: number;
  casePrice: number;
  openingStock: number;
  incomingConfirmed: number;
  outgoingConfirmed: number;
  adjustedStock: number;
  currentStock: number;
  inventoryValue: number;
  stockStatus: "IN_STOCK" | "LOW_STOCK" | "OUT_OF_STOCK";
}

export default function InventoryDashboardPage() {
  const [stockList, setStockList] = useState<StockItem[]>([]);
  const [verifications, setVerifications] = useState<VerificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState<"STOCK" | "VERIFICATIONS">("STOCK");

  // Edit / Recount Modal State
  const [editingItem, setEditingItem] = useState<VerificationItem | null>(null);
  const [correctedCount, setCorrectedCount] = useState<string>("");
  const [correctionReason, setCorrectionReason] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);

  // Manual Adjustment Modal State
  const [showAdjustModal, setShowAdjustModal] = useState(false);
  const [skuInputMode, setSkuInputMode] = useState<"select" | "custom">("select");
  const [adjustSku, setAdjustSku] = useState("");
  const [adjustQty, setAdjustQty] = useState("");
  const [adjustReason, setAdjustReason] = useState("");

  // AI Scan & Auto-Count Modal State
  const [showScanModal, setShowScanModal] = useState(false);
  const [scanCameraId, setScanCameraId] = useState("CAM-01");
  const [scanTargetSku, setScanTargetSku] = useState("");
  const [scanMinConf, setScanMinConf] = useState(0.35);
  const [scanImageBase64, setScanImageBase64] = useState<string | null>(null);
  const [scanImageName, setScanImageName] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<any | null>(null);
  const [previewSnapshot, setPreviewSnapshot] = useState<string | null>(null);

  const handleImageFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setScanImageName(file.name);
    const reader = new FileReader();
    reader.onload = () => {
      setScanImageBase64(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handleTriggerScanAndCount = async () => {
    try {
      setScanning(true);
      setScanResult(null);
      const res = await safeFetch("/api/inventory/scan-and-count", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cameraId: scanCameraId,
          imageBase64: scanImageBase64 || undefined,
          targetMaterialSku: scanTargetSku || undefined,
          minConfidence: scanMinConf,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setScanResult(data);
        fetchData();
      } else {
        const err = await res.json();
        alert(err.detail || "Scanning and counting failed.");
      }
    } catch (e: any) {
      alert(e.message || "Failed to trigger scan.");
    } finally {
      setScanning(false);
    }
  };

  const fetchData = async () => {
    try {
      setLoading(true);
      const [resStock, resVerif] = await Promise.all([
        safeFetch(`/api/inventory/stock${search ? `?query=${encodeURIComponent(search)}` : ""}`),
        safeFetch("/api/inventory/verification"),
      ]);

      if (resStock.ok) {
        const dataStock = await resStock.json();
        setStockList(dataStock);
      }
      if (resVerif.ok) {
        const dataVerif = await resVerif.json();
        setVerifications(dataVerif);
      }
    } catch (e) {
      console.warn("Failed to load inventory data:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [search]);

  // Handle YES — ACCEPT
  const handleAcceptProposal = async (verifId: string) => {
    try {
      setSubmitting(true);
      const res = await safeFetch(`/api/inventory/verification/${verifId}/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ isCorrect: true }),
      });
      if (res.ok) {
        fetchData();
      } else {
        const err = await res.json();
        alert(err.detail || "Verification failed");
      }
    } catch (e: any) {
      alert(e.message || "Request failed");
    } finally {
      setSubmitting(false);
    }
  };

  // Handle NO — EDIT Submission
  const handleSaveCorrection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingItem) return;
    const cnt = parseInt(correctedCount, 10);
    if (isNaN(cnt) || cnt < 0) {
      alert("Please provide a valid non-negative count.");
      return;
    }
    if (!correctionReason.trim()) {
      alert("Please provide a reason for the discrepancy correction.");
      return;
    }

    try {
      setSubmitting(true);
      const res = await safeFetch(`/api/inventory/verification/${editingItem.verificationId}/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          isCorrect: false,
          correctedCount: cnt,
          correctionReason: correctionReason.trim(),
        }),
      });
      if (res.ok) {
        setEditingItem(null);
        setCorrectedCount("");
        setCorrectionReason("");
        fetchData();
      } else {
        const err = await res.json();
        alert(err.detail || "Correction failed");
      }
    } catch (e: any) {
      alert(e.message || "Request failed");
    } finally {
      setSubmitting(false);
    }
  };

  // Handle Manual Stock Adjustment
  const handleManualAdjustment = async (e: React.FormEvent) => {
    e.preventDefault();
    const qty = parseInt(adjustQty, 10);
    if (isNaN(qty) || qty === 0) {
      alert("Please enter a non-zero adjustment delta.");
      return;
    }
    if (!adjustReason.trim()) {
      alert("Adjustment reason is mandatory.");
      return;
    }

    try {
      setSubmitting(true);
      const res = await safeFetch("/api/inventory/adjust", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sku_code: adjustSku,
          qty_adjustment: qty,
          reason: adjustReason.trim(),
        }),
      });
      if (res.ok) {
        setShowAdjustModal(false);
        setAdjustSku("");
        setAdjustQty("");
        setAdjustReason("");
        fetchData();
      } else {
        const err = await res.json();
        alert(err.detail || "Adjustment failed");
      }
    } catch (e: any) {
      alert(e.message || "Request failed");
    } finally {
      setSubmitting(false);
    }
  };

  const pendingVerifications = verifications.filter((v) => v.status === "PENDING_VERIFICATION");

  const totalInventoryValue = stockList.reduce((acc, item) => acc + (item.inventoryValue || 0), 0);
  const totalOnHandUnits = stockList.reduce((acc, item) => acc + (item.currentStock || 0), 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="card-3d flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 p-6 shadow-sm">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center gap-3">
            <Box className="text-[#38BDF8]" /> Inventory Ledger & Opening Stock Census
          </h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">
            Real-time on-hand stock balances, automated IN/OUT movement transactions, and AI-assisted baseline verification.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowScanModal(true)}
            className="btn-3d btn-3d-primary text-sm font-medium flex items-center gap-2 font-mono"
          >
            <Camera size={15} /> Scan & Auto-Count
          </button>
          <button
            onClick={() => setShowAdjustModal(true)}
            className="btn-3d btn-3d-secondary text-sm font-medium flex items-center gap-2 font-mono"
          >
            <Plus size={15} /> Adjust Stock
          </button>
          <button
            onClick={fetchData}
            className="btn-3d btn-3d-secondary text-sm font-medium flex items-center gap-2"
          >
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="stat-box-3d">
          <span className="text-xs font-mono text-[var(--text-secondary)] uppercase">Total On-Hand Units</span>
          <div className="text-2xl font-bold font-mono text-[#38BDF8] mt-1">{totalOnHandUnits.toLocaleString()} U</div>
          <span className="text-[11px] text-[var(--text-muted)] mt-1 block">Live across all storage zones</span>
        </div>
        <div className="stat-box-3d">
          <span className="text-xs font-mono text-[var(--text-secondary)] uppercase">Total Valuation (₹ INR)</span>
          <div className="text-2xl font-bold font-mono text-[#4FD1B3] mt-1">₹ {totalInventoryValue.toLocaleString()}</div>
          <span className="text-[11px] text-[var(--text-muted)] mt-1 block">Indian Rupees asset value</span>
        </div>
        <div className="stat-box-3d">
          <span className="text-xs font-mono text-[var(--text-secondary)] uppercase">Pending Opening Verifications</span>
          <div className="text-2xl font-bold font-mono text-[#E8A33D] mt-1">{pendingVerifications.length} Items</div>
          <span className="text-[11px] text-[var(--text-muted)] mt-1 block">Awaiting operator YES / NO audit</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[var(--border-hairline)] gap-6 text-sm font-mono">
        <button
          onClick={() => setActiveTab("STOCK")}
          className={`pb-3 font-semibold transition-colors flex items-center gap-2 ${
            activeTab === "STOCK"
              ? "text-[#38BDF8] border-b-2 border-[#38BDF8]"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          <Box size={16} /> Current Stock Ledger ({stockList.length})
        </button>
        <button
          onClick={() => setActiveTab("VERIFICATIONS")}
          className={`pb-3 font-semibold transition-colors flex items-center gap-2 ${
            activeTab === "VERIFICATIONS"
              ? "text-[#38BDF8] border-b-2 border-[#38BDF8]"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          <FileCheck size={16} /> Opening Stock Census ({verifications.length})
          {pendingVerifications.length > 0 && (
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-[#E8A33D] text-black font-bold">
              {pendingVerifications.length}
            </span>
          )}
        </button>
      </div>

      {/* Tab Content: Current Stock Ledger */}
      {activeTab === "STOCK" && (
        <div className="space-y-4">
          <div className="card-3d p-4 flex justify-between items-center shadow-sm">
            <div className="relative flex-1 max-w-md">
              <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by SKU or material name..."
                className="w-full input-3d pl-10 pr-4 py-2 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] outline-none focus:border-[#38BDF8]"
              />
            </div>
            <div className="text-xs font-mono text-[var(--text-secondary)]">
              Accounting Invariant: <span className="text-[#4FD1B3]">Current = Opening + IN − OUT + Adj</span>
            </div>
          </div>

          <div className="card-3d overflow-hidden shadow-xl">
            {loading ? (
              <div className="p-12 text-center text-[var(--text-secondary)]">
                <RefreshCw size={28} className="mx-auto mb-3 text-[#38BDF8] animate-spin" />
                <h4 className="text-sm font-bold text-[var(--text-primary)]">Loading Inventory Ledger...</h4>
                <p className="text-xs text-[var(--text-secondary)] mt-1">Calculating real-time on-hand stock and physical balances from ledger.</p>
              </div>
            ) : stockList.length === 0 ? (
              <div className="p-12 text-center text-[var(--text-secondary)]">
                <Box size={40} className="mx-auto mb-3 text-[#2C323D]" />
                <h4 className="text-base font-bold text-[var(--text-primary)]">No inventory records available</h4>
                <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-sm mx-auto">
                  Initial census pending or awaiting receipt dispatch. Register products and conduct an initial opening stock scan to populate the ledger.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="table-3d w-full text-left text-sm">
                  <thead>
                    <tr>
                      <th className="p-4">SKU / CODE</th>
                      <th className="p-4">MATERIAL NAME</th>
                      <th className="p-4">CATEGORY</th>
                      <th className="p-4 text-right">OPENING</th>
                      <th className="p-4 text-right">IN (+)</th>
                      <th className="p-4 text-right">OUT (−)</th>
                      <th className="p-4 text-right">ADJ (±)</th>
                      <th className="p-4 text-right">CURRENT STOCK</th>
                      <th className="p-4 text-right">UNIT PRICE</th>
                      <th className="p-4 text-right">TOTAL VALUE</th>
                      <th className="p-4 text-center">STATUS</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
                    {stockList.map((item, idx) => (
                      <tr key={`${item.skuCode}-${idx}`} className="hover:bg-[var(--bg-panel-hover)] transition-colors font-mono">
                        <td className="p-4 font-bold text-[#38BDF8]">{item.skuCode}</td>
                        <td className="p-4 font-sans font-semibold text-[var(--text-primary)]">{item.productName}</td>
                        <td className="p-4 text-xs text-[var(--text-secondary)]">{item.category}</td>
                        <td className="p-4 text-right text-[var(--text-secondary)]">{item.openingStock} U</td>
                        <td className="p-4 text-right text-[#4FD1B3]">+{item.incomingConfirmed}</td>
                        <td className="p-4 text-right text-[#E5484D]">−{item.outgoingConfirmed}</td>
                        <td className="p-4 text-right text-[#E8A33D]">{item.adjustedStock >= 0 ? `+${item.adjustedStock}` : item.adjustedStock}</td>
                        <td className="p-4 text-right font-bold text-lg text-[var(--text-primary)]">{item.currentStock} U</td>
                        <td className="p-4 text-right text-[var(--text-secondary)]">₹ {item.unitPrice?.toFixed(2) || "0.00"}</td>
                        <td className="p-4 text-right font-bold text-[#4FD1B3]">₹ {item.inventoryValue?.toLocaleString() || "0"}</td>
                        <td className="p-4 text-center">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              item.stockStatus === "IN_STOCK"
                                ? "bg-[#4FD1B3]/15 text-[#4FD1B3] border border-[#4FD1B3]/30"
                                : item.stockStatus === "LOW_STOCK"
                                ? "bg-[#E8A33D]/15 text-[#E8A33D] border border-[#E8A33D]/30"
                                : "bg-[#E5484D]/15 text-[#E5484D] border border-[#E5484D]/30"
                            }`}
                          >
                            {(item.stockStatus || "UNKNOWN").replace(/_/g, " ")}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab Content: Opening Stock Census */}
      {activeTab === "VERIFICATIONS" && (
        <div className="space-y-4">
          <div className="card-3d p-4 text-xs text-[var(--text-secondary)] flex justify-between items-center shadow-sm">
            <div>
              <span className="font-bold text-[var(--text-primary)]">Human-in-the-Loop Opening Stock Protocol:</span>
              <p className="mt-0.5">
                AI scans the floor and proposes baseline counts. Operators verify visually: click <b>YES — ACCEPT</b> to confirm or <b>NO — EDIT</b> to record a manual recount with an audit reason.
              </p>
            </div>
          </div>

          <div className="card-3d overflow-hidden shadow-xl">
            {loading ? (
              <div className="p-12 text-center text-[var(--text-secondary)]">
                <RefreshCw size={28} className="mx-auto mb-3 text-[#38BDF8] animate-spin" />
                <h4 className="text-sm font-bold text-[var(--text-primary)]">Loading Opening Stock Census...</h4>
                <p className="text-xs text-[var(--text-secondary)] mt-1">Retrieving AI proposed baselines and verification audit logs from store database.</p>
              </div>
            ) : verifications.length === 0 ? (
              <div className="p-12 text-center text-[var(--text-secondary)]">
                <FileCheck size={40} className="mx-auto mb-3 text-[#2C323D]" />
                <h4 className="text-base font-bold text-[var(--text-primary)]">No opening stock verification sessions</h4>
                <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-sm mx-auto">
                  When cameras perform initial inventory counts, proposed baselines will be queued here for operator review.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="table-3d w-full text-left text-sm">
                  <thead>
                    <tr>
                      <th className="p-4">STATUS</th>
                      <th className="p-4">SKU / CODE</th>
                      <th className="p-4">MATERIAL NAME</th>
                      <th className="p-4 text-center">AI PROPOSED</th>
                      <th className="p-4 text-center">VERIFIED COUNT</th>
                      <th className="p-4 text-center">VARIANCE</th>
                      <th className="p-4">AUDIT REASON / OPERATOR</th>
                      <th className="p-4 text-right">ACTIONS</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
                    {verifications.map((v, idx) => (
                      <tr key={`${v.verificationId}-${idx}`} className="hover:bg-[var(--bg-panel-hover)] transition-colors font-mono">
                        <td className="p-4">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              v.status === "VERIFIED_ACCURATE"
                                ? "bg-[#4FD1B3]/15 text-[#4FD1B3] border border-[#4FD1B3]/30"
                                : v.status === "CORRECTED"
                                ? "bg-[#38BDF8]/15 text-[#38BDF8] border border-[#38BDF8]/30"
                                : "bg-[#E8A33D]/15 text-[#E8A33D] border border-[#E8A33D]/30 animate-pulse"
                            }`}
                          >
                            {(v.status || "UNKNOWN").replace(/_/g, " ")}
                          </span>
                        </td>
                        <td className="p-4 font-bold text-[#38BDF8]">{v.skuCode}</td>
                        <td className="p-4 font-sans text-[var(--text-primary)]">
                          <div className="flex items-center gap-2.5">
                            {v.snapshotUrl && (
                              <button
                                type="button"
                                onClick={() => setPreviewSnapshot(v.snapshotUrl!)}
                                className="relative group shrink-0 w-9 h-9 rounded-md border border-[var(--border-subtle)] overflow-hidden bg-black/40 hover:border-[#38BDF8] transition-all shadow-sm"
                                title="Click to view camera evidence snapshot"
                              >
                                <img src={v.snapshotUrl} alt="Snapshot" className="w-full h-full object-cover" />
                                <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                                  <Eye size={12} className="text-white" />
                                </div>
                              </button>
                            )}
                            <div>
                              <div className="font-semibold text-sm text-[var(--text-primary)]">{v.productName}</div>
                              <div className="text-[10px] text-[var(--text-muted)] font-mono flex items-center gap-1.5 mt-0.5">
                                <span className="text-[var(--text-secondary)]">{v.cameraId}</span>
                                {v.modelVersion && <span>• {v.modelVersion}</span>}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td className="p-4 text-center font-bold text-[var(--text-primary)]">{v.aiProposedCount} U</td>
                        <td className="p-4 text-center">
                          {v.verifiedCount !== undefined && v.verifiedCount !== null ? (
                            <span className="font-bold text-[#4FD1B3]">{v.verifiedCount} U</span>
                          ) : (
                            <span className="text-[var(--text-muted)]">—</span>
                          )}
                        </td>
                        <td className="p-4 text-center">
                          {v.difference !== undefined && v.difference !== null ? (
                            <span className={v.difference === 0 ? "text-[#4FD1B3]" : "text-[#E8A33D]"}>
                              {v.difference > 0 ? `+${v.difference}` : v.difference}
                            </span>
                          ) : (
                            <span className="text-[var(--text-muted)]">—</span>
                          )}
                        </td>
                        <td className="p-4 text-xs font-sans text-[var(--text-secondary)]">
                          {v.correctionReason || (v.verifiedBy ? `Verified by ${v.verifiedBy}` : "Awaiting operator review")}
                        </td>
                        <td className="p-4 text-right">
                          {v.status === "PENDING_VERIFICATION" ? (
                            <div className="flex items-center justify-end gap-2">
                              <button
                                onClick={() => handleAcceptProposal(v.verificationId)}
                                disabled={submitting}
                                className="btn-3d btn-3d-success text-xs font-bold font-mono flex items-center gap-1 disabled:opacity-50"
                              >
                                <Check size={13} /> YES — ACCEPT
                              </button>
                              <button
                                onClick={() => {
                                  setEditingItem(v);
                                  setCorrectedCount(String(v.aiProposedCount));
                                  setCorrectionReason("");
                                }}
                                disabled={submitting}
                                className="btn-3d btn-3d-danger text-xs font-bold font-mono flex items-center gap-1 disabled:opacity-50"
                              >
                                <X size={13} /> NO — EDIT
                              </button>
                            </div>
                          ) : (
                            <span className="text-xs text-[var(--text-muted)] font-mono">LOCKED</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Recount / Correction Modal */}
      {editingItem && (
        <div className="fixed inset-0 z-[9999] bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="card-3d max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                <FileCheck size={18} className="text-[#E8A33D]" /> Recount Correction: {editingItem.skuCode}
              </h3>
              <button
                onClick={() => setEditingItem(null)}
                className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] p-1 rounded-lg transition-colors"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveCorrection} className="space-y-4 text-sm font-mono">
              <div className="p-3 bg-[var(--bg-canvas)] rounded-lg border border-[var(--border-hairline)] text-xs space-y-1">
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">Material:</span>
                  <span className="text-[var(--text-primary)] font-bold">{editingItem.productName}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">AI Proposed Count:</span>
                  <span className="text-[#38BDF8] font-bold">{editingItem.aiProposedCount} Units</span>
                </div>
              </div>

              <div>
                <label className="block text-xs text-[var(--text-secondary)] mb-1">PHYSICAL RECOUNT VALUE (UNITS) *</label>
                <input
                  type="number"
                  min="0"
                  required
                  value={correctedCount}
                  onChange={(e) => setCorrectedCount(e.target.value)}
                  className="w-full input-3d p-2.5 text-[var(--text-primary)] font-mono outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div>
                <label className="block text-xs text-[var(--text-secondary)] mb-1">MANDATORY REASON FOR CORRECTION *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. 3 cases obscured behind pillar; manual verification done."
                  value={correctionReason}
                  onChange={(e) => setCorrectionReason(e.target.value)}
                  className="w-full input-3d p-2.5 text-[var(--text-primary)] font-sans text-xs outline-none focus:border-[#38BDF8] placeholder-[var(--text-muted)]"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border-hairline)]">
                <button
                  type="button"
                  onClick={() => setEditingItem(null)}
                  className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-xs border border-[var(--border-subtle)]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="btn-3d btn-3d-primary text-xs font-bold disabled:opacity-50"
                >
                  {submitting ? "Saving..." : "Lock Corrected Baseline"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Manual Stock Adjustment Modal */}
      {showAdjustModal && (
        <div className="fixed inset-0 z-[9999] bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="card-3d max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                <Plus size={18} className="text-[#38BDF8]" /> Manual Stock Adjustment
              </h3>
              <button
                onClick={() => setShowAdjustModal(false)}
                className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] p-1 rounded-lg transition-colors"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleManualAdjustment} className="space-y-4 text-sm font-mono">
              <div>
                <div className="flex justify-between items-center mb-1.5">
                  <label className="text-xs text-[var(--text-secondary)] font-semibold">SKU / MATERIAL IDENTIFIER *</label>
                  <div className="flex items-center gap-1 text-[11px]">
                    <button
                      type="button"
                      onClick={() => setSkuInputMode("select")}
                      className={`px-2 py-0.5 rounded transition-colors ${
                        skuInputMode === "select"
                          ? "bg-[#38BDF8]/20 text-[#38BDF8] font-bold border border-[#38BDF8]/40"
                          : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                      }`}
                    >
                      Pick SKU
                    </button>
                    <span className="text-[var(--border-hairline)]">|</span>
                    <button
                      type="button"
                      onClick={() => setSkuInputMode("custom")}
                      className={`px-2 py-0.5 rounded transition-colors ${
                        skuInputMode === "custom"
                          ? "bg-[#38BDF8]/20 text-[#38BDF8] font-bold border border-[#38BDF8]/40"
                          : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                      }`}
                    >
                      Custom SKU
                    </button>
                  </div>
                </div>

                {skuInputMode === "select" && stockList.length > 0 ? (
                  <select
                    required
                    value={adjustSku}
                    onChange={(e) => setAdjustSku(e.target.value)}
                    className="w-full input-3d p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                  >
                    <option value="" className="bg-[var(--bg-panel)] text-[var(--text-secondary)]">-- Select registered material --</option>
                    {stockList.map((s) => (
                      <option key={s.skuCode} value={s.skuCode} className="bg-[var(--bg-panel)] text-[var(--text-primary)]">
                        {s.skuCode} — {s.productName} ({s.currentStock} Units on hand)
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    required
                    placeholder="Enter any SKU Code (e.g. SKU-WAT-500 or RAW-MAT-01)"
                    value={adjustSku}
                    onChange={(e) => setAdjustSku(e.target.value)}
                    className="w-full input-3d p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8] placeholder-[var(--text-muted)] font-mono"
                  />
                )}
              </div>

              <div>
                <label className="block text-xs text-[var(--text-secondary)] font-semibold mb-1">
                  QUANTITY DELTA (+ to Add, − to Deduct) *
                </label>
                <input
                  type="number"
                  step="1"
                  required
                  placeholder="e.g. +10 or -5"
                  value={adjustQty}
                  onChange={(e) => setAdjustQty(e.target.value)}
                  className="w-full input-3d p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8] placeholder-[var(--text-muted)] font-mono text-base font-bold"
                />

                {/* Quick Delta Chips */}
                <div className="flex flex-wrap items-center gap-1.5 mt-2 text-[11px] font-mono">
                  <span className="text-[var(--text-muted)] text-[10px] mr-1">Quick:</span>
                  {[1, 5, 10, 50, 100].map((num) => (
                    <button
                      key={`pos-${num}`}
                      type="button"
                      onClick={() => setAdjustQty(String(num))}
                      className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
                    >
                      +{num}
                    </button>
                  ))}
                  {[-1, -5, -10, -50].map((num) => (
                    <button
                      key={`neg-${num}`}
                      type="button"
                      onClick={() => setAdjustQty(String(num))}
                      className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20 hover:bg-rose-500/20 transition-colors"
                    >
                      {num}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs text-[var(--text-secondary)] font-semibold mb-1">ADJUSTMENT REASON *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Warehouse intake receipt, damaged pallet write-off"
                  value={adjustReason}
                  onChange={(e) => setAdjustReason(e.target.value)}
                  className="w-full input-3d p-2.5 text-[var(--text-primary)] font-sans text-xs outline-none focus:border-[#38BDF8] placeholder-[var(--text-muted)]"
                />

                {/* Quick Reason Chips */}
                <div className="flex flex-wrap gap-1.5 mt-2 font-sans text-[11px]">
                  {[
                    "Warehouse Intake Receipt",
                    "Physical Recount Correction",
                    "Damaged Pallet Write-off",
                    "Customer Return Intake",
                  ].map((r) => (
                    <button
                      key={r}
                      type="button"
                      onClick={() => setAdjustReason(r)}
                      className="px-2 py-0.5 rounded bg-[var(--bg-panel-raised)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border-subtle)] transition-colors"
                    >
                      {r}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border-hairline)]">
                <button
                  type="button"
                  onClick={() => setShowAdjustModal(false)}
                  className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-xs font-mono border border-[var(--border-subtle)]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="btn-3d btn-3d-primary text-xs font-bold font-mono disabled:opacity-50"
                >
                  {submitting ? "Posting..." : "Post Adjustment"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* AI Scan & Auto-Count Modal */}
      {showScanModal && (
        <div className="fixed inset-0 z-[9999] bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="card-3d max-w-xl w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                <Camera size={20} className="text-[#38BDF8]" /> AI Vision Scan & Multi-Material Counting
              </h3>
              <button
                onClick={() => {
                  setShowScanModal(false);
                  setScanResult(null);
                  setScanImageBase64(null);
                  setScanImageName(null);
                }}
                className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] p-1 rounded-lg transition-colors text-lg"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4 text-sm font-mono">
              <p className="text-xs font-sans text-[var(--text-secondary)]">
                Scans live exit & storage cameras or uploaded floor photos. Automatically detects and counts:
                bookshelves, cement bags, iron rebar rods, shipping boxes, and single units without manual entry.
              </p>

              {/* Source Camera Selection */}
              <div>
                <label className="block text-xs text-[var(--text-secondary)] font-semibold mb-1">
                  CAMERA SOURCE / CHANNEL *
                </label>
                <select
                  value={scanCameraId}
                  onChange={(e) => setScanCameraId(e.target.value)}
                  className="w-full input-3d p-2.5 text-[var(--text-primary)] text-xs outline-none focus:border-[#38BDF8]"
                >
                  <option value="CAM-01">CAM-01: Main Warehouse Exit Portal (Live / Snapshot)</option>
                  <option value="CAM-02">CAM-02: Express Dispatch & Bookshelf Bay (Live / Snapshot)</option>
                  <option value="CAM-03">CAM-03: Construction Yard & Cement Stacks (Live / Snapshot)</option>
                  <option value="CAM-04">CAM-04: Rebar & Heavy Materials Dock (Live / Snapshot)</option>
                </select>
              </div>

              {/* Target Material Category */}
              <div>
                <label className="block text-xs text-[var(--text-secondary)] font-semibold mb-1">
                  TARGET MATERIAL (OPTIONAL FILTER)
                </label>
                <select
                  value={scanTargetSku}
                  onChange={(e) => setScanTargetSku(e.target.value)}
                  className="w-full input-3d p-2.5 text-[var(--text-primary)] text-xs outline-none focus:border-[#38BDF8]"
                >
                  <option value="">Auto-Detect All Visible Materials (Recommended)</option>
                  <option value="MAT-BOK-SHELF">Bookshelf Inventory & Documents (MAT-BOK-SHELF)</option>
                  <option value="MAT-CEM-50KG">Portland Construction Cement (50kg Bag) (MAT-CEM-50KG)</option>
                  <option value="MAT-ROD-REBAR">Structural Steel TMT Rebar Rods (MAT-ROD-REBAR)</option>
                  <option value="MAT-BOX-HEAVY">Heavy Corrugated Master Carton (MAT-BOX-HEAVY)</option>
                  <option value="SKU-RETAIL-01">Standard Exposed Retail Item (SKU-RETAIL-01)</option>
                </select>
              </div>

              {/* Optional Floor Image Upload */}
              <div className="p-3 bg-[var(--bg-canvas)] rounded-lg border border-[var(--border-hairline)] space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
                    <Upload size={14} className="text-[#38BDF8]" /> Floor Photo / Snapshot Upload (Optional)
                  </span>
                  {scanImageBase64 && (
                    <button
                      type="button"
                      onClick={() => {
                        setScanImageBase64(null);
                        setScanImageName(null);
                      }}
                      className="text-[11px] text-[#E5484D] hover:underline"
                    >
                      Clear
                    </button>
                  )}
                </div>
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleImageFileChange}
                  className="text-xs text-[var(--text-secondary)] file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-[#38BDF8]/20 file:text-[#38BDF8] hover:file:bg-[#38BDF8]/30 cursor-pointer w-full"
                />
                {scanImageName && (
                  <div className="text-[11px] text-[#4FD1B3] flex items-center gap-1">
                    <CheckCircle size={12} /> Loaded: {scanImageName}
                  </div>
                )}
                <span className="text-[10px] text-[var(--text-muted)] block">
                  Leave empty to capture live frame directly from the selected camera.
                </span>
              </div>

              {/* Confidence Threshold */}
              <div>
                <div className="flex justify-between text-xs text-[var(--text-secondary)] mb-1">
                  <span>DETECTION SENSITIVITY FLOOR</span>
                  <span className="text-[#38BDF8] font-bold">{Math.round(scanMinConf * 100)}%</span>
                </div>
                <input
                  type="range"
                  min="0.15"
                  max="0.80"
                  step="0.05"
                  value={scanMinConf}
                  onChange={(e) => setScanMinConf(parseFloat(e.target.value))}
                  className="w-full accent-[#38BDF8]"
                />
              </div>

              {/* Scan Trigger Button */}
              <button
                type="button"
                onClick={handleTriggerScanAndCount}
                disabled={scanning}
                className="btn-3d btn-3d-primary w-full py-3 text-sm font-bold flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {scanning ? (
                  <>
                    <RefreshCw size={16} className="animate-spin" /> Analyzing Image & Counting Seams...
                  </>
                ) : (
                  <>
                    <ScanLine size={16} /> Run Computer Vision Scan & Count
                  </>
                )}
              </button>

              {/* Scan Results */}
              {scanResult && (
                <div className="mt-4 p-4 bg-[var(--bg-canvas)] rounded-xl border border-[var(--border-hairline)] space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[var(--text-primary)] flex items-center gap-1.5">
                      <CheckCircle size={15} className="text-[#4FD1B3]" /> Scan Completed Successfully
                    </span>
                    <span className="text-xs font-bold text-[#38BDF8] font-mono">
                      Total: {scanResult.totalDetectedUnits} Units
                    </span>
                  </div>

                  {scanResult.snapshotUrl && (
                    <div className="relative rounded-lg overflow-hidden border border-[var(--border-hairline)] max-h-48 bg-black flex items-center justify-center box-3d p-1">
                      <img
                        src={scanResult.snapshotUrl}
                        alt="Scan Detection Overlay"
                        className="w-full object-contain max-h-48"
                      />
                    </div>
                  )}

                  <div className="space-y-1.5">
                    <span className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase">
                      Detected Material Proposals:
                    </span>
                    {scanResult.scannedMaterials?.map((m: any, idx: number) => (
                      <div
                        key={idx}
                        className="flex justify-between items-center p-2 rounded-lg bg-[var(--bg-panel)] border border-[var(--border-subtle)] text-xs shadow-sm"
                      >
                        <div>
                          <span className="font-bold text-[#38BDF8] mr-2">{m.skuCode}</span>
                          <span className="text-[var(--text-primary)] font-sans">{m.productName}</span>
                        </div>
                        <span className="font-bold text-[#4FD1B3] font-mono text-sm">
                          {m.aiProposedCount} Units
                        </span>
                      </div>
                    ))}
                  </div>

                  <div className="pt-2 flex justify-end">
                    <button
                      type="button"
                      onClick={() => {
                        setShowScanModal(false);
                        setActiveTab("VERIFICATIONS");
                        fetchData();
                      }}
                      className="btn-3d btn-3d-success text-xs font-bold flex items-center gap-1.5 font-mono"
                    >
                      <FileCheck size={14} /> Review & Confirm in Opening Census
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Full-size Snapshot Evidence Viewer Modal */}
      {previewSnapshot && (
        <div
          className="fixed inset-0 z-[9999] bg-black/90 backdrop-blur-md flex items-center justify-center p-4 cursor-pointer"
          onClick={() => setPreviewSnapshot(null)}
        >
          <div className="card-3d relative max-w-4xl max-h-[90vh] p-3 shadow-2xl">
            <button
              onClick={() => setPreviewSnapshot(null)}
              className="absolute top-4 right-4 z-10 p-2 bg-black/70 hover:bg-black text-white rounded-full text-xs"
            >
              ✕
            </button>
            <img
              src={previewSnapshot}
              alt="Evidence Snapshot Full View"
              className="max-h-[85vh] max-w-full rounded-lg object-contain"
            />
          </div>
        </div>
      )}
    </div>
  );
}


