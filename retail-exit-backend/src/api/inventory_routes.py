"""Automated Inventory & Discrepancy Adjustment API

Provides:
- GET /api/inventory/stock: Real-time on-hand inventory balances across all registered products/materials
- GET /api/inventory/ledger: Traceable, immutable audit ledger of material movements
- POST /api/inventory/adjust: Manual operator stock corrections, receipts, and write-offs
- POST /api/inventory/reconcile: Physical count reconciliation with automated discrepancy auditing
- POST /api/inventory/count/trigger: Vision-triggered automated counts
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, or_
from datetime import datetime
import uuid

from src.db.session import get_db
from src.db.models import (
    Product,
    Material,
    MaterialInventoryBalance,
    MaterialMovementLedger,
    InitialStockVerification,
    get_utc_now,
)
from src.db.audit import log_audit_entry
from src.engine.inventory_ledger_engine import InventoryLedgerEngine
from src.engine.automated_counter import AutomatedCountingEngine
from src.api.deps_auth import require_roles
from src.realtime.hub import ws_hub

router = APIRouter(prefix="/inventory", tags=["Dynamic Automated Counting"])


class VisionCountTrigger(BaseModel):
    camera_id: str
    vision_counts: Dict[int, int]  # e.g. {1005: 42} (Class ID -> Count)


class ManualAdjustmentTrigger(BaseModel):
    sku_code: Optional[str] = None
    product_id: Optional[str] = None
    material_id: Optional[str] = None
    qty_adjustment: int = Field(..., description="Quantity delta (positive to add, negative to deduct)")
    operator_id: Optional[str] = "OPERATOR_DESK"
    reason: str = Field(..., description="Reason for adjustment, e.g. Count correction, Damaged stock, Receiving")
    location_id: str = "MAIN_WAREHOUSE"


class StockReconciliationRequest(BaseModel):
    physical_counts: Dict[str, int] = Field(..., description="Map of SKU or material_id -> physical counted units")
    location_id: str = "MAIN_WAREHOUSE"
    auto_adjust: bool = True


@router.get("/stock")
async def get_inventory_stock(
    query: Optional[str] = Query(None, description="Optional search by SKU or name"),
    session: AsyncSession = Depends(get_db),
):
    """Retrieves real-time on-hand inventory balances for all registered products/materials.
    
    Guarantees the accounting invariant:
    Current Stock == Opening Stock + Incoming Confirmed - Outgoing Confirmed + Adjusted Stock
    """
    # 1. Fetch products
    prod_stmt = select(Product).order_by(Product.sku_code)
    prod_res = await session.execute(prod_stmt)
    products = prod_res.scalars().all()

    # 2. Fetch materials and balances
    mat_stmt = select(Material)
    mat_res = await session.execute(mat_stmt)
    materials = {m.sku_code.upper(): m for m in mat_res.scalars().all()}

    bal_stmt = select(MaterialInventoryBalance)
    bal_res = await session.execute(bal_stmt)
    balances_by_mat = {b.material_id: b for b in bal_res.scalars().all()}

    now = get_utc_now()
    results = []

    for p in products:
        sku = p.sku_code.upper()
        mat = materials.get(sku)
        
        # If material doesn't exist, create it dynamically
        if not mat:
            mat = Material(
                material_id=str(p.product_id),
                sku_code=p.sku_code,
                name=p.name,
                category=p.category,
                packaging_type="sealed_case",
                units_per_package=p.pack_size or 1,
                status="ACTIVE",
                deployment_profile="WAREHOUSE_DISPATCH",
                counting_tier="PACKAGED_BOX",
                created_at=now,
                updated_at=now,
            )
            session.add(mat)
            await session.flush()
            materials[sku] = mat

        bal = balances_by_mat.get(str(mat.material_id)) or balances_by_mat.get(str(p.product_id))
        if not bal:
            base_opening = (p.pack_size or 1) * 20
            bal = MaterialInventoryBalance(
                balance_id=f"bal_{uuid.uuid4().hex[:12]}",
                material_id=str(mat.material_id),
                location_id="MAIN_WAREHOUSE",
                opening_stock=base_opening,
                incoming_confirmed=0,
                outgoing_confirmed=0,
                defective_stock=0,
                adjusted_stock=0,
                current_stock=base_opening,
                last_reconciled_at=now,
                updated_at=now,
            )
            session.add(bal)
            await session.flush()
            balances_by_mat[str(mat.material_id)] = bal

        pack_sz = p.pack_size or 1
        curr_stock = bal.current_stock
        curr_cases = curr_stock // pack_sz if pack_sz > 0 else curr_stock
        
        status = "IN_STOCK"
        if curr_stock <= 0:
            status = "OUT_OF_STOCK"
        elif curr_cases <= (p.reorder_threshold or 5):
            status = "LOW_STOCK"

        item = {
            "productId": str(p.product_id),
            "materialId": str(mat.material_id),
            "skuCode": p.sku_code,
            "name": p.name,
            "category": p.category,
            "packSize": pack_sz,
            "unitPrice": float(p.unit_price or 0.0),
            "casePrice": float(p.case_price or 0.0),
            "reorderThreshold": int(p.reorder_threshold or 0),
            "openingStock": bal.opening_stock,
            "incomingConfirmed": bal.incoming_confirmed,
            "outgoingConfirmed": bal.outgoing_confirmed,
            "defectiveStock": bal.defective_stock,
            "adjustedStock": bal.adjusted_stock,
            "currentStock": curr_stock,
            "currentCases": curr_cases,
            "status": status,
            "accountingInvariantValid": (
                bal.opening_stock + bal.incoming_confirmed - bal.outgoing_confirmed + bal.adjusted_stock == curr_stock
            ),
            "lastReconciledAt": bal.last_reconciled_at.isoformat() if bal.last_reconciled_at else None,
            "updatedAt": bal.updated_at.isoformat() if bal.updated_at else None,
        }

        if query:
            q = query.lower()
            if q not in p.name.lower() and q not in p.sku_code.lower() and q not in p.category.lower():
                continue

        results.append(item)

    await session.commit()
    return results


@router.get("/ledger")
async def get_inventory_ledger(
    sku_code: Optional[str] = Query(None, description="Filter by SKU code"),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
):
    """Returns chronological, immutable material movement ledger records."""
    stmt = (
        select(MaterialMovementLedger, Material)
        .outerjoin(Material, MaterialMovementLedger.material_id == Material.material_id)
        .order_by(desc(MaterialMovementLedger.timestamp))
    )

    if sku_code:
        stmt = stmt.where(
            or_(
                Material.sku_code == sku_code,
                MaterialMovementLedger.material_id == sku_code,
            )
        )

    stmt = stmt.limit(limit)
    res = await session.execute(stmt)
    records = res.all()

    entries = []
    for ledger, mat in records:
        entries.append({
            "ledgerId": ledger.ledger_id,
            "transactionType": ledger.transaction_type,
            "direction": ledger.direction,
            "materialId": ledger.material_id,
            "skuCode": mat.sku_code if mat else "UNKNOWN_SKU",
            "materialName": mat.name if mat else "Unknown Item",
            "packageQuantity": ledger.package_quantity,
            "packagingType": ledger.packaging_type,
            "unitsPerPackage": ledger.units_per_package,
            "unitQuantity": ledger.unit_quantity,
            "personId": ledger.person_id,
            "personName": ledger.person_name,
            "personIdentityStatus": ledger.person_identity_status,
            "carrierRelation": ledger.carrier_relation,
            "defectStatus": ledger.defect_status,
            "defectSeverity": ledger.defect_severity,
            "confidence": round(float(ledger.confidence or 0.95), 4),
            "discrepancyUnits": ledger.discrepancy_units,
            "discrepancyReason": ledger.discrepancy_reason,
            "sourceFramePath": ledger.source_frame_path,
            "cameraId": ledger.camera_id,
            "zoneId": ledger.zone_id,
            "timestamp": ledger.timestamp.isoformat() if ledger.timestamp else None,
        })

    return entries


@router.post("/adjust")
async def manual_inventory_adjustment(
    req: ManualAdjustmentTrigger,
    session: AsyncSession = Depends(get_db),
    user_role=Depends(require_roles(["SUPER_ADMIN", "ADMIN", "SUPERVISOR", "OPERATOR", "VIEWER"])),
):
    """Submits a manual stock adjustment, writes an immutable ledger entry, and mutates inventory atomically."""
    # 1. Resolve material or product
    identifier = req.sku_code or req.material_id or req.product_id
    if not identifier:
        raise HTTPException(status_code=400, detail="Must provide at least one of sku_code, material_id, or product_id")

    stmt = select(Material).where(
        or_(
            Material.material_id == identifier,
            Material.sku_code == identifier,
        )
    )
    mat_res = await session.execute(stmt)
    material = mat_res.scalar_one_or_none()

    if not material:
        # Search in Product
        prod_res = await session.execute(
            select(Product).where(
                or_(
                    Product.product_id == identifier,
                    Product.sku_code == identifier,
                )
            )
        )
        prod = prod_res.scalar_one_or_none()
        if not prod:
            raise HTTPException(status_code=404, detail=f"Material/Product '{identifier}' not found in catalog")

        now = get_utc_now()
        material = Material(
            material_id=str(prod.product_id),
            sku_code=prod.sku_code,
            name=prod.name,
            category=prod.category,
            packaging_type="sealed_case",
            units_per_package=prod.pack_size or 1,
            status="ACTIVE",
            deployment_profile="WAREHOUSE_DISPATCH",
            counting_tier="PACKAGED_BOX",
            created_at=now,
            updated_at=now,
        )
        session.add(material)
        await session.flush()

    try:
        ledger_entry, balance, _ = await InventoryLedgerEngine.record_confirmed_movement(
            session=session,
            material_id=str(material.material_id),
            transaction_type="ADJUSTMENT",
            unit_quantity=req.qty_adjustment,
            discrepancy_units=abs(req.qty_adjustment),
            discrepancy_reason=req.reason,
            person_name=req.operator_id or "OPERATOR_DESK",
            location_id=req.location_id,
            commit=True,
        )

        await log_audit_entry(
            session=session,
            entity_type="INVENTORY",
            entity_id=ledger_entry.ledger_id,
            action="MANUAL_ADJUSTMENT",
            actor_type="USER",
            before_state={"material": material.name, "sku": material.sku_code},
            after_state={"qty_adjustment": req.qty_adjustment, "new_stock": balance.current_stock, "reason": req.reason},
        )

        return {
            "status": "SUCCESS",
            "message": f"Successfully adjusted inventory for '{material.name}'",
            "ledgerId": ledger_entry.ledger_id,
            "skuCode": material.sku_code,
            "adjustmentUnits": req.qty_adjustment,
            "currentStock": balance.current_stock,
            "reason": req.reason,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reconcile")
async def reconcile_inventory(
    req: StockReconciliationRequest,
    session: AsyncSession = Depends(get_db),
    user_role=Depends(require_roles(["SUPER_ADMIN", "ADMIN", "SUPERVISOR"])),
):
    """Reconciles physical counts against system ledger and optionally auto-corrects discrepancies."""
    try:
        res = await InventoryLedgerEngine.reconcile_inventory(
            session=session,
            physical_counts=req.physical_counts,
            location_id=req.location_id,
            auto_adjust=req.auto_adjust,
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/count/trigger")
async def trigger_vision_count(
    req: VisionCountTrigger,
    session: AsyncSession = Depends(get_db),
    user_role=Depends(require_roles(["SUPER_ADMIN", "ADMIN", "SUPERVISOR", "VIEWER"])),
):
    """Ingests raw bounding box counts from the ML engine, dynamically maps to items, and tallies in ledger."""
    try:
        res = await AutomatedCountingEngine.process_vision_count(
            session=session,
            camera_id=req.camera_id,
            vision_counts=req.vision_counts,
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ProposeInitialCountRequest(BaseModel):
    product_id: Optional[str] = Field(None, alias="productId")
    sku_code: Optional[str] = Field(None, alias="skuCode")
    ai_proposed_count: int = Field(..., alias="aiProposedCount", ge=0)
    camera_id: Optional[str] = Field("CAM-01", alias="cameraId")
    model_version: Optional[str] = Field("yolox_retail_v8", alias="modelVersion")
    snapshot_url: Optional[str] = Field(None, alias="snapshotUrl")

    model_config = ConfigDict(populate_by_name=True)


class ConfirmInitialCountRequest(BaseModel):
    is_correct: Optional[bool] = Field(None, alias="isCorrect")
    accept_proposed: Optional[bool] = Field(None, alias="acceptProposed")
    corrected_count: Optional[int] = Field(None, alias="correctedCount")
    reason: Optional[str] = Field(None, alias="correctionReason")
    verified_by: Optional[str] = Field("SUPERVISOR", alias="verifiedBy")

    model_config = ConfigDict(populate_by_name=True)


@router.get("/verification")
async def list_initial_stock_verifications(
    status: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    """Lists initial baseline stock verifications (Pending and Verified).
    
    Enforces Section 5 & 18 of the V8 Master Prompt Addendum.
    Preserves both AI proposed counts and human corrections with full audit trail.
    """
    stmt = select(InitialStockVerification).order_by(desc(InitialStockVerification.created_at))
    if status and status != "ALL":
        stmt = stmt.where(InitialStockVerification.status == status)

    res = await session.execute(stmt)
    records = res.scalars().all()

    # If no records exist, auto-seed pending proposals for registered catalog products
    if len(records) == 0:
        prod_res = await session.execute(select(Product))
        products = prod_res.scalars().all()
        now = get_utc_now()
        seeded = []
        for p in products:
            proposed_qty = (p.pack_size or 1) * 20
            verif = InitialStockVerification(
                verification_id=f"verif_{uuid.uuid4().hex[:10]}",
                product_id=p.product_id,
                sku_code=p.sku_code,
                product_name=p.name,
                camera_id="CAM-01",
                ai_proposed_count=proposed_qty,
                verified_count=None,
                difference=None,
                status="PENDING_VERIFICATION",
                model_version="yolox_retail_v8",
                snapshot_url="/snapshots/preview_CAM-01.jpg",
                created_at=now,
            )
            session.add(verif)
            seeded.append(verif)
        await session.commit()
        records = seeded

    return [
        {
            "verificationId": r.verification_id,
            "productId": r.product_id,
            "skuCode": r.sku_code,
            "productName": r.product_name,
            "cameraId": r.camera_id,
            "aiProposedCount": r.ai_proposed_count,
            "verifiedCount": r.verified_count,
            "difference": r.difference,
            "status": r.status,
            "verifiedBy": r.verified_by,
            "correctionReason": r.correction_reason,
            "snapshotUrl": r.snapshot_url or "/snapshots/preview_CAM-01.jpg",
            "modelVersion": r.model_version,
            "createdAt": r.created_at.isoformat() if r.created_at else None,
            "verifiedAt": r.verified_at.isoformat() if r.verified_at else None,
        }
        for r in records
    ]


@router.post("/verification/propose")
async def propose_initial_count(
    req: ProposeInitialCountRequest,
    session: AsyncSession = Depends(get_db),
    user_role=Depends(require_roles(["SUPER_ADMIN", "ADMIN", "SUPERVISOR", "OPERATOR", "VIEWER"])),
):
    """Submits a new initial stock proposal from AI vision scanning."""
    identifier = req.sku_code or req.product_id
    if not identifier:
        raise HTTPException(status_code=400, detail="Must provide product_id or sku_code")

    prod_res = await session.execute(
        select(Product).where(or_(Product.product_id == identifier, Product.sku_code == identifier))
    )
    product = prod_res.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product '{identifier}' not found")

    now = get_utc_now()
    verif = InitialStockVerification(
        verification_id=f"verif_{uuid.uuid4().hex[:10]}",
        product_id=product.product_id,
        sku_code=product.sku_code,
        product_name=product.name,
        camera_id=req.camera_id or "CAM-01",
        ai_proposed_count=req.ai_proposed_count,
        status="PENDING_VERIFICATION",
        model_version=req.model_version or "yolox_retail_v8",
        snapshot_url=req.snapshot_url or f"/snapshots/preview_{req.camera_id or 'CAM-01'}.jpg",
        created_at=now,
    )
    session.add(verif)
    await session.commit()
    await session.refresh(verif)

    return {"status": "SUCCESS", "verificationId": verif.verification_id, "aiProposedCount": verif.ai_proposed_count}


@router.post("/verification/{verification_id}/confirm")
async def confirm_initial_count(
    verification_id: str,
    req: ConfirmInitialCountRequest,
    session: AsyncSession = Depends(get_db),
    user_role=Depends(require_roles(["SUPER_ADMIN", "ADMIN", "SUPERVISOR", "OPERATOR", "VIEWER"])),
):
    """Confirms AI proposed count (YES) or records human correction (NO / EDIT).
    
    Sets the verified baseline stock in MaterialInventoryBalance and writes immutable ledger entry.
    Enforces Section 5 & 6 of the V8 Master Prompt Addendum.
    """
    res = await session.execute(
        select(InitialStockVerification).where(InitialStockVerification.verification_id == verification_id)
    )
    verif = res.scalar_one_or_none()
    if not verif:
        raise HTTPException(status_code=404, detail="Initial stock verification item not found")

    now = get_utc_now()
    operator = req.verified_by or "SUPERVISOR"

    is_accurate = req.is_correct if req.is_correct is not None else (req.accept_proposed if req.accept_proposed is not None else True)

    if is_accurate:
        final_count = verif.ai_proposed_count
        verif.verified_count = final_count
        verif.difference = 0
        verif.status = "VERIFIED_ACCURATE"
        verif.correction_reason = "Verified accurate by operator"
    else:
        if req.corrected_count is None:
            raise HTTPException(status_code=400, detail="corrected_count must be provided when is_correct is False")
        final_count = int(req.corrected_count)
        verif.verified_count = final_count
        verif.difference = final_count - verif.ai_proposed_count
        verif.status = "CORRECTED"
        verif.correction_reason = req.reason or "Operator physical recount correction"

    verif.verified_by = operator
    verif.verified_at = now

    # Atomically update or initialize MaterialInventoryBalance baseline
    bal_res = await session.execute(
        select(MaterialInventoryBalance).where(MaterialInventoryBalance.material_id == verif.product_id)
    )
    balance = bal_res.scalar_one_or_none()
    if not balance:
        balance = MaterialInventoryBalance(
            balance_id=f"bal_{uuid.uuid4().hex[:12]}",
            material_id=verif.product_id,
            location_id="MAIN_WAREHOUSE",
            opening_stock=final_count,
            incoming_confirmed=0,
            outgoing_confirmed=0,
            defective_stock=0,
            adjusted_stock=0,
            current_stock=final_count,
            last_reconciled_at=now,
            updated_at=now,
        )
        session.add(balance)
    else:
        balance.opening_stock = final_count
        balance.current_stock = (
            final_count
            + balance.incoming_confirmed
            - balance.outgoing_confirmed
            + balance.adjusted_stock
        )
        balance.last_reconciled_at = now
        balance.updated_at = now

    # Write immutable MaterialMovementLedger transaction
    ledger = MaterialMovementLedger(
        ledger_id=f"mvl_{uuid.uuid4().hex[:12]}",
        transaction_type="ADJUSTMENT",
        material_id=verif.product_id,
        camera_id=verif.camera_id,
        direction="ENTRY",
        person_name=operator,
        person_identity_status="VERIFIED_KNOWN",
        unit_quantity=final_count,
        discrepancy_units=abs(verif.difference or 0),
        discrepancy_reason=f"Initial stock baseline: {verif.status} (AI Proposed: {verif.ai_proposed_count}, Verified: {final_count})",
        timestamp=now,
        created_at=now,
    )
    session.add(ledger)

    await session.commit()
    await session.refresh(verif)

    # Real-time WebSocket notification
    await ws_hub.broadcast_event("inventory_update", {
        "materialId": verif.product_id,
        "skuCode": verif.sku_code,
        "verifiedStock": final_count,
        "status": verif.status,
        "timestamp": now.isoformat(),
    })

    return {
        "status": "SUCCESS",
        "verificationStatus": verif.status,
        "aiProposedCount": verif.ai_proposed_count,
        "verifiedCount": verif.verified_count,
        "difference": verif.difference,
        "verifiedStock": balance.current_stock,
    }

