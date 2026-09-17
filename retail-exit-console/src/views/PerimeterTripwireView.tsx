import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  UserX,
  UserCheck,
  AlertTriangle,
  Plus,
  RefreshCw,
  Camera as CameraIcon,
  Sliders,
  Radio,
} from 'lucide-react';

import type { VirtualTripwireRecord, TripwireCrossingRecord, Camera } from '../types';

export const PerimeterTripwireView: React.FC = () => {
  const [tripwires, setTripwires] = useState<VirtualTripwireRecord[]>([]);
  const [crossings, setCrossings] = useState<TripwireCrossingRecord[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(false);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  // New Tripwire form state
  const [selectedCameraId, setSelectedCameraId] = useState('');
  const [label, setLabel] = useState('');
  const [directionMode, setDirectionMode] = useState<'ENTRY' | 'EXIT' | 'BOTH'>('ENTRY');
  const [x1, setX1] = useState(0.1);
  const [y1, setY1] = useState(0.5);
  const [x2, setX2] = useState(0.9);
  const [y2, setY2] = useState(0.5);

  const fetchTripwireData = async () => {
    setLoading(true);
    try {
      // Fetch cameras
      const camRes = await fetch('/api/cameras');
      if (camRes.ok) {
        const cData = await camRes.json();
        setCameras(cData);
        if (!selectedCameraId && cData.length > 0) {
          setSelectedCameraId(cData[0].cameraId || cData[0].camera_id);
        }
      }

      // Fetch tripwire configurations
      const twRes = await fetch('/api/tripwire/configs');
      if (twRes.ok) {
        const twData = await twRes.json();
        setTripwires(twData);
      }

      // Fetch crossing events
      const crRes = await fetch('/api/tripwire/events?limit=30');
      if (crRes.ok) {
        const crData = await crRes.json();
        setCrossings(crData);
      }
    } catch (err) {
      console.error('Failed to fetch tripwire data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTripwireData();
    const interval = setInterval(fetchTripwireData, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleCreateTripwire = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const resp = await fetch('/api/tripwire/configs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cameraId: selectedCameraId,
          label: label.trim() || 'Perimeter Boundary Line',
          lineCoords: [
            [parseFloat(x1.toString()), parseFloat(y1.toString())],
            [parseFloat(x2.toString()), parseFloat(y2.toString())],
          ],
          directionMode,
          active: true,
        }),
      });
      if (resp.ok) {
        setIsAddModalOpen(false);
        setLabel('');
        fetchTripwireData();
      } else {
        const err = await resp.json();
        alert(`Failed to configure tripwire: ${err.detail || 'Unknown error'}`);
      }
    } catch (err) {
      alert(`Error creating tripwire: ${err}`);
    }
  };

  const tailgatingCount = crossings.filter((c) => c.isTailgating).length;
  const intruderCount = crossings.filter((c) => c.biometricStatus === 'UNKNOWN_INTRUDER').length;

  return (
    <div className="p-4 space-y-4">
      {/* Header Bar */}
      <div className="p-4 bg-panel border border-hairline rounded-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-red-500" />
            <h1 className="text-base-tech font-bold text-text-pri tracking-wide">
              Virtual Tripwire, Anti-Tailgating & Perimeter Ingress
            </h1>
            <span className="px-2 py-0.5 text-[10px] font-mono bg-red-950/40 border border-red-500/40 text-red-400 rounded-full">
              1.2s Temporal Window Interlock
            </span>
          </div>
          <p className="text-xs-tech text-text-sec mt-1">
            2D vector cross-product line trajectory tracking, biometric face handshake, and trailing silhouette concealment defense.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchTripwireData}
            disabled={loading}
            className="p-2 border border-hairline text-text-sec hover:text-text-pri rounded-sm transition-colors"
            title="Refresh Data"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="px-3 py-1.5 bg-red-600 text-white font-semibold text-xs-tech rounded-sm flex items-center gap-1.5 hover:bg-red-500 transition-colors shadow-sm"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Virtual Tripwire
          </button>
        </div>
      </div>

      {/* KPI Radar Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-3 bg-panel border border-hairline rounded-sm">
          <span className="text-[11px] font-mono text-text-sec uppercase">Active Boundaries</span>
          <div className="text-2xl font-mono font-bold text-text-pri mt-1">
            {tripwires.filter((t) => t.active).length} <span className="text-xs text-text-sec font-normal">lines</span>
          </div>
        </div>

        <div className="p-3 bg-panel border border-hairline rounded-sm">
          <span className="text-[11px] font-mono text-text-sec uppercase">Total Crossings (24h)</span>
          <div className="text-2xl font-mono font-bold text-cyan mt-1">
            {crossings.length}
          </div>
        </div>

        <div className="p-3 bg-panel border border-status-high/30 bg-red-950/10 rounded-sm">
          <span className="text-[11px] font-mono text-status-high uppercase">Anti-Tailgating Violations</span>
          <div className="text-2xl font-mono font-bold text-status-high mt-1 flex items-center gap-2">
            {tailgatingCount}
            {tailgatingCount > 0 && <AlertTriangle className="w-4 h-4 text-status-high animate-pulse" />}
          </div>
        </div>

        <div className="p-3 bg-panel border border-hairline rounded-sm">
          <span className="text-[11px] font-mono text-text-sec uppercase">Unknown Intruder Traversal</span>
          <div className="text-2xl font-mono font-bold text-amber mt-1">
            {intruderCount}
          </div>
        </div>
      </div>

      {/* Active Tripwire Lines Overlay & Config Table */}
      <div className="p-4 bg-panel border border-hairline rounded-sm space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs-tech font-bold uppercase tracking-wider text-text-sec flex items-center gap-2">
            <Sliders className="w-4 h-4 text-cyan" />
            Configured Perimeter Boundary Tripwires
          </h2>
          <span className="text-xs-tech font-mono text-text-sec">{tripwires.length} Active Rules</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {tripwires.length === 0 ? (
            <div className="col-span-3 p-6 text-center text-text-sec italic bg-canvas rounded border border-hairline">
              No virtual tripwires configured yet. Click "Add Virtual Tripwire" to set directional line boundaries.
            </div>
          ) : (
            tripwires.map((tw) => (
              <div key={tw.tripwireId} className="p-3 bg-canvas border border-hairline rounded-sm space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-text-pri text-xs truncate">{tw.label}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                    tw.active ? 'bg-green-950/40 text-status-pass border border-green-800' : 'bg-canvas text-text-sec border border-hairline'
                  }`}>
                    {tw.active ? 'ACTIVE' : 'INACTIVE'}
                  </span>
                </div>

                <div className="text-[11px] font-mono text-text-sec space-y-1">
                  <div>Camera: <span className="text-cyan">{tw.cameraId}</span></div>
                  <div>Mode: <strong className="text-text-pri">{tw.directionMode}</strong></div>
                  <div className="text-[10px] text-text-sec">
                    Coordinates: [({tw.lineCoords[0]?.[0]}, {tw.lineCoords[0]?.[1]}) → ({tw.lineCoords[1]?.[0]}, {tw.lineCoords[1]?.[1]})]
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Live Crossing & Anti-Tailgating Event Stream */}
      <div className="p-4 bg-panel border border-hairline rounded-sm space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs-tech font-bold uppercase tracking-wider text-text-sec flex items-center gap-2">
            <Radio className="w-4 h-4 text-cyan animate-pulse" />
            Live Tripwire Traversal & Tailgating Event Stream
          </h2>
          <span className="text-xs-tech font-mono text-text-sec">{crossings.length} Logged Events</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs-tech">
            <thead className="border-b border-hairline text-text-sec font-mono uppercase text-[11px] bg-canvas">
              <tr>
                <th className="p-2.5">Event ID</th>
                <th className="p-2.5">Tripwire / Camera</th>
                <th className="p-2.5">Direction</th>
                <th className="p-2.5">Track ID</th>
                <th className="p-2.5">Entity</th>
                <th className="p-2.5">Biometric Status</th>
                <th className="p-2.5">Tailgating / Concealment</th>
                <th className="p-2.5">Timestamp</th>
                <th className="p-2.5 text-right">Snapshot</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline font-mono">
              {crossings.length === 0 ? (
                <tr>
                  <td colSpan={9} className="p-6 text-center text-text-sec italic">
                    No boundary crossings recorded. Subjects crossing tripwires will appear here in real time.
                  </td>
                </tr>
              ) : (
                crossings.map((cr) => (
                  <tr
                    key={cr.crossingId}
                    className={`transition-colors ${
                      cr.isTailgating
                        ? 'bg-red-950/20 hover:bg-red-950/30'
                        : cr.biometricStatus === 'UNKNOWN_INTRUDER'
                        ? 'bg-yellow-950/10 hover:bg-yellow-950/20'
                        : 'hover:bg-canvas/50'
                    }`}
                  >
                    <td className="p-2.5 font-bold text-text-pri">{cr.crossingId}</td>
                    <td className="p-2.5">
                      <div className="text-text-pri">{cr.tripwireId}</div>
                      <div className="text-[10px] text-text-sec">{cr.cameraId}</div>
                    </td>
                    <td className="p-2.5">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        cr.direction === 'ENTRY'
                          ? 'bg-cyan/20 text-cyan border border-cyan/40'
                          : 'bg-amber/20 text-amber border border-amber/40'
                      }`}>
                        {cr.direction}
                      </span>
                    </td>
                    <td className="p-2.5 text-text-sec">{cr.trackId}</td>
                    <td className="p-2.5">{cr.entityType}</td>
                    <td className="p-2.5">
                      {cr.biometricStatus === 'VERIFIED_KNOWN' ? (
                        <span className="text-status-pass font-semibold flex items-center gap-1">
                          <UserCheck className="w-3.5 h-3.5" /> VERIFIED ({cr.matchedEmployeeId || 'KNOWN'})
                        </span>
                      ) : cr.biometricStatus === 'UNKNOWN_INTRUDER' ? (
                        <span className="text-status-high font-semibold flex items-center gap-1">
                          <UserX className="w-3.5 h-3.5" /> UNKNOWN INTRUDER
                        </span>
                      ) : (
                        <span className="text-text-sec">UNAVAILABLE</span>
                      )}
                    </td>
                    <td className="p-2.5">
                      {cr.isTailgating ? (
                        <span className="px-2 py-0.5 bg-red-950/50 text-status-high border border-status-high/50 rounded font-bold flex items-center gap-1 w-fit">
                          <AlertTriangle className="w-3 h-3" />
                          TAILGATING ({cr.tailgatingDetails?.reason || 'VIOLATION'})
                        </span>
                      ) : (
                        <span className="text-text-sec">Clean Traversal</span>
                      )}
                    </td>
                    <td className="p-2.5 text-text-sec">{new Date(cr.timestamp).toLocaleTimeString()}</td>
                    <td className="p-2.5 text-right">
                      {cr.snapshotUrl ? (
                        <a
                          href={cr.snapshotUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 px-2 py-1 bg-canvas border border-hairline hover:border-cyan text-cyan rounded text-[11px] transition-colors"
                        >
                          <CameraIcon className="w-3 h-3" />
                          Dossier
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

      {/* Add Virtual Tripwire Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-panel border border-hairline rounded-sm max-w-md w-full p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-hairline pb-3">
              <h3 className="text-base-tech font-bold text-text-pri flex items-center gap-2">
                <Plus className="w-4 h-4 text-cyan" />
                Configure Virtual Tripwire Line Boundary
              </h3>
              <button
                onClick={() => setIsAddModalOpen(false)}
                className="text-text-sec hover:text-text-pri font-mono text-sm"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateTripwire} className="space-y-3 text-xs-tech">
              <div>
                <label className="block text-text-sec mb-1">Target Camera *</label>
                <select
                  required
                  value={selectedCameraId}
                  onChange={(e) => setSelectedCameraId(e.target.value)}
                  className="w-full px-3 py-2 bg-canvas border border-hairline rounded text-text-pri font-mono focus:border-cyan focus:outline-none"
                >
                  {cameras.map((c: any) => (
                    <option key={c.cameraId || c.camera_id} value={c.cameraId || c.camera_id}>
                      {c.label || c.cameraId || c.camera_id} ({c.ipAddress || c.ip_address})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-text-sec mb-1">Boundary Label *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Loading Dock 1 Perimeter Tripwire"
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  className="w-full px-3 py-2 bg-canvas border border-hairline rounded text-text-pri font-mono focus:border-cyan focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-text-sec mb-1">Direction Mode</label>
                <select
                  value={directionMode}
                  onChange={(e) => setDirectionMode(e.target.value as any)}
                  className="w-full px-3 py-2 bg-canvas border border-hairline rounded text-text-pri font-mono focus:border-cyan focus:outline-none"
                >
                  <option value="ENTRY">ENTRY (Only crossing inside towards dock)</option>
                  <option value="EXIT">EXIT (Only crossing outside away from dock)</option>
                  <option value="BOTH">BOTH (Bi-directional monitoring)</option>
                </select>
              </div>

              <div className="pt-2 border-t border-hairline space-y-2">
                <span className="font-semibold text-text-pri block">Normalized Coordinates (0.0 to 1.0)</span>
                <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
                  <div>
                    <label className="text-text-sec">X1 (Start X)</label>
                    <input
                      type="number"
                      step="0.05"
                      min="0"
                      max="1"
                      value={x1}
                      onChange={(e) => setX1(parseFloat(e.target.value))}
                      className="w-full px-2 py-1 bg-canvas border border-hairline rounded"
                    />
                  </div>
                  <div>
                    <label className="text-text-sec">Y1 (Start Y)</label>
                    <input
                      type="number"
                      step="0.05"
                      min="0"
                      max="1"
                      value={y1}
                      onChange={(e) => setY1(parseFloat(e.target.value))}
                      className="w-full px-2 py-1 bg-canvas border border-hairline rounded"
                    />
                  </div>
                  <div>
                    <label className="text-text-sec">X2 (End X)</label>
                    <input
                      type="number"
                      step="0.05"
                      min="0"
                      max="1"
                      value={x2}
                      onChange={(e) => setX2(parseFloat(e.target.value))}
                      className="w-full px-2 py-1 bg-canvas border border-hairline rounded"
                    />
                  </div>
                  <div>
                    <label className="text-text-sec">Y2 (End Y)</label>
                    <input
                      type="number"
                      step="0.05"
                      min="0"
                      max="1"
                      value={y2}
                      onChange={(e) => setY2(parseFloat(e.target.value))}
                      className="w-full px-2 py-1 bg-canvas border border-hairline rounded"
                    />
                  </div>
                </div>
              </div>

              <div className="pt-3 border-t border-hairline flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-3 py-1.5 border border-hairline text-text-sec rounded hover:text-text-pri"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-red-600 text-white font-semibold rounded hover:bg-red-500"
                >
                  Save Boundary
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
