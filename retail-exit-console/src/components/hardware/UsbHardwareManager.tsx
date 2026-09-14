import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client';
import type { UsbStatusResponse, UsbDeviceRecord, SensorLane } from '../../types';
import {
  Cpu,
  Scale,
  Camera as CameraIcon,
  AlertTriangle,
  CheckCircle2,
  RotateCw,
  Radio,
  Zap,
} from 'lucide-react';

interface UsbHardwareManagerProps {
  lanes: SensorLane[];
  onRefreshLanes?: () => void;
}

export const UsbHardwareManager: React.FC<UsbHardwareManagerProps> = ({
  lanes,
  onRefreshLanes,
}) => {
  const [usbStatus, setUsbStatus] = useState<UsbStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [configuringPort, setConfiguringPort] = useState<string | null>(null);
  const [selectedType, setSelectedType] = useState<string>('WEIGHT_SCALE');
  const [selectedLane, setSelectedLane] = useState<string>(lanes[0]?.laneId || 'LANE-01');
  const [customModel, setCustomModel] = useState<string>('');
  const [feedbackMessage, setFeedbackMessage] = useState<{ text: string; isError?: boolean } | null>(null);

  const fetchUsb = useCallback(async () => {
    try {
      const data = await api.getUsbDevices();
      setUsbStatus(data);
    } catch (err) {
      console.debug('Failed to query USB status:', err);
    }
  }, []);

  useEffect(() => {
    fetchUsb();
    const interval = setInterval(fetchUsb, 5000);
    return () => clearInterval(interval);
  }, [fetchUsb]);

  const handleManualConfigure = async (port: string) => {
    setLoading(true);
    setFeedbackMessage(null);
    try {
      const res = await api.configureUsbDevice({
        port,
        deviceType: selectedType,
        laneId: selectedLane,
        customModel: customModel || undefined,
      });
      setFeedbackMessage({ text: res.message || 'Device configured successfully' });
      setConfiguringPort(null);
      await fetchUsb();
      if (onRefreshLanes) onRefreshLanes();
    } catch (err: any) {
      setFeedbackMessage({ text: err.message || 'Configuration failed', isError: true });
    } finally {
      setLoading(false);
    }
  };

  const devices: UsbDeviceRecord[] = usbStatus?.devices || [];
  const unrecognizedDevices: UsbDeviceRecord[] = devices.filter(
    (d: UsbDeviceRecord) => d.deviceType === 'UNRECOGNIZED'
  );
  const scaleDevice: UsbDeviceRecord | undefined = devices.find(
    (d: UsbDeviceRecord) => d.deviceType === 'WEIGHT_SCALE' && d.isConnected
  );
  const webcams: UsbDeviceRecord[] = devices.filter(
    (d: UsbDeviceRecord) => d.deviceType === 'WEBCAM'
  );

  return (
    <div className="p-4 bg-panel border border-hairline rounded-sm space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-hairline pb-3">
        <div>
          <h3 className="text-xs-tech font-bold text-text-pri uppercase tracking-wider flex items-center gap-2">
            <Cpu className="w-4 h-4 text-amber" />
            USB Auto-Detect & Hardware Port Interlock (Scale & Webcam)
          </h3>
          <p className="text-[11px] text-text-sec mt-0.5">
            Zero-click auto-detection via OS-level device listener & config-driven VID/PID table. Opens COM/tty ports automatically.
          </p>
        </div>

        <button
          type="button"
          onClick={fetchUsb}
          className="flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-mono rounded bg-canvas border border-hairline hover:bg-panel-raised text-text-pri transition-colors self-start sm:self-auto"
        >
          <RotateCw className="w-3 h-3 text-text-sec" />
          Poll USB Ports
        </button>
      </div>

      {/* Active Hardware Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {/* Scale Card */}
        <div className={`p-3 rounded-sm border ${
          usbStatus?.activeScalePort
            ? 'bg-teal-950/20 border-status-ok/40 text-status-ok'
            : 'bg-canvas border-hairline text-text-sec'
        }`}>
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase font-bold flex items-center gap-1.5">
              <Scale className="w-3.5 h-3.5" />
              Weight Scale Port
            </span>
            {usbStatus?.activeScalePort ? (
              <span className="inline-flex items-center gap-1 text-[10px] font-mono text-status-ok font-bold bg-status-ok/10 px-1.5 py-0.5 rounded">
                <CheckCircle2 className="w-3 h-3" /> ZERO-CLICK ACTIVE
              </span>
            ) : (
              <span className="text-[10px] font-mono text-text-sec">Awaiting Connection</span>
            )}
          </div>
          <div className="mt-2">
            {scaleDevice ? (
              <div>
                <div className="text-xs-tech font-bold text-text-pri">
                  {scaleDevice.model} ({scaleDevice.port})
                </div>
                <div className="text-[10px] font-mono text-text-sec">
                  VID:{scaleDevice.vid} PID:{scaleDevice.pid} · Lane: {scaleDevice.laneId || 'LANE-01'}
                </div>
              </div>
            ) : (
              <div className="text-[11px] text-text-sec">
                Plug in any USB/RS-232 scale (CAS, Toledo, Dymo, FTDI/CH340). Auto-connects with 0 clicks.
              </div>
            )}
          </div>
        </div>

        {/* Webcams Card */}
        <div className="p-3 rounded-sm border bg-canvas border-hairline text-text-sec">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase font-bold flex items-center gap-1.5 text-text-pri">
              <CameraIcon className="w-3.5 h-3.5 text-amber" />
              Direct USB Webcams
            </span>
            <span className="text-[10px] font-mono text-text-pri">
              {webcams.length} Connected
            </span>
          </div>
          <div className="mt-2 text-[11px]">
            {webcams.length > 0 ? (
              webcams.map((w: UsbDeviceRecord) => (
                <div key={w.port} className="text-text-pri font-mono text-[10px]">
                  {w.model} [{w.port}]
                </div>
              ))
            ) : (
              <span className="text-[11px] text-text-sec">
                Plug in USB camera (UVC, Logitech, Microsoft) for secondary optical scanning.
              </span>
            )}
          </div>
        </div>

        {/* Auto-Assignment Status */}
        <div className="p-3 rounded-sm border bg-canvas border-hairline text-text-sec">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase font-bold flex items-center gap-1.5 text-text-pri">
              <Zap className="w-3.5 h-3.5 text-amber" />
              OS Device Listener
            </span>
            <span className="inline-flex items-center gap-1 text-[10px] font-mono text-status-ok">
              <span className="w-1.5 h-1.5 rounded-full bg-status-ok animate-pulse" /> RUNNING
            </span>
          </div>
          <div className="mt-2 text-[11px] text-text-sec space-y-0.5">
            <div>Engine: <span className="font-mono text-text-pri">Hardware USB Manager</span></div>
            <div>Lookup: <span className="font-mono text-text-pri">src/hardware/usb_devices.json</span></div>
          </div>
        </div>
      </div>

      {/* Unrecognized Device Warning Alert */}
      {unrecognizedDevices.length > 0 && (
        <div className="p-3 bg-amber/10 border border-amber/40 rounded-sm space-y-2 animate-in fade-in">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 text-amber shrink-0 mt-0.5" />
            <div className="space-y-1">
              <div className="text-xs-tech font-bold text-amber">
                Unrecognized USB Device Detected ({unrecognizedDevices.length})
              </div>
              <p className="text-[11px] text-text-pri">
                A USB peripheral is plugged in but does not match pre-configured scale or webcam vendor signatures.
                Please select the device class below to bind it to an exit lane:
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-2 pt-1">
            {unrecognizedDevices.map((dev: UsbDeviceRecord) => (
              <div
                key={dev.port}
                className="p-2.5 bg-canvas/90 border border-hairline rounded flex flex-col sm:flex-row sm:items-center justify-between gap-2"
              >
                <div className="font-mono text-[11px]">
                  <span className="font-bold text-text-pri">{dev.port}</span>
                  <span className="text-text-sec ml-2">
                    (VID: {dev.vid || '????'}, PID: {dev.pid || '????'}) — {dev.rawDescription || dev.model}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setConfiguringPort(dev.port);
                      setSelectedType('WEIGHT_SCALE');
                      setCustomModel(dev.rawDescription || 'Custom Weight Scale');
                    }}
                    className="px-2 py-1 text-[10px] font-semibold bg-amber hover:bg-amber/90 text-black rounded transition-colors"
                  >
                    Configure as Scale
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setConfiguringPort(dev.port);
                      setSelectedType('WEBCAM');
                      setCustomModel(dev.rawDescription || 'Custom USB Camera');
                    }}
                    className="px-2 py-1 text-[10px] font-semibold bg-canvas border border-hairline hover:bg-panel-raised text-text-pri rounded transition-colors"
                  >
                    Configure as Camera
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Manual Configuration Modal / Inline Form */}
      {configuringPort && (
        <div className="p-3 bg-panel-raised border border-amber/50 rounded-sm space-y-3">
          <div className="flex items-center justify-between text-xs-tech font-bold text-amber">
            <span>Configure Port: {configuringPort}</span>
            <button
              type="button"
              onClick={() => setConfiguringPort(null)}
              className="text-text-sec hover:text-text-pri"
            >
              ✕
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs-tech">
            <div>
              <label className="text-text-sec block mb-1">Device Class</label>
              <select
                value={selectedType}
                onChange={(e) => setSelectedType(e.target.value)}
                className="w-full px-2 py-1.5 bg-canvas border border-hairline rounded font-mono text-text-pri"
              >
                <option value="WEIGHT_SCALE">Weight Scale (RS-232 / USB Serial)</option>
                <option value="WEBCAM">USB Optical Webcam</option>
              </select>
            </div>

            <div>
              <label className="text-text-sec block mb-1">Bind to Exit Lane</label>
              <select
                value={selectedLane}
                onChange={(e) => setSelectedLane(e.target.value)}
                className="w-full px-2 py-1.5 bg-canvas border border-hairline rounded font-mono text-text-pri"
              >
                {lanes.map((l) => (
                  <option key={l.laneId} value={l.laneId}>
                    {l.laneId} ({l.location})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-text-sec block mb-1">Model / Label</label>
              <input
                type="text"
                value={customModel}
                onChange={(e) => setCustomModel(e.target.value)}
                placeholder="e.g. CAS SW-1 / Toledo"
                className="w-full px-2 py-1.5 bg-canvas border border-hairline rounded font-mono text-text-pri"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={() => setConfiguringPort(null)}
              className="px-3 py-1 text-xs-tech bg-canvas border border-hairline text-text-sec rounded"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => handleManualConfigure(configuringPort)}
              className="px-4 py-1 text-xs-tech font-bold bg-amber text-black hover:bg-amber/90 rounded"
            >
              {loading ? 'Saving...' : 'Save & Open Hardware Port'}
            </button>
          </div>
        </div>
      )}

      {feedbackMessage && (
        <div className={`p-2 text-xs-tech font-mono rounded ${
          feedbackMessage.isError ? 'bg-red-950/20 text-status-high' : 'bg-teal-950/20 text-status-ok'
        }`}>
          {feedbackMessage.text}
        </div>
      )}

      {/* Detected Devices Full Table */}
      <div className="overflow-x-auto border border-hairline rounded-sm">
        <table className="w-full text-left font-mono text-xs-tech">
          <thead>
            <tr className="border-b border-hairline bg-canvas text-text-sec text-[11px]">
              <th className="p-2 font-normal">Port</th>
              <th className="p-2 font-normal">Device Type</th>
              <th className="p-2 font-normal">Model / Description</th>
              <th className="p-2 font-normal">Hardware ID (VID:PID)</th>
              <th className="p-2 font-normal">Assigned Exit Lane</th>
              <th className="p-2 font-normal text-right">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-hairline/50">
            {devices.length > 0 ? (
              devices.map((dev: UsbDeviceRecord) => (
                <tr key={dev.port} className="hover:bg-panel-raised/40">
                  <td className="p-2 font-bold text-text-pri">{dev.port}</td>
                  <td className="p-2">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                      dev.deviceType === 'WEIGHT_SCALE'
                        ? 'bg-teal-950/30 text-status-ok'
                        : dev.deviceType === 'WEBCAM'
                        ? 'bg-blue-950/30 text-blue-400'
                        : 'bg-amber/20 text-amber'
                    }`}>
                      {dev.deviceType}
                    </span>
                  </td>
                  <td className="p-2 font-sans text-text-pri">{dev.model || dev.rawDescription}</td>
                  <td className="p-2 text-mono-val">{dev.vid}:{dev.pid}</td>
                  <td className="p-2 text-text-sec">
                    {dev.laneId ? (
                      <span className="inline-flex items-center gap-1 font-mono text-text-pri">
                        <Radio className="w-3 h-3 text-amber" />
                        {dev.laneId}
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="p-2 text-right">
                    <span className="inline-flex items-center gap-1 text-[10px] font-bold text-status-ok">
                      <CheckCircle2 className="w-3 h-3" />
                      {dev.status}
                    </span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6} className="py-6 text-center text-text-sec font-sans text-xs-tech">
                  No USB peripherals currently attached. Plug in any USB scale or webcam to auto-connect.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
