"""Dynamic Material Catalog & Packaging Lifecycle REST API

Governs physical material attributes, packaging definitions, and the 8-stage
onboarding lifecycle.
Zero hardcoding: all operational items are persisted dynamically in the database.
"""

from typing import List, Optional, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from src.db.session import get_db
from src.db.models import Material, PackageDefinition, Alert, get_utc_now
from src.db.audit import log_audit_entry
from src.schemas.materials import (
    MaterialResponse,
    MaterialCreate,
    MaterialUpdate,
    LifecycleTransitionRequest,
    PackageDefinitionResponse,
    PackageDefinitionCreate,
    DefectInspectionRequest,
    DefectInspectionResponse,
    DefectItemResult,
    TierCountResolveRequest,
    TierCountResolveResponse,
)
from src.ml.defect_detection import MaterialDefectService
from src.cache import cache_service
from src.api.deps_auth import require_roles

router = APIRouter(prefix="/materials", tags=["Materials & Packaging Master"])

VALID_LIFECYCLE_STATES = [
    "DRAFT",
    "DATA_COLLECTION",
    "ANNOTATION",
    "TRAINING",
    "EVALUATION",
    "SHADOW",
    "APPROVED",
    "ACTIVE",
]


def _serialize_package_definition(pd: PackageDefinition) -> PackageDefinitionResponse:
    return PackageDefinitionResponse(
        definitionId=str(pd.definition_id),
        materialId=str(pd.material_id),
        unitsPerPackage=int(pd.units_per_package),
        packageBarcode=pd.package_barcode,
        rfidPrefix=pd.rfid_prefix,
        grossWeightKg=float(pd.gross_weight_kg) if pd.gross_weight_kg is not None else None,
        netWeightKg=float(pd.net_weight_kg) if pd.net_weight_kg is not None else None,
        toleranceRangePct=float(pd.tolerance_range_pct or 5.0),
        effectiveStart=pd.effective_start.isoformat() if pd.effective_start else "",
        effectiveEnd=pd.effective_end.isoformat() if pd.effective_end else None,
        evidenceSource=str(pd.evidence_source or "MANUFACTURER_SPEC"),
        approvalStatus=str(pd.approval_status or "APPROVED"),
        createdAt=pd.created_at.isoformat() if pd.created_at else "",
    )


def _serialize_material(m: Material) -> MaterialResponse:
    pkg_defs = [
        _serialize_package_definition(pd)
        for pd in getattr(m, "package_definitions", []) or []
    ]
    return MaterialResponse(
        materialId=str(m.material_id),
        id=str(m.material_id),
        name=str(m.name),
        skuCode=str(m.sku_code),
        category=str(m.category),
        deploymentProfile=str(m.deployment_profile),
        countUnit=str(m.count_unit),
        packagingType=str(m.packaging_type),
        dimensions=m.dimensions or {},
        nominalUnitWeightKg=float(m.nominal_unit_weight_kg) if m.nominal_unit_weight_kg is not None else None,
        nominal_unit_weight_kg=float(m.nominal_unit_weight_kg) if m.nominal_unit_weight_kg is not None else None,
        weightTolerancePct=float(m.weight_tolerance_pct or 5.0),
        weight_tolerance_pct=float(m.weight_tolerance_pct or 5.0),
        lengthM=float(m.length_m) if m.length_m is not None else None,
        diameterMm=float(m.diameter_mm) if m.diameter_mm is not None else None,
        areaSqm=float(m.area_sqm) if m.area_sqm is not None else None,
        volumeCbm=float(m.volume_cbm) if m.volume_cbm is not None else None,
        bundleQuantity=int(m.bundle_quantity) if m.bundle_quantity is not None else None,
        unitsPerPackage=int(m.units_per_package or 1),
        countingTier=str(getattr(m, "counting_tier", "SINGLE_UNIT") or "SINGLE_UNIT"),
        counting_tier=str(getattr(m, "counting_tier", "SINGLE_UNIT") or "SINGLE_UNIT"),
        barcode=m.barcode,
        rfidEpcPrefix=m.rfid_epc_prefix,
        visualAttributes=m.visual_attributes or {},
        approvedModelClass=m.approved_model_class,
        status=str(m.status),
        effectiveFrom=m.effective_from.isoformat() if m.effective_from else "",
        revision=int(m.revision or 1),
        createdBy=str(m.created_by or "system"),
        approvedBy=m.approved_by,
        notes=m.notes,
        createdAt=m.created_at.isoformat() if m.created_at else "",
        updatedAt=m.updated_at.isoformat() if m.updated_at else "",
        packageDefinitions=pkg_defs,
        package_definitions=pkg_defs,
    )


