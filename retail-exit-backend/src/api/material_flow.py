"""Material Flow, Movement Ledger & Real-Time Inventory Reconciliation API

Implements Master Prompt V9 REST endpoints:
- Movement Ledger listing and atomic transaction recording.
- Person-wise IN vs OUT movement balance and carried material attribution.
- Current on-hand stock and accounting invariant balance checks.
- Discrepancy audits and physical reconciliation.
- Dense bookshelf and file shelf exact instance counting.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import base64
import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload

from src.db.session import get_db
from src.db.models import (
    Material,
    MaterialMovementLedger,
    MaterialInventoryBalance,
    Camera,
    Employee,
    get_utc_now,
)
from src.schemas.material_flow import (
    MaterialMovementCreate,
    MaterialMovementResponse,
    PersonMovementSummaryResponse,
    InventoryBalanceResponse,
    InventoryReconciliationRequest,
    InventoryReconciliationResponse,
    DenseShelfCountRequest,
    DenseShelfCountResponse,
    ShelfFileInstanceModel,
)
from src.engine.inventory_ledger_engine import InventoryLedgerEngine
from src.ml.dense_shelf_counting import DenseShelfCountingService

router = APIRouter(prefix="/materials", tags=["Material Flow & Inventory Ledger"])


def _serialize_ledger_entry(mvl: MaterialMovementLedger, mat: Material, current_stock: Optional[int] = None) -> MaterialMovementResponse:
    return MaterialMovementResponse(
        ledgerId=str(mvl.ledger_id),
        transactionType=str(mvl.transaction_type),
        materialId=str(mvl.material_id),
        materialName=str(mat.name if mat else "Unknown Material"),
        skuCode=str(mat.sku_code if mat else "SKU-UNKNOWN"),
        direction=str(mvl.direction),
        packageQuantity=int(mvl.package_quantity or 0),
        unitsPerPackage=int(mvl.units_per_package or 1),
        unitQuantity=int(mvl.unit_quantity or 0),
        packagingType=str(mvl.packaging_type or "loose_unit"),
        personId=str(mvl.person_id) if mvl.person_id else None,
        personName=str(mvl.person_name or "UNKNOWN_PERSON"),
        personIdentityStatus=str(mvl.person_identity_status or "UNKNOWN_PERSON"),
        carrierRelation=str(mvl.carrier_relation or "standalone"),
        defectStatus=str(mvl.defect_status or "NORMAL"),
        defectSeverity=str(mvl.defect_severity or "NONE"),
        confidence=float(mvl.confidence or 0.9500),
        cameraId=str(mvl.camera_id) if mvl.camera_id else None,
        zoneId=str(mvl.zone_id) if mvl.zone_id else None,
        tripwireId=str(mvl.tripwire_id) if mvl.tripwire_id else None,
        trackId=str(mvl.track_id) if mvl.track_id else None,
        currentStock=current_stock,
        timestamp=mvl.timestamp.isoformat() if mvl.timestamp else get_utc_now().isoformat(),
    )


@router.get("/movement-ledger", response_model=List[MaterialMovementResponse])
async def list_movement_ledger(
    material_id: Optional[str] = Query(None, description="Filter by material ID or SKU"),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type: IN, OUT, ADJUSTMENT, TRANSFER_IN, TRANSFER_OUT, RETURN"),
    direction: Optional[str] = Query(None, description="Filter by direction: ENTRY, EXIT, TRAVERSAL"),
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    person_id: Optional[str] = Query(None, description="Filter by employee/carrier ID"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """Retrieves immutable movement ledger transactions with optional filters."""
    stmt = (
        select(MaterialMovementLedger, Material)
        .join(Material, MaterialMovementLedger.material_id == Material.material_id)
        .order_by(desc(MaterialMovementLedger.timestamp))
    )

    if material_id:
        stmt = stmt.where(
            (MaterialMovementLedger.material_id == material_id)
            | (Material.sku_code == material_id)
        )
    if transaction_type:
        stmt = stmt.where(MaterialMovementLedger.transaction_type == transaction_type.upper().strip())
    if direction:
        stmt = stmt.where(MaterialMovementLedger.direction == direction.upper().strip())
    if camera_id:
        stmt = stmt.where(MaterialMovementLedger.camera_id == camera_id)
    if person_id:
        stmt = stmt.where(
            (MaterialMovementLedger.person_id == person_id)
            | (MaterialMovementLedger.person_name == person_id)
        )

    stmt = stmt.limit(limit).offset(offset)
    res = await session.execute(stmt)
    rows = res.all()

    return [_serialize_ledger_entry(mvl, mat) for mvl, mat in rows]


@router.post("/movement-ledger", response_model=MaterialMovementResponse)
async def record_material_movement(
    body: MaterialMovementCreate,
    session: AsyncSession = Depends(get_db),
):
    """Atomically records a confirmed physical material movement transaction and updates inventory balance."""
    try:
        ledger_entry, balance, _ = await InventoryLedgerEngine.record_confirmed_movement(
            session=session,
            material_id=body.materialId,
            transaction_type=body.transactionType,
            unit_quantity=body.unitQuantity,
            package_quantity=body.packageQuantity,
            units_per_package=body.unitsPerPackage,
            packaging_type=body.packagingType,
            camera_id=body.cameraId,
            zone_id=body.zoneId,
            tripwire_id=body.tripwireId,
            track_id=body.trackId,
            direction=body.direction,
            person_id=body.personId,
            person_name=body.personName,
            person_identity_status=body.personIdentityStatus,
            carrier_relation=body.carrierRelation,
            defect_status=body.defectStatus,
            defect_severity=body.defectSeverity,
            confidence=body.confidence,
            location_id=body.locationId,
            discrepancy_reason=body.discrepancyReason,
            source_frame_path=body.sourceFramePath,
            commit=True,
        )

        mat_res = await session.execute(
            select(Material).where(Material.material_id == ledger_entry.material_id)
        )
        material = mat_res.scalar_one_or_none()

        return _serialize_ledger_entry(ledger_entry, material, current_stock=balance.current_stock)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Failed to record material movement: {str(ex)}")


@router.get("/person-summary/{person_id}", response_model=PersonMovementSummaryResponse)
async def get_person_movement_summary(
    person_id: str = Path(..., description="Employee ID or carrier name"),
    session: AsyncSession = Depends(get_db),
):
    """Retrieves authoritative person-wise IN vs OUT movement balance, carried material history, and net balance."""
    summary = await InventoryLedgerEngine.get_person_movement_summary(
        session=session,
        person_id_or_name=person_id,
    )
    return PersonMovementSummaryResponse(**summary)


@router.get("/inventory-balance", response_model=List[InventoryBalanceResponse])
async def get_inventory_balance(
    material_id: Optional[str] = Query(None, description="Optional material ID or SKU filter"),
    location_id: str = Query("MAIN_WAREHOUSE", description="Storage location identifier"),
    session: AsyncSession = Depends(get_db),
):
    """Retrieves current on-hand stock and ledger balance verified against the accounting invariant."""
    balances = await InventoryLedgerEngine.get_inventory_balance(
        session=session,
        material_id=material_id,
        location_id=location_id,
    )
    return [InventoryBalanceResponse(**b) for b in balances]


@router.post("/inventory-reconciliation", response_model=InventoryReconciliationResponse)
async def reconcile_inventory(
    body: InventoryReconciliationRequest,
    session: AsyncSession = Depends(get_db),
):
    """Compares physical physical counts against ledger stock, flags discrepancies, and optionally auto-adjusts balance."""
    report = await InventoryLedgerEngine.reconcile_inventory(
        session=session,
        physical_counts=body.physicalCounts,
        location_id=body.locationId,
        auto_adjust=body.autoAdjust,
    )
    return InventoryReconciliationResponse(**report)


@router.post("/shelf-dense-count", response_model=DenseShelfCountResponse)
async def count_shelf_files(
    body: DenseShelfCountRequest,
    session: AsyncSession = Depends(get_db),
):
    """Analyzes a bookshelf / file shelf to count exact visible files/books per instance.

    Guarantees:
    - Accurate separation of tightly packed adjacent file spines without merging.
    - Zero fabrication of occluded items behind front files.
    - Rejection of wall pictures, horizontal shelf planks, and shadows.
    """
    frame = None
    if body.imageBase64:
        try:
            clean_b64 = body.imageBase64.split(",")[-1]
            raw_bytes = base64.b64decode(clean_b64)
            nparr = np.frombuffer(raw_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception as _dec_err:
            raise HTTPException(status_code=400, detail="Invalid imageBase64 payload.")
    elif body.cameraId:
        from src.engine.stream_manager import get_latest_frame_bytes, camera_stream_manager

        raw_b = get_latest_frame_bytes(body.cameraId)
        if not raw_b:
            result = await session.execute(select(Camera).where(Camera.camera_id == body.cameraId))
            cam = result.scalar_one_or_none()
            if cam:
                target_path = cam.sub_stream_path if cam.sub_stream_path else cam.rtsp_path
                raw_b, _ = camera_stream_manager.get_latest_jpeg(
                    cam.camera_id,
                    str(cam.ip_address or ""),
                    str(target_path or ""),
                    str(cam.stream_url or "") if cam.stream_url else None,
                    max_wait_sec=0.5,
                )
        if raw_b:
            nparr = np.frombuffer(raw_b, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        raise HTTPException(
            status_code=400,
            detail="Either valid imageBase64 or active cameraId with accessible live frame must be provided.",
        )

    res = DenseShelfCountingService.count_files_on_shelf(
        frame=frame,
        shelf_bbox=body.shelfBbox,
        min_confidence=body.minConfidence,
    )

    models = [
        ShelfFileInstanceModel(
            fileId=inst.file_id,
            bbox=inst.bbox,
            confidence=inst.confidence,
            shelfLevel=inst.shelf_level,
            spineWidth=inst.spine_width,
            aspectRatio=inst.aspect_ratio,
            colorFamily=inst.color_family,
            status=inst.status,
        )
        for inst in res.file_instances
    ]

    return DenseShelfCountResponse(
        shelfDetected=res.shelf_detected,
        shelfBbox=res.shelf_bbox,
        shelfLevelsCount=res.shelf_levels_count,
        totalVisibleFiles=res.total_visible_files,
        fileInstances=models,
        rejectedPlanksCount=res.rejected_planks_count,
        rejectedWallPicturesCount=res.rejected_wall_pictures_count,
        rejectedShadowsCount=res.rejected_shadows_count,
        latencyMs=res.latency_ms,
        summary=res.summary,
    )

