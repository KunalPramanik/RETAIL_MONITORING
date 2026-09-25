"""Pydantic Schemas for Real-Time Material Flow, Movement Ledger & Inventory Reconciliation"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, AliasChoices, ConfigDict


class MaterialMovementCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    materialId: str = Field(..., validation_alias=AliasChoices("materialId", "material_id", "sku", "sku_code"))
    transactionType: str = Field("IN", validation_alias=AliasChoices("transactionType", "transaction_type", "type"))
    unitQuantity: Optional[int] = Field(None, validation_alias=AliasChoices("unitQuantity", "unit_quantity", "quantity", "units"))
    packageQuantity: int = Field(0, validation_alias=AliasChoices("packageQuantity", "package_quantity", "boxes", "cases"))
    unitsPerPackage: Optional[int] = Field(None, validation_alias=AliasChoices("unitsPerPackage", "units_per_package", "pack_size"))
    packagingType: Optional[str] = Field(None, validation_alias=AliasChoices("packagingType", "packaging_type"))
    cameraId: Optional[str] = Field(None, validation_alias=AliasChoices("cameraId", "camera_id"))
    zoneId: Optional[str] = Field(None, validation_alias=AliasChoices("zoneId", "zone_id"))
    tripwireId: Optional[str] = Field(None, validation_alias=AliasChoices("tripwireId", "tripwire_id"))
    trackId: Optional[str] = Field(None, validation_alias=AliasChoices("trackId", "track_id"))
    direction: Optional[str] = Field(None, validation_alias=AliasChoices("direction", "movement_direction"))
    personId: Optional[str] = Field(None, validation_alias=AliasChoices("personId", "person_id", "employee_id"))
    personName: Optional[str] = Field(None, validation_alias=AliasChoices("personName", "person_name", "carrier"))
    personIdentityStatus: Optional[str] = Field(None, validation_alias=AliasChoices("personIdentityStatus", "person_identity_status"))
    carrierRelation: str = Field("carrying", validation_alias=AliasChoices("carrierRelation", "carrier_relation"))
    defectStatus: str = Field("NORMAL", validation_alias=AliasChoices("defectStatus", "defect_status"))
    defectSeverity: str = Field("NONE", validation_alias=AliasChoices("defectSeverity", "defect_severity"))
    confidence: float = Field(0.9500, validation_alias=AliasChoices("confidence", "conf"))
    locationId: str = Field("MAIN_WAREHOUSE", validation_alias=AliasChoices("locationId", "location_id"))
    discrepancyReason: Optional[str] = Field(None, validation_alias=AliasChoices("discrepancyReason", "discrepancy_reason"))
    sourceFramePath: Optional[str] = Field(None, validation_alias=AliasChoices("sourceFramePath", "source_frame_path"))


class MaterialMovementResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    ledgerId: str = Field(..., validation_alias=AliasChoices("ledgerId", "ledger_id", "id"))
    transactionType: str = Field(..., validation_alias=AliasChoices("transactionType", "transaction_type"))
    materialId: str = Field(..., validation_alias=AliasChoices("materialId", "material_id"))
    materialName: str = Field(..., validation_alias=AliasChoices("materialName", "material_name"))
    skuCode: str = Field(..., validation_alias=AliasChoices("skuCode", "sku_code"))
    direction: str
    packageQuantity: int = Field(0, validation_alias=AliasChoices("packageQuantity", "package_quantity"))
    unitsPerPackage: int = Field(1, validation_alias=AliasChoices("unitsPerPackage", "units_per_package"))
    unitQuantity: int = Field(..., validation_alias=AliasChoices("unitQuantity", "unit_quantity"))
    packagingType: str = Field("loose_unit", validation_alias=AliasChoices("packagingType", "packaging_type"))
    personId: Optional[str] = Field(None, validation_alias=AliasChoices("personId", "person_id"))
    personName: str = Field("UNKNOWN_PERSON", validation_alias=AliasChoices("personName", "person_name"))
    personIdentityStatus: str = Field("UNKNOWN_PERSON", validation_alias=AliasChoices("personIdentityStatus", "person_identity_status"))
    carrierRelation: str = Field("standalone", validation_alias=AliasChoices("carrierRelation", "carrier_relation"))
    defectStatus: str = Field("NORMAL", validation_alias=AliasChoices("defectStatus", "defect_status"))
    defectSeverity: str = Field("NONE", validation_alias=AliasChoices("defectSeverity", "defect_severity"))
    confidence: float = Field(0.9500, validation_alias=AliasChoices("confidence", "conf"))
    cameraId: Optional[str] = Field(None, validation_alias=AliasChoices("cameraId", "camera_id"))
    zoneId: Optional[str] = Field(None, validation_alias=AliasChoices("zoneId", "zone_id"))
    tripwireId: Optional[str] = Field(None, validation_alias=AliasChoices("tripwireId", "tripwire_id"))
    trackId: Optional[str] = Field(None, validation_alias=AliasChoices("trackId", "track_id"))
    currentStock: Optional[int] = Field(None, validation_alias=AliasChoices("currentStock", "current_stock"))
    timestamp: str


class PersonMovementSummaryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    personIdentifier: str = Field(..., validation_alias=AliasChoices("personIdentifier", "person_identifier"))
    personId: Optional[str] = Field(None, validation_alias=AliasChoices("personId", "person_id"))
    personName: str = Field(..., validation_alias=AliasChoices("personName", "person_name"))
    personIdentityStatus: str = Field(..., validation_alias=AliasChoices("personIdentityStatus", "person_identity_status"))
    totalBroughtIn: int = Field(..., validation_alias=AliasChoices("totalBroughtIn", "total_brought_in"))
    totalTakenOut: int = Field(..., validation_alias=AliasChoices("totalTakenOut", "total_taken_out"))
    netMovementBalance: int = Field(..., validation_alias=AliasChoices("netMovementBalance", "net_movement_balance"))
    materialsBreakdown: Dict[str, Any] = Field(default_factory=dict, validation_alias=AliasChoices("materialsBreakdown", "materials_breakdown"))
    transactionsCount: int = Field(..., validation_alias=AliasChoices("transactionsCount", "transactions_count"))
    transactions: List[Dict[str, Any]] = Field(default_factory=list)


class InventoryBalanceResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    balanceId: str = Field(..., validation_alias=AliasChoices("balanceId", "balance_id"))
    materialId: str = Field(..., validation_alias=AliasChoices("materialId", "material_id"))
    materialName: str = Field(..., validation_alias=AliasChoices("materialName", "material_name"))
    skuCode: str = Field(..., validation_alias=AliasChoices("skuCode", "sku_code"))
    locationId: str = Field(..., validation_alias=AliasChoices("locationId", "location_id"))
    openingStock: int = Field(..., validation_alias=AliasChoices("openingStock", "opening_stock"))
    incomingConfirmed: int = Field(..., validation_alias=AliasChoices("incomingConfirmed", "incoming_confirmed"))
    outgoingConfirmed: int = Field(..., validation_alias=AliasChoices("outgoingConfirmed", "outgoing_confirmed"))
    defectiveStock: int = Field(..., validation_alias=AliasChoices("defectiveStock", "defective_stock"))
    adjustedStock: int = Field(..., validation_alias=AliasChoices("adjustedStock", "adjusted_stock"))
    currentStock: int = Field(..., validation_alias=AliasChoices("currentStock", "current_stock"))
    accountingInvariantValid: bool = Field(True, validation_alias=AliasChoices("accountingInvariantValid", "accounting_invariant_valid"))
    lastReconciledAt: Optional[str] = Field(None, validation_alias=AliasChoices("lastReconciledAt", "last_reconciled_at"))
    lastTransactionId: Optional[str] = Field(None, validation_alias=AliasChoices("lastTransactionId", "last_transaction_id"))
    updatedAt: Optional[str] = Field(None, validation_alias=AliasChoices("updatedAt", "updated_at"))


class InventoryReconciliationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    physicalCounts: Dict[str, int] = Field(..., validation_alias=AliasChoices("physicalCounts", "physical_counts"))
    locationId: str = Field("MAIN_WAREHOUSE", validation_alias=AliasChoices("locationId", "location_id"))
    autoAdjust: bool = Field(False, validation_alias=AliasChoices("autoAdjust", "auto_adjust"))


class InventoryReconciliationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    reconciledAt: str = Field(..., validation_alias=AliasChoices("reconciledAt", "reconciled_at"))
    locationId: str = Field(..., validation_alias=AliasChoices("locationId", "location_id"))
    totalMaterialsAudited: int = Field(..., validation_alias=AliasChoices("totalMaterialsAudited", "total_materials_audited"))
    matchesCount: int = Field(..., validation_alias=AliasChoices("matchesCount", "matches_count"))
    discrepanciesCount: int = Field(..., validation_alias=AliasChoices("discrepanciesCount", "discrepancies_count"))
    totalDiscrepancyMagnitude: int = Field(..., validation_alias=AliasChoices("totalDiscrepancyMagnitude", "total_discrepancy_magnitude"))
    autoAdjustApplied: bool = Field(False, validation_alias=AliasChoices("autoAdjustApplied", "auto_adjust_applied"))
    discrepancies: List[Dict[str, Any]] = Field(default_factory=list)
    matches: List[Dict[str, Any]] = Field(default_factory=list)


class ShelfFileInstanceModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    fileId: str = Field(..., validation_alias=AliasChoices("fileId", "file_id"))
    bbox: List[int]
    confidence: float
    shelfLevel: int = Field(1, validation_alias=AliasChoices("shelfLevel", "shelf_level"))
    spineWidth: int = Field(..., validation_alias=AliasChoices("spineWidth", "spine_width"))
    aspectRatio: float = Field(..., validation_alias=AliasChoices("aspectRatio", "aspect_ratio"))
    colorFamily: str = Field("MULTI_TONE", validation_alias=AliasChoices("colorFamily", "color_family"))
    status: str = "CONFIRMED_VISIBLE"


class DenseShelfCountRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    imageBase64: Optional[str] = Field(None, validation_alias=AliasChoices("imageBase64", "image_base64"))
    cameraId: Optional[str] = Field(None, validation_alias=AliasChoices("cameraId", "camera_id"))
    shelfBbox: Optional[List[int]] = Field(None, validation_alias=AliasChoices("shelfBbox", "shelf_bbox"))
    minConfidence: float = Field(0.70, validation_alias=AliasChoices("minConfidence", "min_confidence"))


class DenseShelfCountResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    shelfDetected: bool = Field(..., validation_alias=AliasChoices("shelfDetected", "shelf_detected"))
    shelfBbox: Optional[List[int]] = Field(None, validation_alias=AliasChoices("shelfBbox", "shelf_bbox"))
    shelfLevelsCount: int = Field(1, validation_alias=AliasChoices("shelfLevelsCount", "shelf_levels_count"))
    totalVisibleFiles: int = Field(..., validation_alias=AliasChoices("totalVisibleFiles", "total_visible_files"))
    fileInstances: List[ShelfFileInstanceModel] = Field(default_factory=list, validation_alias=AliasChoices("fileInstances", "file_instances"))
    rejectedPlanksCount: int = Field(0, validation_alias=AliasChoices("rejectedPlanksCount", "rejected_planks_count"))
    rejectedWallPicturesCount: int = Field(0, validation_alias=AliasChoices("rejectedWallPicturesCount", "rejected_wall_pictures_count"))
    rejectedShadowsCount: int = Field(0, validation_alias=AliasChoices("rejectedShadowsCount", "rejected_shadows_count"))
    latencyMs: float = Field(..., validation_alias=AliasChoices("latencyMs", "latency_ms"))
    summary: str

