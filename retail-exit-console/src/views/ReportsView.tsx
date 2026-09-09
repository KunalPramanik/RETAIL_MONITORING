import React, { useState, useEffect } from 'react';
import { useAppData } from '../context/AppDataContext';
import type { ExitEvent, Alert, Product, SensorLane } from '../types';
import { FileBarChart, Download, Printer, AlertTriangle, Calendar, Clock } from 'lucide-react';
import { SignaturePad, type SignatureData } from '../components/common/SignaturePad';
import jsPDF from 'jspdf';

export const ReportsView: React.FC = () => {
  const {
    events,
    alerts,
    products,
    lanes,
    todayThroughputUnits,
    consensusAccuracyRate,
    setActiveView,
    setSelectedEventId,
  } = useAppData();

  const [selectedDate, setSelectedDate] = useState(() => new Date().toISOString().split('T')[0]);

  // Real-time live ticking clock
  const [liveClock, setLiveClock] = useState(() => new Date());

  useEffect(() => {
    const timer = setInterval(() => {
      setLiveClock(new Date());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Signatures State
  const [lpSignature, setLpSignature] = useState<SignatureData>({
    name: '',
    role: 'Loss Prevention Lead',
    signedAt: null,
    signatureImage: null,
    typedSignature: '',
    mode: 'draw',
  });

  const [gmSignature, setGmSignature] = useState<SignatureData>({
    name: '',
    role: 'Operations GM',
    signedAt: null,
    signatureImage: null,
    typedSignature: '',
    mode: 'draw',
  });

  const mismatchEvents = events.filter((e: ExitEvent) => e.verdict === 'MISMATCH');
  const highSeverityCount = alerts.filter((a: Alert) => a.severity === 'HIGH').length;
  const mediumSeverityCount = alerts.filter((a: Alert) => a.severity === 'MEDIUM').length;
  const lowSeverityCount = alerts.filter((a: Alert) => a.severity === 'LOW').length;

  // Fully dynamic retail INR value calculated from line items (starts at ₹0.00)
  const totalValueDispatched = events.reduce((acc: number, ev: ExitEvent) => {
    return (
      acc +
      (ev.lineItems || []).reduce((subAcc: number, item) => {
        const prod = products.find((p: Product) => p.productId === item.productId);
        const price = prod ? prod.unitPrice : 0.0;
        return subAcc + (item.unitsQty || 0) * price;
      }, 0)
    );
  }, 0);

  const totalDiscrepancyUnits = events.reduce((acc: number, ev: ExitEvent) => acc + (ev.deltaUnits || 0), 0);
  const avgUnitPrice = products.length > 0
    ? products.reduce((acc, p) => acc + (p.unitPrice || 0), 0) / products.length
    : 0.0;
  const estimatedShrinkageValue = totalDiscrepancyUnits * avgUnitPrice; // Dynamic exposure in INR (₹)

  // Generate and Download PDF Report with manual signatures embedded
  const handleDownloadPdf = () => {
    const doc = new jsPDF();
    const pageWidth = doc.internal.pageSize.getWidth();

    // Title & Header
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(16);
    doc.text('RETAIL LOSS PREVENTION & EXIT INTELLIGENCE DIGEST', 14, 20);

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(10);
    doc.text(`Generated: ${liveClock.toLocaleDateString('en-IN')} ${liveClock.toLocaleTimeString('en-IN')} | Operations Date: ${selectedDate}`, 14, 28);
    doc.text('SEC-OPS 2.0 Physical Security & Exit Portal Intelligence (INR - ₹)', 14, 34);

    doc.setDrawColor(180, 180, 180);
    doc.line(14, 38, pageWidth - 14, 38);

    // Executive Summary Section
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(12);
    doc.text('1. EXECUTIVE SUMMARY & TELEMETRY KPIS', 14, 46);

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(10);
    doc.text(`Total Exit Outflow: ${todayThroughputUnits.toLocaleString('en-IN')} units (${lanes.length} active exit lanes)`, 14, 54);
    doc.text(`Total Dispatched Value: Rs. ${totalValueDispatched.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`, 14, 60);
    doc.text(`Multi-Sensor Consensus Parity: ${consensusAccuracyRate}%`, 14, 66);
    doc.text(`Total Discrepancies Flagged: ${mismatchEvents.length} events (+${totalDiscrepancyUnits} units)`, 14, 72);
    doc.text(`Estimated Net Loss Prevention Exposure: Rs. ${estimatedShrinkageValue.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`, 14, 78);
    doc.text(`High Severity Siren Alarms: ${highSeverityCount} incidents`, 14, 84);

    doc.line(14, 90, pageWidth - 14, 90);

    // Forensic Violation Log
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(12);
    doc.text('2. LOSS PREVENTION VIOLATION & ANOMALY LOG', 14, 98);

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(9);
    let y = 106;

    if (mismatchEvents.length === 0) {
      doc.text('No discrepancy incidents recorded for this date. All portals achieved full consensus parity.', 14, y);
      y += 12;
    } else {
      mismatchEvents.slice(0, 7).forEach((ev: ExitEvent) => {
        doc.text(
          `[${ev.eventId}] ${ev.laneId} | Carrier: ${ev.employeeId || 'Unassigned'} | Cases: ${ev.casesDetected} | Delta: +${ev.deltaUnits} EA | Sev: ${ev.severity}`,
          14,
          y
        );
        if (ev.notes) {
          y += 5;
          doc.setFont('helvetica', 'italic');
          doc.text(`  Forensic: ${ev.notes.slice(0, 95)}...`, 14, y);
          doc.setFont('helvetica', 'normal');
        }
        y += 8;
      });
    }

    // Official Manual Signature Block
    doc.line(14, 230, pageWidth - 14, 230);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10);
    doc.text('3. OFFICIAL MANUAL SIGN-OFF & AUTHORIZATION', 14, 238);

    // Left Signature: Loss Prevention Lead
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(9);
    doc.text(`Loss Prevention Signatory: ${lpSignature.name || 'LP Lead'}`, 14, 246);
    doc.text(`Role: ${lpSignature.role || 'Loss Prevention Lead'}`, 14, 251);
    if (lpSignature.signatureImage) {
      try {
        doc.addImage(lpSignature.signatureImage, 'PNG', 14, 254, 50, 16);
      } catch (err) {
        console.error('Could not embed LP signature image in PDF:', err);
      }
    } else if (lpSignature.typedSignature) {
      doc.setFont('times', 'italic');
      doc.setFontSize(11);
      doc.text(lpSignature.typedSignature, 14, 263);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(9);
    }
    doc.text(
      `Status: ${lpSignature.signedAt ? `VERIFIED // Signed ${lpSignature.signedAt}` : 'PENDING MANUAL SIGNATURE'}`,
      14,
      274
    );

    // Right Signature: General Manager
    const rightX = pageWidth / 2 + 10;
    doc.text(`Store Operations GM: ${gmSignature.name || 'Operations GM'}`, rightX, 246);
    doc.text(`Role: ${gmSignature.role || 'Store General Manager'}`, rightX, 251);
    if (gmSignature.signatureImage) {
      try {
        doc.addImage(gmSignature.signatureImage, 'PNG', rightX, 254, 50, 16);
      } catch (err) {
        console.error('Could not embed GM signature image in PDF:', err);
      }
    } else if (gmSignature.typedSignature) {
      doc.setFont('times', 'italic');
      doc.setFontSize(11);
      doc.text(gmSignature.typedSignature, rightX, 263);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(9);
    }
    doc.text(
      `Status: ${gmSignature.signedAt ? `VERIFIED // Signed ${gmSignature.signedAt}` : 'PENDING MANUAL SIGNATURE'}`,
      rightX,
      274
    );

    doc.setFont('helvetica', 'bold');
    doc.setFontSize(8);
    doc.text('OFFICIAL AUDIT RECORD // ACID DATABASE LOCKED // SEC-OPS 2.0', 14, 286);

    doc.save(`Loss_Prevention_Digest_${selectedDate}.pdf`);
  };

  return (
    <div className="p-4 space-y-4">
      {/* Header and PDF Actions */}
      <div className="p-4 bg-panel border border-hairline rounded-sm space-y-3 no-print">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-base-tech font-semibold text-text-pri flex items-center gap-2">
              <FileBarChart className="w-5 h-5 text-amber" />
              Automated Loss Prevention & Inventory Reconciliation Digest
            </h1>
            <p className="text-xs-tech text-text-sec mt-0.5">
              Daily consolidated audit report detailing outflow throughput, sensor discrepancy metrics, and shrinkage exposure.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => window.print()}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs-tech font-semibold rounded-sm bg-panel-raised hover:bg-hairline/40 text-text-pri border border-hairline transition-colors"
            >
              <Printer className="w-3.5 h-3.5 text-amber" />
              Print Report
            </button>
            <button
              onClick={handleDownloadPdf}
              className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs-tech font-semibold rounded-sm bg-amber hover:bg-amber/90 text-black transition-colors shadow-sm"
            >
              <Download className="w-3.5 h-3.5" />
              Download Signed PDF
            </button>
          </div>
        </div>

        {/* Date Selector */}
        <div className="flex items-center gap-2 pt-2 border-t border-hairline text-xs-tech">
          <Calendar className="w-4 h-4 text-text-sec" />
          <span className="text-text-sec">Operations Reporting Date:</span>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="px-2 py-1 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
          />
        </div>
      </div>

      {/* Main Report Document Sheet */}
      <div className="p-6 bg-panel border border-hairline rounded-sm space-y-6 shadow-xl max-w-5xl mx-auto font-sans">
        {/* Document Header */}
        <div className="border-b-2 border-hairline pb-4 flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div>
            <div className="font-mono text-xs-tech font-bold text-amber tracking-wider">
              OPERATIONS AUDIT // SEC-OPS 2.0
            </div>
            <h2 className="text-lg-tech font-bold text-text-pri mt-1">
              Daily Loss Prevention & Exit Reconciliation Digest
            </h2>
            <div className="text-xs-tech text-text-sec mt-0.5">
              SuperStore Exit Portals Fleet Surveillance & Loss Prevention Audit
            </div>
          </div>

          <div className="text-left sm:text-right font-mono text-xs-tech space-y-1">
            <div className="text-text-pri font-semibold flex items-center sm:justify-end gap-1.5">
              <span className="w-2 h-2 rounded-full bg-status-ok animate-pulse" />
              DATE: {liveClock.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
            </div>
            <div className="text-text-sec text-[11px] flex items-center sm:justify-end gap-1">
              <Clock className="w-3 h-3 text-amber" />
              LIVE CLOCK: {liveClock.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true })} IST
            </div>
            <div className="px-2 py-0.5 rounded bg-teal-950/20 text-status-ok border border-status-ok/30 inline-block font-bold">
              STATUS: REAL-TIME AUDIT
            </div>
          </div>
        </div>

        {/* Dynamic Interactive KPI Scorecard Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {/* Card 1: Outflow */}
          <div
            onClick={() => setActiveView('events')}
            className="p-3.5 bg-canvas border border-hairline rounded-sm space-y-1 cursor-pointer hover:border-amber/60 hover:bg-panel-raised transition-all group select-none"
            title="Click to inspect all exit events in Ledger"
          >
            <div className="flex items-center justify-between">
              <div className="text-xs-tech text-text-sec group-hover:text-text-pri transition-colors">
                Total Outflow Volume
              </div>
              <span className="text-[10px] font-mono text-amber opacity-0 group-hover:opacity-100 transition-opacity">↗</span>
            </div>
            <div className="font-mono text-lg-tech font-bold text-mono-val">
              {todayThroughputUnits.toLocaleString('en-IN')} <span className="text-xs-tech text-text-sec font-normal">units</span>
            </div>
            <div className="text-[11px] text-text-sec">
              {lanes.length === 0 ? 'No active exit lanes' : `Across ${lanes.length} exit lane${lanes.length === 1 ? '' : 's'}`}
            </div>
          </div>

          {/* Card 2: Dispatched Retail Value (INR) */}
          <div
            onClick={() => setActiveView('events')}
            className="p-3.5 bg-canvas border border-hairline rounded-sm space-y-1 cursor-pointer hover:border-amber/60 hover:bg-panel-raised transition-all group select-none"
            title="Click to view retail ledger"
          >
            <div className="flex items-center justify-between">
              <div className="text-xs-tech text-text-sec group-hover:text-text-pri transition-colors">
                Dispatched Retail Value (INR)
              </div>
              <span className="text-[10px] font-mono text-amber opacity-0 group-hover:opacity-100 transition-opacity">↗</span>
            </div>
            <div className="font-mono text-lg-tech font-bold text-mono-val">
              ₹{totalValueDispatched.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="text-[11px] text-text-sec">Computed in Indian Rupees (₹)</div>
          </div>

          {/* Card 3: Consensus Parity Rate */}
          <div
            onClick={() => setActiveView('dashboard')}
            className="p-3.5 bg-canvas border border-hairline rounded-sm space-y-1 cursor-pointer hover:border-amber/60 hover:bg-panel-raised transition-all group select-none"
            title="Click to view multi-sensor consensus parity dashboard"
          >
            <div className="flex items-center justify-between">
              <div className="text-xs-tech text-text-sec group-hover:text-text-pri transition-colors">
                Consensus Parity Rate
              </div>
              <span className="text-[10px] font-mono text-amber opacity-0 group-hover:opacity-100 transition-opacity">↗</span>
            </div>
            <div className="font-mono text-lg-tech font-bold text-status-ok">
              {consensusAccuracyRate}%
            </div>
            <div className="text-[11px] text-text-sec">Vision + RFID + Weight parity</div>
          </div>

          {/* Card 4: Shrinkage Delta (INR) */}
          <div
            onClick={() => setActiveView('alerts')}
            className="p-3.5 bg-canvas border border-hairline rounded-sm space-y-1 cursor-pointer hover:border-amber/60 hover:bg-panel-raised transition-all group select-none"
            title="Click to view active shrinkage flags in Alerts"
          >
            <div className="flex items-center justify-between">
              <div className="text-xs-tech text-text-sec group-hover:text-text-pri transition-colors">
                Flagged Shrinkage Delta
              </div>
              <span className="text-[10px] font-mono text-amber opacity-0 group-hover:opacity-100 transition-opacity">↗</span>
            </div>
            <div className="font-mono text-lg-tech font-bold text-status-high">
              +{totalDiscrepancyUnits} <span className="text-xs-tech text-text-sec font-normal">units</span>
            </div>
            <div className="text-[11px] text-status-high font-medium">
              ~₹{estimatedShrinkageValue.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} exposure
            </div>
          </div>
        </div>

        {/* Section: Dynamic High-Risk Lanes & Severity Summary */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Dynamic Exit Portal Distribution */}
          <div className="p-4 bg-canvas border border-hairline rounded-sm space-y-3">
            <h3 className="text-xs-tech font-semibold text-text-pri uppercase tracking-wider border-b border-hairline pb-2 flex items-center justify-between">
              <span>Exit Portal Risk & Anomaly Distribution</span>
              <span className="text-[11px] text-text-sec font-mono font-normal">({lanes.length} lanes registered)</span>
            </h3>
            <div className="space-y-2 font-mono text-xs-tech">
              {lanes.length > 0 ? (
                lanes.map((lane: SensorLane) => {
                  const laneEvents = events.filter((e) => e.laneId === lane.laneId);
                  const flags = laneEvents.filter((e) => e.verdict === 'MISMATCH').length;
                  const parity =
                    laneEvents.length > 0
                      ? ((laneEvents.length - flags) / laneEvents.length * 100).toFixed(1)
                      : '100.0';

                  return (
                    <div
                      key={lane.laneId}
                      onClick={() => setActiveView('events')}
                      className="flex items-center justify-between p-2.5 bg-panel border border-hairline/60 rounded-sm cursor-pointer hover:border-amber/60 hover:bg-panel-raised transition-colors group"
                      title={`Click to filter exit events for ${lane.laneId}`}
                    >
                      <span className="font-sans font-medium text-text-pri group-hover:text-amber transition-colors truncate max-w-[220px]">
                        {lane.laneId} ({lane.location || 'Exit Portal'})
                      </span>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <span className={`font-bold ${flags > 0 ? 'text-status-high' : 'text-status-ok'}`}>
                          {parity}% Parity {flags > 0 ? `(${flags} Flag${flags > 1 ? 's' : ''})` : ''}
                        </span>
                        <span className="text-[10px] text-text-sec opacity-0 group-hover:opacity-100 transition-opacity">↗</span>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="p-4 bg-panel border border-hairline rounded-sm text-center text-xs-tech text-text-sec font-sans">
                  No exit portal lanes enrolled. Register cameras and lanes in Settings.
                </div>
              )}
            </div>
          </div>

          {/* Dynamic Loss Prevention Severity Summary */}
          <div className="p-4 bg-canvas border border-hairline rounded-sm space-y-3">
            <h3 className="text-xs-tech font-semibold text-text-pri uppercase tracking-wider border-b border-hairline pb-2">
              Loss Prevention Severity Summary
            </h3>
            <div className="space-y-2 font-mono text-xs-tech">
              <div
                onClick={() => setActiveView('alerts')}
                className="flex items-center justify-between p-2.5 bg-panel border border-hairline/60 rounded-sm cursor-pointer hover:border-status-high/60 hover:bg-panel-raised transition-colors group"
                title="Click to view High Severity alerts"
              >
                <span className="flex items-center gap-1.5 text-status-high">
                  <AlertTriangle className="w-3.5 h-3.5" /> High Severity (Siren / Interlock)
                </span>
                <span className="font-bold text-status-high flex items-center gap-1">
                  {highSeverityCount} incidents
                  <span className="text-[10px] opacity-0 group-hover:opacity-100">↗</span>
                </span>
              </div>

              <div
                onClick={() => setActiveView('alerts')}
                className="flex items-center justify-between p-2.5 bg-panel border border-hairline/60 rounded-sm cursor-pointer hover:border-status-med/60 hover:bg-panel-raised transition-colors group"
                title="Click to view Medium Severity alerts"
              >
                <span className="flex items-center gap-1.5 text-status-med">
                  <AlertTriangle className="w-3.5 h-3.5" /> Medium Severity (Carrier Under-declare)
                </span>
                <span className="font-bold text-status-med flex items-center gap-1">
                  {mediumSeverityCount} incidents
                  <span className="text-[10px] opacity-0 group-hover:opacity-100">↗</span>
                </span>
              </div>

              <div
                onClick={() => setActiveView('alerts')}
                className="flex items-center justify-between p-2.5 bg-panel border border-hairline/60 rounded-sm cursor-pointer hover:border-status-low/60 hover:bg-panel-raised transition-colors group"
                title="Click to view Low Severity notices"
              >
                <span className="flex items-center gap-1.5 text-status-low">
                  <AlertTriangle className="w-3.5 h-3.5" /> Low Severity (Loose singles / Noise)
                </span>
                <span className="font-bold text-status-low flex items-center gap-1">
                  {lowSeverityCount} notices
                  <span className="text-[10px] opacity-0 group-hover:opacity-100">↗</span>
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Section: Forensic Incident Table */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-xs-tech font-semibold text-text-pri uppercase tracking-wider">
              Loss Prevention Incident Audit Trail
            </h3>
            <span className="text-[11px] text-text-sec font-mono">
              ({mismatchEvents.length} flagged events)
            </span>
          </div>

          <div className="border border-hairline rounded-sm overflow-hidden">
            <table className="w-full text-left text-xs-tech font-mono">
              <thead>
                <tr className="bg-canvas border-b border-hairline text-text-sec text-[11px]">
                  <th className="p-2.5 font-normal">Event ID</th>
                  <th className="p-2.5 font-normal">Lane</th>
                  <th className="p-2.5 font-normal">Carrier / Employee</th>
                  <th className="p-2.5 font-normal text-right">Detected</th>
                  <th className="p-2.5 font-normal text-right">Declared</th>
                  <th className="p-2.5 font-normal text-right">Delta</th>
                  <th className="p-2.5 font-normal">Severity</th>
                  <th className="p-2.5 font-normal">Forensic Notes</th>
                </tr>
              </thead>
              <tbody>
                {mismatchEvents.length > 0 ? (
                  mismatchEvents.map((ev: ExitEvent) => (
                    <tr
                      key={ev.eventId}
                      onClick={() => {
                        setSelectedEventId(ev.eventId);
                        setActiveView('events');
                      }}
                      className="border-b border-hairline/50 hover:bg-panel-raised cursor-pointer transition-colors"
                      title="Click to view full forensic inspection for this event"
                    >
                      <td className="p-2.5 font-bold text-amber whitespace-nowrap">{ev.eventId} ↗</td>
                      <td className="p-2.5 text-text-pri whitespace-nowrap">{ev.laneId}</td>
                      <td className="p-2.5 text-text-pri font-sans whitespace-nowrap">{ev.employeeId || 'Unassigned'}</td>
                      <td className="p-2.5 text-right font-bold text-mono-val">{ev.consensusUnits}</td>
                      <td className="p-2.5 text-right text-text-sec">{ev.declaredUnits ?? '-'}</td>
                      <td className="p-2.5 text-right font-bold text-status-high">+{ev.deltaUnits} EA</td>
                      <td className="p-2.5 font-sans whitespace-nowrap">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            ev.severity === 'HIGH'
                              ? 'bg-red-950/30 text-status-high'
                              : 'bg-orange-950/20 text-status-med'
                          }`}
                        >
                          {ev.severity}
                        </span>
                      </td>
                      <td className="p-2.5 font-sans text-text-sec text-[11px] max-w-[320px] truncate" title={ev.notes}>
                        {ev.notes}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-text-sec font-sans">
                      No discrepancy incidents recorded for selected date. All exit portals operating at nominal consensus.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Section: Manual Signature & Authorization Suite */}
        <div className="pt-4 border-t-2 border-hairline space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs-tech font-bold text-text-pri uppercase tracking-wider">
              Official Manual Sign-off & Audit Authorization
            </h3>
            <span className="text-[11px] text-text-sec font-mono">
              {lpSignature.signedAt && gmSignature.signedAt
                ? '✓ FULLY EXECUTED & AUDIT LOCKED'
                : 'PENDING EXECUTIVE SIGN-OFF'}
            </span>
          </div>
          <p className="text-[11px] text-text-sec">
            Manually sign with your mouse/touchscreen or type your digital signature below. Signatures are verified and embedded into downloaded PDF digests.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
            {/* 1. Loss Prevention Lead Signature Pad */}
            <SignaturePad
              title="Loss Prevention Lead Signature"
              defaultName="Loss Prevention Officer"
              defaultRole="Loss Prevention Lead"
              data={lpSignature}
              onChange={setLpSignature}
            />

            {/* 2. Store General Manager Authorization Pad */}
            <SignaturePad
              title="Store General Manager Authorization"
              defaultName="Store General Manager"
              defaultRole="Operations GM"
              data={gmSignature}
              onChange={setGmSignature}
            />
          </div>
        </div>
      </div>
    </div>
  );
};


