import React, { useState } from 'react';
import { useAppData } from '../context/AppDataContext';
import { resolveMediaUrl } from '../api/client';
import type { Invoice, InvoiceLineItem, ExitEvent } from '../types';
import { Modal } from '../components/common/Modal';
import { UploadBillModal } from '../components/invoices/UploadBillModal';
import {
  FileSpreadsheet,
  ScanText,
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
  Search,
  FileCheck,
  Upload,
} from 'lucide-react';
import { ExportDropdown } from '../components/common/ExportDropdown';

export const InvoicesView: React.FC = () => {
  const { invoices, events, setSelectedEventId } = useAppData();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);

  const avgOcrConfidence =
    invoices.length > 0
      ? (
          invoices.reduce((acc, inv) => acc + (inv.ocrConfidence || 0), 0) / invoices.length
        ).toFixed(1)
      : '0.0';

  const filteredInvoices = invoices.filter((inv: Invoice) => {
    const q = searchQuery.toLowerCase();
    return (
      inv.invoiceNumber.toLowerCase().includes(q) ||
      inv.carrierName.toLowerCase().includes(q) ||
      inv.storeDestination.toLowerCase().includes(q)
    );
  });

  return (
    <div className="p-4 space-y-4">
      {/* Header */}
      <div className="p-4 bg-panel border border-hairline rounded-sm space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-base-tech font-semibold text-text-pri flex items-center gap-2">
              <FileSpreadsheet className="w-5 h-5 text-amber" />
              OCR Outbound Manifests & Waybill Reconciliation
            </h1>
            <p className="text-xs-tech text-text-sec mt-0.5">
              OCR-scanned carrier bills of lading cross-referenced in real time against multi-sensor exit counts.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="px-2.5 py-1 rounded-sm bg-panel-raised border border-hairline font-mono text-xs-tech text-text-sec">
              OCR Avg Confidence: <strong className="text-status-ok">{avgOcrConfidence}%</strong>
            </span>
            <button
              onClick={() => setIsUploadModalOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs-tech font-semibold rounded-sm bg-amber hover:bg-amber/90 text-black transition-colors shadow-sm"
            >
              <Upload className="w-3.5 h-3.5" />
              Upload Hard-Copy Bill
            </button>
            <ExportDropdown dataset="invoices" />
          </div>
        </div>

        {/* Search */}
        <div className="relative pt-2 border-t border-hairline max-w-md">
          <Search className="w-3.5 h-3.5 text-text-sec absolute left-3 top-4.5" />
          <input
            type="text"
            placeholder="Search invoice number, carrier, destination..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri placeholder:text-text-sec/60 focus-visible:outline-2 focus-visible:outline-amber"
          />
        </div>
      </div>

      {/* Invoices Table */}
      <div className="bg-panel border border-hairline rounded-sm overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-hairline bg-panel-raised text-xs-tech">
          <span className="font-semibold text-text-pri">
            Scanned Dispatch Documents ({filteredInvoices.length} entries)
          </span>
          <span className="font-mono text-text-sec text-[11px]">
            Tesseract & Cloud Vision OCR Pipeline
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-hairline bg-canvas/60 text-xs-tech text-text-sec font-normal">
                <th className="py-2 px-3 font-normal">Manifest #</th>
                <th className="py-2 px-3 font-normal">Logistics Carrier</th>
                <th className="py-2 px-3 font-normal">Destination</th>
                <th className="py-2 px-3 font-normal text-right">OCR Integrity</th>
                <th className="py-2 px-3 font-normal text-right">Declared Units</th>
                <th className="py-2 px-3 font-normal">Linked Exit Event</th>
                <th className="py-2 px-3 font-normal">Parity Status</th>
                <th className="py-2 px-3 text-right">Inspect</th>
              </tr>
            </thead>
            <tbody>
              {filteredInvoices.length > 0 ? (
                filteredInvoices.map((inv: Invoice) => {
                  const linkedEvent = events.find((e: ExitEvent) => e.eventId === inv.linkedEventId);
                const hasDiscrepancy = linkedEvent && linkedEvent.deltaUnits !== 0;

                return (
                  <tr
                    key={inv.invoiceId}
                    className="border-b border-hairline/60 hover:bg-panel-raised/50 transition-colors text-xs-tech"
                  >
                    {/* Invoice Number */}
                    <td className="py-2.5 px-3 font-mono font-semibold text-text-pri whitespace-nowrap">
                      {inv.invoiceNumber}
                    </td>

                    {/* Carrier */}
                    <td className="py-2.5 px-3 text-text-pri font-medium whitespace-nowrap">
                      {inv.carrierName}
                    </td>

                    {/* Destination */}
                    <td className="py-2.5 px-3 text-text-sec whitespace-nowrap text-[11px]">
                      {inv.storeDestination}
                    </td>

                    {/* OCR Confidence */}
                    <td className="py-2.5 px-3 font-mono text-right whitespace-nowrap">
                      <span
                        className={`font-semibold ${
                          inv.ocrConfidence >= 95
                            ? 'text-status-ok'
                            : inv.ocrConfidence >= 90
                            ? 'text-status-low'
                            : 'text-status-med'
                        }`}
                      >
                        {inv.ocrConfidence.toFixed(1)}%
                      </span>
                    </td>

                    {/* Declared Total Units */}
                    <td className="py-2.5 px-3 font-mono text-right text-mono-val font-semibold whitespace-nowrap">
                      {inv.declaredTotalUnits} <span className="text-[11px] text-text-sec font-normal">units</span>
                    </td>

                    {/* Linked Event */}
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      {inv.linkedEventId ? (
                        <button
                          onClick={() => setSelectedEventId(inv.linkedEventId!)}
                          className="font-mono text-xs-tech text-amber hover:underline flex items-center gap-1 font-semibold"
                        >
                          {inv.linkedEventId}
                          <ExternalLink className="w-3 h-3" />
                        </button>
                      ) : (
                        <span className="text-text-sec italic">Unlinked</span>
                      )}
                    </td>

                    {/* Parity Status */}
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      {hasDiscrepancy ? (
                        <span className="inline-flex items-center gap-1 font-mono text-[11px] px-2 py-0.5 rounded-sm bg-red-950/30 text-status-high border border-status-high/40 font-bold">
                          <AlertTriangle className="w-3 h-3" />
                          MISMATCH (Δ +{linkedEvent?.deltaUnits})
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 font-mono text-[11px] px-2 py-0.5 rounded-sm bg-teal-950/20 text-status-ok border border-status-ok/30">
                          <CheckCircle2 className="w-3 h-3" />
                          VERIFIED
                        </span>
                      )}
                    </td>

                    {/* Action */}
                    <td className="py-2.5 px-3 text-right whitespace-nowrap">
                      <button
                        onClick={() => setSelectedInvoice(inv)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs-tech font-semibold rounded-sm bg-panel-raised hover:bg-hairline/40 text-text-pri border border-hairline transition-colors"
                      >
                        <ScanText className="w-3.5 h-3.5 text-amber" />
                        OCR Scan
                      </button>
                    </td>
                  </tr>
                );
              })
              ) : invoices.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-16 text-center text-xs-tech text-text-sec font-sans">
                    <div className="flex flex-col items-center justify-center gap-2.5">
                      <FileSpreadsheet className="w-8 h-8 text-hairline" />
                      <span className="text-text-pri font-medium text-sm-tech">No OCR manifests recorded</span>
                      <span className="text-[11px] max-w-sm text-text-sec">
                        Upload hard-copy bills of lading or dispatch waybills to automatically parse declared items and reconcile against portal sensors.
                      </span>
                      <button
                        onClick={() => setIsUploadModalOpen(true)}
                        className="mt-2 flex items-center gap-1.5 px-4 py-1.5 text-xs-tech font-semibold rounded-sm bg-amber hover:bg-amber/90 text-black transition-colors shadow-sm"
                      >
                        <Upload className="w-3.5 h-3.5" />
                        Upload Hard-Copy Bill Now
                      </button>
                    </div>
                  </td>
                </tr>
              ) : (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-xs-tech text-text-sec font-sans">
                    No manifests matched search query "{searchQuery}".
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Invoice OCR Inspector Modal */}
      {selectedInvoice && (
        <Modal
          isOpen={!!selectedInvoice}
          onClose={() => setSelectedInvoice(null)}
          title={`OCR Inspector: ${selectedInvoice.invoiceNumber}`}
          subtitle={`Carrier: ${selectedInvoice.carrierName} · Extracted: ${new Date(selectedInvoice.scanTimestamp).toLocaleString()}`}
          maxWidth="xl"
        >
          <div className="space-y-4">
            {/* Scanned Document Image Preview if available */}
            {selectedInvoice.rawFileUrl && (
              <div className="p-3 bg-panel border border-hairline rounded-sm space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-text-sec text-[11px] font-semibold flex items-center gap-1.5 font-mono">
                    <FileCheck className="w-3.5 h-3.5 text-amber" />
                    SCANNED BILL EVIDENCE (ARCHIVE: {selectedInvoice.invoiceNumber})
                  </span>
                  <a
                    href={resolveMediaUrl(selectedInvoice.rawFileUrl)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-amber hover:underline text-[11px] font-semibold flex items-center gap-1 font-mono"
                  >
                    <ExternalLink className="w-3 h-3" />
                    Open Document File
                  </a>
                </div>
                <div className="border border-hairline rounded-sm overflow-hidden bg-black/80 flex items-center justify-center max-h-56">
                  <img
                    src={resolveMediaUrl(selectedInvoice.rawFileUrl)}
                    alt="Scanned Waybill"
                    className="object-contain max-h-56 w-full"
                    onError={(e) => {
                      (e.target as HTMLElement).style.display = 'none';
                    }}
                  />
                </div>
              </div>
            )}

            {/* OCR Document Simulation Card */}
            <div className="p-4 bg-canvas border border-hairline rounded-sm space-y-3 font-mono text-xs-tech">
              <div className="flex items-center justify-between border-b border-hairline pb-2">
                <span className="font-bold text-amber flex items-center gap-1.5">
                  <FileCheck className="w-4 h-4" />
                  WAYBILL OCR TEXT EXTRACTION
                </span>
                <span className="text-status-ok font-semibold">
                  CONFIDENCE: {selectedInvoice.ocrConfidence}%
                </span>
              </div>

              {/* Raw text snippet */}
              <pre className="p-3 bg-panel-raised border border-hairline/80 rounded-sm text-text-pri font-mono text-xs-tech leading-relaxed whitespace-pre-wrap overflow-x-auto">
                {selectedInvoice.rawOcrText || 'No raw OCR data stored.'}
              </pre>

              {/* Line Items Table */}
              <div className="mt-3">
                <div className="text-[11px] font-sans font-semibold text-text-sec uppercase mb-1.5">
                  Parsed Line Items
                </div>
                <div className="border border-hairline rounded-sm overflow-hidden">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="bg-panel text-[11px] text-text-sec border-b border-hairline">
                        <th className="p-2 font-normal">SKU</th>
                        <th className="p-2 font-normal">Description</th>
                        <th className="p-2 font-normal text-right">Declared Cases</th>
                        <th className="p-2 font-normal text-right">Pack Size</th>
                        <th className="p-2 font-normal text-right">Total Units</th>
                        <th className="p-2 font-normal">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedInvoice.lineItems.map((li: InvoiceLineItem, idx: number) => (
                        <tr key={idx} className="border-b border-hairline/40 text-[11px]">
                          <td className="p-2 font-bold text-text-pri">{li.skuCode}</td>
                          <td className="p-2 text-text-sec">{li.description}</td>
                          <td className="p-2 text-right">{li.casesDeclared} cs</td>
                          <td className="p-2 text-right">{li.unitsPerCase} ea</td>
                          <td className="p-2 text-right font-bold text-mono-val">{li.totalUnits}</td>
                          <td className="p-2">
                            <span
                              className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                                li.status === 'MATCHED'
                                  ? 'bg-status-ok/20 text-status-ok'
                                  : 'bg-status-high/20 text-status-high'
                              }`}
                            >
                              {li.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setSelectedInvoice(null)}
                className="px-4 py-1.5 text-xs-tech rounded-sm bg-panel border border-hairline text-text-pri hover:bg-hairline/30"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Upload Hard-Copy Bill Modal */}
      <UploadBillModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
      />
    </div>
  );
};

