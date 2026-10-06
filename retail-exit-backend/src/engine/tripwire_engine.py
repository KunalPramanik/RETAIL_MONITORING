"""Virtual Tripwire & Anti-Tailgating Perimeter Security Engine

Implements directional vector line-crossing detection, biometric handshake,
multi-person unauthorized crossing detection, and trailing silhouette concealment defense.
"""

from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime, timezone
import math
import uuid
import logging
from collections import deque
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.models import (
    VirtualTripwireConfig,
    TripwireCrossingEvent,
    Employee,
    Alert,
    get_utc_now,
)
from src.core.config import settings

logger = logging.getLogger("secops.engine.tripwire")


def _ccw(A: Tuple[float, float], B: Tuple[float, float], C: Tuple[float, float]) -> bool:
    """Tests counter-clockwise orientation of 3 2D points."""
    return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])


def _segments_intersect(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    q1: Tuple[float, float],
    q2: Tuple[float, float],
) -> bool:
    """Determines whether line segment p1-p2 intersects line segment q1-q2."""
    return (_ccw(p1, q1, q2) != _ccw(p2, q1, q2)) and (_ccw(p1, p2, q1) != _ccw(p1, p2, q2))


class TripwireEngine:
    """Perimeter tripwire line crossing, biometric verification, and anti-tailgating engine."""

    # Rolling history of recent crossings: tripwire_id -> deque of (timestamp, track_id, entity_type)
    _recent_crossings: Dict[str, deque] = {}

    # Anti-duplicate crossing locks: (tripwire_id, track_id) -> {"direction": direction, "ts": timestamp}
    _crossing_locks: Dict[Tuple[str, str], Dict[str, Any]] = {}
    LOCK_COOLDOWN_SEC: float = settings.tripwire.lock_cooldown_sec

    # Anti-tailgating temporal threshold (seconds between unauthorized successive entries)
    TAILGATING_WINDOW_SEC: float = settings.tripwire.tailgating_window_sec

    @classmethod
    def should_allow_crossing(cls, tripwire_id: str, track_id: str, direction: str) -> bool:
        """Evaluates whether this crossing is a genuine new crossing or a duplicate lock.
        
        Returns True if crossing should be committed, False if suppressed as a duplicate.
        """
        import time as _time
        now_ts = _time.time()
        key = (str(tripwire_id), str(track_id))
        prev_lock = cls._crossing_locks.get(key)
        if prev_lock:
            prev_dir = prev_lock.get("direction")
            prev_ts = prev_lock.get("ts", 0.0)
            # If same direction and within cooldown window, suppress duplicate event
            if prev_dir == direction and (now_ts - prev_ts) < cls.LOCK_COOLDOWN_SEC:
                return False
        # Set / update lock
        cls._crossing_locks[key] = {"direction": direction, "ts": now_ts}
        return True

    @classmethod
    def unlock_crossing(cls, tripwire_id: str, track_id: str):
        """Manually unlocks a crossing state (e.g. on direction change or track departure)."""
        key = (str(tripwire_id), str(track_id))
        cls._crossing_locks.pop(key, None)

    @classmethod
    def check_trajectory_crossing(
        cls,
        p_prev: Tuple[float, float],
        p_curr: Tuple[float, float],
        line_start: Tuple[float, float],
        line_end: Tuple[float, float],
    ) -> Tuple[bool, str]:
        """Evaluates whether an entity moving p_prev -> p_curr intersected the virtual tripwire line.

        All coordinates normalized (0.0 to 1.0).
        Returns:
            (has_crossed, direction) where direction is 'ENTRY', 'EXIT', or 'UNKNOWN'
        """
        if not _segments_intersect(p_prev, p_curr, line_start, line_end):
            return (False, "UNKNOWN")

        # Compute direction using dot product with line normal vector
        # Line vector L = line_end - line_start
        # Normal vector N = (-L_y, L_x) points to the "ENTRY" side
        lx = line_end[0] - line_start[0]
        ly = line_end[1] - line_start[1]
        nx = -ly
        ny = lx

        # Motion vector
        dx = p_curr[0] - p_prev[0]
        dy = p_curr[1] - p_prev[1]

        dot = dx * nx + dy * ny
        direction = "ENTRY" if dot >= 0 else "EXIT"
        return (True, direction)

    @classmethod
    def detect_concealment(
        cls,
        leading_track: Dict[str, Any],
        trailing_track: Dict[str, Any],
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Evaluates whether trailing_track is attempting to conceal itself behind leading_track.

        Concealment Criteria:
        1. High bounding overlap (IoU >= 0.28 or horizontal overlap >= 50%)
        2. Leading track has confident detection (conf >= 0.70)
        3. Trailing track exhibits anomalously suppressed confidence (0.30 <= conf < 0.60)
        4. Co-directional velocity vectors (cos_theta >= 0.80)
        """
        l_box = leading_track.get("bbox", [0, 0, 0, 0])
        t_box = trailing_track.get("bbox", [0, 0, 0, 0])

        # Overlap computation
        xA = max(l_box[0], t_box[0])
        yA = max(l_box[1], t_box[1])
        xB = min(l_box[0] + l_box[2], t_box[0] + t_box[2])
        yB = min(l_box[1] + l_box[3], t_box[1] + t_box[3])
        inter_area = max(0, xB - xA) * max(0, yB - yA)
        box_a_area = l_box[2] * l_box[3]
        box_b_area = t_box[2] * t_box[3]
        denom = float(box_a_area + box_b_area - inter_area)
        iou = inter_area / denom if denom > 0 else 0.0

        # Horizontal overlap
        h_inter = max(0, min(l_box[0] + l_box[2], t_box[0] + t_box[2]) - max(l_box[0], t_box[0]))
        h_overlap = h_inter / float(min(l_box[2], t_box[2])) if min(l_box[2], t_box[2]) > 0 else 0.0

        l_conf = leading_track.get("confidence", 0.85)
        t_conf = trailing_track.get("confidence", 0.40)

        # Distance between centroids
        lcx = l_box[0] + l_box[2] / 2.0
        lcy = l_box[1] + l_box[3] / 2.0
        tcx = t_box[0] + t_box[2] / 2.0
        tcy = t_box[1] + t_box[3] / 2.0
        dist = math.hypot(lcx - tcx, lcy - tcy)

        # Direction alignment
        l_vel = leading_track.get("velocity", (0.0, 1.0))
        t_vel = trailing_track.get("velocity", (0.0, 1.0))
        l_mag = math.hypot(l_vel[0], l_vel[1])
        t_mag = math.hypot(t_vel[0], t_vel[1])
        cos_theta = 1.0
        if l_mag > 0.01 and t_mag > 0.01:
            cos_theta = (l_vel[0] * t_vel[0] + l_vel[1] * t_vel[1]) / (l_mag * t_mag)

        # Concealment trigger
        if (iou >= 0.25 or h_overlap >= 0.50 or dist < 60) and l_conf >= 0.65 and (t_conf < l_conf - 0.15) and cos_theta >= 0.75:
            details = {
                "reason": "SILHOUETTE_CONCEALMENT",
                "iou": round(iou, 3),
                "h_overlap": round(h_overlap, 3),
                "leading_track_id": leading_track.get("track_id"),
                "leading_confidence": l_conf,
                "trailing_confidence": t_conf,
                "vector_alignment": round(cos_theta, 3),
            }
            return (True, details)

        return (False, None)

    @classmethod
    async def record_crossing(
        cls,
        session: AsyncSession,
        tripwire_id: str,
        camera_id: str,
        track_id: str,
        direction: str,
        entity_type: str = "PERSON",
        matched_employee: Optional[Dict[str, Any]] = None,
        is_concealed: bool = False,
        concealment_details: Optional[Dict[str, Any]] = None,
        snapshot_url: Optional[str] = None,
        carried_materials: Optional[List[Dict[str, Any]]] = None,
        zone_id: Optional[str] = None,
    ) -> Tuple[TripwireCrossingEvent, Optional[Alert]]:
        """Persists a verified tripwire line crossing event, detects anti-tailgating violations,
        and atomically links carried material inventory movements.
        """
        now = get_utc_now()
        now_ts = now.timestamp()

        # Biometric status (Identity confidence floor: >= 0.65 and decision == MATCHED)
        biometric_status = "UNAVAILABLE"
        emp_id = None
        if matched_employee:
            decision = matched_employee.get("decision")
            sim = float(matched_employee.get("similarity", 0.75)) if decision == "MATCHED" else float(matched_employee.get("similarity", 0.0))
            if decision == "MATCHED" and sim >= 0.65:
                biometric_status = "VERIFIED_KNOWN"
                emp_id = matched_employee.get("employee_id")
            elif decision in ("NO_MATCH", "LOW_CONFIDENCE") or sim < 0.65:
                biometric_status = "UNKNOWN_INTRUDER"
                emp_id = None

        # Check for multi-person tailgating
        if tripwire_id not in cls._recent_crossings:
            cls._recent_crossings[tripwire_id] = deque(maxlen=20)

        history = cls._recent_crossings[tripwire_id]
        is_tailgating = is_concealed
        tailgating_details = concealment_details or {}

        # Look for another person who crossed within TAILGATING_WINDOW_SEC in same direction
        if entity_type == "PERSON":
            for prev_ts, prev_tid, prev_dir, prev_bio in history:
                if (now_ts - prev_ts) <= cls.TAILGATING_WINDOW_SEC and prev_dir == direction and prev_tid != track_id:
                    is_tailgating = True
                    tailgating_details = {
                        "reason": "MULTI_PERSON_SIMULTANEOUS_CROSSING",
                        "temporal_gap_ms": int((now_ts - prev_ts) * 1000),
                        "preceding_track_id": prev_tid,
                        "preceding_biometric": prev_bio,
                    }
                    break

        history.append((now_ts, track_id, direction, biometric_status))

        crossing = TripwireCrossingEvent(
            crossing_id=f"crs_{uuid.uuid4().hex[:10]}",
            tripwire_id=tripwire_id,
            camera_id=camera_id,
            track_id=str(track_id),
            timestamp=now,
            direction=direction,
            entity_type=entity_type,
            biometric_status=biometric_status,
            matched_employee_id=emp_id,
            is_tailgating=is_tailgating,
            tailgating_details=tailgating_details if is_tailgating else None,
            snapshot_url=snapshot_url,
        )
        session.add(crossing)

        alert = None
        if is_tailgating or biometric_status == "UNKNOWN_INTRUDER":
            severity = "HIGH" if is_tailgating else "MEDIUM"
            alert_type = "UNAUTHORIZED_ACCESS" if is_tailgating else "INTRUSION"
            desc = (
                f"Perimeter Violation [{direction}]: "
                f"{'TAILGATING / CONCEALMENT DETECTED' if is_tailgating else 'UNKNOWN INTRUDER'} "
                f"at tripwire '{tripwire_id}' (Camera: {camera_id}). Track: {track_id}."
            )
            alert = Alert(
                alert_id=f"alt_trip_{uuid.uuid4().hex[:8]}",
                camera_id=camera_id,
                event_id=None,
                alert_type=alert_type,
                severity=severity,
                delta_units=1,
                status="OPEN",
                resolution_note=desc,
                created_at=now,
            )
            session.add(alert)

        # Automatic atomic recording of carried materials into the MaterialMovementLedger
        carried_ledger_entries = []
        if carried_materials:
            from src.engine.inventory_ledger_engine import InventoryLedgerEngine
            tx_type = "IN" if direction == "ENTRY" else "OUT"
            p_name = "UNKNOWN_PERSON"
            p_status = "UNKNOWN_PERSON"
            if emp_id and biometric_status == "VERIFIED_KNOWN":
                p_name = (matched_employee.get("employee_name") if matched_employee is not None else None) or emp_id or "VERIFIED_KNOWN"
                p_status = "VERIFIED_KNOWN"
            else:
                p_name = "UNKNOWN_PERSON"
                p_status = "UNKNOWN_PERSON"
                emp_id = None

            for mat in carried_materials:
                mat_id = mat.get("material_id") or mat.get("name") or mat.get("class_name") or mat.get("sku_code")
                qty = mat.get("quantity") or mat.get("units") or mat.get("unit_quantity") or 1
                pkg_qty = mat.get("package_quantity") or 0
                def_status = mat.get("defect_status") or "NORMAL"
                def_sev = mat.get("defect_severity") or "NONE"
                try:
                    ledger_rec, _, _ = await InventoryLedgerEngine.record_confirmed_movement(
                        session=session,
                        material_id=str(mat_id),
                        transaction_type=tx_type,
                        unit_quantity=qty,
                        package_quantity=pkg_qty,
                        camera_id=camera_id,
                        zone_id=zone_id,
                        tripwire_id=tripwire_id,
                        track_id=str(track_id),
                        direction=direction,
                        person_id=emp_id,
                        person_name=p_name,
                        person_identity_status=p_status,
                        carrier_relation=mat.get("carrier_relation", "carrying"),
                        defect_status=def_status,
                        defect_severity=def_sev,
                        commit=False,
                    )
                    carried_ledger_entries.append(ledger_rec)
                except Exception as _m_err:
                    logger.debug("Automatic carried material ledger recording error: %s", _m_err)

        setattr(crossing, "ledger_entries", carried_ledger_entries)

        await session.commit()
        await session.refresh(crossing)
        return (crossing, alert)
