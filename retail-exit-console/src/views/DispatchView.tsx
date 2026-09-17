import React, { useState, useEffect } from 'react';
import {
  Truck,
  Layers,
  FileCheck2,
  AlertTriangle,
  CheckCircle2,
  Play,
  Square,
  RefreshCw,
  WifiOff,
  Camera as CameraIcon,
} from 'lucide-react';

import type { DispatchSessionRecord, MaterialClassDefinition } from '../types';

export const DispatchView: React.FC = () => {
  const [sessions, setSessions] = useState<DispatchSessionRecord[]>([]);
  const [activeSession, setActiveSession] = useState<DispatchSessionRecord | null>(null);
  const [materialClasses, setMaterialClasses] = useState<MaterialClassDefinition[]>([]);
  const [loading, setLoading] = useState(false);
  const [isStartModalOpen, setIsStartModalOpen] = useState(false);

  // New session form state
  const [dockLaneId, setDockLaneId] = useState('DOCK-01');
  const [manifestId, setManifestId] = useState('');
  const [vehicleIdentifier, setVehicleIdentifier] = useState('');
  const [carrierEmployeeId, setCarrierEmployeeId] = useState('');
  const [manifestExpectedQuantities, setManifestExpectedQuantities] = useState<Record<string, number>>({});
  const [initialStackCounts, setInitialStackCounts] = useState<Record<string, number>>({});

  const fetchDispatchData = async () => {
    setLoading(true);
    try {
      // Fetch material classes
      const classesRes = await fetch('/api/dispatch/materials/classes');
      if (classesRes.ok) {
        const cData = await classesRes.json();
        const mClasses = cData.material_classes || [];
        setMaterialClasses(mClasses);
        // Initialize default inputs
        const initialMap: Record<string, number> = {};
        mClasses.forEach((m: MaterialClassDefinition) => {
          initialMap[m.name] = 0;
        });
        if (Object.keys(manifestExpectedQuantities).length === 0) {
          setManifestExpectedQuantities(initialMap);
          setInitialStackCounts(initialMap);
        }
      }

      // Fetch sessions
      const sessRes = await fetch('/api/dispatch/sessions?limit=20');
      if (sessRes.ok) {
        const sData: DispatchSessionRecord[] = await sessRes.json();
        setSessions(sData);
        const ongoing = sData.find((s) => s.status === 'ACTIVE');
        setActiveSession(ongoing || null);
      }
    } catch (err) {
      console.error('Failed to fetch dispatch telemetry:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDispatchData();
    const interval = setInterval(fetchDispatchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleStartSession = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const resp = await fetch('/api/dispatch/session/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dockLaneId,
          manifestId: manifestId.trim() || undefined,
          vehicleIdentifier: vehicleIdentifier.trim() || undefined,
          carrierEmployeeId: carrierEmployeeId.trim() || undefined,
          manifestExpected: manifestExpectedQuantities,
          manualInitialCount: initialStackCounts,
        }),
      });
      if (resp.ok) {
        setIsStartModalOpen(false);
        fetchDispatchData();
      } else {
        const err = await resp.json();
        alert(`Failed to start session: ${err.detail || 'Unknown error'}`);
      }
    } catch (err) {
      alert(`Error starting session: ${err}`);
    }
  };

  const handleCompleteSession = async (sessionId: string) => {
    if (!confirm('Are you sure you want to finalize and reconcile this dispatch loading session?')) {
      return;
    }
    try {
      const resp = await fetch(`/api/dispatch/session/${sessionId}/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (resp.ok) {
        fetchDispatchData();
      } else {
        const err = await resp.json();
        alert(`Failed to complete session: ${err.detail || 'Unknown error'}`);
      }
    } catch (err) {
      alert(`Error completing session: ${err}`);
    }
  };

  return (
    <div className="p-4 space-y-4">
      {/* Header & Status Bar */}
      <div className="p-4 bg-panel border border-hairline rounded-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Truck className="w-5 h-5 text-cyan" />
            <h1 className="text-base-tech font-bold text-text-pri tracking-wide">
              Industrial Dispatch & Loading Dock Intelligence
            </h1>
            <span className="px-2 py-0.5 text-[10px] font-mono bg-cyan/10 border border-cyan/30 text-cyan rounded-full">
              ≥90% Stack Accuracy Target
            </span>
          </div>
          <p className="text-xs-tech text-text-sec mt-1">
            Real-time universal material segmentation, dense pallet counting, and automated manifest reconciliation.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchDispatchData}
            disabled={loading}
            className="p-2 border border-hairline text-text-sec hover:text-text-pri rounded-sm transition-colors"
            title="Refresh Data"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          {!activeSession ? (
            <button
              onClick={() => setIsStartModalOpen(true)}
              className="px-3 py-1.5 bg-cyan text-black font-semibold text-xs-tech rounded-sm flex items-center gap-1.5 hover:bg-cyan/90 transition-colors shadow-sm"
            >
              <Play className="w-3.5 h-3.5 fill-black" />
              Start Dock Loading Session
            </button>
          ) : (
            <button
              onClick={() => handleCompleteSession(activeSession.sessionId)}
              className="px-3 py-1.5 bg-red-600 text-white font-semibold text-xs-tech rounded-sm flex items-center gap-1.5 hover:bg-red-500 transition-colors shadow-sm animate-pulse"
            >
              <Square className="w-3.5 h-3.5 fill-white" />
              Finalize & Reconcile Dock
            </button>
          )}
        </div>
      </div>

      {/* Active Session Live Audit Banner */}
      {activeSession && (
        <div className="p-4 bg-panel border-2 border-cyan/40 rounded-sm space-y-4 shadow-lg">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-hairline pb-3">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-cyan animate-ping" />
              <span className="text-xs-tech font-bold font-mono text-cyan">
                ACTIVE DISPATCH SESSION: {activeSession.sessionId}
              </span>
              <span className="text-xs-tech text-text-sec font-mono">
                [Dock: {activeSession.dockLaneId}]
              </span>
            </div>
            <div className="flex items-center gap-3 text-xs-tech font-mono">
              <span className="text-text-sec">Vehicle: <strong className="text-text-pri">{activeSession.vehicleIdentifier || 'UNSPECIFIED'}</strong></span>
              <span className="text-text-sec">Manifest: <strong className="text-text-pri">{activeSession.manifestId || 'NONE'}</strong></span>
              {activeSession.trackingInterruptedSeconds > 0 && (
                <span className="px-2 py-0.5 bg-red-950/40 border border-status-high text-status-high rounded flex items-center gap-1">
                  <WifiOff className="w-3 h-3" />
                  Stream Gap: {activeSession.trackingInterruptedSeconds}s
                </span>
              )}
            </div>
          </div>

          {/* Stack Audit Metric Tiles */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div className="p-3 bg-canvas border border-hairline rounded-sm">
              <span className="text-[11px] font-mono text-text-sec uppercase">Initial Stack Count</span>
              <div className="text-xl font-mono font-bold text-text-pri mt-1">
                {Object.values(activeSession.beforeCount || {}).reduce((a, b) => a + b, 0)} <span className="text-xs text-text-sec font-normal">units</span>
              </div>
            </div>

            <div className="p-3 bg-canvas border border-hairline rounded-sm">
              <span className="text-[11px] font-mono text-text-sec uppercase">Manifest Expected</span>
              <div className="text-xl font-mono font-bold text-cyan mt-1">
                {Object.values(activeSession.manifestExpected || {}).reduce((a, b) => a + b, 0)} <span className="text-xs text-text-sec font-normal">units</span>
              </div>
            </div>

            <div className="p-3 bg-canvas border border-hairline rounded-sm">
              <span className="text-[11px] font-mono text-text-sec uppercase">Physical Removed Delta</span>
              <div className="text-xl font-mono font-bold text-amber mt-1">
                {Object.values(activeSession.removedDelta || {}).reduce((a, b) => a + b, 0)} <span className="text-xs text-text-sec font-normal">loaded</span>
              </div>
            </div>

            <div className="p-3 bg-canvas border border-hairline rounded-sm">
              <span className="text-[11px] font-mono text-text-sec uppercase">Reconciliation Status</span>
              <div className="mt-1 flex items-center gap-1.5">
                {activeSession.discrepancyType === 'MATCH' ? (
                  <span className="text-status-pass font-mono font-bold text-sm flex items-center gap-1">
                    <CheckCircle2 className="w-4 h-4" /> VERIFIED MATCH
                  </span>
                ) : (
                  <span className="text-status-high font-mono font-bold text-sm flex items-center gap-1">
                    <AlertTriangle className="w-4 h-4" /> {activeSession.discrepancyType} ({activeSession.discrepancyMagnitude} variance)
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Universal Material Class Registry & Specifications */}
      <div className="p-4 bg-panel border border-hairline rounded-sm space-y-3">
        <h2 className="text-xs-tech font-bold uppercase tracking-wider text-text-sec flex items-center gap-2">
          <Layers className="w-4 h-4 text-cyan" />
          Configured Industrial Material Classes & Stack Geometry
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {materialClasses.map((mat) => (
            <div key={mat.class_id} className="p-3 bg-canvas border border-hairline rounded-sm space-y-2">
              <div className="flex items-start justify-between gap-1">
                <span className="font-semibold text-text-pri text-xs leading-tight">{mat.name}</span>
                <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                  mat.severity_tier === 'HIGH' ? 'bg-red-950/40 text-red-400 border border-red-800' : 'bg-canvas text-text-sec border border-hairline'
                }`}>
                  {mat.severity_tier}
                </span>
              </div>
              <div className="text-[11px] text-text-sec space-y-0.5 font-mono">
                <div>Unit: {mat.count_unit}</div>
                <div>Category: {mat.category}</div>
                <div className="text-[10px] text-text-sec truncate" title={mat.density_notes}>
                  {mat.density_notes}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Historical Dispatch Sessions & Manifest Audit Trail */}
      <div className="p-4 bg-panel border border-hairline rounded-sm space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs-tech font-bold uppercase tracking-wider text-text-sec flex items-center gap-2">
            <FileCheck2 className="w-4 h-4 text-cyan" />
            Dispatch Loading Sessions & Arbitration Audit History
          </h2>
          <span className="text-xs-tech font-mono text-text-sec">{sessions.length} Recorded Sessions</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs-tech">
            <thead className="border-b border-hairline text-text-sec font-mono uppercase text-[11px] bg-canvas">
              <tr>
                <th className="p-2.5">Session ID</th>
                <th className="p-2.5">Dock Lane</th>
                <th className="p-2.5">Vehicle Tag</th>
                <th className="p-2.5">Manifest</th>
                <th className="p-2.5">Status</th>
                <th className="p-2.5">Arbitration</th>
                <th className="p-2.5">Stream Gaps</th>
                <th className="p-2.5">Timestamp</th>
                <th className="p-2.5 text-right">Evidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline font-mono">
              {sessions.length === 0 ? (
                <tr>
                  <td colSpan={9} className="p-6 text-center text-text-sec italic">
                    No dispatch sessions logged. Click "Start Dock Loading Session" to begin.
                  </td>
                </tr>
              ) : (
                sessions.map((s) => (
                  <tr key={s.sessionId} className="hover:bg-canvas/50 transition-colors">
                    <td className="p-2.5 font-bold text-text-pri">{s.sessionId}</td>
                    <td className="p-2.5 text-cyan">{s.dockLaneId}</td>
                    <td className="p-2.5">{s.vehicleIdentifier || '—'}</td>
                    <td className="p-2.5">{s.manifestId || '—'}</td>
                    <td className="p-2.5">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        s.status === 'ACTIVE'
                          ? 'bg-cyan/20 text-cyan border border-cyan/40'
                          : s.status === 'FLAGGED_DISCREPANCY'
                          ? 'bg-red-950/40 text-status-high border border-status-high/40'
                          : 'bg-green-950/40 text-status-pass border border-status-pass/40'
                      }`}>
                        {s.status}
                      </span>
                    </td>
                    <td className="p-2.5">
                      {s.discrepancyType === 'MATCH' ? (
                        <span className="text-status-pass font-semibold">MATCH (0)</span>
                      ) : (
                        <span className="text-status-high font-semibold">
                          {s.discrepancyType} ({s.discrepancyMagnitude > 0 ? `+${s.discrepancyMagnitude}` : s.discrepancyMagnitude})
                        </span>
                      )}
                    </td>
                    <td className="p-2.5">
                      {s.trackingInterruptedSeconds > 0 ? (
                        <span className="text-amber">{s.trackingInterruptedSeconds}s gap</span>
                      ) : (
                        <span className="text-text-sec">0s (Pure Stream)</span>
                      )}
                    </td>
                    <td className="p-2.5 text-text-sec">{new Date(s.startedAt).toLocaleString()}</td>
                    <td className="p-2.5 text-right">
                      {s.archivalSnapshotUrl ? (
                        <a
                          href={s.archivalSnapshotUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 px-2 py-1 bg-canvas border border-hairline hover:border-cyan text-cyan rounded text-[11px] transition-colors"
                        >
                          <CameraIcon className="w-3 h-3" />
                          View
                        </a>
                      ) : (
                        <span className="text-text-sec text-[11px]">—</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Start Session Modal */}
      {isStartModalOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-panel border border-hairline rounded-sm max-w-lg w-full p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-hairline pb-3">
              <h3 className="text-base-tech font-bold text-text-pri flex items-center gap-2">
                <Play className="w-4 h-4 text-cyan" />
                Initialize Industrial Dispatch Session
              </h3>
              <button
                onClick={() => setIsStartModalOpen(false)}
                className="text-text-sec hover:text-text-pri font-mono text-sm"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleStartSession} className="space-y-3 text-xs-tech">
              <div>
                <label className="block text-text-sec mb-1">Dock Bay / Lane ID *</label>
                <input
                  type="text"
                  required
                  value={dockLaneId}
                  onChange={(e) => setDockLaneId(e.target.value)}
                  className="w-full px-3 py-2 bg-canvas border border-hairline rounded text-text-pri font-mono focus:border-cyan focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-text-sec mb-1">Manifest / Order ID</label>
                  <input
                    type="text"
                    placeholder="e.g. MNF-2026-88"
                    value={manifestId}
                    onChange={(e) => setManifestId(e.target.value)}
                    className="w-full px-3 py-2 bg-canvas border border-hairline rounded text-text-pri font-mono focus:border-cyan focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-text-sec mb-1">Vehicle License Tag</label>
                  <input
                    type="text"
                    placeholder="e.g. MH-12-AB-9876"
                    value={vehicleIdentifier}
                    onChange={(e) => setVehicleIdentifier(e.target.value)}
                    className="w-full px-3 py-2 bg-canvas border border-hairline rounded text-text-pri font-mono focus:border-cyan focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-text-sec mb-1">Carrier Driver ID</label>
                <input
                  type="text"
                  placeholder="e.g. EMP-TRUCK-01"
                  value={carrierEmployeeId}
                  onChange={(e) => setCarrierEmployeeId(e.target.value)}
                  className="w-full px-3 py-2 bg-canvas border border-hairline rounded text-text-pri font-mono focus:border-cyan focus:outline-none"
                />
              </div>

              {/* Material expected & initial counts */}
              <div className="pt-2 border-t border-hairline space-y-2">
                <span className="font-semibold text-text-pri block">Material Manifest Expected vs Initial Stack</span>
                <div className="max-h-40 overflow-y-auto space-y-2 pr-1">
                  {materialClasses.map((m) => (
                    <div key={m.name} className="flex items-center justify-between gap-2 p-1.5 bg-canvas border border-hairline rounded">
                      <span className="text-xs truncate w-1/2">{m.name}</span>
                      <div className="flex items-center gap-1 w-1/2">
                        <input
                          type="number"
                          min="0"
                          title="Initial Stack Count"
                          placeholder="Init"
                          value={initialStackCounts[m.name] || 0}
                          onChange={(e) =>
                            setInitialStackCounts({
                              ...initialStackCounts,
                              [m.name]: parseInt(e.target.value) || 0,
                            })
                          }
                          className="w-16 px-1.5 py-1 bg-panel border border-hairline rounded text-center text-text-pri font-mono"
                        />
                        <span className="text-text-sec">→</span>
                        <input
                          type="number"
                          min="0"
                          title="Manifest Expected"
                          placeholder="Exp"
                          value={manifestExpectedQuantities[m.name] || 0}
                          onChange={(e) =>
                            setManifestExpectedQuantities({
                              ...manifestExpectedQuantities,
                              [m.name]: parseInt(e.target.value) || 0,
                            })
                          }
                          className="w-16 px-1.5 py-1 bg-panel border border-cyan/40 rounded text-center text-cyan font-mono"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-3 border-t border-hairline flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsStartModalOpen(false)}
                  className="px-3 py-1.5 border border-hairline text-text-sec rounded hover:text-text-pri"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-cyan text-black font-semibold rounded hover:bg-cyan/90"
                >
                  Start Session
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
