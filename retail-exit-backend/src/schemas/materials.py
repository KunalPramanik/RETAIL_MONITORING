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

