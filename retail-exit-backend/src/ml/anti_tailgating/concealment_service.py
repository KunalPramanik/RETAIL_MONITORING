"""Silhouette Concealment & Anti-Tailgating Detection Service

Identifies unauthorized persons attempting to evade exit cameras or turnstile tripwires
by walking in lockstep directly behind an authorized carrier (person-behind-person occlusion).
"""

from typing import List, Dict, Tuple, Optional, Any
import math
import logging

logger = logging.getLogger("secops.ml.concealment")


class ConcealmentDetectionService:
    """Detects trailing silhouette concealment and person-behind-person tailgating."""

    IOU_THRESHOLD: float = 0.25
    HORIZONTAL_OVERLAP_THRESHOLD: float = 0.50
    CENTROID_PROXIMITY_PX: float = 60.0
    MIN_LEADING_CONFIDENCE: float = 0.65
    CONFIDENCE_DELTA_DROP: float = 0.15
    VELOCITY_COS_THETA_THRESHOLD: float = 0.75

    @classmethod
    def evaluate_pair(
        cls,
        leading_track: Dict[str, Any],
        trailing_track: Dict[str, Any],
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Evaluates whether trailing_track is concealed behind leading_track."""
        l_box = leading_track.get("bbox", [0, 0, 0, 0])
        t_box = trailing_track.get("bbox", [0, 0, 0, 0])

        if len(l_box) < 4 or len(t_box) < 4:
            return False, None

        # Intersection over Union
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
        min_w = float(min(l_box[2], t_box[2]))
        h_overlap = h_inter / min_w if min_w > 0 else 0.0

        l_conf = float(leading_track.get("confidence", 0.85))
        t_conf = float(trailing_track.get("confidence", 0.40))

        # Centroid distance
        lcx = l_box[0] + l_box[2] / 2.0
        lcy = l_box[1] + l_box[3] / 2.0
        tcx = t_box[0] + t_box[2] / 2.0
        tcy = t_box[1] + t_box[3] / 2.0
        dist = math.hypot(lcx - tcx, lcy - tcy)

        # Velocity alignment
        l_vel = leading_track.get("velocity", (0.0, 1.0))
        t_vel = trailing_track.get("velocity", (0.0, 1.0))
        l_mag = math.hypot(l_vel[0], l_vel[1])
        t_mag = math.hypot(t_vel[0], t_vel[1])
        cos_theta = 1.0
        if l_mag > 0.01 and t_mag > 0.01:
            cos_theta = (l_vel[0] * t_vel[0] + l_vel[1] * t_vel[1]) / (l_mag * t_mag)

        # Concealment trigger rule
        is_close_overlap = (iou >= cls.IOU_THRESHOLD or h_overlap >= cls.HORIZONTAL_OVERLAP_THRESHOLD or dist < cls.CENTROID_PROXIMITY_PX)
        is_confident_lead = l_conf >= cls.MIN_LEADING_CONFIDENCE
        has_confidence_drop = t_conf < (l_conf - cls.CONFIDENCE_DELTA_DROP)
        is_aligned = cos_theta >= cls.VELOCITY_COS_THETA_THRESHOLD

        if is_close_overlap and is_confident_lead and has_confidence_drop and is_aligned:
            details = {
                "reason": "SILHOUETTE_CONCEALMENT",
                "iou": round(iou, 3),
                "h_overlap": round(h_overlap, 3),
                "centroid_distance_px": round(dist, 2),
                "leading_track_id": leading_track.get("track_id"),
                "trailing_track_id": trailing_track.get("track_id"),
                "leading_confidence": round(l_conf, 3),
                "trailing_confidence": round(t_conf, 3),
                "vector_alignment": round(cos_theta, 3),
            }
            logger.warning(
                "Concealment detected between leading track %s and trailing track %s (IoU=%.2f, align=%.2f)",
                leading_track.get("track_id"),
                trailing_track.get("track_id"),
                iou,
                cos_theta,
            )
            return True, details

        return False, None

    @classmethod
    def scan_active_tracks(cls, tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Scans all active bounding boxes in an exit lane frame for pair-wise concealment attempts."""
        concealment_events = []
        n = len(tracks)
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                is_concealed, details = cls.evaluate_pair(tracks[i], tracks[j])
                if is_concealed and details:
                    concealment_events.append(details)
        return concealment_events
