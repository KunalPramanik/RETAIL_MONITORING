"use client";

import { safeFetch } from "@/lib/api-client";
﻿import React, { useState, useEffect } from "react";
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
} from "lucide-react";

interface InvoiceItem {
  invoiceId: string;
  source: string;
  extractionConfidence: number;
  declaredTotalUnits: number;
  linkedEventId?: string;
  createdAt: string;
  extractedJson?: any;
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
            className="px-3.5 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
          >
            <RefreshCw size={15} /> Refresh
          </button>
          <button
            onClick={() => setShowUploadModal(true)}
            className="px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-sm font-semibold flex items-center gap-2 shadow-lg shadow-blue-900/30 transition-all"
          >
            <UploadCloud size={16} /> Scan / Upload Bill
          </button>
        </div>
      </div>

      {/* Filter / Search Bar */}
      <div className="bg-[var(--bg-panel)] p-4 rounded-xl border border-[var(--border-hairline)] flex justify-between items-center">
        <div className="relative flex-1 max-w-md">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by invoice ID or carrier name..."
            className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg pl-10 pr-4 py-2 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] outline-none focus:border-[#38BDF8]"
          />
        </div>
        <div className="text-xs font-mono text-[var(--text-secondary)]">
          Invoices Registered: <b className="text-[#38BDF8]">{invoices.length}</b>
        </div>
      </div>

      {/* Invoices Table */}
      <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl overflow-hidden shadow-xl">
        {invoices.length === 0 && !loading ? (
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
                  <th className="p-4">INVOICE ID</th>
                  <th className="p-4">SOURCE</th>
                  <th className="p-4">OCR CONFIDENCE</th>
                  <th className="p-4">DECLARED UNITS</th>
                  <th className="p-4">LINKED EVENT</th>
                  <th className="p-4">REGISTERED TIMESTAMP</th>
                  <th className="p-4 text-right">ACTIONS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
                {invoices.map((inv) => (
                  <tr key={inv.invoiceId} className="hover:bg-[var(--bg-panel-raised)] transition-colors">
                    <td className="p-4 font-mono font-bold text-[#38BDF8]">{inv.invoiceId}</td>
                    <td className="p-4">
                      <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-[var(--bg-canvas)] text-[var(--text-primary)] border border-[var(--border-hairline)]">
                        {inv.source}
                      </span>
                    </td>
                    <td className="p-4 font-mono text-xs">
                      <span
                        className={`font-bold ${
                          inv.extractionConfidence >= 0.85 ? "text-[#4FD1B3]" : "text-[#E8A33D]"
                        }`}
                      >
                        {Math.round(inv.extractionConfidence * 100)}%
                      </span>
                    </td>
                    <td className="p-4 font-mono font-bold text-[#E8A33D]">
                      {inv.declaredTotalUnits} <span className="text-xs font-normal text-[var(--text-secondary)]">units</span>
                    </td>
                    <td className="p-4 font-mono text-xs text-[var(--text-secondary)]">
                      {inv.linkedEventId || <span className="text-[var(--text-secondary)]">PENDING EXIT</span>}
                    </td>
                    <td className="p-4 font-mono text-xs text-[var(--text-secondary)]">
                      {new Date(inv.createdAt).toLocaleString()}
                    </td>
                    <td className="p-4 text-right">
                      <button
                        onClick={() => setSelectedInvoice(inv)}
                        className="px-2.5 py-1 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[#38BDF8] rounded text-xs font-mono border border-[var(--border-hairline)] transition-colors"
                      >
                        Inspect Line Items
                      </button>
                    </td>
                  </tr>
                ))}
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
              <button onClick={() => setShowUploadModal(false)} className="text-[var(--text-secondary)] hover:text-white">
                ✕
              </button>
            </div>

            <form onSubmit={handleUploadInvoice} className="space-y-4 text-sm">
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

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-sm font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploading || !selectedFile}
                  className="px-5 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-sm font-semibold shadow-lg shadow-blue-900/30 disabled:opacity-50"
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
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                <Hash size={18} className="text-[#38BDF8]" /> Manifest Details: {selectedInvoice.invoiceId}
              </h3>
              <button onClick={() => setSelectedInvoice(null)} className="text-[var(--text-secondary)] hover:text-white">
                ✕
              </button>
            </div>

            <div className="space-y-3 text-sm">
              <div className="bg-[var(--bg-canvas)] p-3 rounded-lg border border-[var(--border-hairline)] flex justify-between items-center">
                <span className="text-xs text-[var(--text-secondary)] font-mono">TOTAL DECLARED UNITS:</span>
                <span className="font-mono font-bold text-[#E8A33D] text-lg">
                  {selectedInvoice.declaredTotalUnits} units
                </span>
              </div>
              <div className="bg-[var(--bg-canvas)] p-3 rounded-lg border border-[var(--border-hairline)] flex justify-between items-center">
                <span className="text-xs text-[var(--text-secondary)] font-mono">OCR EXTRACTION CONFIDENCE:</span>
                <span className="font-mono font-bold text-[#4FD1B3]">
                  {Math.round(selectedInvoice.extractionConfidence * 100)}%
                </span>
              </div>

              <div className="border border-[var(--border-hairline)] rounded-lg p-3 bg-[var(--bg-canvas)] text-xs font-mono max-h-48 overflow-y-auto">
                <div className="text-[var(--text-secondary)] mb-2 font-bold uppercase">Extracted Structured JSON:</div>
                <pre className="text-[#B8E3D6] whitespace-pre-wrap">
                  {JSON.stringify(selectedInvoice.extractedJson || { note: "No line item payload stored" }, null, 2)}
                </pre>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setSelectedInvoice(null)}
                className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-sm font-medium"
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
