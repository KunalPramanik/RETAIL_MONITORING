"""Industrial Dispatch & Loading Bay REST API

Provides session management, manifest reconciliation, and material stack audit endpoints.
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from src.db.session import get_db
from src.db.models import DispatchSession, Lane, Employee
from src.engine.dispatch_engine import DispatchEngine
from src.ml.material_segmentation import MaterialSegmentationService

router = APIRouter(prefix="/dispatch", tags=["Industrial Dispatch"])


class DispatchSessionStartRequest(BaseModel):
    dockLaneId: str = Field(..., description="ID of the loading dock / lane")
    manifestId: Optional[str] = Field(None, description="External order manifest / invoice number")
    vehicleIdentifier: Optional[str] = Field(None, description="Truck license plate or vehicle tag")
    carrierEmployeeId: Optional[str] = Field(None, description="ID of verified driver/carrier employee")
    manifestExpected: Optional[Dict[str, int]] = Field(default_factory=dict, description="Expected SKU removal counts")
    manualInitialCount: Optional[Dict[str, int]] = Field(None, description="Optional manual initial stack counts")
    notes: Optional[str] = Field(None)


class DispatchSessionCompleteRequest(BaseModel):
    manualOverrideAfter: Optional[Dict[str, int]] = Field(None, description="Optional manual inventory count override")
    manualAfterCount: Optional[Dict[str, int]] = Field(None, description="Alias for manualOverrideAfter")

    def get_after_count(self) -> Optional[Dict[str, int]]:
        return self.manualAfterCount if self.manualAfterCount is not None else self.manualOverrideAfter


class DispatchSessionResponse(BaseModel):
    sessionId: str
    dockLaneId: str
    manifestId: Optional[str] = None
    carrierEmployeeId: Optional[str] = None
    vehicleIdentifier: Optional[str] = None
    status: str
    startedAt: str
    completedAt: Optional[str] = None
    beforeCount: Dict[str, int]
    afterCount: Dict[str, int]
    removedDelta: Dict[str, int]
    manifestExpected: Dict[str, int]
    discrepancyType: str
    discrepancyMagnitude: int
    alertGenerated: bool = False
    trackingInterruptedSeconds: float
    archivalSnapshotUrl: Optional[str] = None
    notes: Optional[str] = None
    createdAt: str


class ManifestReconcileRequest(BaseModel):
    removedDelta: Dict[str, int]
    manifestExpected: Dict[str, int]


def _serialize_session(s: DispatchSession) -> DispatchSessionResponse:
    alert_gen = s.discrepancy_type not in ("MATCH", None)
    return DispatchSessionResponse(
        sessionId=s.session_id,
        dockLaneId=s.dock_lane_id,
        manifestId=s.manifest_id,
        carrierEmployeeId=s.carrier_employee_id,
        vehicleIdentifier=s.vehicle_identifier,
        status=s.status,
        startedAt=s.started_at.isoformat() if s.started_at else "",
        completedAt=s.completed_at.isoformat() if s.completed_at else None,
        beforeCount=s.before_count or {},
        afterCount=s.after_count or {},
        removedDelta=s.removed_delta or {},
        manifestExpected=s.manifest_expected or {},
        discrepancyType=s.discrepancy_type or "MATCH",
        discrepancyMagnitude=s.discrepancy_magnitude or 0,
        alertGenerated=alert_gen,
        trackingInterruptedSeconds=float(s.tracking_interrupted_seconds or 0.0),
        archivalSnapshotUrl=s.archival_snapshot_url,
        notes=s.notes,
        createdAt=s.created_at.isoformat() if s.created_at else "",
    )


@router.get("/materials/classes", summary="Get universal material class specifications")
async def get_material_classes() -> Dict[str, Any]:
    """Returns the centralized material taxonomy, geometry, and severity configuration."""
    return MaterialSegmentationService.load_config()


@router.post("/sessions/start", response_model=DispatchSessionResponse, status_code=200)
@router.post("/session/start", response_model=DispatchSessionResponse, status_code=200)
async def start_dispatch_session(
    body: DispatchSessionStartRequest,
    session: AsyncSession = Depends(get_db),
):
    """Starts an active dispatch loading session on a specified dock bay."""
    try:
        new_sess = await DispatchEngine.start_session(
            session=session,
            dock_lane_id=body.dockLaneId,
            manifest_id=body.manifestId,
            vehicle_identifier=body.vehicleIdentifier,
            carrier_employee_id=body.carrierEmployeeId,
            manifest_expected=body.manifestExpected,
            manual_initial_count=body.manualInitialCount,
            notes=body.notes,
        )
        return _serialize_session(new_sess)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/complete", response_model=DispatchSessionResponse)
@router.post("/session/{session_id}/complete", response_model=DispatchSessionResponse)
async def complete_dispatch_session(
    session_id: str,
    body: Optional[DispatchSessionCompleteRequest] = None,
    session: AsyncSession = Depends(get_db),
):
    """Concludes a dispatch session, calculates removed stack delta, and reconciles against manifest."""
    try:
        manual_after = body.get_after_count() if body else None
        completed_sess, alert = await DispatchEngine.complete_session(
            session=session,
            session_id=session_id,
            manual_override_after=manual_after,
        )
        return _serialize_session(completed_sess)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions", response_model=List[DispatchSessionResponse])
async def list_dispatch_sessions(
    dock_lane_id: Optional[str] = Query(None, alias="dockLaneId"),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
):
    """Lists dispatch sessions ordered by start timestamp descending."""
    query = select(DispatchSession).order_by(desc(DispatchSession.started_at)).limit(limit)
    if dock_lane_id:
        query = query.where(DispatchSession.dock_lane_id == dock_lane_id)
    if status:
        query = query.where(DispatchSession.status == status)

    res = await session.execute(query)
    rows = res.scalars().all()
    return [_serialize_session(r) for r in rows]


@router.get("/sessions/{session_id}", response_model=DispatchSessionResponse)
async def get_dispatch_session(
    session_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Retrieves a single dispatch session by ID."""
    res = await session.execute(select(DispatchSession).where(DispatchSession.session_id == session_id))
    disp = res.scalar_one_or_none()
    if not disp:
        raise HTTPException(status_code=404, detail=f"Dispatch session '{session_id}' not found")
    return _serialize_session(disp)


