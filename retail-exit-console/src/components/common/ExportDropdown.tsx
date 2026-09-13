import React, { useState, useRef, useEffect } from 'react';
import { Download, FileSpreadsheet, FileText, ChevronDown, Loader2 } from 'lucide-react';
import { api } from '../../api/client';

interface ExportDropdownProps {
  dataset?: 'events' | 'alerts' | 'invoices' | 'products';
  laneId?: string;
  severity?: string;
  startDate?: string;
  endDate?: string;
  className?: string;
}

export const ExportDropdown: React.FC<ExportDropdownProps> = ({
  dataset = 'events',
  laneId,
  severity,
  startDate,
  endDate,
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isExporting, setIsExporting] = useState<'xlsx' | 'csv' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleExportXlsx = async () => {
    setIsExporting('xlsx');
    setError(null);
    try {
      await api.downloadAuditXlsx({ laneId, severity, startDate, endDate });
      setIsOpen(false);
    } catch (err: any) {
      setError(err?.message || 'Excel export failed');
    } finally {
      setIsExporting(null);
    }
  };

  const handleExportCsv = async () => {
    setIsExporting('csv');
    setError(null);
    try {
      await api.downloadCsv(dataset, { laneId, severity });
      setIsOpen(false);
    } catch (err: any) {
      setError(err?.message || 'CSV export failed');
    } finally {
      setIsExporting(null);
    }
  };

  return (
    <div className={`relative inline-block text-left ${className}`} ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={isExporting !== null}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-panel-raised border border-hairline hover:bg-hairline/40 rounded-sm text-xs-tech text-text-pri font-medium transition-colors disabled:opacity-50"
      >
        {isExporting ? (
          <Loader2 className="w-3.5 h-3.5 text-amber animate-spin" />
        ) : (
          <Download className="w-3.5 h-3.5 text-amber" />
        )}
        <span>{isExporting ? 'Generating...' : 'Export Audit'}</span>
        <ChevronDown className={`w-3 h-3 text-text-sec transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-1.5 w-64 bg-panel border border-hairline rounded-sm shadow-xl z-50 py-1 divide-y divide-hairline">
          <div className="px-3 py-2">
            <p className="text-[10px] uppercase font-mono tracking-wider text-text-sec">
              Compliance Export Engine
            </p>
          </div>

          <div className="py-1">
            <button
              onClick={handleExportXlsx}
              disabled={isExporting !== null}
              className="w-full px-3 py-2 text-left flex items-start gap-2.5 hover:bg-hairline/30 transition-colors text-xs-tech text-text-pri group"
            >
              <FileSpreadsheet className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
              <div>
                <p className="font-medium group-hover:text-amber transition-colors">
                  Download Full Audit (.xlsx)
                </p>
                <p className="text-[10px] text-text-sec mt-0.5">
                  5 formatted tabs: Events, Alerts, Catalog, Invoices & Audit Log
                </p>
              </div>
            </button>

            <button
              onClick={handleExportCsv}
              disabled={isExporting !== null}
              className="w-full px-3 py-2 text-left flex items-start gap-2.5 hover:bg-hairline/30 transition-colors text-xs-tech text-text-pri group"
            >
              <FileText className="w-4 h-4 text-sky-400 mt-0.5 shrink-0" />
              <div>
                <p className="font-medium group-hover:text-amber transition-colors">
                  Export Current View (.csv)
                </p>
                <p className="text-[10px] text-text-sec mt-0.5">
                  Streamlined tabular data for active {dataset} dataset
                </p>
              </div>
            </button>
          </div>

          {error && (
            <div className="px-3 py-1.5 bg-rose-950/40 text-[11px] text-rose-300">
              {error}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

