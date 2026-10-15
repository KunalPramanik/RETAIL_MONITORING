"use client";

import { safeFetch } from "@/lib/api-client";
import React, { useState, useEffect } from "react";
import { formatLocalDateTime } from "@/lib/date-utils";
import {
  FileText,
  UploadCloud,
  RefreshCw,
  Search,
  CheckCircle,
  AlertTriangle,
  Layers,
  Eye,
  FileCheck,
  Hash,
  Download,
  ExternalLink,
} from "lucide-react";

interface InvoiceLineItem {
  skuCode: string;
  description: string;
  casesDeclared: number;
  unitsPerCase: number;
  totalUnits: number;
  status: string;
}

interface InvoiceItem {
  invoiceId: string;
  invoiceNumber: string;
  carrierName: string;
  storeDestination: string;
  ocrConfidence: number;
  scanTimestamp: string;
  declaredTotalUnits: number;
  linkedEventId?: string;
  lineItems?: InvoiceLineItem[];
  rawOcrText?: string;
  rawFileUrl?: string;
  source?: string;
  createdAt?: string;
}

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<InvoiceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState<InvoiceItem | null>(null);

  const fetchInvoices = async () => {
    try {
      setLoading(true);
      const url = search
        ? `/api/invoices?query=${encodeURIComponent(search)}`
        : "/api/invoices";
      const res = await safeFetch(url);
      if (res.ok) {
        const data = await res.json();
        setInvoices(data);
      }
    } catch (e) {
      console.warn("Fetch invoices error:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInvoices();
  }, [search]);

  const handleUploadInvoice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const res = await safeFetch("/api/invoices/upload", {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        alert("Invoice scanned and OCR extraction completed!");
        setShowUploadModal(false);
        setSelectedFile(null);
        fetchInvoices();
      } else {
        const err = await res.json();
        alert(err.detail || "Upload & OCR processing failed");
      }
    } catch (e: any) {
      alert(e.message || "Upload error");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-[var(--bg-panel)] p-6 rounded-xl border border-[var(--border-hairline)]">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center gap-3">
            <FileText className="text-[#38BDF8]" /> Bill of Lading & Invoice OCR Extraction
          </h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">
            PaddleOCR and LayoutLMv3 automated document extraction, SKU line-item matching, and declared quantity
            verification.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchInvoices}
            className="px-3.5 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-lg text-sm font-medium flex items-center gap-2 transition-colors font-mono"
          >
            <RefreshCw size={15} /> Refresh
          </button>
          <button
            onClick={() => setShowUploadModal(true)}
            className="px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-sm font-semibold flex items-center gap-2 shadow-lg shadow-blue-900/30 transition-all font-mono"
          >
            <UploadCloud size={16} /> Scan / Upload Bill
          </button>
        </div>
      </div>

      {/* Filter / Search Bar */}
      <div className="bg-[var(--bg-panel)] p-4 rounded-xl border border-[var(--border-hairline)] flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center">
        <div className="relative flex-1 max-w-md w-full">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by invoice number, carrier, or destination..."
            className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg pl-10 pr-4 py-2 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] outline-none focus:border-[#38BDF8]"
          />
        </div>
        <div className="text-xs font-mono text-[var(--text-secondary)]">
          Invoices Registered: <b className="text-[#38BDF8]">{invoices.length}</b>
        </div>
      </div>

      {/* Invoices Table */}
      <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl overflow-hidden shadow-xl">
        {loading ? (
          <div className="p-12 text-center text-[var(--text-secondary)]">
            <RefreshCw size={28} className="mx-auto mb-3 text-[#38BDF8] animate-spin" />
            <h4 className="text-sm font-bold text-[var(--text-primary)]">Loading Invoices & OCR Bills...</h4>
            <p className="text-xs text-[var(--text-secondary)] mt-1">Retrieving delivery manifests and OCR extractions from store database.</p>
          </div>
        ) : invoices.length === 0 ? (
          <div className="p-12 text-center text-[var(--text-secondary)]">
            <FileCheck size={40} className="mx-auto mb-3 text-[#2C323D]" />
            <h4 className="text-base font-bold text-[var(--text-primary)]">No bills or invoices uploaded</h4>
            <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-sm mx-auto">
              Upload delivery manifests or invoice scans to automatically cross-verify physical exit quantities against
              paperwork.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-[var(--bg-canvas)] text-[var(--text-secondary)] text-xs font-mono border-b border-[var(--border-hairline)]">
                <tr>
                  <th className="p-4">INVOICE / MANIFEST</th>
                  <th className="p-4">CARRIER</th>
                  <th className="p-4">DESTINATION</th>
                  <th className="p-4">OCR CONFIDENCE</th>
                  <th className="p-4">DECLARED UNITS</th>
                  <th className="p-4">LINKED EVENT</th>
                  <th className="p-4">SCAN TIMESTAMP</th>
                  <th className="p-4 text-right">ACTIONS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
                {invoices.map((inv) => {
                  const conf = typeof inv.ocrConfidence === "number" ? inv.ocrConfidence : 96.0;
                  const displayConf = conf <= 1.0 ? Math.round(conf * 100) : Math.round(conf);
                  const scanTime = inv.scanTimestamp || inv.createdAt || "";

                  return (
                    <tr key={inv.invoiceId} className="hover:bg-[var(--bg-panel-raised)] transition-colors font-mono">
                      <td className="p-4 font-bold text-[#38BDF8]">
                        <div>{inv.invoiceNumber || inv.invoiceId}</div>
                        <div className="text-[10px] text-[var(--text-muted)] font-normal">{inv.invoiceId}</div>
                      </td>
                      <td className="p-4">
                        <span className="px-2 py-0.5 rounded text-[11px] bg-[var(--bg-canvas)] text-[var(--text-primary)] border border-[var(--border-hairline)]">
                          {inv.carrierName || "Direct Carrier"}
                        </span>
                      </td>
                      <td className="p-4 text-xs font-sans text-[var(--text-secondary)]">
                        {inv.storeDestination || "Store Operations Facility"}
                      </td>
                      <td className="p-4 text-xs">
                        <span
                          className={`font-bold px-2 py-0.5 rounded text-[11px] ${
                            displayConf >= 85
                              ? "bg-[#4FD1B3]/15 text-[#4FD1B3] border border-[#4FD1B3]/30"
                              : "bg-[#E8A33D]/15 text-[#E8A33D] border border-[#E8A33D]/30"
                          }`}
                        >
                          {displayConf}%
                        </span>
                      </td>
                      <td className="p-4 font-bold text-[#E8A33D]">
                        {inv.declaredTotalUnits} <span className="text-xs font-normal text-[var(--text-secondary)]">U</span>
                      </td>
                      <td className="p-4 text-xs">
                        {inv.linkedEventId ? (
                          <span className="text-[#38BDF8] font-bold">{inv.linkedEventId}</span>
                        ) : (
                          <span className="text-[var(--text-muted)]">PENDING EXIT</span>
                        )}
                      </td>
                      <td className="p-4 text-xs text-[var(--text-secondary)]">
                        {scanTime ? formatLocalDateTime(scanTime) : "—"}
                      </td>
                      <td className="p-4 text-right">
                        <button
                          onClick={() => setSelectedInvoice(inv)}
                          className="px-2.5 py-1 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[#38BDF8] rounded text-xs border border-[var(--border-hairline)] transition-colors font-mono"
                        >
                          Inspect Line Items
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Upload Invoice Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                <UploadCloud size={18} className="text-[#38BDF8]" /> Upload Bill / Invoice Scan
              </h3>
              <button onClick={() => setShowUploadModal(false)} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                ✕
              </button>
            </div>

            <form onSubmit={handleUploadInvoice} className="space-y-4 text-sm font-sans">
              <p className="text-xs text-[var(--text-secondary)]">
                Upload a scanned delivery slip, challan, or invoice. The PaddleOCR server pipeline will extract line
                items and quantities automatically.
              </p>

              <div className="border-2 border-dashed border-[var(--border-hairline)] hover:border-[#38BDF8] rounded-xl p-6 text-center cursor-pointer transition-colors bg-[var(--bg-canvas)]">
                <input
                  type="file"
                  accept="image/jpeg,image/png,application/pdf"
                  required
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="hidden"
                  id="invoice-file"
                />
                <label htmlFor="invoice-file" className="cursor-pointer">
                  <FileText size={32} className="mx-auto text-[#38BDF8] mb-2" />
                  {selectedFile ? (
                    <span className="font-mono text-xs text-[#4FD1B3] font-bold">{selectedFile.name}</span>
                  ) : (
                    <>
                      <span className="text-xs font-semibold text-[var(--text-primary)] block">Select Invoice File</span>
                      <span className="text-[11px] text-[var(--text-secondary)] block mt-0.5">PDF, PNG, or JPEG up to 10MB</span>
                    </>
                  )}
                </label>
              </div>

              <div className="flex justify-end gap-3 pt-2 border-t border-[var(--border-hairline)] font-mono">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploading || !selectedFile}
                  className="px-5 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-xs font-bold shadow-lg shadow-blue-900/30 disabled:opacity-50"
                >
                  {uploading ? "Extracting Text & Math..." : "Upload & Parse OCR"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Inspect Line Items Modal */}
      {selectedInvoice && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl max-w-2xl w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                <Hash size={18} className="text-[#38BDF8]" /> Manifest Details: {selectedInvoice.invoiceNumber || selectedInvoice.invoiceId}
              </h3>
              <button onClick={() => setSelectedInvoice(null)} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                ✕
              </button>
            </div>

            <div className="space-y-4 text-sm font-mono">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-[var(--bg-canvas)] p-3 rounded-lg border border-[var(--border-hairline)]">
                  <span className="text-[10px] text-[var(--text-secondary)] block">CARRIER</span>
                  <span className="font-bold text-[var(--text-primary)] text-xs truncate block mt-0.5">
                    {selectedInvoice.carrierName || "Direct"}
                  </span>
                </div>
                <div className="bg-[var(--bg-canvas)] p-3 rounded-lg border border-[var(--border-hairline)]">
                  <span className="text-[10px] text-[var(--text-secondary)] block">DESTINATION</span>
                  <span className="font-bold text-[var(--text-primary)] text-xs truncate block mt-0.5">
                    {selectedInvoice.storeDestination || "Operations Facility"}
                  </span>
                </div>
                <div className="bg-[var(--bg-canvas)] p-3 rounded-lg border border-[var(--border-hairline)]">
                  <span className="text-[10px] text-[var(--text-secondary)] block">TOTAL DECLARED</span>
                  <span className="font-bold text-[#E8A33D] text-sm block mt-0.5">
                    {selectedInvoice.declaredTotalUnits} Units
                  </span>
                </div>
                <div className="bg-[var(--bg-canvas)] p-3 rounded-lg border border-[var(--border-hairline)]">
                  <span className="text-[10px] text-[var(--text-secondary)] block">OCR CONFIDENCE</span>
                  <span className="font-bold text-[#4FD1B3] text-sm block mt-0.5">
                    {selectedInvoice.ocrConfidence <= 1.0
                      ? Math.round(selectedInvoice.ocrConfidence * 100)
                      : Math.round(selectedInvoice.ocrConfidence)}%
                  </span>
                </div>
              </div>

              {/* Line Items Table */}
              <div className="border border-[var(--border-hairline)] rounded-lg overflow-hidden bg-[var(--bg-canvas)]">
                <div className="px-4 py-2 border-b border-[var(--border-hairline)] bg-[var(--bg-panel-raised)] flex justify-between items-center text-xs">
                  <span className="font-bold text-[var(--text-primary)]">EXTRACTED SKU LINE ITEMS</span>
                  <span className="text-[var(--text-muted)]">{selectedInvoice.lineItems?.length || 0} items extracted</span>
                </div>
                {selectedInvoice.lineItems && selectedInvoice.lineItems.length > 0 ? (
                  <div className="max-h-48 overflow-y-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-[var(--bg-canvas)] text-[var(--text-secondary)] border-b border-[var(--border-hairline)]">
                        <tr>
                          <th className="p-2.5">SKU</th>
                          <th className="p-2.5">DESCRIPTION</th>
                          <th className="p-2.5 text-right">CASES</th>
                          <th className="p-2.5 text-right">PACK SIZE</th>
                          <th className="p-2.5 text-right">TOTAL UNITS</th>
                          <th className="p-2.5 text-center">STATUS</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
                        {selectedInvoice.lineItems.map((item, idx) => (
                          <tr key={idx} className="hover:bg-[var(--bg-panel-raised)]">
                            <td className="p-2.5 font-bold text-[#38BDF8]">{item.skuCode}</td>
                            <td className="p-2.5 font-sans">{item.description}</td>
                            <td className="p-2.5 text-right">{item.casesDeclared}</td>
                            <td className="p-2.5 text-right">{item.unitsPerCase}</td>
                            <td className="p-2.5 text-right font-bold text-[#E8A33D]">{item.totalUnits} U</td>
                            <td className="p-2.5 text-center">
                              <span className="px-1.5 py-0.2 rounded text-[10px] bg-[#4FD1B3]/15 text-[#4FD1B3]">
                                {item.status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="p-4 text-center text-xs text-[var(--text-muted)]">
                    No individual line items parsed from OCR document.
                  </div>
                )}
              </div>

              {/* Raw OCR Text Preview */}
              {selectedInvoice.rawOcrText && (
                <div className="border border-[var(--border-hairline)] rounded-lg p-3 bg-[var(--bg-canvas)] text-xs max-h-36 overflow-y-auto">
                  <div className="text-[var(--text-secondary)] mb-1 font-bold">OCR ENGINE EXTRACTION AUDIT LOG:</div>
                  <pre className="text-[#38BDF8] whitespace-pre-wrap font-mono text-[11px]">
                    {selectedInvoice.rawOcrText}
                  </pre>
                </div>
              )}
            </div>

            <div className="flex justify-between items-center pt-2 border-t border-[var(--border-hairline)] font-mono">
              {selectedInvoice.rawFileUrl ? (
                <a
                  href={selectedInvoice.rawFileUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-[#38BDF8] hover:underline flex items-center gap-1.5"
                >
                  <ExternalLink size={13} /> View Original Document
                </a>
              ) : (
                <span className="text-xs text-[var(--text-muted)]">Electronic EDI Waybill</span>
              )}

              <button
                onClick={() => setSelectedInvoice(null)}
                className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-xs font-medium"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