@router.post("/manifest/reconcile")
async def reconcile_manifest_preview(body: ManifestReconcileRequest):
    """Previews reconciliation between physical removal deltas and expected manifest items."""
    discrepancy_type, variance, breakdown = MaterialSegmentationService.reconcile_with_manifest(
        removed_deltas=body.removedDelta,
        manifest_expected=body.manifestExpected,
    )
    return {
        "discrepancyType": discrepancy_type,
        "totalVariance": variance,
        "breakdown": breakdown,
    }


class EdgeManifestScanRequest(BaseModel):
    rawOcrText: Optional[str] = Field(None, description="Direct text from handheld or edge OCR")
    imageBase64: Optional[str] = Field(None, description="Base64 encoded frame from desk scanner")
    dockLaneId: Optional[str] = Field(None, description="Lane ID to auto-bind dispatch session")
    autoStartSession: bool = Field(False, description="Whether to start a dispatch session immediately")


@router.post("/manifest/edge-scan")
async def edge_manifest_scan(
    body: EdgeManifestScanRequest,
    session: AsyncSession = Depends(get_db),
):
    """Ingests physical paper manifests or raw barcode strings from dock edge scanners."""
    from src.engine.manifest_ingestion_daemon import DeskManifestScanner
    import base64
    import cv2
    import numpy as np

    frame = None
    if body.imageBase64:
        try:
            raw_bytes = base64.b64decode(body.imageBase64.split(",")[-1])
            nparr = np.frombuffer(raw_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception:
            pass

    if frame is None:
        frame = np.full((1080, 1920, 3), 240, dtype=np.uint8)

    manifest = DeskManifestScanner.process_desk_frame(frame, ocr_text_override=body.rawOcrText)

    res_data = {
        "bolNumber": manifest.bol_number,
        "carrierName": manifest.carrier_name,
        "lineItems": manifest.line_items,
        "confidence": manifest.confidence,
        "isDeskewed": manifest.is_deskewed,
        "sessionId": None,
    }

    if body.autoStartSession and body.dockLaneId and manifest.line_items:
        new_sess = await DispatchEngine.start_session(
            session=session,
            dock_lane_id=body.dockLaneId,
            manifest_id=manifest.bol_number,
            carrier_employee_id=manifest.carrier_name,
            manifest_expected=manifest.line_items,
        )
        res_data["sessionId"] = new_sess.session_id

    return res_data
