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
import numpy as np

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
        from src.core.config import settings
        if face_confidence < settings.biometric.face_match_threshold or not person_name or person_name.strip() in ("", "UNKNOWN", "UNKNOWN_PERSON"):
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
                delta = max_qty - curr_qty
                # Check bulk goods rule: if acquired in STORAGE and appears at EXIT without intermediate STAGING/DOCK
                zone_ids_visited = [w.zone_id for w in sorted_waypoints]
                has_storage = any("STORAGE" in zid or "AISLE" in zid for zid in zone_ids_visited)
                has_dock = any("DOCK" in zid or "STAGING" in zid or "BAY" in zid for zid in zone_ids_visited)
                is_exit_now = "EXIT" in final_wp.zone_id or "DOOR" in final_wp.zone_id

                if delta > 0 and (final_wp.zone_id in ("EXIT_GATE", "LOADING_DOCK", "CORRIDOR_BLINDSPOT") or (has_storage and is_exit_now and not has_dock)):
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
                "missing_staging_dock_event": (not any("DOCK" in w.zone_id for w in sorted_waypoints)),
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


@dataclass
class ReIDTracklet:
    track_id: str
    camera_id: str
    zone_id: str
    timestamp: float
    feature_vector: np.ndarray           # Normalized 512-d ArcFace / OSNet vector
    person_name: str = "UNKNOWN_PERSON"
    crop_path: Optional[str] = None


class SpatialTopologyGraph:
    """Models warehouse camera adjacency, expected handover durations, and physical transition constraints."""

    # Adjacency transitions: (From_Zone, To_Zone) -> (expected_seconds, sigma_seconds)
    DEFAULT_HANDOVERS: Dict[Tuple[str, str], Tuple[float, float]] = {
        ("ZONE_ENTRY", "ZONE_STORAGE"): (25.0, 8.0),
        ("ZONE_STORAGE", "ZONE_LOADING_DOCK"): (35.0, 10.0),
        ("ZONE_LOADING_DOCK", "ZONE_EXIT"): (20.0, 6.0),
        ("ZONE_STORAGE", "ZONE_EXIT"): (30.0, 8.0),
        ("ZONE_ENTRY", "ZONE_EXIT"): (45.0, 12.0),
        ("ENTRY_LOBBY", "AISLE_STORAGE"): (20.0, 6.0),
        ("AISLE_STORAGE", "LOADING_DOCK"): (30.0, 8.0),
        ("LOADING_DOCK", "EXIT_GATE"): (20.0, 5.0),
        ("ENTRY_LOBBY", "EXIT_GATE"): (40.0, 10.0),
        ("AISLE_STORAGE", "EXIT_GATE"): (30.0, 8.0),
    }

    @classmethod
    def get_handover_stats(cls, from_zone: str, to_zone: str) -> Tuple[float, float, float]:
        """Returns (expected_dt, sigma_t, topology_penalty)."""
        pair = (from_zone.upper(), to_zone.upper())
        if pair in cls.DEFAULT_HANDOVERS:
            exp_dt, sig_t = cls.DEFAULT_HANDOVERS[pair]
            return (exp_dt, sig_t, 0.0)

        # Check reverse or generic connected zones
        rev_pair = (pair[1], pair[0])
        if rev_pair in cls.DEFAULT_HANDOVERS:
            exp_dt, sig_t = cls.DEFAULT_HANDOVERS[rev_pair]
            return (exp_dt, sig_t, 0.0)

        # Disconnected or physically impossible direct path without intermediate corridor
        return (60.0, 20.0, 1e6)


class GlobalHungarianReIDSolver:
    """Solves multi-camera person Re-ID associations across temporal camera handovers."""

    @classmethod
    def solve_associations(
        cls,
        existing_tracks: List[ReIDTracklet],
        new_sightings: List[ReIDTracklet],
        alpha: float = 0.50,
        beta: float = 0.30,
        gamma: float = 0.20,
        max_cost_threshold: float = 1.25,
    ) -> List[Tuple[int, int, float]]:
        """Computes global cost matrix and solves linear sum assignment using the Hungarian algorithm.

        Formula:
            Cost(i, j) = alpha * (1 - CosSim) + beta * ((dt - dt_exp)/sigma)^2 + gamma * TopologyPenalty

        Returns:
            List of (existing_idx, new_idx, association_cost) matches.
        """
        if not existing_tracks or not new_sightings:
            return []

        from scipy.optimize import linear_sum_assignment

        n_ex = len(existing_tracks)
        n_new = len(new_sightings)
        cost_matrix = np.zeros((n_ex, n_new), dtype=np.float64)

        for i, trk in enumerate(existing_tracks):
            v1 = trk.feature_vector / max(1e-6, np.linalg.norm(trk.feature_vector))
            for j, sght in enumerate(new_sightings):
                v2 = sght.feature_vector / max(1e-6, np.linalg.norm(sght.feature_vector))

                # Cosine similarity term
                cos_sim = float(np.dot(v1, v2))
                cos_cost = max(0.0, 1.0 - cos_sim)

                # Temporal handover term
                dt = abs(sght.timestamp - trk.timestamp)
                exp_dt, sig_t, topo_pen = SpatialTopologyGraph.get_handover_stats(trk.zone_id, sght.zone_id)
                time_cost = ((dt - exp_dt) / max(1.0, sig_t)) ** 2
                time_cost = min(10.0, time_cost)  # Clamp temporal penalty to prevent overflow

                total_cost = (alpha * cos_cost) + (beta * time_cost) + (gamma * topo_pen)
                cost_matrix[i, j] = total_cost

        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        matches: List[Tuple[int, int, float]] = []
        for r, c in zip(row_ind, col_ind):
            cost = cost_matrix[r, c]
            if cost <= max_cost_threshold:
                matches.append((int(r), int(c), round(float(cost), 4)))

        return matches