@router.get("", response_model=List[MaterialResponse])
async def list_materials(
    profile: Optional[str] = Query(None, description="Filter by deployment profile"),
    status: Optional[str] = Query(None, description="Filter by lifecycle status"),
    search: Optional[str] = Query(None, description="Search by name, SKU, or barcode"),
    session: AsyncSession = Depends(get_db),
):
    """Retrieves list of registered materials matching active profile and status filters."""
    stmt = select(Material).options(selectinload(Material.package_definitions))

    if profile and profile.upper() != "ALL":
        stmt = stmt.where(Material.deployment_profile == profile.upper())
    if status and status.upper() != "ALL":
        stmt = stmt.where(Material.status == status.upper())
    if search:
        term = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            (Material.name.ilike(term)) | (Material.sku_code.ilike(term)) | (Material.barcode.ilike(term))
        )

    stmt = stmt.order_by(desc(Material.created_at))
    res = await session.execute(stmt)
    materials = res.scalars().all()
    return [_serialize_material(m) for m in materials]


@router.post("", response_model=MaterialResponse, status_code=201)
async def create_material(
    body: MaterialCreate,
    session: AsyncSession = Depends(get_db),
):
    """Dynamically creates a new material class record."""
    import uuid
    sku = (body.skuCode or f"SKU-{uuid.uuid4().hex[:8]}").strip().upper()
    
    # Check for duplicate SKU
    stmt = select(Material).where(Material.sku_code == sku)
    res = await session.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Material with SKU '{sku}' already exists.")

    now = get_utc_now()
    material = Material(
        name=body.name.strip(),
        sku_code=sku,
        category=body.category.strip().upper(),
        deployment_profile=body.deploymentProfile.strip().upper(),
        count_unit=body.countUnit.strip().lower(),
        packaging_type=body.packagingType.strip().lower(),
        counting_tier=(body.countingTier or "SINGLE_UNIT").strip().upper(),
        dimensions=body.dimensions,
        nominal_unit_weight_kg=body.nominalUnitWeightKg,
        weight_tolerance_pct=body.weightTolerancePct,
        length_m=body.lengthM,
        diameter_mm=body.diameterMm,
        area_sqm=body.areaSqm,
        volume_cbm=body.volumeCbm,
        bundle_quantity=body.bundleQuantity,
        units_per_package=body.unitsPerPackage,
        barcode=body.barcode,
        rfid_epc_prefix=body.rfidEpcPrefix,
        visual_attributes=body.visualAttributes,
        approved_model_class=body.approvedModelClass,
        status="DRAFT",
        effective_from=now,
        revision=1,
        created_by=body.createdBy or "operator",
        notes=body.notes,
        created_at=now,
        updated_at=now,
    )
    session.add(material)
    await session.flush()

    # Create initial baseline PackageDefinition
    base_pkg = PackageDefinition(
        material_id=material.material_id,
        units_per_package=body.unitsPerPackage,
        package_barcode=body.barcode,
        rfid_prefix=body.rfidEpcPrefix,
        gross_weight_kg=(body.nominalUnitWeightKg * body.unitsPerPackage) if body.nominalUnitWeightKg else None,
        net_weight_kg=(body.nominalUnitWeightKg * body.unitsPerPackage) if body.nominalUnitWeightKg else None,
        tolerance_range_pct=body.weightTolerancePct,
        effective_start=now,
        evidence_source="ONBOARDING_INITIAL",
        approval_status="APPROVED",
        created_at=now,
    )
    session.add(base_pkg)
    await session.flush()

    await log_audit_entry(
        session=session,
        entity_type="MATERIAL",
        entity_id=str(material.material_id),
        action="CREATE_MATERIAL_DRAFT",
        actor_type="USER",
        before_state=None,
        after_state=body.model_dump(),
    )
    await session.commit()

    # Re-fetch with loaded relationship
    stmt = select(Material).options(selectinload(Material.package_definitions)).where(Material.material_id == material.material_id)
    res = await session.execute(stmt)
    created = res.scalar_one()

    await cache_service.invalidate("materials")
    return _serialize_material(created)


@router.get("/{material_id}", response_model=MaterialResponse)
async def get_material(
    material_id: str = Path(..., description="UUID or SKU code"),
    session: AsyncSession = Depends(get_db),
):
    """Fetches full material record and package definition revision history."""
    stmt = (
        select(Material)
        .options(selectinload(Material.package_definitions))
        .where((Material.material_id == material_id) | (Material.sku_code == material_id.upper()))
    )
    res = await session.execute(stmt)
    material = res.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail=f"Material '{material_id}' not found.")
    return _serialize_material(material)


