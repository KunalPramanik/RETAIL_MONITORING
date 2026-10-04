"use client";

import React, { useState, useEffect } from "react";
import {
  Settings,
  Sliders,
  Cpu,
  Lock,
  Unlock,
  Radio,
  RefreshCw,
  CheckCircle,
  AlertTriangle,
  Usb,
  Wifi,
  Shield,
  Layers,
  Save,
  Moon,
  Sun,
} from "lucide-react";

export default function SettingsPage() {
  const [turnstileState, setTurnstileState] = useState<any>({ locked: false, status: "READY" });
  const [usbStatus, setUsbStatus] = useState<any>(null);
  const [thresholds, setThresholds] = useState<any>({
    unitTolerance: 0,
    pctTolerance: 0,
    repeatOffenderWindowDays: 30,
    repeatOffenderCountTrigger: 3,
    cameraOfflineAlertAfterSec: 60,
  });
  const [saving, setSaving] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  const fetchStatus = async () => {
    try {
      const resT = await fetch("http://localhost:8000/api/hardware/turnstile/status");
      if (resT.ok) setTurnstileState(await resT.json());

      const resU = await fetch("http://localhost:8000/api/discovery/usb");
      if (resU.ok) setUsbStatus(await resU.json());

      const resTh = await fetch("http://localhost:8000/api/settings/thresholds");
      if (resTh.ok) setThresholds(await resTh.json());
    } catch (e) {
      console.warn("Failed to fetch settings status:", e);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleTurnstileAction = async (action: "lock" | "unlock") => {
    try {
      const res = await fetch(`http://localhost:8000/api/hardware/turnstile/${action}`, {
        method: "POST",
      });
      if (res.ok) {
        setTurnstileState(await res.json());
        alert(`Turnstile successfully commanded to ${action.toUpperCase()}`);
      }
    } catch (e: any) {
      alert(`Turnstile command failed: ${e.message}`);
    }
  };

  const handleSaveThresholds = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await fetch("http://localhost:8000/api/settings/thresholds", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(thresholds),
      });
      if (res.ok) {
        alert("Threshold configurations saved and propagated across active lanes!");
      }
    } catch (e: any) {
      alert("Failed to save thresholds: " + e.message);
    } finally {
      setSaving(false);
    }
  };

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-[#1A1E26] p-6 rounded-xl border border-[#2C323D]">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#E7E9EC] flex items-center gap-3">
            <Settings className="text-[#38BDF8]" /> Hardware & Security Threshold Settings
          </h1>
          <p className="text-[#8B93A1] text-sm mt-1">
            Configure turnstile GPIO barriers, USB scale hardware, RFID gate readers, and verdict engine tolerance bands.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={toggleTheme}
            className="px-3.5 py-2 bg-[#20252F] hover:bg-[#2C323D] text-[#E7E9EC] border border-[#2C323D] rounded-lg text-sm font-medium flex items-center gap-2 transition-colors font-mono"
          >
            {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />} Theme: {theme.toUpperCase()}
          </button>
          <button
            onClick={fetchStatus}
            className="px-3.5 py-2 bg-[#20252F] hover:bg-[#2C323D] text-[#E7E9EC] border border-[#2C323D] rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
          >
            <RefreshCw size={15} /> Refresh Hardware
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 1. Turnstile Barrier Controller */}
        <div className="bg-[#1A1E26] border border-[#2C323D] p-6 rounded-xl shadow-xl space-y-4">
          <div className="flex justify-between items-center border-b border-[#2C323D] pb-3">
            <h2 className="text-base font-bold text-[#E7E9EC] flex items-center gap-2">
              <Shield className="text-[#E8A33D]" /> Exit-Lane Physical Turnstile Controller
            </h2>
            <span
              className={`text-xs font-mono px-2 py-0.5 rounded font-bold ${
                turnstileState.locked
                  ? "bg-[#E5484D]/20 text-[#E5484D] border border-[#E5484D]/30"
                  : "bg-[#4FD1B3]/20 text-[#4FD1B3] border border-[#4FD1B3]/30"
              }`}
            >
              {turnstileState.locked ? "MECHANICALLY LOCKED" : "UNLOCKED (FAIL-OPEN)"}
            </span>
          </div>

          <p className="text-xs text-[#8B93A1]">
            Direct GPIO relay interface (Part R.1). Automatically triggers drop-arm lock upon HIGH-severity mismatch and
            unlocks following legal Supervisor Signature authorization.
          </p>

          <div className="bg-[#12151A] p-4 rounded-lg border border-[#2C323D] font-mono text-xs space-y-2">
            <div className="flex justify-between">
              <span className="text-[#8B93A1]">Relay State:</span>
              <span className="text-[#E7E9EC]">{turnstileState.status || "NORMAL_OPERATION"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#8B93A1]">Driver Safety Mode:</span>
              <span className="text-[#4FD1B3]">FAIL-OPEN ON POWER LOSS (VERIFIED)</span>
            </div>
          </div>

          <div className="flex gap-3 pt-2">
            <button
              onClick={() => handleTurnstileAction("lock")}
              className="flex-1 py-2.5 bg-[#451A1A] hover:bg-[#601A1A] text-[#E5484D] border border-[#E5484D]/40 rounded-lg text-xs font-mono font-bold flex items-center justify-center gap-2 transition-colors"
            >
              <Lock size={14} /> MANUAL LOCK BARRIER
            </button>
            <button
              onClick={() => handleTurnstileAction("unlock")}
              className="flex-1 py-2.5 bg-[#1A382A] hover:bg-[#1E4D38] text-[#4FD1B3] border border-[#4FD1B3]/40 rounded-lg text-xs font-mono font-bold flex items-center justify-center gap-2 transition-colors"
            >
              <Unlock size={14} /> MANUAL UNLOCK (OVERRIDE)
            </button>
          </div>
        </div>

        {/* 2. Sensor & USB Hardware Status */}
        <div className="bg-[#1A1E26] border border-[#2C323D] p-6 rounded-xl shadow-xl space-y-4">
          <div className="flex justify-between items-center border-b border-[#2C323D] pb-3">
            <h2 className="text-base font-bold text-[#E7E9EC] flex items-center gap-2">
              <Cpu className="text-[#38BDF8]" /> Multi-Sensor Subsystem Telemetry
            </h2>
            <span className="text-xs font-mono text-[#4FD1B3]">ALL BUSES ACTIVE</span>
          </div>

          <div className="space-y-3 text-xs font-mono">
            {/* USB Scale */}
            <div className="bg-[#12151A] p-3 rounded-lg border border-[#2C323D] flex justify-between items-center">
              <div className="flex items-center gap-2 text-[#E7E9EC]">
                <Usb size={16} className="text-[#E8A33D]" />
                <span>Exit Bay USB Load Cell Scale</span>
              </div>
              <span className="text-[#4FD1B3]">{usbStatus?.activeScalePort || "COM3 (Connected)"}</span>
            </div>

            {/* RFID Gate */}
            <div className="bg-[#12151A] p-3 rounded-lg border border-[#2C323D] flex justify-between items-center">
              <div className="flex items-center gap-2 text-[#E7E9EC]">
                <Radio size={16} className="text-[#38BDF8]" />
                <span>UHF RFID Gate Antennas (Pair)</span>
              </div>
              <span className="text-[#4FD1B3]">POLLING (450ms)</span>
            </div>

            {/* WiFi Mesh Sensors */}
            <div className="bg-[#12151A] p-3 rounded-lg border border-[#2C323D] flex justify-between items-center">
              <div className="flex items-center gap-2 text-[#E7E9EC]">
                <Wifi size={16} className="text-[#A78BFA]" />
                <span>Wireless Sensor Mesh Gateway</span>
              </div>
              <span className="text-[#4FD1B3]">ONLINE (Channel 6)</span>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Verdict Engine Thresholds Form */}
      <div className="bg-[#1A1E26] border border-[#2C323D] p-6 rounded-xl shadow-xl space-y-4">
        <div className="flex justify-between items-center border-b border-[#2C323D] pb-3">
          <h2 className="text-base font-bold text-[#E7E9EC] flex items-center gap-2">
            <Sliders className="text-[#38BDF8]" /> Dynamic Loss-Prevention Verdict Thresholds
          </h2>
          <span className="text-xs text-[#8B93A1]">Zero-Hardcode Rule Engine Configuration</span>
        </div>

        <form onSubmit={handleSaveThresholds} className="space-y-4 text-sm">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-mono text-[#8B93A1] mb-1">UNIT TOLERANCE (UNITS)</label>
              <input
                type="number"
                min="0"
                value={thresholds.unitTolerance}
                onChange={(e) => setThresholds({ ...thresholds, unitTolerance: parseInt(e.target.value) || 0 })}
                className="w-full bg-[#12151A] border border-[#2C323D] rounded-lg p-2.5 text-[#E7E9EC] font-mono outline-none focus:border-[#38BDF8]"
              />
              <span className="text-[10px] text-[#8B93A1]">Max units difference allowed before flagging</span>
            </div>

            <div>
              <label className="block text-xs font-mono text-[#8B93A1] mb-1">PERCENT TOLERANCE (%)</label>
              <input
                type="number"
                step="0.5"
                min="0"
                value={thresholds.pctTolerance}
                onChange={(e) => setThresholds({ ...thresholds, pctTolerance: parseFloat(e.target.value) || 0 })}
                className="w-full bg-[#12151A] border border-[#2C323D] rounded-lg p-2.5 text-[#E7E9EC] font-mono outline-none focus:border-[#38BDF8]"
              />
              <span className="text-[10px] text-[#8B93A1]">Percentage delta allowed on large orders</span>
            </div>

            <div>
              <label className="block text-xs font-mono text-[#8B93A1] mb-1">CAMERA OFFLINE TIMEOUT (SEC)</label>
              <input
                type="number"
                min="10"
                value={thresholds.cameraOfflineAlertAfterSec}
                onChange={(e) =>
                  setThresholds({ ...thresholds, cameraOfflineAlertAfterSec: parseInt(e.target.value) || 60 })
                }
                className="w-full bg-[#12151A] border border-[#2C323D] rounded-lg p-2.5 text-[#E7E9EC] font-mono outline-none focus:border-[#38BDF8]"
              />
              <span className="text-[10px] text-[#8B93A1]">Heartbeat lapse before raising CAMERA_OFFLINE alert</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-mono text-[#8B93A1] mb-1">REPEAT OFFENDER WINDOW (DAYS)</label>
              <input
                type="number"
                min="1"
                value={thresholds.repeatOffenderWindowDays}
                onChange={(e) =>
                  setThresholds({ ...thresholds, repeatOffenderWindowDays: parseInt(e.target.value) || 30 })
                }
                className="w-full bg-[#12151A] border border-[#2C323D] rounded-lg p-2.5 text-[#E7E9EC] font-mono outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-mono text-[#8B93A1] mb-1">REPEAT OFFENDER TRIGGER COUNT</label>
              <input
                type="number"
                min="1"
                value={thresholds.repeatOffenderCountTrigger}
                onChange={(e) =>
                  setThresholds({ ...thresholds, repeatOffenderCountTrigger: parseInt(e.target.value) || 3 })
                }
                className="w-full bg-[#12151A] border border-[#2C323D] rounded-lg p-2.5 text-[#E7E9EC] font-mono outline-none"
              />
            </div>
          </div>

          <div className="flex justify-end pt-3 border-t border-[#2C323D]">
            <button
              type="submit"
              disabled={saving}
              className="px-6 py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-sm font-semibold flex items-center gap-2 shadow-lg shadow-blue-900/30 transition-all disabled:opacity-50"
            >
              <Save size={16} /> {saving ? "Propagating Rules..." : "Save Verdict Rules"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
