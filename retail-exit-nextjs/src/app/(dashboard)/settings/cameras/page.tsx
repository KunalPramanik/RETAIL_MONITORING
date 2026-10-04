"use client";

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
}

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
      const res = await fetch("http://localhost:8000/api/cameras");
      if (res.ok) {
        setCameras(await res.json());
      }
    } catch (e) {
      console.warn("Failed to fetch cameras:", e);
    }
  };

  const fetchDiscovery = async () => {
    try {
      const resDev = await fetch("http://localhost:8000/api/discovery/devices");
      if (resDev.ok) setDiscovered(await resDev.json());
      const resUsb = await fetch("http://localhost:8000/api/discovery/usb");
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
    try {
      const payload: any = {
        label: formData.label || "Test Device",
        ipAddress: formData.connectionType === "USB" ? "0" : formData.ipAddress,
        rtspPath: formData.rtspPath,
        streamUrl: formData.connectionType === "WIFI_HTTP" ? formData.streamUrl : undefined,
        credentials: formData.credentials || undefined,
        laneId: formData.laneId,
      };

      const res = await fetch("http://localhost:8000/api/cameras", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const newCam = await res.json();
        const testRes = await fetch(`http://localhost:8000/api/cameras/${newCam.cameraId}/test-connection`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        });
        setTestResult(await testRes.json());
        fetchCameras();
      } else {
        const err = await res.json();
        setTestResult({ success: false, errorMessage: err.detail || "Validation Error" });
      }
    } catch (err: any) {
      setTestResult({ success: false, errorMessage: err.message || "Failed to reach backend API" });
    } finally {
      setTesting(false);
    }
  };

  const handleConfirmDiscoveredLane = async (dev: DiscoveredDevice) => {
    try {
      await fetch("http://localhost:8000/api/discovery/confirm-lane", {
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
      await fetch(`http://localhost:8000/api/cameras/${cameraId}`, {
        method: "DELETE",
      });
      fetchCameras();
    } catch (e) {
      console.warn("Delete camera failed:", e);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-[#1A1E26] p-6 rounded-xl border border-[#2C323D]">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#E7E9EC] flex items-center gap-3">
            <Camera className="text-[#38BDF8]" /> Camera & Sensor Fleet Management
          </h1>
          <p className="text-[#8B93A1] text-sm mt-1">
            Configure LAN RTSP, PoE, ONVIF, USB webcams, and wireless IoT devices with zero code changes.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => { fetchCameras(); fetchDiscovery(); }}
            className="px-3.5 py-2 bg-[#20252F] hover:bg-[#2C323D] text-[#E7E9EC] border border-[#2C323D] rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
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
            <span className="text-xs text-[#8B93A1]">1-Tap Lane Assignment Available</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {discovered.map((dev) => (
              <div key={dev.deviceId} className="bg-[#12151A] p-4 rounded-lg border border-[#2C323D] flex justify-between items-center">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#4FD1B3]"></span>
                    <span className="font-bold text-sm text-[#E7E9EC] font-mono">{dev.ipAddress}</span>
                  </div>
                  <p className="text-xs text-[#8B93A1] mt-0.5">
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

      <div className="bg-[#1A1E26] border border-[#2C323D] p-4 rounded-xl flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
        <div className="flex items-center gap-6">
          <span className="text-[#8B93A1] flex items-center gap-1.5">
            <Usb size={14} className="text-[#E8A33D]" /> USB SUBSYSTEM:
          </span>
          <span className="text-[#E7E9EC]">
            Active Weight Scale: <b className="text-[#4FD1B3]">{usbStatus?.activeScalePort || "COM3 (Auto-Detected)"}</b>
          </span>
          <span className="text-[#E7E9EC]">
            USB Video Devices: <b className="text-[#38BDF8]">{usbStatus?.videoDevicesCount || "1 Connected"}</b>
          </span>
        </div>
        <button
          onClick={async () => {
            await fetch("http://localhost:8000/api/discovery/scan-now", { method: "POST" });
            fetchDiscovery();
          }}
          className="text-[#E8A33D] hover:underline flex items-center gap-1"
        >
          <RefreshCw size={12} /> Scan Hardware Ports
        </button>
      </div>

      <div className="bg-[#1A1E26] border border-[#2C323D] rounded-xl overflow-hidden shadow-xl">
        <div className="p-5 border-b border-[#2C323D] flex justify-between items-center">
          <h2 className="text-lg font-bold text-[#E7E9EC]">Configured Cameras ({cameras.length})</h2>
          <span className="text-xs font-mono text-[#4FD1B3] bg-[#4FD1B3]/10 px-2.5 py-1 rounded border border-[#4FD1B3]/30">
            {cameras.filter((c) => c.status === "ONLINE").length} ONLINE / {cameras.length} TOTAL
          </span>
        </div>

        {cameras.length === 0 && !loading ? (
          <div className="p-12 text-center text-[#8B93A1]">
            <Camera size={40} className="mx-auto mb-3 text-[#2C323D]" />
            <h4 className="text-base font-bold text-[#E7E9EC]">No exit lanes configured</h4>
            <p className="text-xs text-[#8B93A1] mt-1 max-w-sm mx-auto">
              Add your first camera using the button above or confirm an auto-discovered LAN device.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-[#12151A] text-[#8B93A1] text-xs font-mono border-b border-[#2C323D]">
                <tr>
                  <th className="p-4">STATUS</th>
                  <th className="p-4">CAMERA ID & LABEL</th>
                  <th className="p-4">ASSIGNED LANE</th>
                  <th className="p-4">SOURCE ENDPOINT</th>
                  <th className="p-4">STREAM DETAILS</th>
                  <th className="p-4">METHOD</th>
                  <th className="p-4 text-right">ACTIONS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#2C323D] text-[#E7E9EC]">
                {cameras.map((cam) => (
                  <tr key={cam.cameraId} className="hover:bg-[#20252F] transition-colors">
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
                      <div className="font-bold text-[#E7E9EC]">{cam.label}</div>
                      <div className="text-xs font-mono text-[#8B93A1]">{cam.cameraId}</div>
                    </td>
                    <td className="p-4 font-mono text-xs text-[#38BDF8]">
                      {cam.laneId || <span className="text-[#E8A33D]">UNASSIGNED</span>}
                    </td>
                    <td className="p-4 font-mono text-xs text-[#8B93A1]">
                      {cam.streamUrl || `rtsp://${cam.ipAddress}:554${cam.rtspPath}`}
                    </td>
                    <td className="p-4 font-mono text-xs">
                      {cam.resolution || "1920x1080"} @ {cam.fps || 30} FPS
                    </td>
                    <td className="p-4">
                      <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-[#20252F] text-[#8B93A1] border border-[#2C323D]">
                        {cam.pairingMethod}
                      </span>
                    </td>
                    <td className="p-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={async () => {
                            const res = await fetch(`http://localhost:8000/api/cameras/${cam.cameraId}/test-connection`, { method: "POST" });
                            const dat = await res.json();
                            alert(dat.success ? "Stream handshake SUCCESSFUL!" : `Failed: ${dat.errorMessage}`);
                          }}
                          className="p-1.5 bg-[#20252F] hover:bg-[#2C323D] text-[#38BDF8] rounded border border-[#2C323D] transition-colors"
                          title="Test RTSP Pull"
                        >
                          <Play size={14} />
                        </button>
                        <button
                          onClick={() => handleDeleteCamera(cam.cameraId)}
                          className="p-1.5 bg-[#20252F] hover:bg-[#451A1A] text-[#8B93A1] hover:text-[#E5484D] rounded border border-[#2C323D] transition-colors"
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
          <div className="bg-[#1A1E26] border border-[#2C323D] rounded-xl max-w-xl w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[#2C323D] pb-3">
              <h3 className="text-lg font-bold text-[#E7E9EC] flex items-center gap-2">
                <Plus size={18} className="text-[#38BDF8]" /> Connect New Camera Device
              </h3>
              <button onClick={() => setShowAddModal(false)} className="text-[#8B93A1] hover:text-white">
                ✕
              </button>
            </div>

            <div className="grid grid-cols-3 gap-2 bg-[#12151A] p-1 rounded-lg border border-[#2C323D] text-xs font-mono">
              <button
                onClick={() => setFormData({ ...formData, connectionType: "LAN_RTSP" })}
                className={`p-2 rounded font-medium transition-colors ${
                  formData.connectionType === "LAN_RTSP" ? "bg-[#2563EB] text-white" : "text-[#8B93A1]"
                }`}
              >
                LAN / RTSP / ONVIF
              </button>
              <button
                onClick={() => setFormData({ ...formData, connectionType: "USB" })}
                className={`p-2 rounded font-medium transition-colors ${
                  formData.connectionType === "USB" ? "bg-[#2563EB] text-white" : "text-[#8B93A1]"
                }`}
              >
                USB Camera (0/1)
              </button>
              <button
                onClick={() => setFormData({ ...formData, connectionType: "WIFI_HTTP" })}
                className={`p-2 rounded font-medium transition-colors ${
                  formData.connectionType === "WIFI_HTTP" ? "bg-[#2563EB] text-white" : "text-[#8B93A1]"
                }`}
              >
                WiFi / Mobile HTTP
              </button>
            </div>

            <div className="space-y-3 text-sm">
              <div>
                <label className="block text-xs font-mono text-[#8B93A1] mb-1">CAMERA LABEL</label>
                <input
                  type="text"
                  value={formData.label}
                  onChange={(e) => setFormData({ ...formData, label: e.target.value })}
                  placeholder="e.g. Exit Lane 1 — High Angle"
                  className="w-full bg-[#12151A] border border-[#2C323D] rounded-lg p-2.5 text-[#E7E9EC] focus:border-[#38BDF8] outline-none"
                />
              </div>

              {formData.connectionType === "LAN_RTSP" && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-mono text-[#8B93A1] mb-1">IP ADDRESS</label>
                    <input
                      type="text"
                      value={formData.ipAddress}
                      onChange={(e) => setFormData({ ...formData, ipAddress: e.target.value })}
                      placeholder="192.168.1.101"
                      className="w-full bg-[#12151A] border border-[#2C323D] rounded-lg p-2.5 text-[#E7E9EC] font-mono outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-mono text-[#8B93A1] mb-1">RTSP STREAM PATH</label>
                    <input
                      type="text"
                      value={formData.rtspPath}
                      onChange={(e) => setFormData({ ...formData, rtspPath: e.target.value })}
                      placeholder="/live/ch0 or /h264Preview_01"
                      className="w-full bg-[#12151A] border border-[#2C323D] rounded-lg p-2.5 text-[#E7E9EC] font-mono outline-none"
                    />
                  </div>
                </div>
              )}

              {formData.connectionType === "WIFI_HTTP" && (
                <div>
                  <label className="block text-xs font-mono text-[#8B93A1] mb-1">STREAM URL (MJPEG / HLS)</label>
                  <input
                    type="text"
                    value={formData.streamUrl}
                    onChange={(e) => setFormData({ ...formData, streamUrl: e.target.value })}
                    placeholder="http://192.168.1.50:8080/video"
                    className="w-full bg-[#12151A] border border-[#2C323D] rounded-lg p-2.5 text-[#E7E9EC] font-mono outline-none"
                  />
                </div>
              )}

              {formData.connectionType === "USB" && (
                <div>
                  <label className="block text-xs font-mono text-[#8B93A1] mb-1">DEVICE INDEX</label>
                  <select
                    value={formData.ipAddress}
                    onChange={(e) => setFormData({ ...formData, ipAddress: e.target.value })}
                    className="w-full bg-[#12151A] border border-[#2C323D] rounded-lg p-2.5 text-[#E7E9EC] font-mono outline-none"
                  >
                    <option value="0">Camera Device 0 (Default Laptop/USB Cam)</option>
                    <option value="1">Camera Device 1 (External USB Capture Card)</option>
                    <option value="2">Camera Device 2</option>
                  </select>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-mono text-[#8B93A1] mb-1">ASSIGN TO EXIT LANE</label>
                  <select
                    value={formData.laneId}
                    onChange={(e) => setFormData({ ...formData, laneId: e.target.value })}
                    className="w-full bg-[#12151A] border border-[#2C323D] rounded-lg p-2.5 text-[#E7E9EC] font-mono outline-none"
                  >
                    <option value="LANE-01">Lane 01 (Main Exit)</option>
                    <option value="LANE-02">Lane 02 (Secondary Exit)</option>
                    <option value="LANE-03">Lane 03 (Goods Dispatch)</option>
                    <option value="LANE-04">Lane 04 (Warehouse Loading)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-mono text-[#8B93A1] mb-1">CREDENTIALS (OPTIONAL)</label>
                  <input
                    type="password"
                    value={formData.credentials}
                    onChange={(e) => setFormData({ ...formData, credentials: e.target.value })}
                    placeholder="admin:password"
                    className="w-full bg-[#12151A] border border-[#2C323D] rounded-lg p-2.5 text-[#E7E9EC] font-mono outline-none"
                  />
                </div>
              </div>
            </div>

            {testResult && (
              <div
                className={`p-3 rounded-lg border text-xs font-mono ${
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
                    <AlertTriangle size={15} /> Error: {testResult.errorMessage}
                  </div>
                )}
              </div>
            )}

            <div className="flex justify-between items-center pt-2 border-t border-[#2C323D]">
              <button
                onClick={handleTestConnection}
                disabled={testing}
                className="px-4 py-2 bg-[#20252F] hover:bg-[#2C323D] text-[#E7E9EC] border border-[#2C323D] rounded-lg text-sm font-medium flex items-center gap-2 transition-colors disabled:opacity-50"
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
    </div>
  );
}
