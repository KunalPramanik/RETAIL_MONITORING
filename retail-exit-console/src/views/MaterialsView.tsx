import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import type { MaterialRecord, PackageDefinitionRecord, DefectInspectionResponse } from '../types';
import { Modal } from '../components/common/Modal';
import {
  Boxes,
  Plus,
  Search,
  CheckCircle2,
  AlertTriangle,
  RotateCw,
  PackageCheck,
  ShieldAlert,
} from 'lucide-react';

const LIFECYCLE_STAGES = [
  'DRAFT',
  'DATA_COLLECTION',
  'ANNOTATION',
  'TRAINING',
  'EVALUATION',
  'SHADOW',
  'APPROVED',
  'ACTIVE',
] as const;

export const MaterialsView: React.FC = () => {
  const [materials, setMaterials] = useState<MaterialRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [profileFilter, setProfileFilter] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Modals & Panels
  const [isOnboardModalOpen, setIsOnboardModalOpen] = useState(false);
  const [selectedMaterialForDetail, setSelectedMaterialForDetail] = useState<MaterialRecord | null>(null);
  const [isAddPackageModalOpen, setIsAddPackageModalOpen] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ text: string; isError?: boolean } | null>(null);

  // Defect Inspection Modal State (Part W.3)
  const [isDefectModalOpen, setIsDefectModalOpen] = useState(false);
  const [defectLoading, setDefectLoading] = useState(false);
  const [defectInspectionResult, setDefectInspectionResult] = useState<DefectInspectionResponse | null>(null);
  const [defectTestPreset, setDefectTestPreset] = useState<'torn_cement' | 'cracked_tile' | 'intact_box'>('torn_cement');

  // Onboarding Wizard Form State
  const [onboardStep, setOnboardStep] = useState<number>(1);
  const [formData, setFormData] = useState({
    skuCode: '',
    name: '',
    category: 'STACKED_MATERIAL',
    deploymentProfile: 'WAREHOUSE_DISPATCH',
    countUnit: 'piece',
    packagingType: 'loose_unit',
    countingTier: 'SINGLE_UNIT' as 'SINGLE_UNIT' | 'PACKAGED_BOX' | 'BULK_MATERIAL',
    lengthCm: 60,
    widthCm: 40,
    heightCm: 15,
    nominalUnitWeightKg: 50.0,
    weightTolerancePct: 5.0,
    unitsPerPackage: 1,
    barcode: '',
    rfidEpcPrefix: '',
    approvedModelClass: '',
    notes: '',
  });

  // Package Definition Form State
  const [pkgFormData, setPkgFormData] = useState({
    unitsPerPackage: 24,
    packageBarcode: '',
    rfidPrefix: '',
    grossWeightKg: 25.0,
    netWeightKg: 24.0,
    toleranceRangePct: 5.0,
    evidenceSource: 'MANUFACTURER_SPEC',
  });

  const fetchMaterials = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getMaterials({
        profile: profileFilter !== 'ALL' ? profileFilter : undefined,
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
        query: searchQuery ? searchQuery : undefined,
      });
      setMaterials(data);
      setError(null);
    } catch (err: any) {
      setError(err?.message || 'Failed to load materials catalog');
    } finally {
      setLoading(false);
    }
  }, [profileFilter, statusFilter, searchQuery]);

  useEffect(() => {
    fetchMaterials();
  }, [fetchMaterials]);

  const handleOpenOnboardModal = () => {
    setOnboardStep(1);
    setFormData({
      skuCode: `MAT-${Math.floor(100 + Math.random() * 900)}`,
      name: '',
      category: 'STACKED_MATERIAL',
      deploymentProfile: 'WAREHOUSE_DISPATCH',
      countUnit: 'bag',
      packagingType: 'stack',
      countingTier: 'SINGLE_UNIT',
      lengthCm: 60,
      widthCm: 40,
      heightCm: 15,
      nominalUnitWeightKg: 50.0,
      weightTolerancePct: 5.0,
      unitsPerPackage: 1,
      barcode: '',
      rfidEpcPrefix: '',
      approvedModelClass: '',
      notes: '',
    });
    setIsOnboardModalOpen(true);
  };

  const generatePresetDataUrl = (preset: 'torn_cement' | 'cracked_tile' | 'intact_box'): string => {
    const canvas = document.createElement('canvas');
    canvas.width = 400;
    canvas.height = 300;
    const ctx = canvas.getContext('2d');
    if (!ctx) return '';

    // Dark background
    ctx.fillStyle = '#222';
    ctx.fillRect(0, 0, 400, 300);

    if (preset === 'torn_cement') {
      // Kraft brown sack
      ctx.fillStyle = '#9e7b4f';
      ctx.fillRect(50, 50, 200, 150);
      // Large rupture plume of grey-white cement dust
      ctx.fillStyle = '#d5d5d5';
      ctx.beginPath();
      ctx.arc(150, 120, 65, 0, Math.PI * 2);
      ctx.fill();
      // Jagged dark tear fissure
      ctx.strokeStyle = '#111';
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.moveTo(100, 110);
      ctx.lineTo(130, 135);
      ctx.lineTo(150, 110);
      ctx.lineTo(170, 140);
      ctx.lineTo(200, 115);
      ctx.stroke();
    } else if (preset === 'cracked_tile') {
      // Glazed white tile
      ctx.fillStyle = '#e8e8e8';
      ctx.fillRect(80, 60, 200, 180);
      // Multiple penetrating fracture lines
      ctx.strokeStyle = '#050505';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(95, 75);
      ctx.lineTo(200, 170);
      ctx.lineTo(265, 220);
      ctx.moveTo(200, 170);
      ctx.lineTo(140, 225);
      ctx.moveTo(110, 120);
      ctx.lineTo(250, 140);
      ctx.stroke();
    } else {
      // Intact corrugated carton
      ctx.fillStyle = '#b38247';
      ctx.fillRect(70, 70, 200, 160);
      ctx.strokeStyle = '#734e20';
      ctx.lineWidth = 3;
      ctx.strokeRect(70, 70, 200, 160);
      ctx.beginPath();
      ctx.moveTo(70, 100);
      ctx.lineTo(270, 100);
      ctx.stroke();
    }

    return canvas.toDataURL('image/jpeg', 0.9);
  };

  const handleRunDefectInspection = async () => {
    try {
      setDefectLoading(true);
      const dataUrl = generatePresetDataUrl(defectTestPreset);
      const result = await api.inspectMaterialDefects(dataUrl, 0.95);
      setDefectInspectionResult(result);
    } catch (err: any) {
      setError(err?.message || 'Defect inspection failed');
    } finally {
      setDefectLoading(false);
    }
  };

  const handleCreateMaterial = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.skuCode.trim()) return;

    setActionLoading(true);
    setStatusMessage(null);
    try {
      const created = await api.createMaterial({
        skuCode: formData.skuCode.trim().toUpperCase(),
        name: formData.name.trim(),
        category: formData.category,
        deploymentProfile: formData.deploymentProfile as any,
        countUnit: formData.countUnit,
        packagingType: formData.packagingType,
        countingTier: formData.countingTier,
        dimensions: {
          length_cm: formData.lengthCm,
          width_cm: formData.widthCm,
          height_cm: formData.heightCm,
        },
        nominalUnitWeightKg: formData.nominalUnitWeightKg,
        weightTolerancePct: formData.weightTolerancePct,
        unitsPerPackage: formData.unitsPerPackage,
        barcode: formData.barcode || undefined,
        rfidEpcPrefix: formData.rfidEpcPrefix || undefined,
        approvedModelClass: formData.approvedModelClass || undefined,
        notes: formData.notes || undefined,
      });

      setStatusMessage({ text: `Material '${created.name}' (${created.skuCode}) created in DRAFT state.` });
      setIsOnboardModalOpen(false);
      await fetchMaterials();
    } catch (err: any) {
      setStatusMessage({ text: err?.message || 'Failed to create material', isError: true });
    } finally {
      setActionLoading(false);
    }
  };

  const handleLifecycleTransition = async (materialId: string, nextStatus: string) => {
    setActionLoading(true);
    try {
      const updated = await api.transitionMaterialLifecycle(materialId, nextStatus);
      setStatusMessage({ text: `Transitioned ${updated.skuCode} to ${updated.status}.` });
      if (selectedMaterialForDetail?.materialId === materialId) {
        setSelectedMaterialForDetail(updated);
      }
      await fetchMaterials();
    } catch (err: any) {
      setStatusMessage({ text: err?.message || 'Lifecycle transition failed', isError: true });
    } finally {
      setActionLoading(false);
    }
  };

  const handleAddPackageDefinition = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedMaterialForDetail) return;

    setActionLoading(true);
    try {
      await api.addPackageDefinition(selectedMaterialForDetail.materialId, {
        unitsPerPackage: pkgFormData.unitsPerPackage,
        packageBarcode: pkgFormData.packageBarcode || undefined,
        rfidPrefix: pkgFormData.rfidPrefix || undefined,
        grossWeightKg: pkgFormData.grossWeightKg,
        netWeightKg: pkgFormData.netWeightKg,
        toleranceRangePct: pkgFormData.toleranceRangePct,
        evidenceSource: pkgFormData.evidenceSource,
      });

      const refreshed = await api.getMaterials({ query: selectedMaterialForDetail.skuCode });
      if (refreshed.length > 0) {
        setSelectedMaterialForDetail(refreshed[0]);
      }
      setIsAddPackageModalOpen(false);
      setStatusMessage({ text: 'Versioned package definition registered.' });
      await fetchMaterials();
    } catch (err: any) {
      setStatusMessage({ text: err?.message || 'Failed to add package definition', isError: true });
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="p-4 space-y-4 max-w-7xl mx-auto">
      {/* ── Header ── */}
      <div className="p-4 bg-panel border border-hairline rounded-sm space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-base-tech font-semibold text-text-pri flex items-center gap-2">
              <Boxes className="w-5 h-5 text-amber" />
              Dynamic Material Catalog & Packaging Specification Master
            </h1>
            <p className="text-xs-tech text-text-sec mt-0.5">
              Governs physical material attributes, versioned package definitions, and the 8-stage onboarding lifecycle per Section 5.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={fetchMaterials}
              className="px-2.5 py-1.5 text-xs-tech font-mono flex items-center gap-1.5 bg-panel-raised border border-hairline hover:bg-hairline/40 text-text-pri rounded-sm transition-colors"
            >
              <RotateCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-amber' : ''}`} />
              Refresh
            </button>

            <button
              type="button"
              onClick={() => {
                setIsDefectModalOpen(true);
                setDefectInspectionResult(null);
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs-tech font-semibold rounded-sm bg-panel-raised hover:bg-hairline/40 text-fuchsia-400 border border-fuchsia-500/40 transition-colors"
            >
              <ShieldAlert className="w-4 h-4 text-fuchsia-400" />
              Test Defect Detection (Part W.3)
            </button>

            <button
              type="button"
              onClick={handleOpenOnboardModal}
              className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs-tech font-semibold rounded-sm bg-amber hover:bg-amber/90 text-black transition-colors"
            >
              <Plus className="w-4 h-4" />
              Onboard Physical Material
            </button>
          </div>
        </div>

        {/* Error Notification Banner */}
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

        {/* Status Notification Banner */}
        {statusMessage && (
          <div
            className={`p-2.5 rounded-sm text-xs-tech font-mono flex items-center justify-between border ${
              statusMessage.isError
                ? 'bg-red-950/20 border-status-high text-status-high'
                : 'bg-teal-950/20 border-status-ok text-status-ok'
            }`}
          >
            <span className="flex items-center gap-2">
              {statusMessage.isError ? <AlertTriangle className="w-4 h-4" /> : <CheckCircle2 className="w-4 h-4" />}
              {statusMessage.text}
            </span>
            <button
              type="button"
              onClick={() => setStatusMessage(null)}
              className="text-text-sec hover:text-text-pri px-1"
            >
              ×
            </button>
          </div>
        )}

        {/* Filters Strip */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 pt-2 border-t border-hairline/60">
          {/* Search */}
          <div className="relative">
            <Search className="w-4 h-4 text-text-sec absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search by SKU, name, category..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
            />
          </div>

          {/* Profile Filter */}
          <div className="flex items-center gap-2">
            <span className="text-xs-tech text-text-sec font-mono">Profile:</span>
            <select
              value={profileFilter}
              onChange={(e) => setProfileFilter(e.target.value)}
              className="flex-1 px-2 py-1.5 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri"
            >
              <option value="ALL">All Deployment Profiles</option>
              <option value="WAREHOUSE_DISPATCH">Warehouse Dispatch</option>
              <option value="RETAIL_EXIT">Retail Exit Monitoring</option>
              <option value="INDUSTRIAL_PERIMETER">Industrial Perimeter</option>
            </select>
          </div>

          {/* Lifecycle Status Filter */}
          <div className="flex items-center gap-2">
            <span className="text-xs-tech text-text-sec font-mono">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="flex-1 px-2 py-1.5 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri"
            >
              <option value="ALL">All Lifecycle States</option>
              {LIFECYCLE_STAGES.map((st) => (
                <option key={st} value={st}>
                  {st}
                </option>
              ))}
            </select>
          </div>

          <div className="text-right text-xs-tech font-mono text-text-sec flex items-center justify-end">
            <span>{materials.length} Materials Active in Registry</span>
          </div>
        </div>
      </div>

      {/* ── Materials Table or Clean Empty State ── */}
      <div className="p-4 bg-panel border border-hairline rounded-sm">
        {loading ? (
          <div className="py-12 text-center text-text-sec text-xs-tech font-mono flex items-center justify-center gap-2">
            <RotateCw className="w-4 h-4 animate-spin text-amber" />
            Loading dynamic materials catalog from database...
          </div>
        ) : materials.length === 0 ? (
          <div className="py-16 text-center space-y-3">
            <div className="w-12 h-12 rounded-full bg-amber/10 border border-amber/30 text-amber mx-auto flex items-center justify-center">
              <Boxes className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h3 className="text-xs-tech font-bold text-text-pri uppercase tracking-wider">
                Zero Operational Materials Registered
              </h3>
              <p className="text-xs-tech text-text-sec max-w-md mx-auto">
                Per Section 2.1 zero-hardcode policy, the database starts empty. No demo or mock items are seeded.
                Use the onboarding button above to register physical cement, rebar, tiles, aluminium, or retail carton items.
              </p>
            </div>
            <button
              type="button"
              onClick={handleOpenOnboardModal}
              className="px-4 py-2 text-xs-tech font-semibold rounded-sm bg-amber hover:bg-amber/90 text-black transition-colors"
            >
              Onboard First Physical Material
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs-tech">
              <thead>
                <tr className="border-b border-hairline text-text-sec text-[11px]">
                  <th className="p-2 font-normal">SKU Code</th>
                  <th className="p-2 font-normal">Material Name</th>
                  <th className="p-2 font-normal">Category</th>
                  <th className="p-2 font-normal">Profile</th>
                  <th className="p-2 font-normal">Counting Tier</th>
                  <th className="p-2 font-normal text-right">Units/Pkg</th>
                  <th className="p-2 font-normal text-right">Nominal Weight</th>
                  <th className="p-2 font-normal text-right">Dimensions</th>
                  <th className="p-2 font-normal text-center">Lifecycle Status</th>
                  <th className="p-2 font-normal text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {materials.map((m: MaterialRecord) => {
                  const dims = m.dimensions as any;
                  const dimStr =
                    dims?.length_cm && dims?.width_cm && dims?.height_cm
                      ? `${dims.length_cm}×${dims.width_cm}×${dims.height_cm}cm`
                      : '—';

                  return (
                    <tr
                      key={m.materialId}
                      className="border-b border-hairline/40 hover:bg-panel-raised/50 transition-colors"
                    >
                      <td className="p-2 font-bold text-text-pri">{m.skuCode}</td>
                      <td className="p-2 font-sans font-medium text-text-pri">
                        {m.name}
                        {m.barcode && (
                          <span className="block text-[10px] text-text-sec font-mono">Barcode: {m.barcode}</span>
                        )}
                      </td>
                      <td className="p-2 text-text-sec text-[11px]">{m.category}</td>
                      <td className="p-2 text-text-sec text-[11px] font-sans">
                        <span className="px-1.5 py-0.2 rounded text-[10px] bg-canvas border border-hairline">
                          {m.deploymentProfile.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="p-2">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            m.countingTier === 'PACKAGED_BOX'
                              ? 'bg-amber-950/40 text-amber border border-amber/40'
                              : m.countingTier === 'BULK_MATERIAL'
                              ? 'bg-cyan-950/40 text-cyan-400 border border-cyan-400/40'
                              : 'bg-canvas text-text-sec border border-hairline'
                          }`}
                        >
                          {m.countingTier || 'SINGLE_UNIT'}
                        </span>
                      </td>
                      <td className="p-2 text-right">
                        <span className="font-bold text-text-pri">{m.unitsPerPackage}</span> {m.countUnit}
                      </td>
                      <td className="p-2 text-right">
                        {m.nominalUnitWeightKg ? (
                          <span>
                            {m.nominalUnitWeightKg} kg <span className="text-[10px] text-text-sec">±{m.weightTolerancePct}%</span>
                          </span>
                        ) : (
                          <span className="text-text-sec">—</span>
                        )}
                      </td>
                      <td className="p-2 text-right text-text-sec">{dimStr}</td>
                      <td className="p-2 text-center">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            m.status === 'ACTIVE'
                              ? 'bg-teal-950/30 text-status-ok border border-status-ok/30'
                              : m.status === 'APPROVED'
                              ? 'bg-cyan-950/30 text-cyan-400 border border-cyan-400/30'
                              : m.status === 'SHADOW'
                              ? 'bg-purple-950/30 text-purple-400 border border-purple-400/30'
                              : m.status === 'TRAINING' || m.status === 'EVALUATION'
                              ? 'bg-yellow-950/30 text-amber border border-amber/30'
                              : 'bg-canvas text-text-sec border border-hairline'
                          }`}
                        >
                          {m.status}
                        </span>
                      </td>
                      <td className="p-2 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={() => setSelectedMaterialForDetail(m)}
                            className="px-2 py-1 text-[10px] font-semibold bg-panel-raised hover:bg-hairline/40 text-text-pri border border-hairline rounded-sm transition-colors"
                            title="Inspect physical attributes and versioned package history"
                          >
                            Details & History
                          </button>

                          {/* Quick Lifecycle Advance Button */}
                          {m.status !== 'ACTIVE' && (
                            <button
                              type="button"
                              onClick={() => {
                                const curIdx = LIFECYCLE_STAGES.indexOf(m.status as any);
                                if (curIdx >= 0 && curIdx < LIFECYCLE_STAGES.length - 1) {
                                  handleLifecycleTransition(m.materialId, LIFECYCLE_STAGES[curIdx + 1]);
                                }
                              }}
                              disabled={actionLoading}
                              className="px-2 py-1 text-[10px] font-semibold bg-amber/15 text-amber border border-amber/40 hover:bg-amber/30 rounded-sm transition-colors"
                              title={`Advance lifecycle to next stage`}
                            >
                              Advance →
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Detail & Versioned Package Definitions Drawer / Modal ── */}
      {selectedMaterialForDetail && (
        <Modal
          isOpen={true}
          onClose={() => setSelectedMaterialForDetail(null)}
          title={`Material Specification: ${selectedMaterialForDetail.name} (${selectedMaterialForDetail.skuCode})`}
        >
          <div className="space-y-4 max-h-[75vh] overflow-y-auto pr-1">
            {/* Metadata Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 p-3 bg-canvas border border-hairline rounded-sm text-xs-tech font-mono">
              <div>
                <span className="text-text-sec block text-[10px]">Category</span>
                <span className="font-bold text-text-pri">{selectedMaterialForDetail.category}</span>
              </div>
              <div>
                <span className="text-text-sec block text-[10px]">Deployment Profile</span>
                <span className="font-bold text-text-pri">{selectedMaterialForDetail.deploymentProfile}</span>
              </div>
              <div>
                <span className="text-text-sec block text-[10px]">Count Unit</span>
                <span className="font-bold text-text-pri">{selectedMaterialForDetail.countUnit}</span>
              </div>
              <div>
                <span className="text-text-sec block text-[10px]">Lifecycle State</span>
                <span className="font-bold text-amber">{selectedMaterialForDetail.status}</span>
              </div>
              <div>
                <span className="text-text-sec block text-[10px]">Nominal Weight</span>
                <span className="font-bold text-text-pri">
                  {selectedMaterialForDetail.nominalUnitWeightKg || '—'} kg (±{selectedMaterialForDetail.weightTolerancePct}%)
                </span>
              </div>
              <div>
                <span className="text-text-sec block text-[10px]">Revision</span>
                <span className="font-bold text-text-pri">Rev #{selectedMaterialForDetail.revision}</span>
              </div>
              <div>
                <span className="text-text-sec block text-[10px]">Approved Model Class</span>
                <span className="font-bold text-text-pri">{selectedMaterialForDetail.approvedModelClass || 'UNBOUND'}</span>
              </div>
              <div>
                <span className="text-text-sec block text-[10px]">Approved By</span>
                <span className="font-bold text-text-pri">{selectedMaterialForDetail.approvedBy || 'PENDING'}</span>
              </div>
            </div>

            {/* Lifecycle Progression Stepper */}
            <div className="p-3 bg-panel-raised border border-hairline rounded-sm space-y-2">
              <span className="text-xs-tech font-bold text-text-pri uppercase font-mono block">
                8-Stage Class Onboarding Lifecycle
              </span>
              <div className="grid grid-cols-4 sm:grid-cols-8 gap-1 pt-1">
                {LIFECYCLE_STAGES.map((stage, idx) => {
                  const isCurrent = selectedMaterialForDetail.status === stage;
                  const isPast = LIFECYCLE_STAGES.indexOf(selectedMaterialForDetail.status as any) > idx;

                  return (
                    <button
                      key={stage}
                      type="button"
                      onClick={() => handleLifecycleTransition(selectedMaterialForDetail.materialId, stage)}
                      disabled={actionLoading}
                      className={`p-1.5 rounded text-center border text-[9px] font-mono transition-all ${
                        isCurrent
                          ? 'bg-amber text-black font-bold border-amber'
                          : isPast
                          ? 'bg-teal-950/20 text-status-ok border-status-ok/30'
                          : 'bg-canvas text-text-sec border-hairline hover:text-text-pri'
                      }`}
                    >
                      <span className="block text-[8px] text-text-sec font-normal">#{idx + 1}</span>
                      {stage}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Versioned Package Definitions Section */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between border-b border-hairline pb-1.5">
                <span className="text-xs-tech font-bold text-text-pri uppercase font-mono flex items-center gap-1.5">
                  <PackageCheck className="w-4 h-4 text-amber" />
                  Versioned Packaging & Case Definitions (Section 5.2)
                </span>
                <button
                  type="button"
                  onClick={() => setIsAddPackageModalOpen(true)}
                  className="px-2.5 py-1 text-[10px] font-semibold bg-amber/20 hover:bg-amber/30 text-amber border border-amber/40 rounded-sm transition-colors"
                >
                  + Add Package Definition
                </button>
              </div>

              {selectedMaterialForDetail.packageDefinitions.length === 0 ? (
                <div className="py-4 text-center text-text-sec text-xs-tech font-mono">
                  No historical package definitions recorded.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left font-mono text-xs-tech">
                    <thead>
                      <tr className="border-b border-hairline text-text-sec text-[10px]">
                        <th className="p-1.5">Units/Pkg</th>
                        <th className="p-1.5">Gross Weight</th>
                        <th className="p-1.5">Net Weight</th>
                        <th className="p-1.5">Tolerance</th>
                        <th className="p-1.5">Effective Start</th>
                        <th className="p-1.5">Evidence Source</th>
                        <th className="p-1.5">Approval</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedMaterialForDetail.packageDefinitions.map((pd: PackageDefinitionRecord) => (
                        <tr key={pd.definitionId} className="border-b border-hairline/30">
                          <td className="p-1.5 font-bold text-text-pri">{pd.unitsPerPackage} units</td>
                          <td className="p-1.5">{pd.grossWeightKg ? `${pd.grossWeightKg} kg` : '—'}</td>
                          <td className="p-1.5">{pd.netWeightKg ? `${pd.netWeightKg} kg` : '—'}</td>
                          <td className="p-1.5">±{pd.toleranceRangePct}%</td>
                          <td className="p-1.5 text-text-sec text-[10px]">
                            {pd.effectiveStart ? new Date(pd.effectiveStart).toLocaleDateString() : '—'}
                          </td>
                          <td className="p-1.5 text-text-sec text-[10px]">{pd.evidenceSource}</td>
                          <td className="p-1.5">
                            <span className="px-1.5 py-0.2 rounded text-[9px] bg-teal-950/30 text-status-ok border border-status-ok/30">
                              {pd.approvalStatus}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </Modal>
      )}

      {/* ── Add Package Definition Modal ── */}
      {isAddPackageModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsAddPackageModalOpen(false)}
          title="Register Versioned Packaging Specification"
        >
          <form onSubmit={handleAddPackageDefinition} className="space-y-3 font-mono text-xs-tech">
            <p className="text-[11px] text-text-sec font-sans">
              Per Section 5.2, package definitions are versioned records with effective dates, gross/net weight targets, and tolerance bands rather than mutable pack-size columns.
            </p>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-text-sec block mb-1">Units Per Package *</label>
                <input
                  type="number"
                  min={1}
                  required
                  value={pkgFormData.unitsPerPackage}
                  onChange={(e) => setPkgFormData({ ...pkgFormData, unitsPerPackage: parseInt(e.target.value) || 1 })}
                  className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                />
              </div>

              <div>
                <label className="text-text-sec block mb-1">Tolerance Range (%)</label>
                <input
                  type="number"
                  step="0.5"
                  value={pkgFormData.toleranceRangePct}
                  onChange={(e) => setPkgFormData({ ...pkgFormData, toleranceRangePct: parseFloat(e.target.value) || 5.0 })}
                  className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                />
              </div>

              <div>
                <label className="text-text-sec block mb-1">Gross Weight (kg)</label>
                <input
                  type="number"
                  step="0.1"
                  value={pkgFormData.grossWeightKg}
                  onChange={(e) => setPkgFormData({ ...pkgFormData, grossWeightKg: parseFloat(e.target.value) || 0.0 })}
                  className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                />
              </div>

              <div>
                <label className="text-text-sec block mb-1">Net Weight (kg)</label>
                <input
                  type="number"
                  step="0.1"
                  value={pkgFormData.netWeightKg}
                  onChange={(e) => setPkgFormData({ ...pkgFormData, netWeightKg: parseFloat(e.target.value) || 0.0 })}
                  className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                />
              </div>

              <div>
                <label className="text-text-sec block mb-1">Package Barcode</label>
                <input
                  type="text"
                  placeholder="Optional GTIN-14"
                  value={pkgFormData.packageBarcode}
                  onChange={(e) => setPkgFormData({ ...pkgFormData, packageBarcode: e.target.value })}
                  className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                />
              </div>

              <div>
                <label className="text-text-sec block mb-1">Evidence Source</label>
                <select
                  value={pkgFormData.evidenceSource}
                  onChange={(e) => setPkgFormData({ ...pkgFormData, evidenceSource: e.target.value })}
                  className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                >
                  <option value="MANUFACTURER_SPEC">Manufacturer Spec</option>
                  <option value="CALIBRATED_LOAD_CELL">Calibrated Load Cell Scale</option>
                  <option value="HISTORICAL_AUDIT">Historical Dispatch Audit</option>
                </select>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-hairline">
              <button
                type="button"
                onClick={() => setIsAddPackageModalOpen(false)}
                className="px-3 py-1.5 text-text-sec hover:text-text-pri"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={actionLoading}
                className="px-4 py-1.5 bg-amber hover:bg-amber/90 text-black font-semibold rounded-sm"
              >
                Save Package Version
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ── 4-Step Material Onboarding Wizard Modal ── */}
      {isOnboardModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsOnboardModalOpen(false)}
          title={`Onboard Physical Material — Step ${onboardStep} of 4`}
        >
          <form onSubmit={handleCreateMaterial} className="space-y-4 font-mono text-xs-tech">
            {/* Step Indicators */}
            <div className="grid grid-cols-4 gap-1 border-b border-hairline pb-2 text-[10px]">
              <div className={`p-1 text-center rounded ${onboardStep === 1 ? 'bg-amber text-black font-bold' : 'text-text-sec'}`}>
                1. Identification
              </div>
              <div className={`p-1 text-center rounded ${onboardStep === 2 ? 'bg-amber text-black font-bold' : 'text-text-sec'}`}>
                2. Physical Specs
              </div>
              <div className={`p-1 text-center rounded ${onboardStep === 3 ? 'bg-amber text-black font-bold' : 'text-text-sec'}`}>
                3. Packaging & Scale
              </div>
              <div className={`p-1 text-center rounded ${onboardStep === 4 ? 'bg-amber text-black font-bold' : 'text-text-sec'}`}>
                4. Model & Review
              </div>
            </div>

            {/* Step 1: Identification */}
            {onboardStep === 1 && (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-text-sec block mb-1">SKU / Material Code *</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. MAT-CEM-50KG"
                      value={formData.skuCode}
                      onChange={(e) => setFormData({ ...formData, skuCode: e.target.value })}
                      className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                    />
                  </div>

                  <div>
                    <label className="text-text-sec block mb-1">Material Name *</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Portland Cement (50kg Bag)"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                    />
                  </div>

                  <div>
                    <label className="text-text-sec block mb-1">Category *</label>
                    <select
                      value={formData.category}
                      onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                      className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                    >
                      <option value="STACKED_MATERIAL">Stacked Material (Dense Bags, Rods, Bricks)</option>
                      <option value="BULK_GOODS">Bulk Goods</option>
                      <option value="DISCRETE_PACKAGE">Discrete Package / Carton</option>
                      <option value="CONTAINER">Container / Pallet</option>
                      <option value="HAZARD">Hazardous Material</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-text-sec block mb-1">Deployment Profile *</label>
                    <select
                      value={formData.deploymentProfile}
                      onChange={(e) => setFormData({ ...formData, deploymentProfile: e.target.value })}
                      className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                    >
                      <option value="WAREHOUSE_DISPATCH">Warehouse Dispatch Profile</option>
                      <option value="RETAIL_EXIT">Retail Exit Monitoring Profile</option>
                      <option value="INDUSTRIAL_PERIMETER">Industrial Perimeter Profile</option>
                    </select>
                  </div>

                  <div className="col-span-2">
                    <label className="text-text-sec block mb-1">Formalized Counting Tier (Part W.1) *</label>
                    <select
                      value={formData.countingTier}
                      onChange={(e) => setFormData({ ...formData, countingTier: e.target.value as any })}
                      className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri font-bold text-amber"
                    >
                      <option value="SINGLE_UNIT">SINGLE_UNIT — 1:1 Discrete unit identity mapping (e.g. single item)</option>
                      <option value="PACKAGED_BOX">PACKAGED_BOX — Master carton/case containing N units inside</option>
                      <option value="BULK_MATERIAL">BULK_MATERIAL — Continuous or dense-stacked physical goods (cement, rebar, bricks)</option>
                    </select>
                    <span className="text-[10px] text-text-sec block mt-1">
                      {formData.countingTier === 'SINGLE_UNIT' && 'Zero ambiguity: each physical detected entity corresponds to exactly 1 inventory unit.'}
                      {formData.countingTier === 'PACKAGED_BOX' && 'Eliminates box vs unit ambiguity: counts in boxes and mathematically resolves to total units via package definition.'}
                      {formData.countingTier === 'BULK_MATERIAL' && 'Dense stacks or continuous goods counted via polygonal watershed instance segmentation or load-cell weight delta.'}
                    </span>
                  </div>
                </div>

                <div className="flex justify-end pt-2">
                  <button
                    type="button"
                    onClick={() => setOnboardStep(2)}
                    disabled={!formData.name.trim() || !formData.skuCode.trim()}
                    className="px-4 py-1.5 bg-amber hover:bg-amber/90 text-black font-semibold rounded-sm disabled:opacity-50"
                  >
                    Next: Physical Specs →
                  </button>
                </div>
              </div>
            )}

            {/* Step 2: Physical Specs */}
            {onboardStep === 2 && (
              <div className="space-y-3">
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="text-text-sec block mb-1">Count Unit *</label>
                    <select
                      value={formData.countUnit}
                      onChange={(e) => setFormData({ ...formData, countUnit: e.target.value })}
                      className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                    >
                      <option value="bag">Bag</option>
                      <option value="piece">Piece</option>
                      <option value="sheet">Sheet</option>
                      <option value="tile">Tile</option>
                      <option value="rod">Rod</option>
                      <option value="bundle">Bundle</option>
                      <option value="carton">Carton</option>
                      <option value="pallet">Pallet</option>
                      <option value="layer">Layer</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-text-sec block mb-1">Packaging Form *</label>
                    <select
                      value={formData.packagingType}
                      onChange={(e) => setFormData({ ...formData, packagingType: e.target.value })}
                      className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                    >
                      <option value="stack">Stack</option>
                      <option value="bundle">Bundle</option>
                      <option value="loose_unit">Loose Unit</option>
                      <option value="sealed_case">Sealed Case</option>
                      <option value="pallet">Pallet</option>
                      <option value="sheet">Sheet</option>
                      <option value="rod">Rod</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-text-sec block mb-1">Nominal Weight (kg) *</label>
                    <input
                      type="number"
                      step="0.1"
                      required
                      value={formData.nominalUnitWeightKg}
                      onChange={(e) => setFormData({ ...formData, nominalUnitWeightKg: parseFloat(e.target.value) || 0 })}
                      className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                    />
                  </div>

                  <div>
                    <label className="text-text-sec block mb-1">Length (cm)</label>
                    <input
                      type="number"
                      value={formData.lengthCm}
                      onChange={(e) => setFormData({ ...formData, lengthCm: parseFloat(e.target.value) || 0 })}
                      className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                    />
                  </div>

                  <div>
                    <label className="text-text-sec block mb-1">Width (cm)</label>
                    <input
                      type="number"
                      value={formData.widthCm}
                      onChange={(e) => setFormData({ ...formData, widthCm: parseFloat(e.target.value) || 0 })}
                      className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                    />
                  </div>

                  <div>
                    <label className="text-text-sec block mb-1">Height (cm)</label>
                    <input
                      type="number"
                      value={formData.heightCm}
                      onChange={(e) => setFormData({ ...formData, heightCm: parseFloat(e.target.value) || 0 })}
                      className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                    />
                  </div>
                </div>

                <div className="flex justify-between pt-2">
                  <button
                    type="button"
                    onClick={() => setOnboardStep(1)}
                    className="px-3 py-1.5 text-text-sec hover:text-text-pri"
                  >
                    ← Back
                  </button>
                  <button
                    type="button"
                    onClick={() => setOnboardStep(3)}
                    className="px-4 py-1.5 bg-amber hover:bg-amber/90 text-black font-semibold rounded-sm"
                  >
                    Next: Packaging & Scale →
                  </button>
                </div>
              </div>
            )}

            {/* Step 3: Packaging & Scale */}
            {onboardStep === 3 && (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-text-sec block mb-1">Units Per Primary Package *</label>
                    <input
                      type="number"
                      min={1}
                      required
                      value={formData.unitsPerPackage}
                      onChange={(e) => setFormData({ ...formData, unitsPerPackage: parseInt(e.target.value) || 1 })}
                      className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                    />
                  </div>

                  <div>
                    <label className="text-text-sec block mb-1">Weight Tolerance Range (%)</label>
                    <input
                      type="number"
                      step="0.5"
                      value={formData.weightTolerancePct}
                      onChange={(e) => setFormData({ ...formData, weightTolerancePct: parseFloat(e.target.value) || 5.0 })}
                      className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                    />
                  </div>

                  <div>
                    <label className="text-text-sec block mb-1">Barcode (EAN/GTIN)</label>
                    <input
                      type="text"
                      placeholder="Optional barcode"
                      value={formData.barcode}
                      onChange={(e) => setFormData({ ...formData, barcode: e.target.value })}
                      className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                    />
                  </div>

                  <div>
                    <label className="text-text-sec block mb-1">RFID EPC Prefix</label>
                    <input
                      type="text"
                      placeholder="Optional RFID hex prefix"
                      value={formData.rfidEpcPrefix}
                      onChange={(e) => setFormData({ ...formData, rfidEpcPrefix: e.target.value })}
                      className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                    />
                  </div>
                </div>

                <div className="flex justify-between pt-2">
                  <button
                    type="button"
                    onClick={() => setOnboardStep(2)}
                    className="px-3 py-1.5 text-text-sec hover:text-text-pri"
                  >
                    ← Back
                  </button>
                  <button
                    type="button"
                    onClick={() => setOnboardStep(4)}
                    className="px-4 py-1.5 bg-amber hover:bg-amber/90 text-black font-semibold rounded-sm"
                  >
                    Next: Model & Confirmation →
                  </button>
                </div>
              </div>
            )}

            {/* Step 4: Model & Review */}
            {onboardStep === 4 && (
              <div className="space-y-3">
                <div className="p-3 bg-canvas border border-hairline rounded-sm space-y-1.5">
                  <span className="text-text-pri font-bold block">Summary Review:</span>
                  <p className="text-text-sec text-[11px]">
                    Material: <span className="text-text-pri font-bold">{formData.name}</span> ({formData.skuCode})<br />
                    Profile: <span className="text-text-pri">{formData.deploymentProfile}</span> | Category: <span className="text-text-pri">{formData.category}</span><br />
                    Weight: <span className="text-text-pri">{formData.nominalUnitWeightKg} kg ±{formData.weightTolerancePct}%</span> | Pack: <span className="text-text-pri">{formData.unitsPerPackage} {formData.countUnit}/pkg</span>
                  </p>
                </div>

                <div>
                  <label className="text-text-sec block mb-1">Approved Model Class Identifier</label>
                  <input
                    type="text"
                    placeholder="e.g. cement_bag_50kg (Optional at DRAFT stage)"
                    value={formData.approvedModelClass}
                    onChange={(e) => setFormData({ ...formData, approvedModelClass: e.target.value })}
                    className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                  />
                  <span className="text-[10px] text-text-sec block mt-1">
                    Will be bound during the TRAINING & EVALUATION lifecycle stages.
                  </span>
                </div>

                <div>
                  <label className="text-text-sec block mb-1">Audit Notes / Procurement Rationale</label>
                  <textarea
                    rows={2}
                    placeholder="Notes for compliance and verification..."
                    value={formData.notes}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    className="w-full px-2.5 py-1.5 bg-canvas border border-hairline rounded-sm text-text-pri"
                  />
                </div>

                <div className="flex justify-between pt-2 border-t border-hairline">
                  <button
                    type="button"
                    onClick={() => setOnboardStep(3)}
                    className="px-3 py-1.5 text-text-sec hover:text-text-pri"
                  >
                    ← Back
                  </button>
                  <button
                    type="submit"
                    disabled={actionLoading}
                    className="px-5 py-2 bg-amber hover:bg-amber/90 text-black font-semibold rounded-sm"
                  >
                    Complete Onboarding & Save DRAFT
                  </button>
                </div>
              </div>
            )}
          </form>
        </Modal>
      )}

      {/* ── Two-Stage Defect & Damage Inspection Modal (Part W.3) ── */}
      {isDefectModalOpen && (
        <Modal
          isOpen={isDefectModalOpen}
          onClose={() => {
            setIsDefectModalOpen(false);
            setDefectInspectionResult(null);
          }}
          title="Part W.3 — Two-Stage Defect & Damage Detection Test Bench"
        >
          <div className="space-y-4 max-h-[80vh] overflow-y-auto pr-1 text-xs-tech font-mono">
            <div className="p-3 bg-panel-raised border border-hairline rounded-sm">
              <span className="text-text-pri font-bold block mb-1 font-sans">
                Stage 1 Instance Segmentation + Stage 2 Surface Defect Classifier
              </span>
              <p className="text-text-sec text-[11px] leading-relaxed">
                Reuses Part U instance segmentation boundaries to isolate individual objects, then runs surface-texture defect analysis
                (torn cement bags, cracked tiles, dented cartons, bent iron rods). Defect classification enforces the mandatory
                <strong> &ge; 95% accuracy gate</strong> with honest degradation for ambiguous anomalies.
              </p>
            </div>

            {/* Test Input Preset Selection */}
            <div>
              <label className="text-text-sec block mb-1.5 font-bold">Select Inspection Test Scenario:</label>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setDefectTestPreset('torn_cement');
                    setDefectInspectionResult(null);
                  }}
                  className={`p-2.5 rounded-sm border text-left transition-colors ${
                    defectTestPreset === 'torn_cement'
                      ? 'border-status-crit bg-red-950/30 text-text-pri'
                      : 'border-hairline bg-canvas text-text-sec hover:text-text-pri'
                  }`}
                >
                  <span className="font-bold block text-status-crit">Torn Cement Bag</span>
                  <span className="text-[10px] text-text-sec">Rupture tear & cement powder plume</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setDefectTestPreset('cracked_tile');
                    setDefectInspectionResult(null);
                  }}
                  className={`p-2.5 rounded-sm border text-left transition-colors ${
                    defectTestPreset === 'cracked_tile'
                      ? 'border-status-crit bg-red-950/30 text-text-pri'
                      : 'border-hairline bg-canvas text-text-sec hover:text-text-pri'
                  }`}
                >
                  <span className="font-bold block text-status-crit">Cracked Ceramic Tile</span>
                  <span className="text-[10px] text-text-sec">Penetrating fracture fissure lines</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setDefectTestPreset('intact_box');
                    setDefectInspectionResult(null);
                  }}
                  className={`p-2.5 rounded-sm border text-left transition-colors ${
                    defectTestPreset === 'intact_box'
                      ? 'border-status-ok bg-teal-950/30 text-text-pri'
                      : 'border-hairline bg-canvas text-text-sec hover:text-text-pri'
                  }`}
                >
                  <span className="font-bold block text-status-ok">Intact Corrugated Box</span>
                  <span className="text-[10px] text-text-sec">Clean surface, undamaged corners</span>
                </button>
              </div>
            </div>

            {/* Run Inspection Action */}
            <div className="flex items-center justify-between pt-1">
              <span className="text-text-sec text-[11px]">
                Threshold: <span className="text-amber font-bold">0.95</span> | Auto-alerts to dispatch lane
              </span>
              <button
                type="button"
                onClick={handleRunDefectInspection}
                disabled={defectLoading}
                className="px-4 py-2 bg-amber hover:bg-amber/90 text-black font-semibold rounded-sm transition-colors flex items-center gap-1.5"
              >
                {defectLoading ? 'Analyzing Surface Defects...' : 'Execute Two-Stage Inspection →'}
              </button>
            </div>

            {/* Results Display */}
            {defectInspectionResult && (
              <div className="mt-4 space-y-3 pt-3 border-t border-hairline">
                <div className="flex items-center justify-between p-2.5 bg-canvas border border-hairline rounded-sm">
                  <div>
                    <span className="text-text-sec block text-[10px]">Inspection Summary</span>
                    <span className="font-bold text-text-pri">
                      Examined: {defectInspectionResult.totalInstances} | Defective: {defectInspectionResult.defectiveInstances}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="text-text-sec block text-[10px]">Processing Latency</span>
                    <span className="font-bold text-amber">{defectInspectionResult.latencyMs.toFixed(1)} ms</span>
                  </div>
                </div>

                {defectInspectionResult.alertId && (
                  <div className="p-2.5 bg-red-950/40 border border-status-crit/40 text-status-crit rounded-sm">
                    <span className="font-bold block">Automated Dispatch Alert Triggered</span>
                    <span className="text-[11px]">
                      Alert Record ID: <span className="font-mono text-text-pri">{defectInspectionResult.alertId}</span> has been logged to the central dispatch queue.
                    </span>
                  </div>
                )}



                {/* Defect Item Cards */}
                <div>
                  <label className="text-text-sec block mb-1 text-[11px] font-bold">Inspected Items & Stage 2 Telemetry:</label>
                  <div className="space-y-1.5">
                    {defectInspectionResult.items.map((item, idx) => (
                      <div
                        key={idx}
                        className={`p-2.5 rounded-sm border flex items-center justify-between ${
                          item.isDefective
                            ? 'border-status-crit/40 bg-red-950/20'
                            : item.honestDegradation
                            ? 'border-amber/40 bg-yellow-950/20'
                            : 'border-status-ok/30 bg-teal-950/20'
                        }`}
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-text-pri">{item.className}</span>
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                item.isDefective
                                  ? 'bg-red-900/40 text-status-crit border border-status-crit/40'
                                  : item.honestDegradation
                                  ? 'bg-yellow-900/40 text-amber border border-amber/40'
                                  : 'bg-teal-900/40 text-status-ok border border-status-ok/40'
                              }`}
                            >
                              {item.defectType || "INTACT"}
                            </span>
                          </div>
                          {item.honestDegradation && (
                            <span className="text-[10px] text-amber block mt-0.5">
                              Honest Degradation: {item.degradationReason || 'Borderline anomaly requires operator confirmation'}
                            </span>
                          )}
                        </div>

                        <div className="text-right">
                          <span className="text-text-sec block text-[10px]">Confidence</span>
                          <span
                            className={`font-bold ${
                              item.defectConfidence >= 0.95
                                ? 'text-status-ok'
                                : item.defectConfidence >= 0.6
                                ? 'text-amber'
                                : 'text-text-sec'
                            }`}
                          >
                            {(item.defectConfidence * 100).toFixed(1)}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
};
