import React from 'react';
import { Modal } from '../common/Modal';
import { useAppData } from '../../context/AppDataContext';
import { Zap, ShieldCheck, AlertTriangle, Radio, Users, FileWarning } from 'lucide-react';

interface SimulatorDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SimulatorDrawer: React.FC<SimulatorDrawerProps> = ({ isOpen, onClose }) => {
  const { injectSimulatedScenario } = useAppData();

  const scenarios = [
    {
      type: 'CLEAN_PASS' as const,
      title: '1. Standard Clean Exit (100% Multi-Modal Parity)',
      description: 'Vision, RFID gate, and floor scale all agree. Declared units equal detected count. Verdict: PASS.',
      icon: ShieldCheck,
      color: 'text-status-ok',
      border: 'border-status-ok/30',
      badge: 'VERIFIED PASS',
    },
    {
      type: 'CASE_PACK_OVER' as const,
      title: '2. Case Pack + Loose Singles Discrepancy',
      description: 'Carrier pushed 4 full cases (96 units) + 3 loose single bottles. Declared invoice was 96. Δ +3 units.',
      icon: AlertTriangle,
      color: 'text-status-low',
      border: 'border-status-low/30',
      badge: 'LOW SEVERITY',
    },
    {
      type: 'RFID_BLINDSPOT' as const,
      title: '3. RFID Gate Signal Attenuation / Shielding',
      description: 'Metallic packaging shields RFID tags. Vision AI (60) + Floor Scale (16.2kg) override RFID (50). 2/3 Consensus.',
      icon: Radio,
      color: 'text-amber',
      border: 'border-amber/30',
      badge: 'SENSOR DISAGREEMENT',
    },
    {
      type: 'UNDER_DECLARE_OCR' as const,
      title: '4. OCR Outbound Manifest Under-Declaration',
      description: 'Carrier manifest declared 4 cases (48 units) but exit lane detected 6 full cases (72 units). Δ +24 units.',
      icon: FileWarning,
      color: 'text-status-med',
      border: 'border-status-med/30',
      badge: 'MEDIUM SEVERITY',
    },
    {
      type: 'REPEAT_OFFENDER_HIGH' as const,
      title: '5. High-Risk Repeat Offender Anomaly',
      description: 'Carrier with 4 prior 30d mismatches carries 8 cases vs 4 declared (+24 units). Triggers HIGH Siren.',
      icon: Users,
      color: 'text-status-high',
      border: 'border-status-high/40',
      badge: 'HIGH ALARM + SIREN',
    },
  ];

  const handleTrigger = (type: typeof scenarios[number]['type']) => {
    injectSimulatedScenario(type);
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Exit Lane Event Injector & Simulation Suite"
      subtitle="Trigger edge-hardware telemetry scenarios to test consensus math, alarm sirens, and audit trails."
      maxWidth="lg"
    >
      <div className="space-y-3">
        {scenarios.map((sc) => {
          const Icon = sc.icon;
          return (
            <div
              key={sc.type}
              className={`p-3.5 bg-panel-raised border ${sc.border} rounded-sm flex items-start justify-between gap-3 hover:bg-panel transition-colors`}
            >
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-sm bg-canvas border border-hairline flex-shrink-0 mt-0.5">
                  <Icon className={`w-5 h-5 ${sc.color}`} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="text-xs-tech font-semibold text-text-pri">{sc.title}</h4>
                    <span className={`font-mono text-[10px] font-bold px-1.5 py-0.2 rounded bg-black/40 ${sc.color}`}>
                      {sc.badge}
                    </span>
                  </div>
                  <p className="text-xs-tech text-text-sec mt-1 leading-normal">{sc.description}</p>
                </div>
              </div>

              <button
                onClick={() => handleTrigger(sc.type)}
                className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs-tech font-semibold rounded-sm bg-amber/20 hover:bg-amber/30 text-amber border border-amber/40 transition-colors"
              >
                <Zap className="w-3.5 h-3.5" />
                Trigger
              </button>
            </div>
          );
        })}
      </div>
    </Modal>
  );
};

