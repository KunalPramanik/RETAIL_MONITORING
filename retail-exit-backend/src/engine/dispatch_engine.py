"""Industrial Dispatch Session Engine

Manages warehouse loading bay sessions, steady-state baseline stack counting,
real-time removal monitoring, manifest reconciliation, and automated theft/over-authorization alerting.
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
import os
import uuid
import logging
import cv2
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from src.db.models import (
    DispatchSession,
    Lane,
    Camera,
    Employee,
    Alert,
    AuditLog,
    get_utc_now,
)
from src.ml.material_segmentation import (
    MaterialSegmentationService,
    SegmentationCountResult,
)

logger = logging.getLogger("secops.engine.dispatch")

EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "dispatch_evidence")
os.makedirs(EVIDENCE_DIR, exist_ok=True)


class DispatchEngine:
    """Orchestrates industrial dispatch and loading dock sessions."""

    _active_sessions_by_lane: Dict[str, str] = {}  # lane_id -> session_id
    _last_frame_timestamps: Dict[str, float] = {}  # camera_id -> timestamp

    @classmethod
    async def start_session(
        cls,
        session: AsyncSession,
        dock_lane_id: str,
        manifest_id: Optional[str] = None,
        vehicle_identifier: Optional[str] = None,
        carrier_employee_id: Optional[str] = None,
        manifest_expected: Optional[Dict[str, int]] = None,
        current_frame: Optional[np.ndarray] = None,
        camera_id: Optional[str] = None,
        notes: Optional[str] = None,
        manual_initial_count: Optional[Dict[str, int]] = None,
    ) -> DispatchSession:
        """Starts a new dispatch session on a loading dock, establishing steady-state before_count."""
        # Check if lane exists
        lane_res = await session.execute(select(Lane).where(Lane.lane_id == dock_lane_id))
        lane = lane_res.scalar_one_or_none()
        if not lane:
            raise ValueError(f"Dock Lane '{dock_lane_id}' not found")

        # Check for existing active session on this lane
        existing_res = await session.execute(
            select(DispatchSession).where(
                DispatchSession.dock_lane_id == dock_lane_id,
                DispatchSession.status == "ACTIVE",
            )
        )
        existing = existing_res.scalar_one_or_none()
        if existing:
            raise ValueError(f"Lane '{dock_lane_id}' already has an ACTIVE dispatch session ({existing.session_id})")

        # Establish baseline before_count using instance segmentation
        before_count: Dict[str, int] = {}
        snapshot_url = None

        if manual_initial_count is not None:
            before_count = manual_initial_count
        elif current_frame is not None and current_frame.size > 0:
            seg_res = MaterialSegmentationService.segment_materials(current_frame)
            before_count = seg_res.counts_by_class

            # Save baseline snapshot
            ts_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            snap_name = f"baseline_{dock_lane_id}_{ts_str}.jpg"
            snap_path = os.path.join(EVIDENCE_DIR, snap_name)
            annotated = MaterialSegmentationService.annotate_frame_with_masks(current_frame, seg_res.instances)
            cv2.imwrite(snap_path, annotated)
            snapshot_url = f"/data/dispatch_evidence/{snap_name}"

        sess_id = f"disp_{uuid.uuid4().hex[:10]}"
        now = get_utc_now()

        new_session = DispatchSession(
            session_id=sess_id,
            dock_lane_id=dock_lane_id,
            manifest_id=manifest_id,
            carrier_employee_id=carrier_employee_id,
            vehicle_identifier=vehicle_identifier,
            status="ACTIVE",
            started_at=now,
            before_count=before_count,
            after_count={},
            removed_delta={},
            manifest_expected=manifest_expected or {},
            discrepancy_type="MATCH",
            discrepancy_magnitude=0,
            tracking_interrupted_seconds=0.0,
            archival_snapshot_url=snapshot_url,
            notes=notes,
            created_at=now,
        )
        session.add(new_session)
        await session.commit()
        await session.refresh(new_session)

        cls._active_sessions_by_lane[dock_lane_id] = sess_id
        logger.info("Started dispatch session %s on dock %s with initial count %s", sess_id, dock_lane_id, before_count)
        return new_session

    @classmethod
    async def complete_session(
        cls,
        session: AsyncSession,
        session_id: str,
        current_frame: Optional[np.ndarray] = None,
        manual_override_after: Optional[Dict[str, int]] = None,
    ) -> Tuple[DispatchSession, Optional[Alert]]:
        """Completes dispatch session, calculates removed delta, and arbitrates against manifest."""
        res = await session.execute(select(DispatchSession).where(DispatchSession.session_id == session_id))
        disp = res.scalar_one_or_none()
        if not disp:
            raise ValueError(f"Dispatch session '{session_id}' not found")
        if disp.status != "ACTIVE":
            raise ValueError(f"Session '{session_id}' is already {disp.status}")

        now = get_utc_now()
        disp.completed_at = now

        # Determine after_count
        after_count: Dict[str, int] = {}
        if manual_override_after is not None:
            after_count = manual_override_after
        elif current_frame is not None and current_frame.size > 0:
            seg_res = MaterialSegmentationService.segment_materials(current_frame)
            after_count = seg_res.counts_by_class

            # Save completion evidence snapshot
            ts_str = now.strftime("%Y%m%d_%H%M%S")
            snap_name = f"evidence_{disp.session_id}_{ts_str}.jpg"
            snap_path = os.path.join(EVIDENCE_DIR, snap_name)
            annotated = MaterialSegmentationService.annotate_frame_with_masks(current_frame, seg_res.instances)
            cv2.imwrite(snap_path, annotated)
            disp.archival_snapshot_url = f"/data/dispatch_evidence/{snap_name}"

        disp.after_count = after_count

        # Compute delta = before - after
        before_count = disp.before_count or {}
        removed_delta = MaterialSegmentationService.calculate_stack_removal_delta(before_count, after_count)
        disp.removed_delta = removed_delta

        # Reconcile against manifest
        manifest_expected = disp.manifest_expected or {}
        discrepancy_type, variance, breakdown = MaterialSegmentationService.reconcile_with_manifest(
            removed_delta, manifest_expected
        )
        disp.discrepancy_type = discrepancy_type
        disp.discrepancy_magnitude = variance

        alert = None
        if discrepancy_type != "MATCH":
            disp.status = "FLAGGED_DISCREPANCY"
            severity = "HIGH" if discrepancy_type == "OVER_AUTHORIZED" else "MEDIUM"
            alert_type = "OVER_CARRY" if discrepancy_type == "OVER_AUTHORIZED" else "UNDER_DECLARE"
            carrier_str = disp.carrier_employee_id or "UNKNOWN_PERSON"
            desc = (
                f"Dispatch Discrepancy [{discrepancy_type}]: Dock '{disp.dock_lane_id}' variance of {variance} units. "
                f"Carrier: {carrier_str}. Vehicle: {disp.vehicle_identifier or 'UNKNOWN'}, Manifest: {disp.manifest_id or 'NONE'}."
            )
            alert = Alert(
                alert_id=f"alt_disp_{uuid.uuid4().hex[:8]}",
                camera_id=None,
                event_id=None,
                alert_type=alert_type,
                severity=severity,
                delta_units=abs(variance),
                status="OPEN",
                resolution_note=desc,
                created_at=now,
            )
            session.add(alert)
        else:
            disp.status = "COMPLETED"

        cls._active_sessions_by_lane.pop(disp.dock_lane_id, None)
        await session.commit()
        await session.refresh(disp)

        logger.info(
            "Completed dispatch session %s: status=%s, delta=%s, manifest=%s, variance=%d",
            session_id, disp.status, removed_delta, manifest_expected, variance
        )
        return (disp, alert)

    @classmethod
    async def record_stream_gap(
        cls,
        session: AsyncSession,
        dock_lane_id: str,
        gap_seconds: float,
    ) -> None:
        """Records uninterrupted tracking gap when a camera drops offline during an active dispatch session."""
        if gap_seconds <= 0:
            return

        active_sess_id = cls._active_sessions_by_lane.get(dock_lane_id)
        if not active_sess_id:
            # Check DB directly
            res = await session.execute(
                select(DispatchSession).where(
                    DispatchSession.dock_lane_id == dock_lane_id,
                    DispatchSession.status == "ACTIVE",
                )
            )
            active = res.scalar_one_or_none()
            if active:
                active_sess_id = active.session_id

        if active_sess_id:
            res = await session.execute(select(DispatchSession).where(DispatchSession.session_id == active_sess_id))
            disp = res.scalar_one_or_none()
            if disp:
                current_gap = float(disp.tracking_interrupted_seconds or 0.0)
                disp.tracking_interrupted_seconds = round(current_gap + gap_seconds, 2)
                await session.commit()
                logger.warning(
                    "Recorded %.1fs stream gap for active dispatch session %s on dock %s",
                    gap_seconds, active_sess_id, dock_lane_id
                )
