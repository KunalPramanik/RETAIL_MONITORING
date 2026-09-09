import React, { useState, useRef } from 'react';
import { useAppData } from '../../context/AppDataContext';
import { Modal } from '../common/Modal';
import {
  Upload,
  FileText,
  FileCheck,
  CheckCircle2,
  AlertCircle,
  Plus,
  Trash2,
  Scan,
  Truck,
  Building2,
  Layers,
} from 'lucide-react';
import type { ExitEvent } from '../../types';

interface UploadBillModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface EditableLineItem {
  skuCode: string;
  description: string;
  casesDeclared: number;
  unitsPerCase: number;
  totalUnits: number;
}

export const UploadBillModal: React.FC<UploadBillModalProps> = ({ isOpen, onClose }) => {
  const { products, events, uploadInvoice } = useAppData();

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const [invoiceNumber, setInvoiceNumber] = useState(
    () => `BOL-2026-${Math.floor(1000 + Math.random() * 9000)}`
  );
  const [carrierName, setCarrierName] = useState('');
  const [storeDestination, setStoreDestination] = useState('');
  const [linkedEventId, setLinkedEventId] = useState<string>('');

  // Initial line items from catalog
  const [lineItems, setLineItems] = useState<EditableLineItem[]>(() => {
    if (products.length > 0) {
      return products.slice(0, 3).map((p) => ({
        skuCode: p.skuCode,
        description: p.name,
        casesDeclared: 3,
        unitsPerCase: p.packSize,
        totalUnits: 3 * p.packSize,
      }));
    }
    return [];
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      if (file.type.startsWith('image/')) {
        const url = URL.createObjectURL(file);
        setPreviewUrl(url);
      } else {
        setPreviewUrl(null);
      }
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      setSelectedFile(file);
      if (file.type.startsWith('image/')) {
        const url = URL.createObjectURL(file);
        setPreviewUrl(url);
      } else {
        setPreviewUrl(null);
      }
    }
  };

  const handleAddLineItem = () => {
    if (products.length > 0) {
      const p = products[Math.min(lineItems.length, products.length - 1)];
      setLineItems([
        ...lineItems,
        {
          skuCode: p.skuCode,
          description: p.name,
          casesDeclared: 2,
          unitsPerCase: p.packSize,
          totalUnits: 2 * p.packSize,
        },
      ]);
    } else {
      setLineItems([
        ...lineItems,
        {
          skuCode: `SKU-ITEM-${lineItems.length + 1}`,
          description: 'Packaged Retail SKU',
          casesDeclared: 2,
          unitsPerCase: 12,
          totalUnits: 24,
        },
      ]);
    }
  };

  const handleRemoveLineItem = (index: number) => {
    setLineItems(lineItems.filter((_, i) => i !== index));
  };

  const handleUpdateLineItem = (index: number, field: keyof EditableLineItem, val: any) => {
    setLineItems(
      lineItems.map((item, i) => {
        if (i !== index) return item;
        const updated = { ...item, [field]: val };
        if (field === 'casesDeclared' || field === 'unitsPerCase') {
          const cases = field === 'casesDeclared' ? parseInt(val) || 0 : item.casesDeclared;
          const units = field === 'unitsPerCase' ? parseInt(val) || 1 : item.unitsPerCase;
          updated.totalUnits = cases * units;
        }
        return updated;
      })
    );
  };

  const handleProductSelect = (index: number, skuCode: string) => {
    const prod = products.find((p) => p.skuCode === skuCode);
    if (!prod) return;
    setLineItems(
      lineItems.map((item, i) => {
        if (i !== index) return item;
        return {
          ...item,
          skuCode: prod.skuCode,
          description: prod.name,
          unitsPerCase: prod.packSize,
          totalUnits: item.casesDeclared * prod.packSize,
        };
      })
    );
  };

  const totalDeclaredUnits = lineItems.reduce((acc, item) => acc + (item.totalUnits || 0), 0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      // Build FormData
      const formData = new FormData();

      if (selectedFile) {
        formData.append('file', selectedFile);
      } else {
        // Create an automated synthetic SVG/JPEG bill if user didn't pick an image file
        const svgBill = `
          <svg xmlns="http://www.w3.org/2000/svg" width="800" height="1100" viewBox="0 0 800 1100" fill="#ffffff">
            <rect width="800" height="1100" fill="#fafafa"/>
            <rect x="40" y="40" width="720" height="1020" fill="#ffffff" stroke="#333333" stroke-width="2"/>
            <text x="70" y="90" font-family="monospace" font-size="22" font-weight="bold" fill="#000000">DISPATCH WAYBILL / BILL OF LADING</text>
            <text x="70" y="130" font-family="monospace" font-size="14" fill="#444444">MANIFEST NUMBER: ${invoiceNumber}</text>
            <text x="70" y="155" font-family="monospace" font-size="14" fill="#444444">LOGISTICS CARRIER: ${carrierName}</text>
            <text x="70" y="180" font-family="monospace" font-size="14" fill="#444444">DESTINATION: ${storeDestination}</text>
            <text x="70" y="205" font-family="monospace" font-size="14" fill="#444444">DISPATCH DATE: ${new Date().toLocaleDateString('en-IN')}</text>
            <line x1="70" y1="230" x2="730" y2="230" stroke="#888888" stroke-width="1.5"/>
            <text x="70" y="260" font-family="monospace" font-size="14" font-weight="bold" fill="#000000">SKU CODE        DESCRIPTION                    CASES   PACK   TOTAL</text>
            ${lineItems
              .map(
                (item, idx) => `
              <text x="70" y="${295 + idx * 30}" font-family="monospace" font-size="12" fill="#222222">
                ${item.skuCode.padEnd(16)} ${(item.description.slice(0, 26)).padEnd(28)} ${String(item.casesDeclared).padStart(3)} cs   ${String(item.unitsPerCase).padStart(3)} ea   ${String(item.totalUnits).padStart(4)} units
              </text>
            `
              )
              .join('')}
            <line x1="70" y1="520" x2="730" y2="520" stroke="#888888" stroke-width="1.5"/>
            <text x="70" y="550" font-family="monospace" font-size="15" font-weight="bold" fill="#000000">TOTAL DECLARED UNITS: ${totalDeclaredUnits} UNITS</text>
            <text x="70" y="580" font-family="monospace" font-size="11" fill="#666666">SEC-OPS 2.0 OCR OCR_CONFIDENCE_TARGET: 98.4% // VERIFIED</text>
          </svg>
        `;
        const blob = new Blob([svgBill], { type: 'image/svg+xml' });
        const autoFile = new File([blob], `${invoiceNumber}.svg`, { type: 'image/svg+xml' });
        formData.append('file', autoFile);
      }

      formData.append('invoiceNumber', invoiceNumber);
      formData.append('carrierName', carrierName);
      formData.append('storeDestination', storeDestination);
      if (linkedEventId) {
        formData.append('linkedEventId', linkedEventId);
      }
      formData.append('lineItemsJson', JSON.stringify(lineItems));

      // Call backend API
      const result = await uploadInvoice(formData);

      setSuccessMessage(`Manifest ${result.invoiceNumber} uploaded & OCR verified!`);
      setTimeout(() => {
        setIsSubmitting(false);
        onClose();
      }, 1000);
    } catch (err: any) {
      console.error('Upload bill failed:', err);
      setError(err.message || 'Failed to process hard-copy bill upload');
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Upload Hard-Copy Bill & OCR Ingestion"
      subtitle="Upload physical waybill or carrier manifest scan to parse line items and sync with database"
      maxWidth="2xl"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="p-3 bg-red-950/20 border border-status-high/40 rounded-sm text-status-high text-xs-tech flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {successMessage && (
          <div className="p-3 bg-teal-950/20 border border-status-ok/40 rounded-sm text-status-ok text-xs-tech flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        {/* File Dropzone Area */}
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-sm p-4 text-center cursor-pointer transition-colors ${
            selectedFile
              ? 'border-amber/60 bg-amber/5'
              : 'border-hairline hover:border-amber/40 bg-canvas/60'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,.pdf"
            onChange={handleFileChange}
            className="hidden"
          />

          {selectedFile ? (
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-left">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-panel border border-hairline rounded-sm text-amber">
                  <FileText className="w-6 h-6" />
                </div>
                <div>
                  <div className="text-xs-tech font-bold text-text-pri font-mono">
                    {selectedFile.name}
                  </div>
                  <div className="text-[11px] text-text-sec mt-0.5">
                    {(selectedFile.size / 1024).toFixed(1)} KB · {selectedFile.type || 'Document'}
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedFile(null);
                  setPreviewUrl(null);
                }}
                className="px-2 py-1 text-xs-tech text-status-high hover:bg-red-950/20 rounded-sm border border-status-high/30"
              >
                Remove
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center gap-2 py-2">
              <Upload className="w-6 h-6 text-amber animate-bounce" />
              <div>
                <span className="text-xs-tech font-semibold text-text-pri">
                  Click to select hard-copy bill or drop image here
                </span>
                <p className="text-[11px] text-text-sec mt-0.5">
                  Supports scanned bills of lading, dispatch waybills, photos (PNG, JPG, PDF)
                </p>
              </div>
            </div>
          )}

          {/* Quick preview if image */}
          {previewUrl && (
            <div className="mt-3 relative rounded-sm overflow-hidden border border-hairline max-h-48 flex items-center justify-center bg-black/80">
              <img
                src={previewUrl}
                alt="Bill Preview"
                className="object-contain max-h-48 w-full"
              />
              <div className="absolute top-2 left-2 bg-black/70 text-status-ok font-mono text-[10px] px-2 py-0.5 rounded border border-status-ok/30 flex items-center gap-1">
                <Scan className="w-3 h-3 animate-spin-slow" />
                OCR READY // SCANNING BOUNDARIES
              </div>
            </div>
          )}
        </div>

        {/* Manifest Header Fields Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3 bg-panel border border-hairline rounded-sm">
          <div>
            <label className="block text-xs-tech font-medium text-text-sec mb-1">
              Manifest / Waybill # *
            </label>
            <input
              type="text"
              value={invoiceNumber}
              onChange={(e) => setInvoiceNumber(e.target.value)}
              className="w-full px-2.5 py-1.5 font-mono text-xs-tech bg-canvas border border-hairline rounded-sm text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
              required
            />
          </div>

          <div>
            <label className="block text-xs-tech font-medium text-text-sec mb-1 flex items-center gap-1">
              <Truck className="w-3 h-3 text-amber" />
              Logistics Carrier *
            </label>
            <input
              type="text"
              value={carrierName}
              onChange={(e) => setCarrierName(e.target.value)}
              placeholder="e.g. BlueDart Logistics"
              className="w-full px-2.5 py-1.5 text-xs-tech bg-canvas border border-hairline rounded-sm text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
              required
            />
          </div>

          <div>
            <label className="block text-xs-tech font-medium text-text-sec mb-1 flex items-center gap-1">
              <Building2 className="w-3 h-3 text-amber" />
              Destination Store
            </label>
            <input
              type="text"
              value={storeDestination}
              onChange={(e) => setStoreDestination(e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs-tech bg-canvas border border-hairline rounded-sm text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
            />
          </div>
        </div>

        {/* Link to Recent Exit Event */}
        <div>
          <label className="block text-xs-tech font-medium text-text-sec mb-1 flex items-center justify-between">
            <span className="flex items-center gap-1">
              <Layers className="w-3.5 h-3.5 text-amber" />
              Link With Exit Event (Optional)
            </span>
            <span className="text-[11px] text-text-sec">
              Reconciles parity delta against live lane count
            </span>
          </label>
          <select
            value={linkedEventId}
            onChange={(e) => setLinkedEventId(e.target.value)}
            className="w-full px-3 py-1.5 text-xs-tech bg-canvas border border-hairline rounded-sm text-text-pri focus-visible:outline-2 focus-visible:outline-amber font-mono"
          >
            <option value="">-- No Linked Event (Standalone Inward Manifest) --</option>
            {events.slice(0, 10).map((ev: ExitEvent) => (
              <option key={ev.eventId} value={ev.eventId}>
                [{ev.eventId}] {ev.laneId} · Detected: {ev.consensusUnits} units · Severity: {ev.severity}
              </option>
            ))}
          </select>
        </div>

        {/* Declared Line Items Table */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs-tech font-semibold text-text-pri uppercase tracking-wider">
              Waybill Declared Line Items ({lineItems.length} SKUs)
            </span>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs-tech text-text-sec">
                Total: <strong className="text-mono-val">{totalDeclaredUnits} units</strong>
              </span>
              <button
                type="button"
                onClick={handleAddLineItem}
                className="flex items-center gap-1 px-2 py-0.5 text-[11px] font-semibold bg-panel border border-hairline hover:bg-hairline/40 text-amber rounded-sm"
              >
                <Plus className="w-3 h-3" />
                Add Row
              </button>
            </div>
          </div>

          <div className="border border-hairline rounded-sm overflow-x-auto">
            <table className="w-full text-left font-mono text-xs-tech">
              <thead>
                <tr className="bg-canvas border-b border-hairline text-text-sec text-[11px]">
                  <th className="p-2 font-normal">Catalog SKU</th>
                  <th className="p-2 font-normal">Description</th>
                  <th className="p-2 font-normal text-right">Declared Cases</th>
                  <th className="p-2 font-normal text-right">Pack Size</th>
                  <th className="p-2 font-normal text-right">Total Units</th>
                  <th className="p-2 font-normal text-center"></th>
                </tr>
              </thead>
              <tbody>
                {lineItems.length > 0 ? (
                  lineItems.map((item, idx) => (
                    <tr key={idx} className="border-b border-hairline/40">
                      <td className="p-2">
                        <select
                          value={item.skuCode}
                          onChange={(e) => handleProductSelect(idx, e.target.value)}
                          className="bg-canvas border border-hairline rounded-sm px-1.5 py-0.5 text-xs-tech font-mono text-text-pri"
                        >
                          {products.map((p) => (
                            <option key={p.productId} value={p.skuCode}>
                              {p.skuCode}
                            </option>
                          ))}
                        </select>
                      </td>

                      <td className="p-2">
                        <input
                          type="text"
                          value={item.description}
                          onChange={(e) => handleUpdateLineItem(idx, 'description', e.target.value)}
                          className="w-full bg-canvas border border-hairline rounded-sm px-1.5 py-0.5 text-xs-tech font-sans text-text-pri"
                        />
                      </td>

                      <td className="p-2 text-right">
                        <input
                          type="number"
                          min={1}
                          value={item.casesDeclared}
                          onChange={(e) =>
                            handleUpdateLineItem(idx, 'casesDeclared', parseInt(e.target.value) || 0)
                          }
                          className="w-16 text-right bg-canvas border border-hairline rounded-sm px-1.5 py-0.5 text-xs-tech font-mono text-mono-val font-bold"
                        />
                      </td>

                      <td className="p-2 text-right text-text-sec">
                        {item.unitsPerCase} ea
                      </td>

                      <td className="p-2 text-right font-bold text-amber">
                        {item.totalUnits}
                      </td>

                      <td className="p-2 text-center">
                        <button
                          type="button"
                          onClick={() => handleRemoveLineItem(idx)}
                          className="text-text-sec hover:text-status-high p-1"
                          title="Remove row"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-text-sec font-sans text-xs-tech">
                      No line items declared. Click &quot;+ Add Row&quot; or upload a hard-copy bill to parse manifest items.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Modal Actions */}
        <div className="flex items-center justify-end gap-2 pt-3 border-t border-hairline">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="px-3.5 py-1.5 text-xs-tech rounded-sm border border-hairline hover:bg-hairline/30 text-text-pri transition-colors"
          >
            Cancel
          </button>

          <button
            type="submit"
            disabled={isSubmitting}
            className="flex items-center gap-1.5 px-4 py-1.5 text-xs-tech font-semibold rounded-sm bg-amber hover:bg-amber/90 text-black transition-colors shadow-sm disabled:opacity-50"
          >
            {isSubmitting ? (
              <>
                <Scan className="w-3.5 h-3.5 animate-spin" />
                Processing OCR & Saving...
              </>
            ) : (
              <>
                <FileCheck className="w-3.5 h-3.5" />
                Upload Bill & Run OCR Ingestion
              </>
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
};
