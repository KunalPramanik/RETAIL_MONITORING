import React, { useState } from 'react';
import { Modal } from '../common/Modal';
import type { Alert } from '../../types';
import { useAppData } from '../../context/AppDataContext';
import { CheckCircle2, AlertCircle } from 'lucide-react';

interface ResolveAlertModalProps {
  alert: Alert | null;
  isOpen: boolean;
  onClose: () => void;
}

export const ResolveAlertModal: React.FC<ResolveAlertModalProps> = ({ alert, isOpen, onClose }) => {
  const { resolveAlert } = useAppData();
  const [resolverName, setResolverName] = useState('Loss Prevention Supervisor');
  const [note, setNote] = useState('');
  const [resolutionCode, setResolutionCode] = useState('CART_INSPECTED_RECONCILED');
  const [error, setError] = useState<string | null>(null);

  if (!alert) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!note.trim()) {
      setError('Resolution note is required for the loss prevention audit trail.');
      return;
    }

    const fullNote = `[${resolutionCode}] ${note.trim()}`;
    resolveAlert(alert.alertId, fullNote, resolverName);
    setNote('');
    setError(null);
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Resolve Alert: ${alert.alertId}`}
      subtitle={`Linked Event: ${alert.eventId} · Type: ${alert.alertType}`}
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Resolver Name */}
        <div>
          <label className="block text-xs-tech font-medium text-text-sec mb-1">
            Investigating Officer / Supervisor Name
          </label>
          <input
            type="text"
            value={resolverName}
            onChange={(e) => setResolverName(e.target.value)}
            className="w-full px-3 py-2 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
            required
          />
        </div>

        {/* Resolution Action Category */}
        <div>
          <label className="block text-xs-tech font-medium text-text-sec mb-1">
            Disposition Action Category
          </label>
          <select
            value={resolutionCode}
            onChange={(e) => setResolutionCode(e.target.value)}
            className="w-full px-3 py-2 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
          >
            <option value="CART_INSPECTED_RECONCILED">Physical Cart Inspected & Discrepancy Reconciled</option>
            <option value="INVOICE_OCR_MANUAL_OVERRIDE">Carrier Manifest Updated / OCR Override</option>
            <option value="RFID_SENSOR_CALIBRATION">RFID Gate / Hardware Recalibrated</option>
            <option value="GOODS_RECOVERED">Unaccounted Stock Recovered into Inventory</option>
            <option value="FALSE_ALARM_VERIFIED">False Positive / Verified Multi-Pack Scan</option>
          </select>
        </div>

        {/* Mandatory Resolution Note */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs-tech font-medium text-text-sec">
              Mandatory Resolution Notes <span className="text-status-high">*</span>
            </label>
            <span className="text-[11px] text-text-sec">Min 10 characters</span>
          </div>
          <textarea
            value={note}
            onChange={(e) => {
              setNote(e.target.value);
              if (error) setError(null);
            }}
            placeholder="Document findings, cart inspection details, customer confirmation, or supervisor actions taken..."
            rows={3}
            className="w-full px-3 py-2 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri placeholder:text-text-sec/50 focus-visible:outline-2 focus-visible:outline-amber"
          />
          {error && (
            <div className="flex items-center gap-1.5 mt-1 text-xs-tech text-status-high">
              <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Form Actions */}
        <div className="flex items-center justify-end gap-2 pt-2 border-t border-hairline">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-xs-tech rounded-sm border border-hairline hover:bg-hairline/30 text-text-sec transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs-tech font-semibold rounded-sm bg-status-ok/20 hover:bg-status-ok/30 text-status-ok border border-status-ok/40 transition-colors"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            Sign & Close Incident
          </button>
        </div>
      </form>
    </Modal>
  );
};

