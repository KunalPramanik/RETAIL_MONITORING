"use client";

import { safeFetch, formatErrorMessage } from "@/lib/api-client";

import React, { useState, useEffect } from "react";
import {
  Camera,
  Plus,
  Radio,
  RefreshCw,
  Trash2,
  CheckCircle,
  AlertTriangle,
  Play,
  Sliders,
  ShieldCheck,
  Cpu,
  Wifi,
  Usb,
  ExternalLink,
  ChevronRight,
  Info,
  Maximize2,
  Check,
  MoveUp,
  MoveDown,
} from "lucide-react";

interface CameraItem {
  cameraId: string;
  label: string;
  laneId?: string;
  ipAddress: string;
  rtspPath: string;
  streamUrl?: string;
  status: "ONLINE" | "OFFLINE" | "PENDING_SETUP" | "DEGRADED";
  pairingMethod: string;
  resolution?: string;
  fps?: number;
  lastHeartbeatAt?: string;
  ignoredClasses?: string[];
}

const AVAILABLE_IGNORE_CLASSES = [
  { id: "Wall Picture Frame", label: "Wall Picture Frame / Poster", desc: "Prevents static portrait/art on walls from triggering person detection" },
  { id: "Display / Screen", label: "Display / TV / Screen", desc: "Prevents digital signage and monitors from being tracked as active carriers" },
  { id: "Doorway / Exit Door", label: "Doorway / Exit Door Frame", desc: "Suppresses door structural frame edges and glass reflections" },
  { id: "Ceiling / Floor Tile", label: "Ceiling / Floor Tile Pattern", desc: "Ignores high-contrast flooring grids and overhead light fixtures" },
  { id: "Shopping Cart / Basket Frame", label: "Shopping Cart / Basket Frame", desc: "Ignores empty metal/plastic cart frames at stanchions" },
  { id: "Storage Shelf / Stanchion", label: "Storage Shelf / Bollard Stanchion", desc: "Ignores structural beams, shelves, and dividing poles" },
  { id: "POS Terminal / Stand", label: "POS Terminal / Countertop Stand", desc: "Ignores register stands, card readers, and pin pads" },
];

interface DiscoveredDevice {
  deviceId: string;
  deviceType: string;
  ipAddress: string;
  manufacturer?: string;
  model?: string;
  suggestedLane?: string;
  isReachable: boolean;
}

