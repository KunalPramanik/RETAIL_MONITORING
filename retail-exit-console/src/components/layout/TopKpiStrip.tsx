import React, { useState, useEffect } from 'react';
import { KpiTile } from './KpiTile';
import { useAppData } from '../../context/AppDataContext';
import { Radio, AlertTriangle, ShieldCheck, Activity, Zap, Camera, Wifi, Clock } from 'lucide-react';

interface TopKpiStripProps {
  onOpenSimulator?: () => void;
}

export const TopKpiStrip: React.FC<TopKpiStripProps> = ({ onOpenSimulator }) => {
  const {
    todayThroughputUnits,
    openAlertsCount,
    openAlertsBySeverity,
    consensusAccuracyRate,
    activeLanesCount,
    lanes,
    camerasOnlineCount,
    camerasTotalCount,
    isStreaming,
    setIsStreaming,
    wsConnected,
    setActiveView,
  } = useAppData();

  // Real-time live ticking clock
  const [liveTime, setLiveTime] = useState(() => new Date());

  useEffect(() => {
    const timer = setInterval(() => {
      setLiveTime(new Date());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 p-4 border-b border-hairline bg-canvas">
      {/* 1. Throughput Units */}
      <KpiTile
        label="Today's Outflow Units"
        value={todayThroughputUnits.toLocaleString()}
        unit="units"
        statusColor="neutral"
        subtext={
          lanes.length === 0
            ? 'No active exit portals'
            : `Live across ${lanes.length} exit portal${lanes.length === 1 ? '' : 's'}`
        }
        badge={<Activity className="w-3.5 h-3.5 text-text-sec" />}
        onClick={() => setActiveView('events')}
        clickableHint="Click to inspect all exit events in Ledger"
      />

      {/* 2. Open Alerts by Severity */}
      <KpiTile
        label="Open Active Alerts"
        value={openAlertsCount}
        statusColor={openAlertsBySeverity.high > 0 ? 'high' : openAlertsBySeverity.medium > 0 ? 'amber' : 'ok'}
        subtext={
          <span className="flex items-center gap-1.5 font-mono text-xs-tech">
            <span className="text-status-high font-medium">{openAlertsBySeverity.high} High</span>
            <span className="text-hairline">|</span>
            <span className="text-status-med font-medium">{openAlertsBySeverity.medium} Med</span>
            <span className="text-hairline">|</span>
            <span className="text-status-low font-medium">{openAlertsBySeverity.low} Low</span>
          </span>
        }
        badge={<AlertTriangle className={`w-3.5 h-3.5 ${openAlertsBySeverity.high > 0 ? 'text-status-high' : 'text-text-sec'}`} />}
        onClick={() => setActiveView('alerts')}
        clickableHint="Click to open Active Alerts Queue"
      />

      {/* 3. Consensus Accuracy Rate */}
      <KpiTile
        label="Consensus Match Rate"
        value={`${consensusAccuracyRate}%`}
        statusColor={consensusAccuracyRate >= 95 ? 'ok' : 'amber'}
        subtext="Vision + RFID + Weight parity"
        badge={<ShieldCheck className="w-3.5 h-3.5 text-status-ok" />}
        onClick={() => setActiveView('dashboard')}
        clickableHint="Click to view Live Consensus Dashboard & Sensor Parity"
      />

      {/* 4. Active Exit Lanes */}
      <KpiTile
        label="Exit Lanes Online"
        value={`${activeLanesCount}/${lanes.length}`}
        statusColor={activeLanesCount === lanes.length ? 'ok' : 'amber'}
        subtext={
          <span className="flex items-center gap-1 text-xs-tech text-text-sec font-mono">
            <span className={`w-1.5 h-1.5 rounded-full ${activeLanesCount > 0 ? 'bg-status-ok' : 'bg-text-sec'}`} />
            {activeLanesCount} Active Portal{activeLanesCount === 1 ? '' : 's'}
          </span>
        }
        badge={<Radio className="w-3.5 h-3.5 text-status-ok" />}
        onClick={() => setActiveView('settings')}
        clickableHint="Click to manage Edge Sensor Lanes in Settings"
      />

      {/* 5. Cameras Online Fleet Counter */}
      <KpiTile
        label="Cameras Online"
        value={`${camerasOnlineCount}/${camerasTotalCount}`}
        statusColor={camerasOnlineCount === camerasTotalCount && camerasTotalCount > 0 ? 'ok' : camerasOnlineCount >= 3 ? 'amber' : 'high'}
        subtext={
          <span className="flex items-center gap-1 text-xs-tech text-text-sec font-mono">
            <span className={`w-1.5 h-1.5 rounded-full ${camerasTotalCount === 0 ? 'bg-text-sec' : camerasOnlineCount === camerasTotalCount ? 'bg-status-ok' : 'bg-status-high'}`} />
            {camerasTotalCount === 0
              ? 'No cameras enrolled'
              : camerasTotalCount - camerasOnlineCount === 0
              ? 'All streams nominal'
              : `${camerasTotalCount - camerasOnlineCount} Offline`}
          </span>
        }
        badge={<Camera className="w-3.5 h-3.5 text-amber" />}
        onClick={() => setActiveView('settings')}
        clickableHint="Click to configure Surveillance Camera Fleet in Settings"
      />

      {/* 6. Stream Control & Simulation Action */}
      <div className="flex flex-col justify-between px-3.5 py-3 bg-panel border border-hairline rounded-sm col-span-2 sm:col-span-1">
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-text-sec flex items-center gap-1">
            <Wifi className={`w-3 h-3 ${wsConnected ? 'text-status-ok' : 'text-text-sec'}`} />
            Edge WebSocket
          </span>
          <span className="flex items-center gap-1 font-mono text-[10px] text-status-ok">
            <span className={`w-1.5 h-1.5 rounded-full ${isStreaming ? 'bg-status-ok animate-pulse' : 'bg-text-sec'}`} />
            {isStreaming ? 'STREAMING' : 'PAUSED'}
          </span>
        </div>

        {/* Real-time Ticking Clock in Indian Standard Time (IST) */}
        <div className="flex items-center justify-between font-mono text-[11px] px-2 py-1 bg-canvas border border-hairline/60 rounded-sm my-1.5">
          <span className="flex items-center gap-1 text-text-sec text-[10px]">
            <Clock className="w-3 h-3 text-amber" />
            {liveTime.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}
          </span>
          <span className="text-text-pri font-bold">
            {liveTime.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true })}
          </span>
        </div>

        <div className="flex items-center gap-1.5 mt-1">
          <button
            onClick={() => setIsStreaming(!isStreaming)}
            className={`flex-1 px-2 py-1 text-[11px] font-medium rounded-sm border transition-colors ${
              isStreaming
                ? 'border-hairline bg-canvas hover:bg-hairline/40 text-text-sec hover:text-text-pri'
                : 'border-amber bg-amber/10 text-amber font-semibold'
            }`}
          >
            {isStreaming ? 'Pause' : 'Resume'}
          </button>

          {onOpenSimulator && (
            <button
              onClick={onOpenSimulator}
              className="flex items-center gap-1 px-2 py-1 text-[11px] font-semibold bg-amber/20 hover:bg-amber/30 text-amber border border-amber/40 rounded-sm transition-colors"
              title="Inject test scenarios (Clean Pass, Anomaly, Mismatch)"
            >
              <Zap className="w-3 h-3" />
              Sim
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
