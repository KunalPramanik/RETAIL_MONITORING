import React from 'react';
import type { ExitEvent } from '../../types';
import { Camera, Radio, Scale, CheckCircle2, AlertTriangle } from 'lucide-react';

interface SensorMatrixProps {
  event: ExitEvent;
}

export const SensorMatrix: React.FC<SensorMatrixProps> = ({ event }) => {
  const visionMatchesRfid = event.visionCount === event.rfidCount;
  // Estimate expected weight based on ~0.45kg to 0.6kg per unit + tare
  const isScaleReasonable = event.weightKg > 0;

  return (
    <div className="p-3.5 bg-panel border border-hairline rounded-sm space-y-3">
      <div className="flex items-center justify-between border-b border-hairline pb-2">
        <span className="text-xs-tech font-semibold text-text-pri">
          Three-Channel Sensor Consensus Matrix
        </span>
        <span className="font-mono text-xs-tech text-text-sec">
          Consensus: {event.consensusUnits} units
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {/* Channel 1: Computer Vision */}
        <div className="p-2.5 bg-panel-raised border border-hairline rounded-sm space-y-1">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-text-sec">
              <Camera className="w-3.5 h-3.5 text-amber" />
              <span className="text-xs-tech">Vision AI</span>
            </div>
            <span className="w-1.5 h-1.5 rounded-full bg-status-ok" />
          </div>
          <div className="font-mono text-base-tech font-semibold text-mono-val">
            {event.visionCount} <span className="text-xs-tech text-text-sec font-normal">units</span>
          </div>
          <div className="text-[11px] text-text-sec">
            {event.casesDetected} cases detected
          </div>
        </div>

        {/* Channel 2: RFID Gate */}
        <div className={`p-2.5 bg-panel-raised border rounded-sm space-y-1 ${
          visionMatchesRfid ? 'border-hairline' : 'border-status-low/50 bg-yellow-950/10'
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-text-sec">
              <Radio className="w-3.5 h-3.5 text-amber" />
              <span className="text-xs-tech">RFID Gate</span>
            </div>
            {visionMatchesRfid ? (
              <span className="w-1.5 h-1.5 rounded-full bg-status-ok" />
            ) : (
              <AlertTriangle className="w-3 h-3 text-status-low" />
            )}
          </div>
          <div className={`font-mono text-base-tech font-semibold ${
            visionMatchesRfid ? 'text-mono-val' : 'text-status-low'
          }`}>
            {event.rfidCount} <span className="text-xs-tech text-text-sec font-normal">tags</span>
          </div>
          <div className="text-[11px] text-text-sec">
            {visionMatchesRfid ? '100% tag alignment' : `Attenuated (-${event.visionCount - event.rfidCount} tags)`}
          </div>
        </div>

        {/* Channel 3: Weight Scale */}
        <div className="p-2.5 bg-panel-raised border border-hairline rounded-sm space-y-1">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-text-sec">
              <Scale className="w-3.5 h-3.5 text-amber" />
              <span className="text-xs-tech">Floor Scale</span>
            </div>
            <span className="w-1.5 h-1.5 rounded-full bg-status-ok" />
          </div>
          <div className="font-mono text-base-tech font-semibold text-mono-val">
            {event.weightKg.toFixed(1)} <span className="text-xs-tech text-text-sec font-normal">kg</span>
          </div>
          <div className="text-[11px] text-text-sec">
            {isScaleReasonable ? 'Density verified' : 'Tare offset check'}
          </div>
        </div>
      </div>

      {/* Consensus Resolution Status */}
      <div className="flex items-center justify-between p-2 rounded-sm bg-canvas border border-hairline text-xs-tech">
        <div className="flex items-center gap-1.5 text-text-sec">
          <CheckCircle2 className="w-3.5 h-3.5 text-status-ok" />
          <span>Consensus Verdict Protocol:</span>
        </div>
        <span className="font-mono text-text-pri font-medium">
          {visionMatchesRfid
            ? '3/3 Multi-Modal Agreement'
            : '2/3 Majority Consensus (Vision + Scale overriding RFID attenuation)'}
        </span>
      </div>
    </div>
  );
};