export default function CameraManagementPage() {
  const [cameras, setCameras] = useState<CameraItem[]>([]);
  const [discovered, setDiscovered] = useState<DiscoveredDevice[]>([]);
  const [usbStatus, setUsbStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [testing, setTesting] = useState(false);
  const [viewingPreview, setViewingPreview] = useState<any>(null);
  const [previewModalNonce, setPreviewModalNonce] = useState<number>(0);

  // CC.2.1 Ignored Classes Filter Modal State
  const [selectedCameraForIgnore, setSelectedCameraForIgnore] = useState<CameraItem | null>(null);
  const [currentIgnoredClasses, setCurrentIgnoredClasses] = useState<string[]>([]);
  const [savingIgnore, setSavingIgnore] = useState(false);

  // Gate / Tripwire Line Suggestion State
  const [selectedCameraForGate, setSelectedCameraForGate] = useState<CameraItem | null>(null);
  const [suggestedGateLine, setSuggestedGateLine] = useState<{ x: number; y: number }[]>([]);
  const [gateExplanation, setGateExplanation] = useState<string>("");
  const [savingGateLine, setSavingGateLine] = useState<boolean>(false);
  const [manualDrawMode, setManualDrawMode] = useState<boolean>(false);

  const openGateLineModal = async (cam: CameraItem) => {
    setSelectedCameraForGate(cam);
    setPreviewModalNonce(Date.now());
    setManualDrawMode(false);
    try {
      const res = await safeFetch(`/api/cameras/${cam.cameraId}/suggest-gate-line`);
      if (res.ok) {
        const data = await res.json();
        setSuggestedGateLine(data.suggestedLine || [{ x: 0.12, y: 0.82 }, { x: 0.88, y: 0.82 }]);
        setGateExplanation(data.explanation || "Calculated ground passage threshold for accurate footfall traversal tracking.");
      } else {
        setSuggestedGateLine([{ x: 0.12, y: 0.82 }, { x: 0.88, y: 0.82 }]);
        setGateExplanation("Default baseline ground passage line.");
      }
    } catch {
      setSuggestedGateLine([{ x: 0.12, y: 0.82 }, { x: 0.88, y: 0.82 }]);
      setGateExplanation("Default baseline ground passage line.");
    }
  };

  const handleSaveGateLine = async (linePoints: { x: number; y: number }[]) => {
    if (!selectedCameraForGate) return;
    setSavingGateLine(true);
    try {
      const res = await safeFetch(`/api/cameras/${selectedCameraForGate.cameraId}/save-gate-line`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ line: linePoints }),
      });
      if (res.ok) {
        alert("Gate passage line saved successfully!");
        setSelectedCameraForGate(null);
        fetchCameras();
      } else {
        alert("Failed to save gate line.");
      }
    } catch (e: any) {
      alert(`Error saving gate line: ${e.message}`);
    } finally {
      setSavingGateLine(false);
    }
  };

  const [formData, setFormData] = useState({
    connectionType: "LAN_RTSP",
    label: "",
    ipAddress: "",
    rtspPath: "/live/ch0",
    streamUrl: "",
    laneId: "LANE-01",
    credentials: "",
    resolution: "1920x1080",
    fps: 30,
  });

  const fetchCameras = async () => {
    try {
      const res = await safeFetch("/api/cameras");
      if (res.ok) {
        setCameras(await res.json());
      }
    } catch (e) {
      console.warn("Failed to fetch cameras:", e);
    }
  };

  const fetchDiscovery = async () => {
    try {
      const resDev = await safeFetch("/api/discovery/devices");
      if (resDev.ok) setDiscovered(await resDev.json());
      const resUsb = await safeFetch("/api/discovery/usb");
      if (resUsb.ok) setUsbStatus(await resUsb.json());
    } catch (e) {
      console.warn("Discovery fetch failed:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCameras();
    fetchDiscovery();
    const interval = setInterval(fetchCameras, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);

    // Enforce explicit camera configuration; prevent submitting unconfigured fake defaults
    if (!formData.label.trim()) {
      setTestResult({ success: false, errorMessage: "Camera label is required before pairing." });
      setTesting(false);
      return;
    }
    if (formData.connectionType !== "USB" && formData.connectionType !== "WIFI_HTTP" && !formData.ipAddress.trim()) {
      setTestResult({ success: false, errorMessage: "Valid camera IP address or hostname is required." });
      setTesting(false);
      return;
    }
    if (formData.connectionType === "WIFI_HTTP" && !formData.streamUrl.trim()) {
      setTestResult({ success: false, errorMessage: "HTTP / MJPEG Stream URL is required." });
      setTesting(false);
      return;
    }

    try {
      const payload: any = {
        label: formData.label.trim(),
        ipAddress: formData.connectionType === "USB" ? (formData.ipAddress || "0") : formData.ipAddress.trim(),
        rtspPath: formData.rtspPath.trim() || "/live/ch0",
        streamUrl: formData.connectionType === "WIFI_HTTP" ? formData.streamUrl.trim() : (formData.connectionType === "USB" ? (formData.ipAddress || "0") : undefined),
        credentials: formData.credentials.trim() || undefined,
        laneId: formData.laneId,
      };

      const res = await safeFetch("/api/cameras", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const newCam = await res.json();
        const testRes = await safeFetch(`/api/cameras/${newCam.cameraId}/test-connection`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        });
        const testData = await testRes.json();
        setTestResult({
          success: Boolean(testData.success),
          latencyMs: testData.latencyMs,
          errorMessage: testData.errorMessage ? formatErrorMessage(testData.errorMessage) : undefined,
          previewImageBase64: testData.previewImageBase64,
          snapshotUrl: testData.snapshotUrl,
        });
        fetchCameras();
      } else {
        const err = await res.json();
        setTestResult({ success: false, errorMessage: formatErrorMessage(err.detail || err.message || "Validation Error") });
      }
    } catch (err: any) {
      setTestResult({ success: false, errorMessage: formatErrorMessage(err.message || "Failed to reach backend API") });
    } finally {
      setTesting(false);
    }
  };

  const handleConfirmDiscoveredLane = async (dev: DiscoveredDevice) => {
    try {
      await safeFetch("/api/discovery/confirm-lane", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          deviceId: dev.deviceId,
          laneId: dev.suggestedLane || "LANE-01",
          customLabel: `${dev.manufacturer || "IP"} Camera (${dev.ipAddress})`,
        }),
      });
      fetchCameras();
      fetchDiscovery();
    } catch (e) {
      console.warn("Confirm lane error:", e);
    }
  };

  const handleDeleteCamera = async (cameraId: string) => {
    if (!confirm(`Are you sure you want to decommission camera ${cameraId}?`)) return;
    try {
      await safeFetch(`/api/cameras/${cameraId}`, {
        method: "DELETE",
      });
      fetchCameras();
    } catch (e) {
      console.warn("Delete camera failed:", e);
    }
  };

  const openIgnoreClassesModal = (cam: CameraItem) => {
    setSelectedCameraForIgnore(cam);
    setCurrentIgnoredClasses(cam.ignoredClasses || []);
  };

  const handleSaveIgnoredClasses = async () => {
    if (!selectedCameraForIgnore) return;
    setSavingIgnore(true);
    try {
      const res = await safeFetch(`/api/cameras/${selectedCameraForIgnore.cameraId}/ignored-classes`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ignoredClasses: currentIgnoredClasses }),
      });
      if (res.ok) {
        await fetchCameras();
        setSelectedCameraForIgnore(null);
      } else {
        alert("Failed to update ignored classes.");
      }
    } catch (err) {
      console.error("Error saving ignored classes:", err);
    } finally {
      setSavingIgnore(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-[var(--bg-panel)] p-6 rounded-xl border border-[var(--border-hairline)]">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center gap-3">
            <Camera className="text-[#38BDF8]" /> Camera & Sensor Fleet Management
          </h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">
            Configure LAN RTSP, PoE, ONVIF, USB webcams, and wireless IoT devices with zero code changes.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => { fetchCameras(); fetchDiscovery(); }}
            className="px-3.5 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
          >
            <RefreshCw size={15} /> Refresh Fleet
          </button>
          <button
            onClick={() => { setShowAddModal(true); setTestResult(null); }}
            className="px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-sm font-semibold flex items-center gap-2 shadow-lg shadow-blue-900/30 transition-all"
          >
            <Plus size={16} /> Add / Connect Camera
          </button>
        </div>
      </div>

      {discovered.length > 0 && (
        <div className="bg-[#1A2634] border border-[#38BDF8]/40 p-5 rounded-xl">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-[#38BDF8] flex items-center gap-2 font-mono">
              <Radio size={16} className="animate-pulse" /> DISCOVERED NETWORK DEVICES ({discovered.length})
            </h3>
            <span className="text-xs text-[var(--text-secondary)]">1-Tap Lane Assignment Available</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {discovered.map((dev) => (
              <div key={dev.deviceId} className="bg-[var(--bg-canvas)] p-4 rounded-lg border border-[var(--border-hairline)] flex justify-between items-center">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#4FD1B3]"></span>
                    <span className="font-bold text-sm text-[var(--text-primary)] font-mono">{dev.ipAddress}</span>
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                    {dev.manufacturer || "ONVIF"} {dev.model || "CCTV Camera"}
                  </p>
                </div>
                <button
                  onClick={() => handleConfirmDiscoveredLane(dev)}
                  className="px-3 py-1.5 bg-[#4FD1B3]/20 hover:bg-[#4FD1B3]/30 text-[#4FD1B3] border border-[#4FD1B3]/40 rounded text-xs font-semibold font-mono flex items-center gap-1 transition-colors"
                >
                  Assign {dev.suggestedLane || "Lane"} <ChevronRight size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] p-4 rounded-xl flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
        <div className="flex items-center gap-6">
          <span className="text-[var(--text-secondary)] flex items-center gap-1.5">
            <Usb size={14} className="text-[#E8A33D]" /> USB SUBSYSTEM:
          </span>
          <span className="text-[var(--text-primary)]">
            Active Weight Scale: <b className="text-[#4FD1B3]">{usbStatus?.activeScalePort || "Not Connected"}</b>
          </span>
          <span className="text-[var(--text-primary)]">
            USB Video Devices: <b className="text-[#38BDF8]">{usbStatus?.videoDevicesCount !== undefined ? `${usbStatus.videoDevicesCount} Connected` : "None Detected"}</b>
          </span>
        </div>
        <button
          onClick={async () => {
            await safeFetch("/api/discovery/scan-now", { method: "POST" });
            fetchDiscovery();
          }}
          className="text-[#E8A33D] hover:underline flex items-center gap-1"
        >
          <RefreshCw size={12} /> Scan Hardware Ports
        </button>
      </div>

      <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl overflow-hidden shadow-xl">
        <div className="p-5 border-b border-[var(--border-hairline)] flex justify-between items-center">
          <h2 className="text-lg font-bold text-[var(--text-primary)]">Configured Cameras ({cameras.length})</h2>
          <span className="text-xs font-mono text-[#4FD1B3] bg-[#4FD1B3]/10 px-2.5 py-1 rounded border border-[#4FD1B3]/30">
            {cameras.filter((c) => c.status === "ONLINE").length} ONLINE / {cameras.length} TOTAL
          </span>
        </div>

        {cameras.length === 0 && !loading ? (
          <div className="p-12 text-center text-[var(--text-secondary)]">
            <Camera size={40} className="mx-auto mb-3 text-[#2C323D]" />
            <h4 className="text-base font-bold text-[var(--text-primary)]">No exit lanes configured</h4>
            <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-sm mx-auto">
              Add your first camera using the button above or confirm an auto-discovered LAN device.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-[var(--bg-canvas)] text-[var(--text-secondary)] text-xs font-mono border-b border-[var(--border-hairline)]">
                <tr>
                  <th className="p-4">STATUS</th>
                  <th className="p-4">CAMERA ID & LABEL</th>
                  <th className="p-4">ASSIGNED LANE</th>
                  <th className="p-4">SOURCE ENDPOINT</th>
                  <th className="p-4">STREAM DETAILS</th>
                  <th className="p-4">METHOD</th>
                  <th className="p-4">IGNORED CLASSES (CC.2.1)</th>
                  <th className="p-4 text-right">ACTIONS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
                {cameras.map((cam) => (
                  <tr key={cam.cameraId} className="hover:bg-[var(--bg-panel-raised)] transition-colors">
                    <td className="p-4">
                      <div className="flex items-center gap-2">
                        <span
                          className={`w-2.5 h-2.5 rounded-full ${
                            cam.status === "ONLINE"
                              ? "bg-[#4FD1B3] shadow-[0_0_8px_#4FD1B3]"
                              : cam.status === "PENDING_SETUP"
                              ? "bg-[#E8A33D]"
                              : "bg-[#E5484D]"
                          }`}
                        />
                        <span className="font-mono text-xs">{cam.status}</span>
                      </div>
                    </td>
                    <td className="p-4">
                      <div className="font-bold text-[var(--text-primary)]">{cam.label}</div>
                      <div className="text-xs font-mono text-[var(--text-secondary)]">{cam.cameraId}</div>
                    </td>
                    <td className="p-4 font-mono text-xs text-[#38BDF8]">
                      {cam.laneId || <span className="text-[#E8A33D]">UNASSIGNED</span>}
                    </td>
                    <td className="p-4 font-mono text-xs text-[var(--text-secondary)]">
                      {cam.streamUrl || `rtsp://${cam.ipAddress}:554${cam.rtspPath}`}
                    </td>
                    <td className="p-4 font-mono text-xs">
                      {cam.resolution || "1920x1080"} @ {cam.fps || 30} FPS
                    </td>
                    <td className="p-4">
                      <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-[var(--bg-panel-raised)] text-[var(--text-secondary)] border border-[var(--border-hairline)]">
                        {cam.pairingMethod}
                      </span>
                    </td>
                    <td className="p-4">
                      <button
                        onClick={() => openIgnoreClassesModal(cam)}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] border border-[var(--border-hairline)] text-[var(--text-secondary)] hover:text-[#38BDF8] transition-colors"
                        title="Configure Ignored Classes"
                      >
                        <Sliders size={12} className="text-[#38BDF8]" />
                        <span>{(cam.ignoredClasses || []).length} Filtered</span>
                      </button>
                    </td>
                    <td className="p-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => openIgnoreClassesModal(cam)}
                          className="p-1.5 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[#38BDF8] rounded border border-[var(--border-hairline)] transition-colors"
                          title="Configure Ignored Classes (CC.2.1)"
                        >
                          <Sliders size={14} />
                        </button>
                        <button
                          onClick={() => openGateLineModal(cam)}
                          className="p-1.5 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[#4FD1B3] rounded border border-[var(--border-hairline)] transition-colors"
                          title="Configure Gate / Tripwire Line (Section 13)"
                        >
                          <Maximize2 size={14} />
                        </button>
                        <button
                          onClick={async () => {
                            try {
                              const nonce = Date.now();
                              setPreviewModalNonce(nonce);
                              const res = await safeFetch(`/api/cameras/${cam.cameraId}/test-connection`, { method: "POST" });
                              const dat = await res.json();
                              setViewingPreview({
                                label: cam.label,
                                cameraId: cam.cameraId,
                                snapshotUrl: dat.previewImageBase64 || `/snapshots/preview_${cam.cameraId}.jpg?t=${nonce}`,
                                success: Boolean(dat.success),
                                latencyMs: dat.latencyMs,
                                errorMessage: dat.errorMessage,
                              });
                            } catch (e: any) {
                              alert(`Connection test error: ${e.message}`);
                            }
                          }}
                          className="p-1.5 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[#38BDF8] rounded border border-[var(--border-hairline)] transition-colors"
                          title="Test Live Stream & View Screenshot"
                        >
                          <Play size={14} />
                        </button>
                        <button
                          onClick={() => handleDeleteCamera(cam.cameraId)}
                          className="p-1.5 bg-[var(--bg-panel-raised)] hover:bg-[#451A1A] text-[var(--text-secondary)] hover:text-[#E5484D] rounded border border-[var(--border-hairline)] transition-colors"
                          title="Decommission Camera"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl max-w-xl w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                <Plus size={18} className="text-[#38BDF8]" /> Connect New Camera Device
              </h3>
              <button onClick={() => setShowAddModal(false)} className="text-[var(--text-secondary)] hover:text-white">
                ✕
              </button>
            </div>

            <div className="grid grid-cols-3 gap-2 bg-[var(--bg-canvas)] p-1 rounded-lg border border-[var(--border-hairline)] text-xs font-mono">
              <button
                onClick={() => setFormData({ ...formData, connectionType: "LAN_RTSP" })}
                className={`p-2 rounded font-medium transition-colors ${
                  formData.connectionType === "LAN_RTSP" ? "bg-[#2563EB] text-white" : "text-[var(--text-secondary)]"
                }`}
              >
                LAN / RTSP / ONVIF
              </button>
              <button
                onClick={() => setFormData({ ...formData, connectionType: "USB" })}
                className={`p-2 rounded font-medium transition-colors ${
                  formData.connectionType === "USB" ? "bg-[#2563EB] text-white" : "text-[var(--text-secondary)]"
                }`}
              >
                USB Camera (0/1)
              </button>
              <button
                onClick={() => setFormData({ ...formData, connectionType: "WIFI_HTTP" })}
                className={`p-2 rounded font-medium transition-colors ${
                  formData.connectionType === "WIFI_HTTP" ? "bg-[#2563EB] text-white" : "text-[var(--text-secondary)]"
                }`}
              >
                WiFi / Mobile HTTP
              </button>
            </div>

            <div className="space-y-3 text-sm">
              <div>
                <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">CAMERA LABEL</label>
                <input
                  type="text"
                  value={formData.label}
                  onChange={(e) => setFormData({ ...formData, label: e.target.value })}
                  placeholder="e.g. Exit Lane 1 — High Angle"
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] focus:border-[#38BDF8] outline-none"
                />
              </div>

              {formData.connectionType === "LAN_RTSP" && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">IP ADDRESS</label>
                    <input
                      type="text"
                      value={formData.ipAddress}
                      onChange={(e) => setFormData({ ...formData, ipAddress: e.target.value })}
                      placeholder="192.168.1.101"
                      className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] font-mono outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">RTSP STREAM PATH</label>
                    <input
                      type="text"
                      value={formData.rtspPath}
                      onChange={(e) => setFormData({ ...formData, rtspPath: e.target.value })}
                      placeholder="/live/ch0 or /h264Preview_01"
                      className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] font-mono outline-none"
                    />
                  </div>
                </div>
              )}

              {formData.connectionType === "WIFI_HTTP" && (
                <div>
                  <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">STREAM URL (MJPEG / HLS)</label>
                  <input
                    type="text"
                    value={formData.streamUrl}
                    onChange={(e) => setFormData({ ...formData, streamUrl: e.target.value })}
                    placeholder="http://192.168.1.50:8080/video"
                    className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] font-mono outline-none"
                  />
                </div>
              )}

              {formData.connectionType === "USB" && (
                <div>
                  <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">DEVICE INDEX</label>
                  <select
                    value={formData.ipAddress}
                    onChange={(e) => setFormData({ ...formData, ipAddress: e.target.value })}
                    className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] font-mono outline-none"
                  >
                    <option value="0">Camera Device 0 (Default Laptop/USB Cam)</option>
                    <option value="1">Camera Device 1 (External USB Capture Card)</option>
                    <option value="2">Camera Device 2</option>
                  </select>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">ASSIGN TO EXIT LANE</label>
                  <select
                    value={formData.laneId}
                    onChange={(e) => setFormData({ ...formData, laneId: e.target.value })}
                    className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] font-mono outline-none"
                  >
                    <option value="LANE-01">Lane 01 (Main Exit)</option>
                    <option value="LANE-02">Lane 02 (Secondary Exit)</option>
                    <option value="LANE-03">Lane 03 (Goods Dispatch)</option>
                    <option value="LANE-04">Lane 04 (Warehouse Loading)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">CREDENTIALS (OPTIONAL)</label>
                  <input
                    type="password"
                    value={formData.credentials}
                    onChange={(e) => setFormData({ ...formData, credentials: e.target.value })}
                    placeholder="admin:password"
                    className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] font-mono outline-none"
                  />
                </div>
              </div>
            </div>

            {testResult && (
              <div
                className={`p-3 rounded-lg border text-xs font-mono space-y-2.5 ${
                  testResult.success
                    ? "bg-[#4FD1B3]/10 border-[#4FD1B3]/40 text-[#4FD1B3]"
                    : "bg-[#E5484D]/10 border-[#E5484D]/40 text-[#E5484D]"
                }`}
              >
                {testResult.success ? (
                  <div className="flex items-center gap-2">
                    <CheckCircle size={15} /> Handshake Verified! Latency: {testResult.latencyMs}ms
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <AlertTriangle size={15} /> Error: {formatErrorMessage(testResult.errorMessage)}
                  </div>
                )}

                {(testResult.previewImageBase64 || testResult.snapshotUrl) && (
                  <div className="relative rounded-lg overflow-hidden border border-white/10 bg-black aspect-video flex items-center justify-center">
                    <img
                      src={testResult.previewImageBase64 || testResult.snapshotUrl}
                      alt="Live Camera Preview"
                      className="w-full h-full object-contain"
                    />
                    <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-emerald-600/90 text-white text-[10px] font-mono font-bold tracking-wider uppercase shadow">
                      LIVE PREVIEW SCREENSHOT
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="flex justify-between items-center pt-2 border-t border-[var(--border-hairline)]">
              <button
                onClick={handleTestConnection}
                disabled={testing}
                className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-lg text-sm font-medium flex items-center gap-2 transition-colors disabled:opacity-50"
              >
                <Play size={14} /> {testing ? "Verifying Stream..." : "Test Connection"}
              </button>
              <button
                onClick={() => { setShowAddModal(false); fetchCameras(); }}
                className="px-5 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-sm font-semibold shadow-lg shadow-blue-900/30 transition-all"
              >
                Save & Deploy Camera
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedCameraForIgnore && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <div>
                <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                  <Sliders size={18} className="text-[#38BDF8]" /> Ignored Detection Classes (CC.2.1)
                </h3>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5 font-mono">
                  Camera: {selectedCameraForIgnore.label} ({selectedCameraForIgnore.cameraId})
                </p>
              </div>
              <button
                onClick={() => setSelectedCameraForIgnore(null)}
                className="text-[var(--text-secondary)] hover:text-white"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-[var(--text-secondary)]">
              Select static background artifacts or non-carrier objects to suppress on this camera stream. Items selected will be ignored from AI person tracking and shrinkage verification.
            </p>

            <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
              {AVAILABLE_IGNORE_CLASSES.map((cls) => {
                const isChecked = currentIgnoredClasses.includes(cls.id);
                return (
                  <label
                    key={cls.id}
                    className={`flex items-start gap-3 p-3 rounded-lg border transition-colors cursor-pointer ${
                      isChecked
                        ? "bg-[#38BDF8]/10 border-[#38BDF8]/40 text-[var(--text-primary)]"
                        : "bg-[var(--bg-canvas)] border-[var(--border-hairline)] text-[var(--text-secondary)] hover:bg-[var(--bg-panel-raised)]"
                    }`}
                  >
                    <input
                      type="checkbox"
                      className="mt-1 rounded accent-[#38BDF8]"
                      checked={isChecked}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setCurrentIgnoredClasses([...currentIgnoredClasses, cls.id]);
                        } else {
                          setCurrentIgnoredClasses(currentIgnoredClasses.filter((c) => c !== cls.id));
                        }
                      }}
                    />
                    <div className="flex-1">
                      <div className="text-sm font-semibold text-[var(--text-primary)]">{cls.label}</div>
                      <div className="text-xs text-[var(--text-secondary)] mt-0.5">{cls.desc}</div>
                    </div>
                  </label>
                );
              })}
            </div>

            <div className="flex justify-between items-center pt-3 border-t border-[var(--border-hairline)]">
              <span className="text-xs font-mono text-[var(--text-secondary)]">
                {currentIgnoredClasses.length} class(es) filtered
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setSelectedCameraForIgnore(null)}
                  className="px-3.5 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-lg text-sm font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveIgnoredClasses}
                  disabled={savingIgnore}
                  className="px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-sm font-semibold transition-all disabled:opacity-50"
                >
                  {savingIgnore ? "Saving Filter..." : "Save Filter Config"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {viewingPreview && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl max-w-2xl w-full p-5 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <div>
                <h3 className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2 font-mono">
                  <Camera size={18} className="text-[#38BDF8]" />
                  Camera Live Feed — {viewingPreview.label} ({viewingPreview.cameraId})
                </h3>
                <p className="text-xs text-[var(--text-secondary)] font-mono mt-0.5">
                  Latency: {viewingPreview.latencyMs ? `${viewingPreview.latencyMs}ms` : "Live"} | Status:{" "}
                  <span className={viewingPreview.success ? "text-[#4FD1B3]" : "text-[#E5484D]"}>
                    {viewingPreview.success ? "ONLINE (VERIFIED)" : "CONNECTION_FAILED"}
                  </span>
                </p>
              </div>
              <button
                onClick={() => setViewingPreview(null)}
                className="text-[var(--text-secondary)] hover:text-white p-1"
              >
                ✕
              </button>
            </div>

            <div className="relative aspect-video bg-neutral-900 rounded-lg overflow-hidden border border-[var(--border-hairline)] flex items-center justify-center">
              {viewingPreview.success ? (
                <img
                  src={`/api/cameras/${viewingPreview.cameraId}/stream?raw=false&t=${previewModalNonce}`}
                  alt={viewingPreview.label}
                  className="w-full h-full object-contain"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = viewingPreview.snapshotUrl;
                  }}
                />
              ) : (
                <div className="flex flex-col items-center justify-center p-6 text-center space-y-2">
                  <AlertTriangle size={32} className="text-[#E5484D]" />
                  <div className="text-sm font-mono font-bold text-white">Stream Pull Failed</div>
                  <p className="text-xs text-neutral-400 max-w-sm font-mono">
                    {formatErrorMessage(viewingPreview.errorMessage || "Camera device unreachable or preempted.")}
                  </p>
                </div>
              )}
            </div>

            <div className="flex justify-end pt-2 border-t border-[var(--border-hairline)]">
              <button
                onClick={() => setViewingPreview(null)}
                className="px-4 py-1.5 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-xs font-mono border border-[var(--border-hairline)] transition-colors"
              >
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Gate / Tripwire Passage Line Configuration Modal */}
      {selectedCameraForGate && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl max-w-2xl w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <div>
                <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                  <Maximize2 size={18} className="text-[#4FD1B3]" /> Gate & Tripwire Suggestion: {selectedCameraForGate.label}
                </h3>
                <p className="text-xs text-[var(--text-secondary)] font-mono mt-0.5">
                  AI-suggested passage traversal threshold line for boundary crossing detection
                </p>
              </div>
              <button onClick={() => setSelectedCameraForGate(null)} className="text-[var(--text-secondary)] hover:text-white p-1">
                ✕
              </button>
            </div>

            <div className="relative aspect-video bg-neutral-900 rounded-lg overflow-hidden border border-[var(--border-hairline)] flex items-center justify-center select-none">
              <img
                src={`/snapshots/preview_${selectedCameraForGate.cameraId}.jpg?t=${previewModalNonce}`}
                alt={selectedCameraForGate.label}
                className="w-full h-full object-cover"
                onError={(e: any) => {
                  e.currentTarget.src = "/snapshots/preview_CAM-01.jpg";
                }}
              />
              {/* Dynamic SVG Tripwire Line Overlay */}
              <svg className="absolute inset-0 w-full h-full pointer-events-none">
                {suggestedGateLine.length >= 2 && (
                  <>
                    <line
                      x1={`${suggestedGateLine[0].x * 100}%`}
                      y1={`${suggestedGateLine[0].y * 100}%`}
                      x2={`${suggestedGateLine[1].x * 100}%`}
                      y2={`${suggestedGateLine[1].y * 100}%`}
                      stroke="#4FD1B3"
                      strokeWidth="3"
                      strokeDasharray="6 3"
                    />
                    <circle
                      cx={`${suggestedGateLine[0].x * 100}%`}
                      cy={`${suggestedGateLine[0].y * 100}%`}
                      r="6"
                      fill="#38BDF8"
                    />
                    <circle
                      cx={`${suggestedGateLine[1].x * 100}%`}
                      cy={`${suggestedGateLine[1].y * 100}%`}
                      r="6"
                      fill="#38BDF8"
                    />
                    <text
                      x={`${((suggestedGateLine[0].x + suggestedGateLine[1].x) / 2) * 100}%`}
                      y={`${((suggestedGateLine[0].y + suggestedGateLine[1].y) / 2) * 100 - 2}%`}
                      fill="#4FD1B3"
                      fontSize="12"
                      fontWeight="bold"
                      fontFamily="monospace"
                      textAnchor="middle"
                    >
                      PASSAGE TRIPWIRE
                    </text>
                  </>
                )}
              </svg>
            </div>

            <div className="bg-[var(--bg-canvas)] p-3 rounded-lg border border-[var(--border-hairline)] text-xs font-mono text-[var(--text-secondary)] flex justify-between items-center">
              <div>
                <span className="text-white font-bold">Tripwire Coordinates: </span>
                {suggestedGateLine.map((p, i) => `P${i + 1}: (${p.x.toFixed(2)}, ${p.y.toFixed(2)})`).join("  →  ")}
              </div>
              <div className="text-[11px] text-[var(--text-muted)]">{gateExplanation}</div>
            </div>

            <div className="flex flex-wrap justify-between items-center gap-2 pt-2 border-t border-[var(--border-hairline)] font-mono text-xs">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() =>
                    setSuggestedGateLine((prev) =>
                      prev.map((p) => ({ ...p, y: Math.max(0.1, Number((p.y - 0.05).toFixed(2))) }))
                    )
                  }
                  className="px-2.5 py-1.5 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-white rounded border border-[var(--border-hairline)] flex items-center gap-1"
                >
                  <MoveUp size={13} /> NUDGE UP
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setSuggestedGateLine((prev) =>
                      prev.map((p) => ({ ...p, y: Math.min(0.95, Number((p.y + 0.05).toFixed(2))) }))
                    )
                  }
                  className="px-2.5 py-1.5 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-white rounded border border-[var(--border-hairline)] flex items-center gap-1"
                >
                  <MoveDown size={13} /> NUDGE DOWN
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setSuggestedGateLine([
                      { x: 0.12, y: 0.82 },
                      { x: 0.88, y: 0.82 },
                    ]);
                  }}
                  className="px-2.5 py-1.5 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-secondary)] rounded border border-[var(--border-hairline)]"
                >
                  RESET
                </button>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedCameraForGate(null)}
                  className="px-3.5 py-1.5 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => handleSaveGateLine(suggestedGateLine)}
                  disabled={savingGateLine}
                  className="px-4 py-1.5 bg-[#10B981] hover:bg-[#059669] text-white font-bold rounded flex items-center gap-1.5 shadow-md shadow-emerald-900/30 disabled:opacity-50"
                >
                  <Check size={14} /> {savingGateLine ? "Saving..." : "ACCEPT (Save Line)"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
