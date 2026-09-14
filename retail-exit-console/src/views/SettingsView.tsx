import React, { useState, useEffect } from 'react';
import { useAppData } from '../context/AppDataContext';
import { useTheme } from '../context/ThemeContext';
import type { SensorLane } from '../types';
import { CameraManagementPanel } from '../components/cameras/CameraManagementPanel';
import { StaticImageLogTable } from '../components/cameras/StaticImageLogTable';
import { UsbHardwareManager } from '../components/hardware/UsbHardwareManager';
import { Settings, Sliders, Volume2, ShieldAlert, Radio, Sun, Moon, Check, Clock, Image as ImageIcon } from 'lucide-react';

export const SettingsView: React.FC = () => {
  const { settings, updateSettings, resetDatabase, testAlarmSound, lanes, staticImages, refreshStaticImages } = useAppData();
  const { theme, setTheme } = useTheme();
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  useEffect(() => {
    refreshStaticImages();
  }, [refreshStaticImages]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    await updateSettings(settings);
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 2200);
  };

  return (
    <div className="p-4 space-y-4 max-w-5xl mx-auto">
      {/* Header */}
      <div className="p-4 bg-panel border border-hairline rounded-sm space-y-1">
        <div className="flex items-center justify-between">
          <h1 className="text-base-tech font-semibold text-text-pri flex items-center gap-2">
            <Settings className="w-5 h-5 text-amber" />
            System Calibration, Camera Fleet & Operational Threshold Settings
          </h1>

          {savedSuccess && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm bg-teal-950/20 text-status-ok border border-status-ok/30 font-mono text-xs-tech font-bold animate-in fade-in">
              <Check className="w-3.5 h-3.5" />
              Configuration Deployed to Edge Nodes
            </span>
          )}
        </div>
        <p className="text-xs-tech text-text-sec">
          Tune severity tolerance brackets, repeat-offender thresholds, camera offline timeouts, audio alerts, and manage edge surveillance cameras.
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-4">
        {/* Section 1: Visual Theme & Appearance Tokens */}
        <div className="p-4 bg-panel border border-hairline rounded-sm space-y-3">
          <div className="flex items-center justify-between border-b border-hairline pb-2">
            <h2 className="text-xs-tech font-bold text-text-pri uppercase tracking-wider flex items-center gap-2">
              <Sliders className="w-4 h-4 text-amber" />
              1. Visual Appearance & Control Room Theme Mode
            </h2>
            <span className="font-mono text-xs-tech text-text-sec">Active: {theme.toUpperCase()}</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
            {/* Dark Mode Card */}
            <div
              onClick={() => setTheme('dark')}
              className={`p-4 rounded-sm border cursor-pointer transition-all flex items-start gap-3 ${
                theme === 'dark'
                  ? 'bg-panel-raised border-amber ring-1 ring-amber/50'
                  : 'bg-canvas border-hairline hover:bg-panel-raised/50'
              }`}
            >
              <div className="p-2 rounded-sm bg-black text-amber border border-hairline">
                <Moon className="w-5 h-5" />
              </div>
              <div className="space-y-1">
                <div className="text-xs-tech font-bold text-text-pri flex items-center gap-2">
                  Dark Mode (Control Room Standard)
                  {theme === 'dark' && <span className="text-amber text-[11px] font-mono font-bold">[ACTIVE]</span>}
                </div>
                <p className="text-[11px] text-text-sec">
                  Graphite background (#12151A) engineered for dim surveillance control rooms. Eliminates screen glare.
                </p>
              </div>
            </div>

            {/* Light Mode Card */}
            <div
              onClick={() => setTheme('light')}
              className={`p-4 rounded-sm border cursor-pointer transition-all flex items-start gap-3 ${
                theme === 'light'
                  ? 'bg-panel-raised border-amber ring-1 ring-amber/50'
                  : 'bg-canvas border-hairline hover:bg-panel-raised/50'
              }`}
            >
              <div className="p-2 rounded-sm bg-white text-amber border border-hairline">
                <Sun className="w-5 h-5" />
              </div>
              <div className="space-y-1">
                <div className="text-xs-tech font-bold text-text-pri flex items-center gap-2">
                  Light Mode (Floor Supervisor Tablet)
                  {theme === 'light' && <span className="text-amber text-[11px] font-mono font-bold">[ACTIVE]</span>}
                </div>
                <p className="text-[11px] text-text-sec">
                  Warm light grey canvas (#F1F0EC) with darkened AA contrast tokens for bright exit lanes.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Section 2: Severity Anomaly Thresholds & Camera Offline Trigger */}
        <div className="p-4 bg-panel border border-hairline rounded-sm space-y-4">
          <div className="flex items-center justify-between border-b border-hairline pb-2">
            <h2 className="text-xs-tech font-bold text-text-pri uppercase tracking-wider flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-amber" />
              2. Loss Prevention Anomaly & Severity Thresholds
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {/* Low Severity */}
            <div className="p-3 bg-panel-raised border border-status-low/30 rounded-sm space-y-1.5">
              <label className="text-xs-tech font-bold text-status-low block">
                Low Severity Delta (Units)
              </label>
              <input
                type="number"
                min={1}
                max={5}
                value={settings.lowSeverityThreshold}
                onChange={(e) => updateSettings({ lowSeverityThreshold: parseInt(e.target.value) || 1 })}
                className="w-full px-2.5 py-1.5 font-mono bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
              />
              <span className="text-[11px] text-text-sec block">
                Triggers visual warning flag for minor multi-pack singles or loose items.
              </span>
            </div>

            {/* Med Severity */}
            <div className="p-3 bg-panel-raised border border-status-med/30 rounded-sm space-y-1.5">
              <label className="text-xs-tech font-bold text-status-med block">
                Medium Severity Delta (Units)
              </label>
              <input
                type="number"
                min={2}
                max={10}
                value={settings.medSeverityThreshold}
                onChange={(e) => updateSettings({ medSeverityThreshold: parseInt(e.target.value) || 3 })}
                className="w-full px-2.5 py-1.5 font-mono bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
              />
              <span className="text-[11px] text-text-sec block">
                Triggers operator prompt and requires digital supervisor acknowledgement.
              </span>
            </div>

            {/* High Severity */}
            <div className="p-3 bg-panel-raised border border-status-high/30 rounded-sm space-y-1.5">
              <label className="text-xs-tech font-bold text-status-high block">
                High Severity Delta (Units)
              </label>
              <input
                type="number"
                min={5}
                max={50}
                value={settings.highSeverityThreshold}
                onChange={(e) => updateSettings({ highSeverityThreshold: parseInt(e.target.value) || 6 })}
                className="w-full px-2.5 py-1.5 font-mono bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
              />
              <span className="text-[11px] text-text-sec block">
                Triggers siren alert, turnstile lock recommendation, and mandatory investigation note.
              </span>
            </div>
          </div>

          {/* Repeat Offender & Camera Offline Alert Window */}
          <div className="p-3 bg-panel-raised border border-hairline rounded-sm grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="text-xs-tech font-bold text-text-pri block mb-1">
                Repeat Offender Escalation Rule
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={settings.repeatOffenderThreshold}
                  onChange={(e) => updateSettings({ repeatOffenderThreshold: parseInt(e.target.value) || 3 })}
                  className="w-20 px-2.5 py-1.5 font-mono bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
                />
                <span className="text-xs-tech text-text-sec">mismatches</span>
              </div>
              <p className="text-[11px] text-text-sec mt-1">
                When a carrier reaches {settings.repeatOffenderThreshold} mismatches, future events automatically escalate +1 severity band.
              </p>
            </div>

            <div>
              <label className="text-xs-tech font-bold text-text-pri block mb-1">
                Evaluation Rolling Window
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={7}
                  max={90}
                  value={settings.repeatOffenderWindowDays}
                  onChange={(e) => updateSettings({ repeatOffenderWindowDays: parseInt(e.target.value) || 30 })}
                  className="w-20 px-2.5 py-1.5 font-mono bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
                />
                <span className="text-xs-tech text-text-sec">days</span>
              </div>
              <p className="text-[11px] text-text-sec mt-1">
                Rolling timeframe checked against employee RFID badge records.
              </p>
            </div>

            <div>
              <label className="text-xs-tech font-bold text-status-high block mb-1 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5" />
                Camera Offline Alert Timeout
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={15}
                  max={300}
                  value={settings.cameraOfflineAlertAfterSec || 60}
                  onChange={(e) => updateSettings({ cameraOfflineAlertAfterSec: parseInt(e.target.value) || 60 })}
                  className="w-20 px-2.5 py-1.5 font-mono bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
                />
                <span className="text-xs-tech text-text-sec">seconds</span>
              </div>
              <p className="text-[11px] text-text-sec mt-1">
                Generates a HIGH-severity CAMERA_OFFLINE alert if heartbeat ceases.
              </p>
            </div>
          </div>
        </div>

        {/* Section 3: Audio Siren & Physical Interlock Settings */}
        <div className="p-4 bg-panel border border-hairline rounded-sm space-y-4">
          <div className="flex items-center justify-between border-b border-hairline pb-2">
            <h2 className="text-xs-tech font-bold text-text-pri uppercase tracking-wider flex items-center gap-2">
              <Volume2 className="w-4 h-4 text-amber" />
              3. Alarm Sound Synthesizer & Turnstile Auto-Lock
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Audio Alarm */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs-tech font-medium text-text-pri">
                  Web Audio API Synthetic Alarm Siren
                </label>
                <input
                  type="checkbox"
                  checked={settings.audioAlarmEnabled}
                  onChange={(e) => updateSettings({ audioAlarmEnabled: e.target.checked })}
                  className="w-4 h-4 rounded text-amber focus-visible:outline-2 focus-visible:outline-amber"
                />
              </div>

              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="0.1"
                  max="1.0"
                  step="0.05"
                  value={settings.alarmVolume}
                  onChange={(e) => updateSettings({ alarmVolume: parseFloat(e.target.value) })}
                  className="flex-1 accent-amber"
                />
                <button
                  type="button"
                  onClick={testAlarmSound}
                  className="px-2.5 py-1 text-xs-tech font-semibold bg-panel-raised border border-hairline hover:bg-hairline/40 text-amber rounded-sm transition-colors"
                >
                  Test Siren Tone
                </button>
              </div>
            </div>

            {/* Turnstile Auto Lock */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs-tech font-medium text-text-pri">
                  Auto-Engage Turnstile Lock on HIGH Severity
                </label>
                <input
                  type="checkbox"
                  checked={settings.turnstileAutoLockOnHigh}
                  onChange={(e) => updateSettings({ turnstileAutoLockOnHigh: e.target.checked })}
                  className="w-4 h-4 rounded text-amber focus-visible:outline-2 focus-visible:outline-amber"
                />
              </div>
              <p className="text-[11px] text-text-sec">
                Automatically engages electromagnetic drop-bar when a high-severity mismatch or unbadged intrusion occurs.
              </p>
            </div>
          </div>
        </div>

        {/* Section 4: Camera Fleet Management */}
        <CameraManagementPanel />

        {/* Section 5: Edge Sensor Hardware Registry */}
        <div className="p-4 bg-panel border border-hairline rounded-sm space-y-3">
          <div className="flex items-center justify-between border-b border-hairline pb-2">
            <h2 className="text-xs-tech font-bold text-text-pri uppercase tracking-wider flex items-center gap-2">
              <Radio className="w-4 h-4 text-amber" />
              5. Edge Sensor Lane Hardware Registry
            </h2>
            <span className="font-mono text-xs-tech text-status-ok">{lanes.length} Portals Connected</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs-tech">
              <thead>
                <tr className="border-b border-hairline text-text-sec text-[11px]">
                  <th className="p-2 font-normal">Lane ID</th>
                  <th className="p-2 font-normal">Physical Location</th>
                  <th className="p-2 font-normal">Edge IP Address</th>
                  <th className="p-2 font-normal text-right">Camera FPS</th>
                  <th className="p-2 font-normal text-right">RFID Gate (dBm)</th>
                  <th className="p-2 font-normal text-right">Scale Tare (kg)</th>
                  <th className="p-2 font-normal text-right">Status</th>
                </tr>
              </thead>
              <tbody>
                {lanes.length > 0 ? (
                  lanes.map((lane: SensorLane) => (
                    <tr key={lane.laneId} className="border-b border-hairline/50">
                      <td className="p-2 font-bold text-text-pri">{lane.laneId}</td>
                      <td className="p-2 font-sans text-text-sec">{lane.location}</td>
                      <td className="p-2 text-mono-val">{lane.cameraIp}</td>
                      <td className="p-2 text-right">{lane.cameraFps} fps</td>
                      <td className="p-2 text-right">{lane.rfidGatePowerDbm} dBm</td>
                      <td className="p-2 text-right">{lane.scaleTareKg} kg</td>
                      <td className="p-2 text-right font-sans">
                        <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                          lane.status === 'ONLINE' ? 'bg-teal-950/20 text-status-ok' : 'bg-yellow-950/20 text-status-low'
                        }`}>
                          {lane.status}
                        </span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-text-sec font-sans">
                      No exit lanes configured. Register an optical camera in Section 4 above to bind your first physical exit portal.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Section 5a: Zero-Click USB Hardware Auto-Detect (Scale & Webcam) */}
        <UsbHardwareManager lanes={lanes} />

        {/* Section 5b: Static Image & Spoof Prevention Audit Log */}
        <div className="p-4 bg-panel border border-hairline rounded-sm space-y-3">
          <div className="flex items-center justify-between border-b border-hairline pb-2">
            <h2 className="text-xs-tech font-bold text-text-pri uppercase tracking-wider flex items-center gap-2">
              <ImageIcon className="w-4 h-4 text-amber" />
              5b. Static Image & Spoof Prevention Audit Log
            </h2>
            <span className="font-mono text-xs-tech text-text-sec">
              {staticImages.length} Detections Logged · Suppressed False Alarms
            </span>
          </div>

          <p className="text-xs-tech text-text-sec">
            Two-stage anti-spoofing engine continuously identifies static representations (religious frames, employee wall photos, posters, and digital displays). Detections recorded here have alarms suppressed (<span className="font-mono text-status-ok font-bold">suppressed_alert = true</span>) to prevent false alerts.
          </p>

          <StaticImageLogTable
            records={staticImages}
            onRefresh={refreshStaticImages}
          />
        </div>

        {/* Section 6: Part I Compliance — Zero-Data Audit Purge */}
        <div className="p-4 bg-panel border border-hairline rounded-sm space-y-3">
          <div className="flex items-center justify-between border-b border-hairline pb-2">
            <h2 className="text-xs-tech font-bold text-text-pri uppercase tracking-wider flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-status-high" />
              6. Part I Compliance & Zero-State Database Reset
            </h2>
            <span className="font-mono text-[11px] text-text-sec">AUDIT & VERIFICATION MODE</span>
          </div>

          <p className="text-xs-tech text-text-sec">
            Per Part I of the SEC-OPS Specification, this system ships with zero hardcoded or fake mock data.
            Executing a reset purges all products, employees, cameras, lanes, and exit event tables back to a pure zero state, leaving only the baseline store and threshold definitions.
          </p>

          <div className="pt-1">
            <button
              type="button"
              disabled={isResetting}
              onClick={async () => {
                if (confirm('PERMANENT ACTION: Purge all products, employees, cameras, lanes, and events back to pure zero-data state per Part I policy?')) {
                  setIsResetting(true);
                  try {
                    await resetDatabase();
                  } catch (e) {
                    console.error('Reset failed:', e);
                  } finally {
                    setIsResetting(false);
                  }
                }
              }}
              className="px-3.5 py-2 text-xs-tech font-semibold bg-red-950/20 hover:bg-red-950/40 text-status-high border border-status-high/40 rounded-sm transition-colors disabled:opacity-50"
            >
              {isResetting ? 'Purging Database...' : 'Purge Database to Pure Zero-State (Part I Audit)'}
            </button>
          </div>
        </div>

        {/* Submit Save */}
        <div className="flex justify-end pt-2">
          <button
            type="submit"
            className="px-5 py-2 text-xs-tech font-semibold rounded-sm bg-amber hover:bg-amber/90 text-black transition-colors"
          >
            Apply & Save Operational Settings
          </button>
        </div>
      </form>
    </div>
  );
};
