import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client';
import type { DiscoveredDevice, SensorLane } from '../../types';
import {
  Wifi,
  Camera as CameraIcon,
  Radio,
  CheckCircle2,
  RotateCw,
  ArrowRight,
  ShieldCheck,
  Zap,
} from 'lucide-react';

interface DiscoveredDevicesTrayProps {
  lanes: SensorLane[];
  onDeviceConfirmed: () => void;
}

export const DiscoveredDevicesTray: React.FC<DiscoveredDevicesTrayProps> = ({
  lanes,
  onDeviceConfirmed,
}) => {
  const [discoveredDevices, setDiscoveredDevices] = useState<DiscoveredDevice[]>([]);
  const [isScanning, setIsScanning] = useState(false);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [selectedLanes, setSelectedLanes] = useState<Record<string, string>>({});
  const [confirmationSuccess, setConfirmationSuccess] = useState<string | null>(null);

  const fetchDiscovered = useCallback(async () => {
    try {
      const list = await api.getDiscoveredDevices();
      setDiscoveredDevices(list);
      // Pre-select suggested lane for each device
      const initLanes: Record<string, string> = {};
      list.forEach((d) => {
        initLanes[d.discoveryId] = d.suggestedLaneId || (lanes[0] ? lanes[0].laneId : '');
      });
      setSelectedLanes((prev) => ({ ...initLanes, ...prev }));
    } catch (err) {
      console.debug('Failed loading discovered devices:', err);
    }
  }, [lanes]);

  useEffect(() => {
    fetchDiscovered();
    const interval = setInterval(fetchDiscovered, 8000);
    return () => clearInterval(interval);
  }, [fetchDiscovered]);

  const handleScanNow = async () => {
    setIsScanning(true);
    try {
      await api.scanDiscoveryNow();
      await fetchDiscovered();
    } finally {
      setIsScanning(false);
    }
  };

  const handleConfirm = async (device: DiscoveredDevice) => {
    const targetLaneId = selectedLanes[device.discoveryId] || device.suggestedLaneId || lanes[0]?.laneId;
    if (!targetLaneId) {
      alert('Please select or configure an exit lane first.');
      return;
    }

    setConfirmingId(device.discoveryId);
    try {
      await api.confirmDiscoveredDevice({
        discoveryId: device.discoveryId,
        laneId: targetLaneId,
        label: `${device.manufacturer} ${device.model} (${device.ipAddress})`,
      });
      setConfirmationSuccess(device.discoveryId);
      setTimeout(() => {
        setConfirmationSuccess(null);
        fetchDiscovered();
        onDeviceConfirmed();
      }, 1200);
    } catch (err: any) {
      alert(`Failed to confirm device: ${err.message}`);
    } finally {
      setConfirmingId(null);
    }
  };

  if (discoveredDevices.length === 0) {
    return (
      <div className="p-3 bg-panel-raised border border-hairline rounded-sm flex items-center justify-between text-xs-tech">
        <div className="flex items-center gap-2 text-text-sec font-mono">
          <Wifi className="w-4 h-4 text-amber animate-pulse" />
          <span>Continuous background discovery active (ONVIF WS-Discovery / mDNS / Subnet probe)</span>
        </div>
        <button
          type="button"
          onClick={handleScanNow}
          disabled={isScanning}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-canvas border border-hairline hover:bg-panel text-text-pri transition-colors text-[11px] font-mono"
        >
          <RotateCw className={`w-3 h-3 ${isScanning ? 'animate-spin text-amber' : 'text-text-sec'}`} />
          {isScanning ? 'Scanning Network...' : 'Scan Network Now'}
        </button>
      </div>
    );
  }

  return (
    <div className="p-3.5 bg-gradient-to-r from-amber/10 via-panel to-panel border border-amber/40 rounded-sm space-y-3 animate-in fade-in">
      <div className="flex items-center justify-between border-b border-hairline/60 pb-2">
        <div className="flex items-center gap-2">
          <div className="p-1 rounded bg-amber/20 text-amber">
            <Zap className="w-4 h-4" />
          </div>
          <div>
            <span className="text-xs-tech font-bold text-amber uppercase tracking-wider block">
              Auto-Discovered Network Devices ({discoveredDevices.length})
            </span>
            <span className="text-[11px] text-text-sec font-mono">
              Pre-tested & verified reachable on local LAN · Single-tap lane confirmation required
            </span>
          </div>
        </div>

        <button
          type="button"
          onClick={handleScanNow}
          disabled={isScanning}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-canvas border border-hairline hover:bg-panel text-text-pri transition-colors text-[11px] font-mono"
        >
          <RotateCw className={`w-3 h-3 ${isScanning ? 'animate-spin text-amber' : 'text-text-sec'}`} />
          {isScanning ? 'Scanning...' : 'Scan Now'}
        </button>
      </div>

      <div className="grid grid-cols-1 gap-2.5">
        {discoveredDevices.map((dev) => {
          const isConfirming = confirmingId === dev.discoveryId;
          const isSuccess = confirmationSuccess === dev.discoveryId;
          const assignedLaneId = selectedLanes[dev.discoveryId] || dev.suggestedLaneId || lanes[0]?.laneId;
          const matchedLane = lanes.find((l) => l.laneId === assignedLaneId);

          return (
            <div
              key={dev.discoveryId}
              className="p-3 bg-canvas/80 border border-hairline rounded-sm flex flex-col md:flex-row md:items-center justify-between gap-3"
            >
              {/* Device Metadata */}
              <div className="flex items-start gap-3">
                <div className="p-2 rounded bg-panel border border-hairline text-amber mt-0.5">
                  {dev.deviceType === 'RFID_GATE' ? (
                    <Radio className="w-5 h-5" />
                  ) : (
                    <CameraIcon className="w-5 h-5" />
                  )}
                </div>

                <div className="space-y-1 text-xs-tech">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold text-text-pri font-mono">
                      {dev.manufacturer} {dev.model}
                    </span>
                    <span className="px-1.5 py-0.2 rounded bg-status-ok/20 text-status-ok border border-status-ok/30 text-[10px] font-mono font-bold flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3" />
                      PRE-TESTED: REACHABLE ({dev.latencyMs}ms)
                    </span>
                  </div>

                  <div className="text-[11px] font-mono text-text-sec flex items-center gap-2 flex-wrap">
                    <span>IP: {dev.ipAddress}</span>
                    <span>·</span>
                    <span>RTSP: {dev.rtspPath}</span>
                    {dev.macAddress && (
                      <>
                        <span>·</span>
                        <span>MAC: {dev.macAddress}</span>
                      </>
                    )}
                  </div>

                  {dev.suggestedLaneName && (
                    <div className="text-[11px] font-mono text-amber flex items-center gap-1">
                      <span>Smart Suggestion:</span>
                      <span className="font-bold underline">{dev.suggestedLaneName}</span>
                      <span className="text-[10px] text-text-sec">
                        ({((dev.suggestionConfidence ?? 0.85) * 100).toFixed(0)}% correlation)
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* The One-Tap Confirmation Action */}
              <div className="flex items-center gap-2 shrink-0">
                {/* Lane Selector */}
                <select
                  value={assignedLaneId || ''}
                  onChange={(e) =>
                    setSelectedLanes((prev) => ({
                      ...prev,
                      [dev.discoveryId]: e.target.value,
                    }))
                  }
                  className="px-2 py-1.5 bg-panel border border-hairline rounded-sm text-xs-tech font-mono text-text-pri focus-visible:outline-amber"
                >
                  {lanes.map((l) => (
                    <option key={l.laneId} value={l.laneId}>
                      {l.laneId} ({l.location})
                    </option>
                  ))}
                </select>

                {/* Confirm Button */}
                <button
                  type="button"
                  onClick={() => handleConfirm(dev)}
                  disabled={isConfirming || isSuccess}
                  className={`px-3 py-1.5 text-xs-tech font-bold font-mono rounded-sm border flex items-center gap-1.5 transition-all ${
                    isSuccess
                      ? 'bg-status-ok text-white border-status-ok'
                      : 'bg-amber hover:bg-amber-hover text-black border-amber shadow-sm'
                  }`}
                >
                  {isSuccess ? (
                    <>
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Confirmed!
                    </>
                  ) : isConfirming ? (
                    <>
                      <RotateCw className="w-3.5 h-3.5 animate-spin" />
                      Binding...
                    </>
                  ) : (
                    <>
                      <span>This is {matchedLane ? matchedLane.laneId : 'Lane'}</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                      <span>Confirm</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