@router.put("/{material_id}", response_model=MaterialResponse)
async def update_material(
    material_id: str,
    body: MaterialUpdate,
    session: AsyncSession = Depends(get_db),
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Updates material physical attributes, increments revision, and logs audit record."""
    stmt = select(Material).options(selectinload(Material.package_definitions)).where(Material.material_id == material_id)
    res = await session.execute(stmt)
    material = res.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail=f"Material '{material_id}' not found.")

    before_state = {
        "name": material.name,
        "category": material.category,
        "nominalUnitWeightKg": float(material.nominal_unit_weight_kg) if material.nominal_unit_weight_kg else None,
        "revision": material.revision,
    }

    if body.name is not None:
        material.name = body.name.strip()
    if body.category is not None:
        material.category = body.category.strip().upper()
    if body.deploymentProfile is not None:
        material.deployment_profile = body.deploymentProfile.strip().upper()
    if body.countUnit is not None:
        material.count_unit = body.countUnit.strip().lower()
    if body.packagingType is not None:
        material.packaging_type = body.packagingType.strip().lower()
    if body.countingTier is not None:
        material.counting_tier = body.countingTier.strip().upper()
    if body.dimensions is not None:
        material.dimensions = body.dimensions
    if body.nominalUnitWeightKg is not None:
        material.nominal_unit_weight_kg = body.nominalUnitWeightKg
    if body.weightTolerancePct is not None:
        material.weight_tolerance_pct = body.weightTolerancePct
    if body.lengthM is not None:
        material.length_m = body.lengthM
    if body.diameterMm is not None:
        material.diameter_mm = body.diameterMm
    if body.areaSqm is not None:
        material.area_sqm = body.areaSqm
    if body.volumeCbm is not None:
        material.volume_cbm = body.volumeCbm
    if body.bundleQuantity is not None:
        material.bundle_quantity = body.bundleQuantity
    if body.unitsPerPackage is not None:
        material.units_per_package = body.unitsPerPackage
    if body.barcode is not None:
        material.barcode = body.barcode
    if body.rfidEpcPrefix is not None:
        material.rfid_epc_prefix = body.rfidEpcPrefix
    if body.visualAttributes is not None:
        material.visual_attributes = body.visualAttributes
    if body.approvedModelClass is not None:
        material.approved_model_class = body.approvedModelClass
    if body.notes is not None:
        material.notes = body.notes

    material.revision = (material.revision or 1) + 1
    material.updated_at = get_utc_now()

    await log_audit_entry(
        session=session,
        entity_type="MATERIAL",
        entity_id=str(material.material_id),
        action="UPDATE_MATERIAL_ATTRIBUTES",
        actor_type="USER",
        before_state=before_state,
        after_state=body.model_dump(exclude_unset=True),
    )
    await session.commit()
    await cache_service.invalidate("materials")
    return _serialize_material(material)


@router.post("/{material_id}/lifecycle", response_model=MaterialResponse)
async def transition_lifecycle(
    material_id: str,
    body: LifecycleTransitionRequest,
    session: AsyncSession = Depends(get_db),
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Transitions a material through the 8-stage lifecycle:
    DRAFT -> DATA_COLLECTION -> ANNOTATION -> TRAINING -> EVALUATION -> SHADOW -> APPROVED -> ACTIVE.
    """
    target = body.targetStatus.strip().upper()
    if target not in VALID_LIFECYCLE_STATES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target lifecycle state '{target}'. Must be one of {VALID_LIFECYCLE_STATES}.",
        )

    stmt = select(Material).options(selectinload(Material.package_definitions)).where(Material.material_id == material_id)
    res = await session.execute(stmt)
    material = res.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail=f"Material '{material_id}' not found.")

    current = material.status
    if current == target:
        return _serialize_material(material)

    # State machine transition rules
    allowed_transitions = {
        "DRAFT": {"DATA_COLLECTION"},
        "DATA_COLLECTION": {"ANNOTATION", "DRAFT"},
        "ANNOTATION": {"TRAINING", "DATA_COLLECTION"},
        "TRAINING": {"EVALUATION", "ANNOTATION"},
        "EVALUATION": {"SHADOW", "TRAINING"},
        "SHADOW": {"APPROVED", "EVALUATION"},
        "APPROVED": {"ACTIVE", "SHADOW"},
        "ACTIVE": {"SHADOW"},
    }

    if target not in allowed_transitions.get(current, set()):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid lifecycle transition from '{current}' to '{target}'.",
        )

    # Prerequisite verification
    if target == "ACTIVE" and current not in ("APPROVED", "SHADOW"):
        raise HTTPException(
            status_code=422,
            detail=f"Cannot activate material '{material.sku_code}' directly from '{current}'. Must reach 'APPROVED' or 'SHADOW' first.",
        )

    before_state = {"status": current, "approvedBy": material.approved_by}

    material.status = target
    if target == "APPROVED" or target == "ACTIVE":
        material.approved_by = body.approvedBy or "supervisor"
    material.updated_at = get_utc_now()

    await log_audit_entry(
        session=session,
        entity_type="MATERIAL",
        entity_id=str(material.material_id),
        action=f"LIFECYCLE_TRANSITION_{current}_TO_{target}",
        actor_type="USER",
        before_state=before_state,
        after_state={"status": target, "notes": body.notes, "approvedBy": material.approved_by},
    )
    await session.commit()
    await cache_service.invalidate("materials")
    return _serialize_material(material)


