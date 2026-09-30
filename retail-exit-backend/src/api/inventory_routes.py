"""Automated Inventory & Discrepancy Adjustment API"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.engine.automated_counter import AutomatedCountingEngine
from src.api.deps_auth import require_roles

router = APIRouter(prefix="/inventory", tags=["Dynamic Automated Counting"])

class VisionCountTrigger(BaseModel):
    camera_id: str
    vision_counts: Dict[int, int] # e.g. {1005: 42} (Class ID -> Count)

class ManualAdjustmentTrigger(BaseModel):
    product_id: str
    qty_adjustment: int
    operator_id: str
    reason: str

@router.post("/count/trigger")
async def trigger_vision_count(
    req: VisionCountTrigger,
    session: AsyncSession = Depends(get_db),
    user=Depends(require_roles(["SUPER_ADMIN", "SECURITY_SUPERVISOR", "SYSTEM"]))
):
    """
    Ingests raw bounding box counts from the ML engine, dynamically maps to items, and tallies in the ledger.
    """
    try:
        res = await AutomatedCountingEngine.process_vision_count(
            session=session,
            camera_id=req.camera_id,
            vision_counts=req.vision_counts
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/adjust")
async def manual_inventory_adjustment(
    req: ManualAdjustmentTrigger,
    session: AsyncSession = Depends(get_db),
    user=Depends(require_roles(["SUPER_ADMIN", "ADMIN"]))
):
    """
    Submit a manual discrepancy adjustment (Recount override). 
    Appends an immutable correction row to the ledger.
    """
    try:
        res = await AutomatedCountingEngine.manual_adjustment(
            session=session,
            product_id=req.product_id,
            qty_adjustment=req.qty_adjustment,
            operator_id=req.operator_id,
            reason=req.reason
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
