"""Cross-Camera Spatiotemporal Journey & Material Diversion Engine

Reconstructs the multi-camera trajectory of individuals and tracked carriers across
facility zones (e.g. Entry Lobby -> Storage Aisles -> Staging Bay -> Exit Gate).

Capabilities:
1. Multi-camera spatiotemporal path fusion using identity & track embeddings.
2. In-transit inventory balance reconciliation across consecutive zone hand-offs.
3. Internal material diversion detection (e.g., items picked in an aisle but diverted
   before reaching the staging bay or exit gate).
4. Strictly adheres to the Zero-Speculation Identity Rule (confidence < 0.65 = UNKNOWN_PERSON).
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
import logging

logger = logging.getLogger("secops.engine.journey")


@dataclass
class ZoneWaypoint:
    camera_id: str
    zone_id: str
    zone_name: str
    timestamp: datetime
    dwell_seconds: float
    items_in_possession: Dict[str, int]
    face_confidence: float
    carrier_identity: str


@dataclass
class JourneyTrajectory:
    journey_id: str
    person_identifier: str
    person_name: str
    identity_status: str
    waypoints: List[ZoneWaypoint]
    total_duration_seconds: float
    start_time: datetime
    end_time: datetime
    has_diversion_anomaly: bool
    diversion_details: Optional[Dict[str, Any]]
    journey_status: str  # "IN_PROGRESS", "COMPLETED", "FLAGGED_DIVERSION"


class CrossCameraJourneyEngine:
    """Tracks continuous carrier journey across facility cameras and detects in-transit shrinkage."""

    _active_journeys: Dict[str, List[ZoneWaypoint]] = {}  # person_key -> list of waypoints

    @classmethod
    def record_waypoint(
        cls,
        camera_id: str,
        zone_id: str,
        zone_name: str,
        person_name: str,
        face_confidence: float,
        items_in_possession: Dict[str, int],
        timestamp: Optional[datetime] = None,
        dwell_seconds: float = 5.0,
    ) -> ZoneWaypoint:
        """Records a subject sighting at a camera/zone waypoint."""
        ts = timestamp or datetime.now(timezone.utc)

        # Enforce Zero-Speculation Identity Rule
        if face_confidence < 0.65 or not person_name or person_name.strip() in ("", "UNKNOWN", "UNKNOWN_PERSON"):
            carrier_id = "UNKNOWN_PERSON"
            person_key = f"anon_{uuid.uuid4().hex[:6]}"
        else:
            carrier_id = person_name.strip()
            person_key = carrier_id

        waypoint = ZoneWaypoint(
            camera_id=camera_id,
            zone_id=zone_id,
            zone_name=zone_name,
            timestamp=ts,
            dwell_seconds=dwell_seconds,
            items_in_possession={k: int(v) for k, v in items_in_possession.items() if v > 0},
            face_confidence=round(face_confidence, 4),
            carrier_identity=carrier_id,
        )

        if person_key not in cls._active_journeys:
            cls._active_journeys[person_key] = []
        cls._active_journeys[person_key].append(waypoint)

        logger.debug(
            "Recorded journey waypoint for %s in zone %s (%s items)",
            carrier_id, zone_name, items_in_possession
        )
        return waypoint

    @classmethod
    def evaluate_journey(
        cls,
        person_key: str,
        mark_completed: bool = False,
    ) -> Optional[JourneyTrajectory]:
        """Evaluates an active carrier trajectory, calculating duration and detecting diversion."""
        waypoints = cls._active_journeys.get(person_key)
        if not waypoints:
            return None

        sorted_waypoints = sorted(waypoints, key=lambda w: w.timestamp)
        start_t = sorted_waypoints[0].timestamp
        end_t = sorted_waypoints[-1].timestamp
        total_duration = max(0.0, (end_t - start_t).total_seconds())

        carrier_identity = sorted_waypoints[-1].carrier_identity
        identity_status = "VERIFIED_EMPLOYEE" if carrier_identity != "UNKNOWN_PERSON" else "UNKNOWN_PERSON"

        # Material balance check along the path:
        # Detect if items picked in an early zone disappear without being staged or registered at exit
        max_held: Dict[str, int] = {}
        for wp in sorted_waypoints:
            for mat, qty in wp.items_in_possession.items():
                max_held[mat] = max(max_held.get(mat, 0), qty)

        final_wp = sorted_waypoints[-1]
        final_held = final_wp.items_in_possession

        has_diversion = False
        diversion_details = None

        diverted_items: Dict[str, int] = {}
        for mat, max_qty in max_held.items():
            curr_qty = final_held.get(mat, 0)
            if max_qty > curr_qty:
                # Discrepancy between peak held and final waypoint
                delta = max_qty - curr_qty
                # If final zone is exit or transit and items disappeared without authorized drop
                if delta > 0 and final_wp.zone_id in ("EXIT_GATE", "LOADING_DOCK", "CORRIDOR_BLINDSPOT"):
                    diverted_items[mat] = delta

        if diverted_items:
            has_diversion = True
            diversion_details = {
                "diverted_items": diverted_items,
                "peak_possession": max_held,
                "exit_possession": final_held,
                "last_seen_zone": final_wp.zone_name,
                "last_seen_camera": final_wp.camera_id,
                "severity": "CRITICAL" if any(q >= 3 for q in diverted_items.values()) else "HIGH",
            }

        status = "FLAGGED_DIVERSION" if has_diversion else ("COMPLETED" if mark_completed else "IN_PROGRESS")

        trajectory = JourneyTrajectory(
            journey_id=f"jrn_{uuid.uuid4().hex[:10]}",
            person_identifier=person_key,
            person_name=carrier_identity,
            identity_status=identity_status,
            waypoints=sorted_waypoints,
            total_duration_seconds=round(total_duration, 1),
            start_time=start_t,
            end_time=end_t,
            has_diversion_anomaly=has_diversion,
            diversion_details=diversion_details,
            journey_status=status,
        )

        if mark_completed:
            cls._active_journeys.pop(person_key, None)

        return trajectory

    @classmethod
    def clear_all(cls) -> None:
        """Clears active memory state."""
        cls._active_journeys.clear()
