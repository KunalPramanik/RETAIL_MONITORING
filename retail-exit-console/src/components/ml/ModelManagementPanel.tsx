import React, { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../../api/client';
import type { ModelRegistryResponse, ModelVersionData, TrainingJobStatusResponse } from '../../types';
import {
  Cpu,
  Zap,
  CheckCircle2,
  AlertTriangle,
  RotateCw,
  ShieldCheck,
  Sliders,
  Play,
  Square,
  Activity,
  Sparkles,
  Layers,
  Info,
  Eye,
  Crosshair,
  Scan,
} from 'lucide-react';

const PRESET_CLASSES = [
  { id: 'retail_carton', label: 'Retail Carton', category: 'Retail' },
  { id: 'pack_bottle_case', label: 'Pack Bottle Case', category: 'Retail' },
  { id: 'loose_unit', label: 'Loose Unit', category: 'Retail' },
  { id: 'cement_bag', label: 'Cement Bag', category: 'Industrial' },
  { id: 'iron_rod_bundle', label: 'Iron Rod Bundle', category: 'Industrial' },
  { id: 'brick_pallet', label: 'Brick Pallet', category: 'Industrial' },
  { id: 'fire_flame', label: 'Fire / Flame', category: 'Hazard' },
  { id: 'smoke_hazard', label: 'Smoke Hazard', category: 'Hazard' },
  { id: 'person_carrier', label: 'Person Carrier', category: 'Biometrics' },
  { id: 'ppe_hard_hat', label: 'PPE Hard Hat', category: 'Compliance' },
  { id: 'ppe_vest', label: 'PPE Safety Vest', category: 'Compliance' },
];

export const ModelManagementPanel: React.FC = () => {
  const [registryData, setRegistryData] = useState<ModelRegistryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fine-Tuning form parameters
  const [epochs, setEpochs] = useState<number>(10);
  const [learningRate, setLearningRate] = useState<number>(0.0005);
  const [batchSize, setBatchSize] = useState<number>(16);
  const [selectedClasses, setSelectedClasses] = useState<string[]>([
    'retail_carton',
    'pack_bottle_case',
    'cement_bag',
    'iron_rod_bundle',
  ]);
  const [autoPromote, setAutoPromote] = useState<boolean>(true);
  const [autoShadow, setAutoShadow] = useState<boolean>(false);
  const [shadowTrafficPct, setShadowTrafficPct] = useState<number>(25);

  // Training state & live polling
  const [trainingJob, setTrainingJob] = useState<TrainingJobStatusResponse | null>(null);
  const [actionMessage, setActionMessage] = useState<{ text: string; isError?: boolean } | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Shadow traffic modal/slider
  const [selectedModelForShadow, setSelectedModelForShadow] = useState<string | null>(null);
  const [tempShadowTraffic, setTempShadowTraffic] = useState<number>(25);

  const pollIntervalRef = useRef<number | null>(null);

  const fetchRegistry = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getModels();
      setRegistryData(data);
      setError(null);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch ML model registry');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchTrainingStatus = useCallback(async () => {
    try {
      const status = await api.getTrainingStatus();
      setTrainingJob(status);
      return status;
    } catch (err) {
      console.error('Error fetching training status:', err);
      return null;
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchRegistry();
    fetchTrainingStatus();
  }, [fetchRegistry, fetchTrainingStatus]);

  // Polling loop when training is active
  useEffect(() => {
    const isJobActive =
      trainingJob &&
      (trainingJob.status === 'TRAINING' ||
        trainingJob.status === 'PREPARING' ||
        trainingJob.status === 'EVALUATING');

    if (isJobActive) {
      if (!pollIntervalRef.current) {
        pollIntervalRef.current = window.setInterval(async () => {
          const res = await fetchTrainingStatus();
          if (res && (res.status === 'COMPLETED' || res.status === 'FAILED' || res.status === 'CANCELLED')) {
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
            fetchRegistry();
          }
        }, 1500);
      }
    } else {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    }

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [trainingJob?.status, fetchTrainingStatus, fetchRegistry]);

  const handleStartTraining = async () => {
    setActionLoading(true);
    setActionMessage(null);
    try {
      const res = await api.startModelTraining({
        epochs,
        learningRate,
        batchSize,
        targetClasses: selectedClasses,
        autoPromote,
        autoShadow,
        shadowTrafficPct,
      });
      setActionMessage({ text: res.message || 'Fine-tuning job launched successfully.' });
      await fetchTrainingStatus();
    } catch (err: any) {
      setActionMessage({ text: err?.message || 'Failed to start fine-tuning job', isError: true });
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancelTraining = async () => {
    setActionLoading(true);
    try {
      const res = await api.cancelTraining();
      setActionMessage({ text: res.message || 'Training cancellation requested' });
      await fetchTrainingStatus();
    } catch (err: any) {
      setActionMessage({ text: err?.message || 'Failed to cancel training', isError: true });
    } finally {
      setActionLoading(false);
    }
  };

  const handlePromote = async (version: string, bypass = false) => {
    setActionLoading(true);
    try {
      const res = await api.promoteModel(version, bypass);
      setActionMessage({ text: res.message });
      await fetchRegistry();
    } catch (err: any) {
      setActionMessage({ text: err?.message || 'Model promotion failed', isError: true });
    } finally {
      setActionLoading(false);
    }
  };

  const handleRollback = async (version: string) => {
    setActionLoading(true);
    try {
      const res = await api.rollbackModel(version);
      setActionMessage({ text: res.message });
      await fetchRegistry();
    } catch (err: any) {
      setActionMessage({ text: err?.message || 'Rollback failed', isError: true });
    } finally {
      setActionLoading(false);
    }
  };

  const handleApplyShadow = async (version: string | null, pct: number) => {
    setActionLoading(true);
    try {
      await api.setShadowMode(version, pct);
      setActionMessage({
        text: version ? `Shadow mode deployed for ${version} at ${pct}% traffic.` : 'Shadow mode disabled.',
      });
      setSelectedModelForShadow(null);
      await fetchRegistry();
    } catch (err: any) {
      setActionMessage({ text: err?.message || 'Failed to configure shadow mode', isError: true });
    } finally {
      setActionLoading(false);
    }
  };

  const toggleClass = (classId: string) => {
    if (selectedClasses.includes(classId)) {
      if (selectedClasses.length > 1) {
        setSelectedClasses(selectedClasses.filter((c) => c !== classId));
      }
    } else {
      setSelectedClasses([...selectedClasses, classId]);
    }
  };

  const activeProdModel = registryData?.models.find(
    (m) => m.model_version === registryData.active_production_version
  );

  return (
    <div className="p-4 bg-panel border border-hairline rounded-sm space-y-5">
      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-hairline pb-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Cpu className="w-5 h-5 text-amber" />
            <h2 className="text-xs-tech font-bold text-text-pri uppercase tracking-wider">
              Machine Learning Model Lifecycle, Open-Source Blueprints & Automated Fine-Tuning
            </h2>
          </div>
          <p className="text-xs-tech text-text-sec">
            Edge-native, zero-cloud-fee computer vision backbone: Megvii YOLOX-Tiny/Small (Apache 2.0), InsightFace ArcFace, MoveNet Pose, OpenCLIP & Adaptive Watershed.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              fetchRegistry();
              fetchTrainingStatus();
            }}
            className="px-2.5 py-1 text-xs-tech font-mono flex items-center gap-1.5 bg-panel-raised border border-hairline hover:bg-hairline/40 text-text-pri rounded-sm transition-colors"
          >
            <RotateCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-amber' : ''}`} />
            Refresh Registry
          </button>
        </div>
      </div>

      {/* ── Global Error / Action Banners ── */}
      {error && (
        <div className="p-2.5 rounded-sm text-xs-tech font-mono flex items-center justify-between border bg-red-950/20 border-status-high text-status-high">
          <span className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            {error}
          </span>
          <button
            type="button"
            onClick={() => setError(null)}
            className="text-text-sec hover:text-text-pri px-1"
          >
            ×
          </button>
        </div>
      )}

      {actionMessage && (
        <div
          className={`p-2.5 rounded-sm text-xs-tech font-mono flex items-center justify-between border ${
            actionMessage.isError
              ? 'bg-red-950/20 border-status-high text-status-high'
              : 'bg-teal-950/20 border-status-ok text-status-ok'
          }`}
        >
          <span className="flex items-center gap-2">
            {actionMessage.isError ? <AlertTriangle className="w-4 h-4" /> : <CheckCircle2 className="w-4 h-4" />}
            {actionMessage.text}
          </span>
          <button
            type="button"
            onClick={() => setActionMessage(null)}
            className="text-text-sec hover:text-text-pri px-1"
          >
            ×
          </button>
        </div>
      )}

      {/* ── Section 1: Best Free Open-Source Architecture Blueprint ── */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-mono text-amber font-bold tracking-wider uppercase flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5" />
            Open-Source Edge ML Architecture (100% Free · Permissive Apache 2.0 / MIT / BSD)
          </span>
          <span className="text-[10px] font-mono text-status-ok px-2 py-0.5 bg-teal-950/20 border border-status-ok/30 rounded-sm font-bold">
            ZERO CLOUD API FEES · 100% ON-PREMISES
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-2.5">
          {/* Tile 1: YOLOX */}
          <div className="p-3 bg-panel-raised border border-amber/30 rounded-sm space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs-tech font-bold text-text-pri flex items-center gap-1.5">
                <Crosshair className="w-3.5 h-3.5 text-amber" />
                YOLOX-Tiny / Small
              </span>
              <span className="text-[9px] font-mono bg-amber/10 text-amber px-1 py-0.2 rounded border border-amber/30">
                APACHE 2.0
              </span>
            </div>
            <p className="text-[11px] text-text-sec">
              Anchor-free object & carton pack detection. ONNX Runtime CPU latency 15–20ms. Target 95%+ precision.
            </p>
            <div className="text-[10px] font-mono text-text-pri pt-1 flex justify-between border-t border-hairline/40">
              <span>Primary Backbone</span>
              <span className="text-amber">ONNX Engine</span>
            </div>
          </div>

          {/* Tile 2: InsightFace */}
          <div className="p-3 bg-panel-raised border border-hairline rounded-sm space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs-tech font-bold text-text-pri flex items-center gap-1.5">
                <Scan className="w-3.5 h-3.5 text-status-ok" />
                InsightFace ArcFace
              </span>
              <span className="text-[9px] font-mono bg-teal-950/30 text-status-ok px-1 py-0.2 rounded border border-status-ok/30">
                OPEN SOURCE
              </span>
            </div>
            <p className="text-[11px] text-text-sec">
              SCRFD face detector + ArcFace ResNet-50. Deep 512-d biometric embeddings with cosine similarity verification.
            </p>
            <div className="text-[10px] font-mono text-text-pri pt-1 flex justify-between border-t border-hairline/40">
              <span>Employee Roster</span>
              <span className="text-status-ok">99.8% LFW</span>
            </div>
          </div>

          {/* Tile 3: MoveNet Pose */}
          <div className="p-3 bg-panel-raised border border-hairline rounded-sm space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs-tech font-bold text-text-pri flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-status-med" />
                MoveNet / Pose
              </span>
              <span className="text-[9px] font-mono bg-yellow-950/30 text-status-med px-1 py-0.2 rounded border border-status-med/30">
                APACHE 2.0
              </span>
            </div>
            <p className="text-[11px] text-text-sec">
              17-keypoint skeleton pose estimation. Detects loitering, crouching, concealment, and unbadged traversal.
            </p>
            <div className="text-[10px] font-mono text-text-pri pt-1 flex justify-between border-t border-hairline/40">
              <span>Kinematic Speed</span>
              <span className="text-status-med">25+ FPS CPU</span>
            </div>
          </div>

          {/* Tile 4: OpenCLIP */}
          <div className="p-3 bg-panel-raised border border-hairline rounded-sm space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs-tech font-bold text-text-pri flex items-center gap-1.5">
                <Eye className="w-3.5 h-3.5 text-cyan-400" />
                OpenCLIP ViT-B/32
              </span>
              <span className="text-[9px] font-mono bg-cyan-950/30 text-cyan-400 px-1 py-0.2 rounded border border-cyan-400/30">
                MIT / APACHE
              </span>
            </div>
            <p className="text-[11px] text-text-sec">
              Zero-shot open-vocabulary image classifier. Identifies uncatalogued brand items & emergency hazards instantly.
            </p>
            <div className="text-[10px] font-mono text-text-pri pt-1 flex justify-between border-t border-hairline/40">
              <span>Novel Classes</span>
              <span className="text-cyan-400">Zero-Shot</span>
            </div>
          </div>

          {/* Tile 5: Adaptive Watershed */}
          <div className="p-3 bg-panel-raised border border-hairline rounded-sm space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs-tech font-bold text-text-pri flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-purple-400" />
                Adaptive Watershed
              </span>
              <span className="text-[9px] font-mono bg-purple-950/30 text-purple-400 px-1 py-0.2 rounded border border-purple-400/30">
                BSD (OPENCV)
              </span>
            </div>
            <p className="text-[11px] text-text-sec">
              Instance separation for dense stacks (cement bags, iron rod bundles, brick layers). Sub-millisecond execution.
            </p>
            <div className="text-[10px] font-mono text-text-pri pt-1 flex justify-between border-t border-hairline/40">
              <span>Stack Isolation</span>
              <span className="text-purple-400">&lt; 5ms</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Section 2: Active Production Model & Step 5 Numeric Promotion Gates ── */}
      <div className="p-3 bg-panel-raised border border-hairline rounded-sm space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-hairline/60 pb-2">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-status-ok" />
            <span className="text-xs-tech font-bold text-text-pri uppercase">
              Active Production Deployment & Step 5 Numeric Promotion Gates
            </span>
          </div>

          <div className="flex items-center gap-3 font-mono text-xs-tech">
            <span className="text-text-sec">Active Version:</span>
            <span className="px-2 py-0.5 rounded-sm bg-teal-950/30 text-status-ok border border-status-ok/40 font-bold">
              {registryData?.active_production_version || 'None'}
            </span>
            {registryData?.active_shadow_version && (
              <span className="px-2 py-0.5 rounded-sm bg-cyan-950/30 text-cyan-400 border border-cyan-400/40">
                Shadow: {registryData.active_shadow_version} ({registryData.shadow_traffic_pct}%)
              </span>
            )}
          </div>
        </div>

        {activeProdModel ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {/* Metric 1: mAP@0.5 */}
            <div className="p-2 bg-canvas border border-hairline rounded-sm">
              <span className="text-[10px] text-text-sec block font-mono">mAP@0.5 (Gate: ≥ 75%)</span>
              <div className="flex items-baseline gap-1.5 mt-0.5">
                <span
                  className={`text-base-tech font-mono font-bold ${
                    activeProdModel.metrics.map_50 >= 0.75 ? 'text-status-ok' : 'text-status-high'
                  }`}
                >
                  {(activeProdModel.metrics.map_50 * 100).toFixed(1)}%
                </span>
                <span className="text-[10px] text-text-sec font-mono">/ 95% target</span>
              </div>
              <div className="w-full bg-hairline/30 h-1 mt-1.5 rounded-full overflow-hidden">
                <div
                  className="bg-status-ok h-full"
                  style={{ width: `${Math.min(100, activeProdModel.metrics.map_50 * 100)}%` }}
                />
              </div>
            </div>

            {/* Metric 2: Case/Unit Recall */}
            <div className="p-2 bg-canvas border border-hairline rounded-sm">
              <span className="text-[10px] text-text-sec block font-mono">Case Recall (Gate: ≥ 90%)</span>
              <div className="flex items-baseline gap-1.5 mt-0.5">
                <span
                  className={`text-base-tech font-mono font-bold ${
                    activeProdModel.metrics.case_unit_recall >= 0.9 ? 'text-status-ok' : 'text-status-high'
                  }`}
                >
                  {(activeProdModel.metrics.case_unit_recall * 100).toFixed(1)}%
                </span>
                <span className="text-[10px] text-text-sec font-mono">/ 97% critical</span>
              </div>
              <div className="w-full bg-hairline/30 h-1 mt-1.5 rounded-full overflow-hidden">
                <div
                  className="bg-status-ok h-full"
                  style={{ width: `${Math.min(100, activeProdModel.metrics.case_unit_recall * 100)}%` }}
                />
              </div>
            </div>

            {/* Metric 3: Empty Scene FP Rate */}
            <div className="p-2 bg-canvas border border-hairline rounded-sm">
              <span className="text-[10px] text-text-sec block font-mono">Empty Scene FP (Gate: &lt; 5%)</span>
              <div className="flex items-baseline gap-1.5 mt-0.5">
                <span
                  className={`text-base-tech font-mono font-bold ${
                    activeProdModel.metrics.empty_scene_fp_rate <= 0.05 ? 'text-status-ok' : 'text-status-high'
                  }`}
                >
                  {(activeProdModel.metrics.empty_scene_fp_rate * 100).toFixed(1)}%
                </span>
                <span className="text-[10px] text-text-sec font-mono">FP rate</span>
              </div>
              <div className="w-full bg-hairline/30 h-1 mt-1.5 rounded-full overflow-hidden">
                <div
                  className={`h-full ${
                    activeProdModel.metrics.empty_scene_fp_rate <= 0.05 ? 'bg-status-ok' : 'bg-status-high'
                  }`}
                  style={{ width: `${Math.min(100, activeProdModel.metrics.empty_scene_fp_rate * 500)}%` }}
                />
              </div>
            </div>

            {/* Metric 4: Pairwise Precision */}
            <div className="p-2 bg-canvas border border-hairline rounded-sm">
              <span className="text-[10px] text-text-sec block font-mono">Pairwise Prec. (Gate: ≥ 80%)</span>
              <div className="flex items-baseline gap-1.5 mt-0.5">
                <span
                  className={`text-base-tech font-mono font-bold ${
                    activeProdModel.metrics.pairwise_precision >= 0.8 ? 'text-status-ok' : 'text-status-high'
                  }`}
                >
                  {(activeProdModel.metrics.pairwise_precision * 100).toFixed(1)}%
                </span>
                <span className="text-[10px] text-text-sec font-mono">vs confusion</span>
              </div>
              <div className="w-full bg-hairline/30 h-1 mt-1.5 rounded-full overflow-hidden">
                <div
                  className="bg-status-ok h-full"
                  style={{ width: `${Math.min(100, activeProdModel.metrics.pairwise_precision * 100)}%` }}
                />
              </div>
            </div>

            {/* Metric 5: Edge Latency */}
            <div className="p-2 bg-canvas border border-hairline rounded-sm">
              <span className="text-[10px] text-text-sec block font-mono">Edge Latency (CPU)</span>
              <div className="flex items-baseline gap-1.5 mt-0.5">
                <span className="text-base-tech font-mono font-bold text-amber">
                  {activeProdModel.metrics.latency_ms.toFixed(1)}
                </span>
                <span className="text-[10px] text-text-sec font-mono">ms / frame</span>
              </div>
              <div className="w-full bg-hairline/30 h-1 mt-1.5 rounded-full overflow-hidden">
                <div className="bg-amber h-full" style={{ width: `${Math.min(100, (activeProdModel.metrics.latency_ms / 40) * 100)}%` }} />
              </div>
            </div>

            {/* Metric 6: Eval Dataset Size */}
            <div className="p-2 bg-canvas border border-hairline rounded-sm">
              <span className="text-[10px] text-text-sec block font-mono">Gold Standard Test Set</span>
              <div className="flex items-baseline gap-1.5 mt-0.5">
                <span className="text-base-tech font-mono font-bold text-text-pri">
                  {activeProdModel.metrics.eval_dataset_size.toLocaleString()}
                </span>
                <span className="text-[10px] text-text-sec font-mono">samples</span>
              </div>
              <span className="text-[9px] text-text-sec block truncate font-mono mt-1">
                Base: {activeProdModel.base_model || 'yolox'}
              </span>
            </div>
          </div>
        ) : (
          <div className="py-4 text-center text-text-sec text-xs-tech font-mono">
            No active production model registered in weights directory.
          </div>
        )}
      </div>

      {/* ── Section 3: Automated Fine-Tuning & Transfer Learning Studio ── */}
      <div className="p-4 bg-panel-raised border border-hairline rounded-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-hairline pb-2">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber" />
            <h3 className="text-xs-tech font-bold text-text-pri uppercase tracking-wider">
              Automated Fine-Tuning & Transfer Learning Studio
            </h3>
          </div>
          <span className="text-[11px] font-mono text-text-sec">
            Trains on Human-in-the-Loop Active Learning Datasets + Hard Negative Mining
          </span>
        </div>

        {/* Form Inputs Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Epochs */}
          <div className="p-2.5 bg-canvas border border-hairline rounded-sm space-y-1.5">
            <label className="text-xs-tech font-bold text-text-pri block">
              Training Epochs: <span className="font-mono text-amber">{epochs}</span>
            </label>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={2}
                max={50}
                value={epochs}
                onChange={(e) => setEpochs(parseInt(e.target.value) || 10)}
                className="flex-1 accent-amber"
              />
            </div>
            <div className="flex gap-1.5 pt-0.5">
              {[5, 10, 20, 30].map((ep) => (
                <button
                  key={ep}
                  type="button"
                  onClick={() => setEpochs(ep)}
                  className={`px-2 py-0.5 text-[10px] font-mono rounded ${
                    epochs === ep ? 'bg-amber text-black font-bold' : 'bg-panel border border-hairline text-text-sec'
                  }`}
                >
                  {ep} ep
                </button>
              ))}
            </div>
          </div>

          {/* Learning Rate */}
          <div className="p-2.5 bg-canvas border border-hairline rounded-sm space-y-1.5">
            <label className="text-xs-tech font-bold text-text-pri block">Learning Rate</label>
            <select
              value={learningRate}
              onChange={(e) => setLearningRate(parseFloat(e.target.value))}
              className="w-full px-2 py-1.5 font-mono text-xs-tech bg-panel border border-hairline rounded-sm text-text-pri"
            >
              <option value={0.0001}>0.0001 (Fine Refinement)</option>
              <option value={0.0005}>0.0005 (Recommended Default)</option>
              <option value={0.001}>0.001 (Aggressive Adaptation)</option>
              <option value={0.002}>0.002 (Fast Transfer)</option>
            </select>
            <span className="text-[10px] text-text-sec block">Cosine annealing decay schedule applied.</span>
          </div>

          {/* Batch Size */}
          <div className="p-2.5 bg-canvas border border-hairline rounded-sm space-y-1.5">
            <label className="text-xs-tech font-bold text-text-pri block">Mini-Batch Size</label>
            <select
              value={batchSize}
              onChange={(e) => setBatchSize(parseInt(e.target.value))}
              className="w-full px-2 py-1.5 font-mono text-xs-tech bg-panel border border-hairline rounded-sm text-text-pri"
            >
              <option value={8}>8 (Low Memory Edge CPU)</option>
              <option value={16}>16 (Optimal Balance)</option>
              <option value={32}>32 (Workstation / GPU)</option>
            </select>
            <span className="text-[10px] text-text-sec block">Automatic grad-accumulation fallback.</span>
          </div>

          {/* Deployment Automation */}
          <div className="p-2.5 bg-canvas border border-hairline rounded-sm space-y-2">
            <span className="text-xs-tech font-bold text-text-pri block">Deployment Automation</span>
            <div className="space-y-1.5">
              <label className="flex items-center gap-2 cursor-pointer text-xs-tech text-text-pri">
                <input
                  type="checkbox"
                  checked={autoPromote}
                  onChange={(e) => setAutoPromote(e.target.checked)}
                  className="w-3.5 h-3.5 rounded text-amber accent-amber"
                />
                <span>Auto-Promote if Step 5 Gates Pass</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer text-xs-tech text-text-pri">
                <input
                  type="checkbox"
                  checked={autoShadow}
                  onChange={(e) => setAutoShadow(e.target.checked)}
                  className="w-3.5 h-3.5 rounded text-amber accent-amber"
                />
                <span>Auto-Deploy as Shadow ({shadowTrafficPct}%)</span>
              </label>

              {autoShadow && (
                <div className="flex items-center gap-2 pl-5 pt-1">
                  <input
                    type="range"
                    min={5}
                    max={50}
                    step={5}
                    value={shadowTrafficPct}
                    onChange={(e) => setShadowTrafficPct(parseInt(e.target.value) || 25)}
                    className="flex-1 accent-amber h-1"
                  />
                  <span className="text-[10px] font-mono text-amber font-bold">{shadowTrafficPct}%</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Target Classes Selection Chips */}
        <div className="space-y-1.5">
          <label className="text-xs-tech font-bold text-text-pri block">
            Target Retraining Classes ({selectedClasses.length} selected):
          </label>
          <div className="flex flex-wrap gap-1.5">
            {PRESET_CLASSES.map((cls) => {
              const isSelected = selectedClasses.includes(cls.id);
              return (
                <button
                  key={cls.id}
                  type="button"
                  onClick={() => toggleClass(cls.id)}
                  className={`px-2.5 py-1 text-xs-tech rounded-sm font-mono flex items-center gap-1.5 border transition-all ${
                    isSelected
                      ? 'bg-amber/15 border-amber text-amber font-semibold shadow-xs'
                      : 'bg-canvas border-hairline text-text-sec hover:text-text-pri'
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      isSelected ? 'bg-amber' : 'bg-hairline'
                    }`}
                  />
                  {cls.label}
                  <span className="text-[9px] text-text-sec">[{cls.category}]</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Action Controls & Launch */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-hairline/60">
          <div className="text-[11px] font-mono text-text-sec flex items-center gap-2">
            <Info className="w-3.5 h-3.5 text-amber" />
            Checkpoints are verified against 4 numeric gates before production promotion.
          </div>

          <div className="flex items-center gap-2">
            {trainingJob &&
            (trainingJob.status === 'TRAINING' ||
              trainingJob.status === 'PREPARING' ||
              trainingJob.status === 'EVALUATING') ? (
              <button
                type="button"
                onClick={handleCancelTraining}
                disabled={actionLoading}
                className="px-3 py-1.5 text-xs-tech font-mono font-bold bg-red-950/30 text-status-high border border-status-high hover:bg-red-950/50 rounded-sm flex items-center gap-1.5 transition-colors"
              >
                <Square className="w-3.5 h-3.5 fill-current" />
                Abort Training Job
              </button>
            ) : (
              <button
                type="button"
                onClick={handleStartTraining}
                disabled={actionLoading || selectedClasses.length === 0}
                className="px-4 py-2 text-xs-tech font-semibold bg-amber hover:bg-amber/90 text-black rounded-sm flex items-center gap-2 transition-colors disabled:opacity-50"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                Launch Automated Fine-Tuning
              </button>
            )}
          </div>
        </div>

        {/* ── Live Training Job Monitor ── */}
        {trainingJob && trainingJob.status !== 'IDLE' && (
          <div className="p-3 bg-canvas border border-amber/30 rounded-sm space-y-2.5 animate-in fade-in">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span
                  className={`w-2 h-2 rounded-full ${
                    trainingJob.status === 'TRAINING' || trainingJob.status === 'PREPARING'
                      ? 'bg-amber animate-ping'
                      : trainingJob.status === 'COMPLETED'
                      ? 'bg-status-ok'
                      : 'bg-status-high'
                  }`}
                />
                <span className="text-xs-tech font-bold font-mono text-text-pri">
                  Job Status: {trainingJob.status}
                </span>
                {trainingJob.candidate_version && (
                  <span className="text-[10px] font-mono px-1.5 py-0.2 bg-panel rounded border border-hairline text-amber">
                    {trainingJob.candidate_version}
                  </span>
                )}
              </div>

              <div className="font-mono text-xs-tech text-text-sec flex items-center gap-3">
                {trainingJob.current_epoch && trainingJob.total_epochs && (
                  <span>
                    Epoch {trainingJob.current_epoch} / {trainingJob.total_epochs}
                  </span>
                )}
                {trainingJob.train_loss !== undefined && (
                  <span>Loss: {trainingJob.train_loss.toFixed(4)}</span>
                )}
                {trainingJob.duration_seconds && (
                  <span>Elapsed: {trainingJob.duration_seconds.toFixed(1)}s</span>
                )}
              </div>
            </div>

            {/* Progress Bar */}
            <div className="w-full bg-panel h-2 rounded-full overflow-hidden border border-hairline">
              <div
                className={`h-full transition-all duration-300 ${
                  trainingJob.status === 'COMPLETED'
                    ? 'bg-status-ok'
                    : trainingJob.status === 'FAILED' || trainingJob.status === 'CANCELLED'
                    ? 'bg-status-high'
                    : 'bg-amber'
                }`}
                style={{ width: `${Math.max(3, trainingJob.progress_pct)}%` }}
              />
            </div>

            {/* Status Details / Gate Checklist */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[11px] font-mono pt-1">
              <span className="text-text-sec">{trainingJob.message}</span>

              {trainingJob.metrics && (
                <div className="flex items-center gap-2 text-[10px]">
                  <span
                    className={`px-1.5 py-0.5 rounded border ${
                      trainingJob.metrics.map_50 >= 0.75
                        ? 'bg-teal-950/20 text-status-ok border-status-ok/30'
                        : 'bg-red-950/20 text-status-high border-status-high/30'
                    }`}
                  >
                    mAP: {(trainingJob.metrics.map_50 * 100).toFixed(1)}%
                  </span>
                  <span
                    className={`px-1.5 py-0.5 rounded border ${
                      trainingJob.metrics.case_unit_recall >= 0.9
                        ? 'bg-teal-950/20 text-status-ok border-status-ok/30'
                        : 'bg-red-950/20 text-status-high border-status-high/30'
                    }`}
                  >
                    Recall: {(trainingJob.metrics.case_unit_recall * 100).toFixed(1)}%
                  </span>
                  <span
                    className={`px-1.5 py-0.5 rounded border ${
                      trainingJob.metrics.empty_scene_fp_rate <= 0.05
                        ? 'bg-teal-950/20 text-status-ok border-status-ok/30'
                        : 'bg-red-950/20 text-status-high border-status-high/30'
                    }`}
                  >
                    FP: {(trainingJob.metrics.empty_scene_fp_rate * 100).toFixed(1)}%
                  </span>
                </div>
              )}
            </div>

            {trainingJob.gate_failures && trainingJob.gate_failures.length > 0 && (
              <div className="p-2 rounded bg-red-950/20 border border-status-high/30 text-status-high text-[11px] font-mono">
                <span className="font-bold">Step 5 Gate Violations:</span>
                <ul className="list-disc pl-4 mt-0.5">
                  {trainingJob.gate_failures.map((f, i) => (
                    <li key={i}>{f}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Section 4: Model Registry & Checkpoint History ── */}
      <div className="p-4 bg-panel border border-hairline rounded-sm space-y-3">
        <div className="flex items-center justify-between border-b border-hairline pb-2">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-amber" />
            <h3 className="text-xs-tech font-bold text-text-pri uppercase tracking-wider">
              Model Checkpoint Registry & Deployment History
            </h3>
          </div>
          <span className="font-mono text-xs-tech text-text-sec">
            {registryData?.models.length || 0} Checkpoints Registered
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs-tech">
            <thead>
              <tr className="border-b border-hairline text-text-sec text-[11px]">
                <th className="p-2 font-normal">Model Version</th>
                <th className="p-2 font-normal">Base Architecture</th>
                <th className="p-2 font-normal">Status</th>
                <th className="p-2 font-normal text-right">mAP@0.5</th>
                <th className="p-2 font-normal text-right">Recall</th>
                <th className="p-2 font-normal text-right">Empty FP</th>
                <th className="p-2 font-normal text-right">Pair Prec.</th>
                <th className="p-2 font-normal text-right">Latency</th>
                <th className="p-2 font-normal text-right">Lifecycle Actions</th>
              </tr>
            </thead>
            <tbody>
              {registryData && registryData.models.length > 0 ? (
                registryData.models.map((m: ModelVersionData) => {
                  const isProd = m.model_version === registryData.active_production_version;
                  const isShadow = m.model_version === registryData.active_shadow_version;

                  return (
                    <tr
                      key={m.model_version}
                      className={`border-b border-hairline/40 transition-colors ${
                        isProd ? 'bg-teal-950/10' : isShadow ? 'bg-cyan-950/10' : 'hover:bg-panel-raised/50'
                      }`}
                    >
                      {/* Version & Name */}
                      <td className="p-2">
                        <div className="font-bold text-text-pri flex items-center gap-1.5">
                          {m.model_version}
                          {isProd && (
                            <span className="px-1.5 py-0.2 rounded text-[9px] bg-status-ok text-black font-bold font-sans">
                              PROD
                            </span>
                          )}
                          {isShadow && (
                            <span className="px-1.5 py-0.2 rounded text-[9px] bg-cyan-400 text-black font-bold font-sans">
                              SHADOW {registryData.shadow_traffic_pct}%
                            </span>
                          )}
                        </div>
                        <span className="text-[10px] text-text-sec font-sans block">{m.model_name}</span>
                      </td>

                      {/* Base Model */}
                      <td className="p-2 text-text-sec text-[11px]">
                        {m.base_model || 'yolox-tiny'}
                      </td>

                      {/* Status */}
                      <td className="p-2 font-sans">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            isProd
                              ? 'bg-teal-950/30 text-status-ok border border-status-ok/30'
                              : isShadow
                              ? 'bg-cyan-950/30 text-cyan-400 border border-cyan-400/30'
                              : m.status === 'candidate'
                              ? 'bg-yellow-950/30 text-amber border border-amber/30'
                              : 'bg-panel-raised text-text-sec border border-hairline'
                          }`}
                        >
                          {isProd ? 'PRODUCTION' : isShadow ? 'SHADOW' : m.status.toUpperCase()}
                        </span>
                      </td>

                      {/* Metrics */}
                      <td className="p-2 text-right">
                        <span
                          className={
                            m.metrics.map_50 >= 0.75 ? 'text-status-ok font-bold' : 'text-text-sec'
                          }
                        >
                          {(m.metrics.map_50 * 100).toFixed(1)}%
                        </span>
                      </td>

                      <td className="p-2 text-right">
                        <span
                          className={
                            m.metrics.case_unit_recall >= 0.9 ? 'text-status-ok font-bold' : 'text-text-sec'
                          }
                        >
                          {(m.metrics.case_unit_recall * 100).toFixed(1)}%
                        </span>
                      </td>

                      <td className="p-2 text-right">
                        <span
                          className={
                            m.metrics.empty_scene_fp_rate <= 0.05 ? 'text-status-ok' : 'text-status-high font-bold'
                          }
                        >
                          {(m.metrics.empty_scene_fp_rate * 100).toFixed(1)}%
                        </span>
                      </td>

                      <td className="p-2 text-right">
                        <span
                          className={
                            m.metrics.pairwise_precision >= 0.8 ? 'text-status-ok' : 'text-text-sec'
                          }
                        >
                          {(m.metrics.pairwise_precision * 100).toFixed(1)}%
                        </span>
                      </td>

                      <td className="p-2 text-right text-text-pri">
                        {m.metrics.latency_ms.toFixed(1)} ms
                      </td>

                      {/* Actions */}
                      <td className="p-2 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {!isProd && (
                            <button
                              type="button"
                              onClick={() => handlePromote(m.model_version, false)}
                              disabled={actionLoading}
                              className="px-2 py-1 text-[10px] font-semibold bg-teal-950/30 text-status-ok border border-status-ok/40 hover:bg-teal-950/60 rounded-sm transition-colors"
                              title="Promote this model to Production (enforcing Step 5 gates)"
                            >
                              Promote Prod
                            </button>
                          )}

                          {!isShadow && !isProd && (
                            <button
                              type="button"
                              onClick={() => {
                                setSelectedModelForShadow(m.model_version);
                                setTempShadowTraffic(25);
                              }}
                              disabled={actionLoading}
                              className="px-2 py-1 text-[10px] font-semibold bg-cyan-950/30 text-cyan-400 border border-cyan-400/40 hover:bg-cyan-950/60 rounded-sm transition-colors"
                              title="Deploy as Shadow to evaluate on live traffic without impacting alarms"
                            >
                              Shadow
                            </button>
                          )}

                          {isShadow && (
                            <button
                              type="button"
                              onClick={() => handleApplyShadow(null, 0)}
                              disabled={actionLoading}
                              className="px-2 py-1 text-[10px] font-semibold bg-panel-raised text-text-sec hover:text-text-pri border border-hairline rounded-sm transition-colors"
                              title="Disable Shadow Mode"
                            >
                              End Shadow
                            </button>
                          )}

                          {!isProd && (
                            <button
                              type="button"
                              onClick={() => handleRollback(m.model_version)}
                              disabled={actionLoading}
                              className="px-2 py-1 text-[10px] font-semibold bg-panel-raised text-amber border border-amber/30 hover:bg-amber/10 rounded-sm transition-colors"
                              title="Rollback production to this verified version"
                            >
                              Rollback To
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={9} className="py-6 text-center text-text-sec font-sans">
                    No models registered in registry.json. Baseline will initialize on first inference.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Shadow Configuration Popover / Sub-strip */}
        {selectedModelForShadow && (
          <div className="p-3 bg-canvas border border-cyan-400/40 rounded-sm space-y-2 mt-2">
            <div className="flex items-center justify-between">
              <span className="text-xs-tech font-bold text-cyan-400 flex items-center gap-1.5 font-mono">
                <Sliders className="w-3.5 h-3.5" />
                Deploy Shadow Traffic: {selectedModelForShadow}
              </span>
              <button
                type="button"
                onClick={() => setSelectedModelForShadow(null)}
                className="text-text-sec hover:text-text-pri text-xs-tech"
              >
                Cancel
              </button>
            </div>

            <p className="text-[11px] text-text-sec">
              Shadow deployments run parallel asynchronous inference on a randomized fraction of frames. Alarms and consensus verifications continue to use the active production model while shadow accuracy is recorded.
            </p>

            <div className="flex items-center gap-3">
              <span className="text-xs-tech font-mono text-text-pri">Traffic %:</span>
              <input
                type="range"
                min={5}
                max={100}
                step={5}
                value={tempShadowTraffic}
                onChange={(e) => setTempShadowTraffic(parseInt(e.target.value) || 25)}
                className="flex-1 accent-cyan-400"
              />
              <span className="font-mono text-xs-tech text-cyan-400 font-bold w-12 text-right">
                {tempShadowTraffic}%
              </span>
              <button
                type="button"
                onClick={() => handleApplyShadow(selectedModelForShadow, tempShadowTraffic)}
                disabled={actionLoading}
                className="px-3 py-1 text-xs-tech font-semibold bg-cyan-500 hover:bg-cyan-400 text-black rounded-sm transition-colors"
              >
                Apply Shadow Traffic
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
