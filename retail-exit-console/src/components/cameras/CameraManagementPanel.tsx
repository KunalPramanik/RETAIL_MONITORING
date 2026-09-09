import React, { useState } from 'react';
import { useAppData } from '../../context/AppDataContext';
import type { Camera } from '../../types';
import { CameraStatusDot } from './CameraStatusDot';
import { AddCameraModal } from './AddCameraModal';
import { Modal } from '../common/Modal';
import {
  Camera as CameraIcon,
  Plus,
  Trash2,
  Radio,
  CheckCircle2,
  AlertTriangle,
  RotateCw,
  ShieldAlert,
  QrCode,
  Sliders,
} from 'lucide-react';

export const CameraManagementPanel: React.FC = () => {
  const { cameras, lanes, removeCamera, updateCamera, testCameraConnection } = useAppData();

  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  
  // Decommission confirmation state
  const [cameraToDelete, setCameraToDelete] = useState<Camera | null>(null);

  // Live test feed state
  const [testingCamId, setTestingCamId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{
    cameraId: string;
    success: boolean;
    message: string;
    snapshotUrl?: string;
  } | null>(null);

  // Reassign modal / inline state
  const [reassigningCam, setReassigningCam] = useState<Camera | null>(null);
  const [targetLaneId, setTargetLaneId] = useState<string>('');

  const activeCameras = cameras.filter((c) => !c.removedAt);

  const handleTestFeed = async (cam: Camera) => {
    setTestingCamId(cam.cameraId);
    setTestResult(null);
    try {
      const res = await testCameraConnection(cam.cameraId);
      setTestResult({
        cameraId: cam.cameraId,
        success: res.success,
        snapshotUrl: res.snapshotUrl,
        message: res.success
          ? `Stream verified (${res.latencyMs}ms) @ ${cam.resolution} ${cam.fps}fps`
          : (res.errorMessage || 'Feed unavailable'),
      });
    } catch (e: any) {
      setTestResult({
        cameraId: cam.cameraId,
        success: false,
        message: e.message || 'Stream test failed',
      });
    } finally {
      setTestingCamId(null);
    }
  };

  const handleConfirmDelete = () => {
    if (!cameraToDelete) return;
    removeCamera(cameraToDelete.cameraId);
    setCameraToDelete(null);
  };

  const handleConfirmReassign = () => {
    if (!reassigningCam) return;
    updateCamera({
      cameraId: reassigningCam.cameraId,
      laneId: targetLaneId || undefined,
    });
    setReassigningCam(null);
  };

  const getRelativeTime = (isoString?: string) => {
    if (!isoString) return 'Never';
    const diffSec = Math.round((Date.now() - new Date(isoString).getTime()) / 1000);
    if (diffSec < 5) return 'Just now';
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.round(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHrs = Math.round(diffMin / 60);
    return `${diffHrs}h ago`;
  };

  return (
    <div className="p-4 bg-panel border border-hairline rounded-sm space-y-4">
      {/* Panel Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-hairline pb-3">
        <div>
          <h2 className="text-xs-tech font-bold text-text-pri uppercase tracking-wider flex items-center gap-2">
            <CameraIcon className="w-4 h-4 text-amber" />
            Surveillance Camera Fleet & Lane Optical Sensor Registry
          </h2>
          <p className="text-[11px] text-text-sec mt-0.5">
            Add, calibrate, test RTSP video streams, and dynamically bind cameras to exit portals.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs-tech font-semibold bg-amber hover:bg-amber/90 text-black rounded-sm transition-colors shadow-sm"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Camera to Fleet
          </button>
        </div>
      </div>

      {/* Fleet Overview Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        <div className="p-2.5 bg-canvas border border-hairline rounded-sm">
          <span className="text-[11px] text-text-sec block">Total Fleet Size</span>
          <span className="text-lg font-mono font-bold text-text-pri">{activeCameras.length} Units</span>
        </div>
        <div className="p-2.5 bg-canvas border border-status-ok/30 rounded-sm">
          <span className="text-[11px] text-status-ok block">Online Streams</span>
          <span className="text-lg font-mono font-bold text-status-ok">
            {activeCameras.filter((c) => c.status === 'ONLINE').length} Active
          </span>
        </div>
        <div className="p-2.5 bg-canvas border border-status-low/30 rounded-sm">
          <span className="text-[11px] text-status-low block">Degraded / Retrying</span>
          <span className="text-lg font-mono font-bold text-status-low">
            {activeCameras.filter((c) => c.status === 'DEGRADED').length} Nodes
          </span>
        </div>
        <div className="p-2.5 bg-canvas border border-status-high/30 rounded-sm">
          <span className="text-[11px] text-status-high block">Offline Alerts</span>
          <span className="text-lg font-mono font-bold text-status-high">
            {activeCameras.filter((c) => c.status === 'OFFLINE').length} Offline
          </span>
        </div>
      </div>

      {/* Test Notification Banner if active */}
      {testResult && (
        <div
          className={`p-2.5 rounded-sm border text-xs-tech flex items-center justify-between animate-in fade-in ${
            testResult.success
              ? 'bg-teal-950/20 border-status-ok/40 text-status-ok'
              : 'bg-red-950/20 border-status-high/40 text-status-high'
          }`}
        >
          <span className="flex items-center gap-3">
            {testResult.success ? (
              <CheckCircle2 className="w-4 h-4 text-status-ok shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-status-high shrink-0" />
            )}
            {testResult.snapshotUrl && (
              <img
                src={testResult.snapshotUrl.startsWith('http') ? testResult.snapshotUrl : `http://127.0.0.1:8000${testResult.snapshotUrl}?t=${Date.now()}`}
                alt="Camera live frame"
                className="w-14 h-9 object-cover rounded border border-hairline shrink-0"
              />
            )}
            <span className="font-mono">{testResult.message}</span>
          </span>
          <button
            type="button"
            onClick={() => setTestResult(null)}
            className="text-text-sec hover:text-text-pri text-[11px]"
          >
            ✕
          </button>
        </div>
      )}

      {/* Camera Registry Table */}
      <div className="overflow-x-auto border border-hairline rounded-sm">
        <table className="w-full text-left font-mono text-xs-tech">
          <thead>
            <tr className="border-b border-hairline bg-canvas text-text-sec text-[11px]">
              <th className="p-2.5 font-normal">Status</th>
              <th className="p-2.5 font-normal">Camera Label & ID</th>
              <th className="p-2.5 font-normal">Assigned Lane</th>
              <th className="p-2.5 font-normal">Pairing Method</th>
              <th className="p-2.5 font-normal">RTSP Endpoint</th>
              <th className="p-2.5 font-normal text-right">Stream Format</th>
              <th className="p-2.5 font-normal text-right">Last Heartbeat</th>
              <th className="p-2.5 font-normal text-right">Fleet Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-hairline/50">
            {activeCameras.length > 0 ? (
              activeCameras.map((cam) => {
                const assignedLane = lanes.find((l) => l.laneId === cam.laneId);

                return (
                  <tr key={cam.cameraId} className="hover:bg-panel-raised/40 transition-colors">
                    {/* Status Dot */}
                    <td className="p-2.5 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <CameraStatusDot status={cam.status} />
                        <span
                          className={`text-[11px] font-semibold ${
                            cam.status === 'ONLINE'
                              ? 'text-status-ok'
                              : cam.status === 'DEGRADED'
                              ? 'text-status-low'
                              : cam.status === 'OFFLINE'
                              ? 'text-status-high'
                              : 'text-text-sec'
                          }`}
                        >
                          {cam.status}
                        </span>
                      </div>
                    </td>

                    {/* Camera Label & ID */}
                    <td className="p-2.5 font-sans">
                      <div className="text-text-pri font-medium">{cam.label}</div>
                      <div className="font-mono text-[10px] text-text-sec">{cam.cameraId}</div>
                    </td>

                    {/* Assigned Lane */}
                    <td className="p-2.5 font-sans">
                      {cam.laneId ? (
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm bg-panel-raised border border-hairline text-text-pri font-mono text-[11px]">
                          <Radio className="w-3 h-3 text-amber" />
                          {cam.laneId}
                          <span className="text-text-sec">({assignedLane?.location || 'Assigned'})</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm bg-yellow-950/20 text-status-low border border-status-low/30 font-mono text-[11px]">
                          UNASSIGNED (SPARE)
                        </span>
                      )}
                    </td>

                    {/* Pairing Method */}
                    <td className="p-2.5 font-sans">
                      {cam.pairingMethod === 'QR_APP_GENERATED' ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm bg-teal-950/30 text-status-ok border border-status-ok/30 font-mono text-[10px]">
                          <QrCode className="w-3 h-3 text-status-ok" />
                          QR (TOKEN)
                        </span>
                      ) : cam.pairingMethod === 'QR_CAMERA_DISPLAYED' ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm bg-blue-950/30 text-blue-400 border border-blue-800/40 font-mono text-[10px]">
                          <QrCode className="w-3 h-3 text-blue-400" />
                          QR (SCANNED)
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm bg-panel-raised border border-hairline text-text-sec font-mono text-[10px]">
                          <Sliders className="w-3 h-3 text-text-sec" />
                          MANUAL
                        </span>
                      )}
                    </td>

                    {/* RTSP / HTTP Stream IP */}
                    <td className="p-2.5">
                      <div className="text-mono-val">
                        {cam.streamUrl?.includes(':8080') ? `${cam.ipAddress}:8080` : `${cam.ipAddress}:554`}
                      </div>
                      <div className="text-[10px] text-text-sec truncate max-w-[160px]">{cam.rtspPath}</div>
                    </td>

                    {/* Stream Format */}
                    <td className="p-2.5 text-right">
                      <span className="text-text-pri font-medium">{cam.resolution || '1080p'}</span>
                      <span className="text-text-sec text-[11px] ml-1.5">@{cam.fps || 30}fps</span>
                    </td>

                    {/* Last Heartbeat */}
                    <td className="p-2.5 text-right text-mono-val">
                      {getRelativeTime(cam.lastHeartbeatAt)}
                    </td>

                    {/* Actions */}
                    <td className="p-2.5 text-right font-sans">
                      <div className="flex items-center justify-end gap-1.5">
                        {/* Test Connection */}
                        <button
                          type="button"
                          onClick={() => handleTestFeed(cam)}
                          disabled={testingCamId === cam.cameraId}
                          className="p-1 text-text-sec hover:text-amber rounded hover:bg-hairline/30 transition-colors"
                          title="Execute live RTSP test pull"
                        >
                          <RotateCw
                            className={`w-3.5 h-3.5 ${
                              testingCamId === cam.cameraId ? 'animate-spin text-amber' : ''
                            }`}
                          />
                        </button>

                        {/* Reassign Lane */}
                        <button
                          type="button"
                          onClick={() => {
                            setReassigningCam(cam);
                            setTargetLaneId(cam.laneId || '');
                          }}
                          className="p-1 text-text-sec hover:text-text-pri rounded hover:bg-hairline/30 transition-colors"
                          title="Reassign to exit lane"
                        >
                          <Radio className="w-3.5 h-3.5 text-text-sec hover:text-amber" />
                        </button>

                        {/* Decommission Camera */}
                        <button
                          type="button"
                          onClick={() => setCameraToDelete(cam)}
                          className="p-1 text-text-sec hover:text-status-high rounded hover:bg-red-950/20 transition-colors"
                          title="Decommission camera from fleet"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={8} className="py-16 text-center text-xs-tech text-text-sec font-sans">
                  <div className="flex flex-col items-center justify-center gap-2">
                    <CameraIcon className="w-7 h-7 text-hairline" />
                    <span className="text-text-pri font-medium">No cameras registered in fleet</span>
                    <span className="text-[11px] max-w-sm">
                      Add an IP/RTSP camera and assign it to an exit portal lane to begin real-time egress surveillance.
                    </span>
                    <button
                      type="button"
                      onClick={() => setIsAddModalOpen(true)}
                      className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber hover:bg-amber/90 text-black font-semibold rounded-sm transition-colors shadow-sm"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      Add First Camera
                    </button>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Add Camera Modal */}
      <AddCameraModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
      />

      {/* Reassign Lane Modal */}
      {reassigningCam && (
        <Modal
          isOpen={true}
          onClose={() => setReassigningCam(null)}
          title={`Reassign Camera: ${reassigningCam.label}`}
          maxWidth="md"
        >
          <div className="space-y-4">
            <p className="text-xs-tech text-text-sec">
              Reassign this optical sensor to another exit portal lane. Moving a camera between lanes is atomic with respect to in-flight inferences.
            </p>

            <div>
              <label className="text-xs-tech font-medium text-text-pri block mb-1">
                Target Exit Lane Portal
              </label>
              <select
                value={targetLaneId}
                onChange={(e) => setTargetLaneId(e.target.value)}
                className="w-full px-3 py-2 font-mono bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
              >
                <option value="">-- Unassigned (Spare Pool) --</option>
                {lanes.map((lane) => (
                  <option key={lane.laneId} value={lane.laneId}>
                    {lane.laneId} — {lane.location}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setReassigningCam(null)}
                className="px-3 py-1.5 text-xs-tech font-medium bg-panel-raised border border-hairline text-text-sec rounded-sm"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmReassign}
                className="px-4 py-1.5 text-xs-tech font-semibold bg-amber text-black rounded-sm hover:bg-amber/90"
              >
                Save Lane Binding
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Decommission Confirmation Dialog */}
      {cameraToDelete && (
        <Modal
          isOpen={true}
          onClose={() => setCameraToDelete(null)}
          title="Decommission Surveillance Camera"
          maxWidth="md"
        >
          <div className="space-y-3.5">
            <div className="p-3 bg-red-950/20 border border-status-high/40 rounded-sm flex items-start gap-2.5">
              <ShieldAlert className="w-5 h-5 text-status-high shrink-0 mt-0.5" />
              <div className="space-y-1">
                <div className="text-xs-tech font-bold text-status-high">
                  Destructive Fleet Action
                </div>
                <p className="text-[11px] text-text-sec">
                  Are you sure you want to decommission <strong className="text-text-pri">{cameraToDelete.label}</strong> ({cameraToDelete.cameraId})?
                </p>
              </div>
            </div>

            <p className="text-[11px] text-text-sec">
              The camera will be soft-deleted and unlinked from{' '}
              <strong className="text-text-pri">{cameraToDelete.laneId || 'spare pool'}</strong>. Historical exit events and detection records will remain preserved for forensic audits.
            </p>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setCameraToDelete(null)}
                className="px-3 py-1.5 text-xs-tech font-medium bg-panel-raised border border-hairline text-text-sec rounded-sm"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                className="px-4 py-1.5 text-xs-tech font-bold bg-status-high text-white rounded-sm hover:bg-status-high/90"
              >
                Confirm Decommission
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
