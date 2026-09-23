"""Pydantic Schemas for Dynamic Material Catalog & Versioned Package Definitions per Section 5."""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, AliasChoices, ConfigDict


class PackageDefinitionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    definitionId: str = Field(..., validation_alias=AliasChoices("definitionId", "definition_id", "id"))
    materialId: str = Field(..., validation_alias=AliasChoices("materialId", "material_id"))
    unitsPerPackage: int = Field(..., validation_alias=AliasChoices("unitsPerPackage", "units_per_package"))
    packageBarcode: Optional[str] = Field(None, validation_alias=AliasChoices("packageBarcode", "package_barcode"))
    rfidPrefix: Optional[str] = Field(None, validation_alias=AliasChoices("rfidPrefix", "rfid_prefix"))
    grossWeightKg: Optional[float] = Field(None, validation_alias=AliasChoices("grossWeightKg", "gross_weight_kg"))
    netWeightKg: Optional[float] = Field(None, validation_alias=AliasChoices("netWeightKg", "net_weight_kg"))
    toleranceRangePct: float = Field(5.0, validation_alias=AliasChoices("toleranceRangePct", "tolerance_range_pct"))
    effectiveStart: str = Field(..., validation_alias=AliasChoices("effectiveStart", "effective_start"))
    effectiveEnd: Optional[str] = Field(None, validation_alias=AliasChoices("effectiveEnd", "effective_end"))
    evidenceSource: str = Field("MANUFACTURER_SPEC", validation_alias=AliasChoices("evidenceSource", "evidence_source"))
    approvalStatus: str = Field("APPROVED", validation_alias=AliasChoices("approvalStatus", "approval_status"))
    createdAt: str = Field(..., validation_alias=AliasChoices("createdAt", "created_at"))

    # Dual snake_case access
    @property
    def units_per_package(self) -> int:
        return self.unitsPerPackage

    @property
    def approval_status(self) -> str:
        return self.approvalStatus


class PackageDefinitionCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    unitsPerPackage: int = Field(..., gt=0, validation_alias=AliasChoices("unitsPerPackage", "units_per_package"), description="Units per case, pallet, or bundle")
    packageBarcode: Optional[str] = Field(None, validation_alias=AliasChoices("packageBarcode", "package_barcode"))
    rfidPrefix: Optional[str] = Field(None, validation_alias=AliasChoices("rfidPrefix", "rfid_prefix"))
    grossWeightKg: Optional[float] = Field(None, validation_alias=AliasChoices("grossWeightKg", "gross_weight_kg"))
    netWeightKg: Optional[float] = Field(None, validation_alias=AliasChoices("netWeightKg", "net_weight_kg"))
    toleranceRangePct: float = Field(5.0, ge=0.0, le=50.0, validation_alias=AliasChoices("toleranceRangePct", "tolerance_range_pct", "weight_tolerance_pct"))
    evidenceSource: str = Field("MANUFACTURER_SPEC", validation_alias=AliasChoices("evidenceSource", "evidence_source"), description="Calibration source or spec origin")
    approvalStatus: str = Field("APPROVED", validation_alias=AliasChoices("approvalStatus", "approval_status"))
    approvedBy: Optional[str] = Field(None, validation_alias=AliasChoices("approvedBy", "approved_by"))


class MaterialResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    materialId: str = Field(..., validation_alias=AliasChoices("materialId", "material_id", "id"))
    id: Optional[str] = None
    name: str
    skuCode: str = Field(..., validation_alias=AliasChoices("skuCode", "sku_code", "sku"))
    category: str
    deploymentProfile: str = Field(..., validation_alias=AliasChoices("deploymentProfile", "deployment_profile"))
    countUnit: str = Field(..., validation_alias=AliasChoices("countUnit", "count_unit"))
    packagingType: str = Field(..., validation_alias=AliasChoices("packagingType", "packaging_type"))
    dimensions: Optional[Dict[str, Any]] = None
    nominalUnitWeightKg: Optional[float] = Field(None, validation_alias=AliasChoices("nominalUnitWeightKg", "nominal_unit_weight_kg"))
    nominal_unit_weight_kg: Optional[float] = None
    weightTolerancePct: float = Field(5.0, validation_alias=AliasChoices("weightTolerancePct", "weight_tolerance_pct"))
    weight_tolerance_pct: Optional[float] = 5.0
    lengthM: Optional[float] = Field(None, validation_alias=AliasChoices("lengthM", "length_m"))
    diameterMm: Optional[float] = Field(None, validation_alias=AliasChoices("diameterMm", "diameter_mm"))
    areaSqm: Optional[float] = Field(None, validation_alias=AliasChoices("areaSqm", "area_sqm"))
    volumeCbm: Optional[float] = Field(None, validation_alias=AliasChoices("volumeCbm", "volume_cbm"))
    bundleQuantity: Optional[int] = Field(None, validation_alias=AliasChoices("bundleQuantity", "bundle_quantity"))
    unitsPerPackage: int = Field(1, validation_alias=AliasChoices("unitsPerPackage", "units_per_package"))
    countingTier: str = Field("SINGLE_UNIT", validation_alias=AliasChoices("countingTier", "counting_tier"))
    counting_tier: Optional[str] = "SINGLE_UNIT"
    barcode: Optional[str] = None
    rfidEpcPrefix: Optional[str] = Field(None, validation_alias=AliasChoices("rfidEpcPrefix", "rfid_epc_prefix"))
    visualAttributes: Optional[Dict[str, Any]] = Field(None, validation_alias=AliasChoices("visualAttributes", "visual_attributes"))
    approvedModelClass: Optional[str] = Field(None, validation_alias=AliasChoices("approvedModelClass", "approved_model_class"))
    status: str
    effectiveFrom: str = Field(..., validation_alias=AliasChoices("effectiveFrom", "effective_from"))
    revision: int = 1
    createdBy: str = Field("system", validation_alias=AliasChoices("createdBy", "created_by"))
    approvedBy: Optional[str] = Field(None, validation_alias=AliasChoices("approvedBy", "approved_by"))
    notes: Optional[str] = None
    createdAt: str = Field(..., validation_alias=AliasChoices("createdAt", "created_at"))
    updatedAt: str = Field(..., validation_alias=AliasChoices("updatedAt", "updated_at"))
    packageDefinitions: List[PackageDefinitionResponse] = Field(default=[], validation_alias=AliasChoices("packageDefinitions", "package_definitions"))
    package_definitions: List[PackageDefinitionResponse] = []


class MaterialCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    name: str = Field(..., min_length=1, max_length=255)
    skuCode: Optional[str] = Field(None, validation_alias=AliasChoices("skuCode", "sku", "sku_code"))
    category: str = Field("GENERAL", validation_alias=AliasChoices("category", "material_category"))
    deploymentProfile: str = Field("WAREHOUSE_DISPATCH", validation_alias=AliasChoices("deploymentProfile", "deployment_profile", "profile"))
    countUnit: str = Field("piece", validation_alias=AliasChoices("countUnit", "count_unit"))
    packagingType: str = Field("loose_unit", validation_alias=AliasChoices("packagingType", "packaging_type"))
    countingTier: str = Field("SINGLE_UNIT", validation_alias=AliasChoices("countingTier", "counting_tier"))
    dimensions: Optional[Dict[str, Any]] = None
    nominalUnitWeightKg: Optional[float] = Field(None, validation_alias=AliasChoices("nominalUnitWeightKg", "nominal_unit_weight_kg"))
    weightTolerancePct: float = Field(5.0, ge=0.0, le=50.0, validation_alias=AliasChoices("weightTolerancePct", "weight_tolerance_pct"))
    lengthM: Optional[float] = Field(None, validation_alias=AliasChoices("lengthM", "length_m", "length_mm"))
    diameterMm: Optional[float] = Field(None, validation_alias=AliasChoices("diameterMm", "diameter_mm"))
    areaSqm: Optional[float] = Field(None, validation_alias=AliasChoices("areaSqm", "area_sqm"))
    volumeCbm: Optional[float] = Field(None, validation_alias=AliasChoices("volumeCbm", "volume_cbm"))
    bundleQuantity: Optional[int] = Field(None, validation_alias=AliasChoices("bundleQuantity", "bundle_quantity"))
    unitsPerPackage: int = Field(1, ge=1, validation_alias=AliasChoices("unitsPerPackage", "units_per_package"))
    barcode: Optional[str] = None
    rfidEpcPrefix: Optional[str] = Field(None, validation_alias=AliasChoices("rfidEpcPrefix", "rfid_epc_prefix"))
    visualAttributes: Optional[Dict[str, Any]] = Field(None, validation_alias=AliasChoices("visualAttributes", "visual_attributes"))
    approvedModelClass: Optional[str] = Field(None, validation_alias=AliasChoices("approvedModelClass", "approved_model_class"))
    notes: Optional[str] = None
    createdBy: Optional[str] = Field("operator", validation_alias=AliasChoices("createdBy", "created_by"))


class MaterialUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    name: Optional[str] = None
    category: Optional[str] = None
    deploymentProfile: Optional[str] = Field(None, validation_alias=AliasChoices("deploymentProfile", "deployment_profile"))
    countUnit: Optional[str] = Field(None, validation_alias=AliasChoices("countUnit", "count_unit"))
    packagingType: Optional[str] = Field(None, validation_alias=AliasChoices("packagingType", "packaging_type"))
    countingTier: Optional[str] = Field(None, validation_alias=AliasChoices("countingTier", "counting_tier"))
    dimensions: Optional[Dict[str, Any]] = None
    nominalUnitWeightKg: Optional[float] = Field(None, validation_alias=AliasChoices("nominalUnitWeightKg", "nominal_unit_weight_kg"))
    weightTolerancePct: Optional[float] = Field(None, validation_alias=AliasChoices("weightTolerancePct", "weight_tolerance_pct"))
    lengthM: Optional[float] = Field(None, validation_alias=AliasChoices("lengthM", "length_m"))
    diameterMm: Optional[float] = Field(None, validation_alias=AliasChoices("diameterMm", "diameter_mm"))
    areaSqm: Optional[float] = Field(None, validation_alias=AliasChoices("areaSqm", "area_sqm"))
    volumeCbm: Optional[float] = Field(None, validation_alias=AliasChoices("volumeCbm", "volume_cbm"))
    bundleQuantity: Optional[int] = Field(None, validation_alias=AliasChoices("bundleQuantity", "bundle_quantity"))
    unitsPerPackage: Optional[int] = Field(None, validation_alias=AliasChoices("unitsPerPackage", "units_per_package"))
    barcode: Optional[str] = None
    rfidEpcPrefix: Optional[str] = Field(None, validation_alias=AliasChoices("rfidEpcPrefix", "rfid_epc_prefix"))
    visualAttributes: Optional[Dict[str, Any]] = None
    approvedModelClass: Optional[str] = Field(None, validation_alias=AliasChoices("approvedModelClass", "approved_model_class"))
    notes: Optional[str] = None


class LifecycleTransitionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    targetStatus: str = Field(
        ...,
        validation_alias=AliasChoices("targetStatus", "target_stage", "target_status"),
        description="Target lifecycle state: DRAFT, DATA_COLLECTION, ANNOTATION, TRAINING, EVALUATION, SHADOW, APPROVED, ACTIVE",
    )
    notes: Optional[str] = None
    approvedBy: Optional[str] = Field(None, validation_alias=AliasChoices("approvedBy", "approved_by", "actor"))


class DefectItemResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    instanceIndex: int = Field(..., validation_alias=AliasChoices("instanceIndex", "instance_index"))
    classId: Optional[str] = Field(None, validation_alias=AliasChoices("classId", "class_id"))
    className: str = Field(..., validation_alias=AliasChoices("className", "class_name"))
    bbox: List[int]  # [x, y, w, h]
    polygon: Optional[List[List[int]]] = None
    isDefective: bool = Field(..., validation_alias=AliasChoices("isDefective", "is_defective"))
    defectType: Optional[str] = Field(None, validation_alias=AliasChoices("defectType", "defect_type"))
    defectConfidence: float = Field(0.0, validation_alias=AliasChoices("defectConfidence", "defect_confidence"))
    defectSeverity: str = Field("NONE", validation_alias=AliasChoices("defectSeverity", "defect_severity"))
    honestDegradation: bool = Field(False, validation_alias=AliasChoices("honestDegradation", "honest_degradation"))
    degradationReason: Optional[str] = Field(None, validation_alias=AliasChoices("degradationReason", "degradation_reason"))
    details: Dict[str, Any] = Field(default_factory=dict)


class DefectInspectionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    totalInstances: int = Field(..., validation_alias=AliasChoices("totalInstances", "total_instances"))
    defectiveInstances: int = Field(..., validation_alias=AliasChoices("defectiveInstances", "defective_instances"))
    alertRaised: bool = Field(..., validation_alias=AliasChoices("alertRaised", "alert_raised"))
    alertId: Optional[str] = Field(None, validation_alias=AliasChoices("alertId", "alert_id"))
    latencyMs: float = Field(..., validation_alias=AliasChoices("latencyMs", "latency_ms"))
    items: List[DefectItemResult]


class DefectInspectionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    imageBase64: Optional[str] = Field(None, validation_alias=AliasChoices("imageBase64", "image_base64"))
    targetRoi: Optional[List[int]] = Field(None, validation_alias=AliasChoices("targetRoi", "target_roi"))
    minConfidence: float = Field(0.95, validation_alias=AliasChoices("minConfidence", "min_confidence"))
    materialId: Optional[str] = Field(None, validation_alias=AliasChoices("materialId", "material_id"))


class TierCountResolveRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    materialId: str = Field(..., validation_alias=AliasChoices("materialId", "material_id"))
    rawDetectedCount: int = Field(..., validation_alias=AliasChoices("rawDetectedCount", "raw_detected_count"))
    observedWeightKg: Optional[float] = Field(None, validation_alias=AliasChoices("observedWeightKg", "observed_weight_kg"))
    forceTier: Optional[str] = Field(None, validation_alias=AliasChoices("forceTier", "force_tier"))


class TierCountResolveResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    materialId: str = Field(..., validation_alias=AliasChoices("materialId", "material_id"))
    skuCode: str = Field(..., validation_alias=AliasChoices("skuCode", "sku_code"))
    name: str
    countingTier: str = Field(..., validation_alias=AliasChoices("countingTier", "counting_tier"))
    unitsPerPackage: int = Field(..., validation_alias=AliasChoices("unitsPerPackage", "units_per_package"))
    resolvedTotalUnits: int = Field(..., validation_alias=AliasChoices("resolvedTotalUnits", "resolved_total_units"))
    resolvedPackagesCount: int = Field(..., validation_alias=AliasChoices("resolvedPackagesCount", "resolved_packages_count"))
    formulaApplied: str = Field(..., validation_alias=AliasChoices("formulaApplied", "formula_applied"))
    arithmeticTrace: str = Field(..., validation_alias=AliasChoices("arithmeticTrace", "arithmetic_trace"))
    honestDegradation: bool = Field(False, validation_alias=AliasChoices("honestDegradation", "honest_degradation"))
    notes: Optional[str] = None