@router.post("/{material_id}/package-definitions", response_model=PackageDefinitionResponse, status_code=201)
async def add_package_definition(
    material_id: str,
    body: PackageDefinitionCreate,
    session: AsyncSession = Depends(get_db),
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Adds a new versioned packaging or bundle specification."""
    stmt = select(Material).where(Material.material_id == material_id)
    res = await session.execute(stmt)
    material = res.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail=f"Material '{material_id}' not found.")

    now = get_utc_now()
    pkg_def = PackageDefinition(
        material_id=material.material_id,
        units_per_package=body.unitsPerPackage,
        package_barcode=body.packageBarcode,
        rfid_prefix=body.rfidPrefix,
        gross_weight_kg=body.grossWeightKg,
        net_weight_kg=body.netWeightKg,
        tolerance_range_pct=body.toleranceRangePct,
        effective_start=now,
        evidence_source=body.evidenceSource,
        approval_status="APPROVED",
        created_at=now,
    )
    session.add(pkg_def)
    await session.flush()

    # Update material's primary unitsPerPackage if helpful
    material.units_per_package = body.unitsPerPackage
    material.updated_at = now

    await log_audit_entry(
        session=session,
        entity_type="PACKAGE_DEFINITION",
        entity_id=str(pkg_def.definition_id),
        action="CREATE_PACKAGE_DEFINITION",
        actor_type="USER",
        before_state=None,
        after_state=body.model_dump(),
    )
    await session.commit()
    await cache_service.invalidate("materials")
    return _serialize_package_definition(pkg_def)


@router.delete("/{material_id}", status_code=204)
async def delete_material(
    material_id: str,
    session: AsyncSession = Depends(get_db),
    _role: str = Depends(require_roles(["ADMIN"])),
):
    """Deletes or soft-deactivates an unverified material record."""
    stmt = select(Material).where(Material.material_id == material_id)
    res = await session.execute(stmt)
    material = res.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail=f"Material '{material_id}' not found.")

    await log_audit_entry(
        session=session,
        entity_type="MATERIAL",
        entity_id=str(material.material_id),
        action="DELETE_MATERIAL",
        actor_type="USER",
        before_state={"sku_code": material.sku_code, "name": material.name},
        after_state=None,
    )
    await session.delete(material)
    await session.commit()
    await cache_service.invalidate("materials")
    return None


@router.post("/defect-inspect", response_model=DefectInspectionResponse)
async def inspect_material_defects(
    body: DefectInspectionRequest,
    session: AsyncSession = Depends(get_db),
):
    """Executes two-stage defect and damage detection on an image."""
    import base64
    import cv2
    import numpy as np

    if not body.imageBase64:
        raise HTTPException(status_code=400, detail="imageBase64 is required for defect inspection.")

    try:
        raw_b64 = body.imageBase64
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        img_bytes = base64.b64decode(raw_b64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None or frame.size == 0:
            raise ValueError("Decoded image is empty or invalid format.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to decode image: {e}")

    # Run two-stage inspection
    result = MaterialDefectService.inspect_frame_defects(
        frame=frame,
        target_roi=body.targetRoi,
        min_confidence=body.minConfidence,
    )

    alert_id = None
    if result.alert_triggered:
        import uuid
        now = get_utc_now()
        alert_id = f"alt_def_{uuid.uuid4().hex[:8]}"
        severity = "HIGH" if result.critical_defects_count > 0 else "MEDIUM"
        alert = Alert(
            alert_id=alert_id,
            camera_id=None,
            event_id=None,
            alert_type="MATERIAL_DEFECT",
            severity=severity,
            delta_units=result.defective_instances,
            status="OPEN",
            resolution_note=f"Automated Defect Detection: {result.defective_instances} damaged instances identified with >= {int(body.minConfidence * 100)}% confidence.",
            created_at=now,
        )
        session.add(alert)
        await session.commit()

    items = [
        DefectItemResult(
            instanceIndex=inst.instance_index,
            classId=inst.class_id,
            className=inst.class_name,
            bbox=inst.bbox,
            polygon=inst.polygon,
            isDefective=inst.is_defective,
            defectType=inst.defect_type,
            defectConfidence=inst.defect_confidence,
            defectSeverity=inst.defect_severity,
            honestDegradation=inst.honest_degradation,
            degradationReason=inst.degradation_reason,
            details=inst.defect_details,
        )
        for inst in result.instances
    ]

    return DefectInspectionResponse(
        totalInstances=result.total_instances,
        defectiveInstances=result.defective_instances,
        alertRaised=result.alert_triggered,
        alertId=alert_id,
        latencyMs=result.latency_ms,
        items=items,
    )


@router.post("/{material_id}/resolve-tier-count", response_model=TierCountResolveResponse)
async def resolve_tier_count(
    material_id: str,
    body: TierCountResolveRequest,
    session: AsyncSession = Depends(get_db),
):
    """Resolves raw detected counts to exact, unambiguous inventory units based on counting tier."""
    stmt = (
        select(Material)
        .options(selectinload(Material.package_definitions))
        .where((Material.material_id == material_id) | (Material.sku_code == material_id))
    )
    res = await session.execute(stmt)
    material = res.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail=f"Material '{material_id}' not found.")

    tier = (body.forceTier or material.counting_tier or "SINGLE_UNIT").strip().upper()
    units_per_pkg = int(material.units_per_package or 1)

    # Find active package definition if available
    if material.package_definitions:
        for pd in material.package_definitions:
            if pd.approval_status == "APPROVED" and pd.effective_end is None:
                units_per_pkg = int(pd.units_per_package)
                break

    resolved_units = 0
    resolved_packages = 0
    formula = ""
    trace = ""
    honest_degradation = False
    notes = None

    if tier == "SINGLE_UNIT":
        resolved_units = max(0, body.rawDetectedCount)
        resolved_packages = resolved_units
        formula = "resolved_units = raw_count"
        trace = f"{body.rawDetectedCount} units detected (1:1 single unit identity mapping)"
    elif tier == "PACKAGED_BOX":
        resolved_packages = max(0, body.rawDetectedCount)
        resolved_units = resolved_packages * units_per_pkg
        formula = f"resolved_units = raw_boxes * units_per_package ({units_per_pkg})"
        trace = f"{resolved_packages} boxes detected @ {units_per_pkg} units/box = {resolved_units} total units"
    elif tier == "BULK_MATERIAL":
        nominal_wt = float(material.nominal_unit_weight_kg) if material.nominal_unit_weight_kg else None
        if body.observedWeightKg is not None and nominal_wt and nominal_wt > 0:
            resolved_units = max(0, int(round(body.observedWeightKg / nominal_wt)))
            resolved_packages = 1
            formula = f"resolved_units = round(observed_weight_kg / nominal_unit_weight_kg [{nominal_wt:.2f}])"
            trace = f"Observed weight {body.observedWeightKg:.2f} kg / {nominal_wt:.2f} kg/unit = {resolved_units} units"
        else:
            resolved_units = max(0, body.rawDetectedCount)
            resolved_packages = 1
            formula = "resolved_units = segmented_instance_count"
            trace = f"{body.rawDetectedCount} bulk instances segmented via polygonal mask analysis"
            if nominal_wt is None and body.observedWeightKg is not None:
                honest_degradation = True
                notes = "Material missing nominal_unit_weight_kg; fell back to raw vision count"
    else:
        resolved_units = max(0, body.rawDetectedCount)
        resolved_packages = resolved_units
        formula = "fallback: 1:1"
        trace = f"Unrecognized tier '{tier}'; defaulted to 1:1 unit count"

    return TierCountResolveResponse(
        materialId=str(material.material_id),
        skuCode=str(material.sku_code),
        name=str(material.name),
        countingTier=tier,
        unitsPerPackage=units_per_pkg,
        resolvedTotalUnits=resolved_units,
        resolvedPackagesCount=resolved_packages,
        formulaApplied=formula,
        arithmeticTrace=trace,
        honestDegradation=honest_degradation,
        notes=notes,
    )
