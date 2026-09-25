"""Automated Worker Ergonomics & Industrial Safety Intelligence (OSHA / ISO 45001)

Performs kinematic posture analysis and industrial safety checks using 2D skeletal poses:
1. Lumbar Spine Flexion Kinematics (Trunk angle relative to vertical).
2. Lift Technique Classification:
   - LEG_SQUAT_COMPLIANT: Knees bent, torso upright (safe industrial lifting).
   - BACK_FLEXION_HAZARDOUS: Back bent > 45 deg, knees straight (high lumbar strain risk).
3. Team-Lift Rule Enforcement:
   - Mandates >= 2 workers for items > 25kg or BULK_MATERIAL tier.
4. PPE Detection (High-Visibility Vest & Hard Hat chromaticity & contour analysis).
5. Comprehensive Ergonomic Risk Rating (REBA / RULA inspired scoring).
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import math
import numpy as np
import cv2
import logging

logger = logging.getLogger("secops.ml.ergonomics")


@dataclass
class ErgonomicAssessment:
    person_box: List[int]
    spine_flexion_deg: float
    lift_technique: str                   # "UPRIGHT_STANDING", "LEG_SQUAT_COMPLIANT", "BACK_FLEXION_HAZARDOUS"
    is_hazardous_bend: bool
    team_lift_required: bool
    team_lift_compliant: bool
    workers_in_proximity: int
    ppe_high_vis_vest: bool
    ppe_hard_hat: bool
    ppe_compliant: bool
    ergonomic_safety_score: float         # 0.0 (extreme hazard) to 100.0 (fully compliant)
    violations: List[str]
    recommendation: Optional[str]


class ErgonomicSafetyAnalyzer:
    """Analyzes skeletal posture kinematics, team lift rules, and PPE compliance."""

    @classmethod
    def calculate_spine_flexion(
        cls,
        keypoints: Dict[str, Tuple[int, int]],
    ) -> float:
        """Calculates torso flexion angle relative to vertical (degrees).

        0 deg = perfectly upright standing.
        90 deg = horizontal back bending (extreme lumbar strain).
        """
        neck = keypoints.get("neck") or keypoints.get("nose")
        mid_hip = keypoints.get("mid_hip")

        if not neck or not mid_hip:
            return 0.0

        dx = neck[0] - mid_hip[0]
        dy = mid_hip[1] - neck[1]  # Inverted Y in image space (neck is higher = smaller y)

        if dy <= 0:
            # Upside down or completely bent forward
            return 90.0

        # Angle relative to vertical axis (dx=0, dy>0)
        angle_rad = math.atan2(abs(dx), dy)
        angle_deg = math.degrees(angle_rad)
        return round(float(angle_deg), 1)

    @classmethod
    def classify_lift_technique(
        cls,
        keypoints: Dict[str, Tuple[int, int]],
        spine_flexion_deg: float,
    ) -> Tuple[str, bool]:
        """Classifies lifting biomechanics into safe leg squat vs hazardous back bending."""
        left_hip = keypoints.get("left_hip")
        left_knee = keypoints.get("left_knee")
        left_ankle = keypoints.get("left_ankle")

        knee_flexion_detected = False
        if left_hip and left_knee and left_ankle:
            # Check vertical distance compression between hip and knee
            hip_knee_dy = abs(left_knee[1] - left_hip[1])
            knee_ankle_dy = abs(left_ankle[1] - left_knee[1])
            if knee_ankle_dy > 10 and hip_knee_dy < (knee_ankle_dy * 0.75):
                knee_flexion_detected = True

        if spine_flexion_deg > 45.0:
            if knee_flexion_detected:
                return ("PARTIAL_SQUAT_WARN", True)
            return ("BACK_FLEXION_HAZARDOUS", True)
        elif spine_flexion_deg > 25.0 and knee_flexion_detected:
            return ("LEG_SQUAT_COMPLIANT", False)
        elif spine_flexion_deg <= 25.0:
            return ("UPRIGHT_STANDING", False)

        return ("MODERATE_LEAN", False)

    @classmethod
    def inspect_ppe(
        cls,
        frame_bgr: np.ndarray,
        person_bbox: List[int],
    ) -> Tuple[bool, bool]:
        """Inspects upper body ROI for high-vis vest and head ROI for hard hat."""
        px, py, pw, ph = person_bbox
        frame_h, frame_w = frame_bgr.shape[:2]

        rx1 = max(0, px)
        ry1 = max(0, py)
        rx2 = min(frame_w, px + pw)
        ry2 = min(frame_h, py + ph)
        roi_w = rx2 - rx1
        roi_h = ry2 - ry1

        if roi_w < 20 or roi_h < 30:
            return (False, False)

        # ── Head ROI for Hard Hat (top 20% of person) ──
        head_roi = frame_bgr[ry1 : ry1 + int(roi_h * 0.22), rx1:rx2]
        has_hard_hat = False
        if head_roi.size > 0:
            hsv_head = cv2.cvtColor(head_roi, cv2.COLOR_BGR2HSV)
            # High-visibility yellow/white/orange safety helmet masks
            mask_yellow = cv2.inRange(hsv_head, np.array([20, 100, 100]), np.array([35, 255, 255]))
            mask_white = cv2.inRange(hsv_head, np.array([0, 0, 180]), np.array([180, 40, 255]))
            mask_orange = cv2.inRange(hsv_head, np.array([5, 120, 120]), np.array([18, 255, 255]))
            combined_helmet = cv2.bitwise_or(mask_yellow, cv2.bitwise_or(mask_white, mask_orange))
            ratio_helmet = np.sum(combined_helmet > 0) / float(head_roi.shape[0] * head_roi.shape[1])
            has_hard_hat = ratio_helmet >= 0.15

        # ── Torso ROI for High-Vis Vest (20% to 55% of person) ──
        torso_roi = frame_bgr[ry1 + int(roi_h * 0.20) : ry1 + int(roi_h * 0.55), rx1:rx2]
        has_high_vis = False
        if torso_roi.size > 0:
            hsv_torso = cv2.cvtColor(torso_roi, cv2.COLOR_BGR2HSV)
            # Fluorescent safety yellow/green (Hue 35-75, Sat > 80, Val > 80)
            # Fluorescent safety orange (Hue 5-18, Sat > 120, Val > 120)
            mask_hi_green = cv2.inRange(hsv_torso, np.array([35, 80, 80]), np.array([75, 255, 255]))
            mask_hi_orange = cv2.inRange(hsv_torso, np.array([5, 120, 120]), np.array([18, 255, 255]))
            combined_vest = cv2.bitwise_or(mask_hi_green, mask_hi_orange)
            ratio_vest = np.sum(combined_vest > 0) / float(torso_roi.shape[0] * torso_roi.shape[1])
            has_high_vis = ratio_vest >= 0.18

        return (bool(has_high_vis), bool(has_hard_hat))

    @classmethod
    def evaluate_ergonomic_safety(
        cls,
        frame_bgr: np.ndarray,
        person_bbox: List[int],
        keypoints: Dict[str, Tuple[int, int]],
        material_weight_kg: float = 0.0,
        material_tier: str = "SINGLE_UNIT",
        nearby_persons_count: int = 1,
        enforce_ppe: bool = True,
    ) -> ErgonomicAssessment:
        """Runs comprehensive ergonomic assessment for a worker handling materials.

        Args:
            frame_bgr: Video frame (BGR).
            person_bbox: [x, y, w, h] person bounding box.
            keypoints: Anatomical skeleton keypoints.
            material_weight_kg: Estimated gross weight of handled material.
            material_tier: "SINGLE_UNIT", "PACKAGED_BOX", or "BULK_MATERIAL".
            nearby_persons_count: Total workers active in the immediate 1.5m vicinity.
            enforce_ppe: Whether to check PPE requirements for the current zone.

        Returns:
            ErgonomicAssessment with OSHA/ISO compliance flags and safety score.
        """
        spine_flexion = cls.calculate_spine_flexion(keypoints)
        lift_technique, is_hazardous_bend = cls.classify_lift_technique(keypoints, spine_flexion)

        # Team lift check: Items > 25kg or BULK_MATERIAL tier require >= 2 people
        team_lift_req = (material_weight_kg >= 25.0) or (material_tier == "BULK_MATERIAL")
        team_lift_ok = True
        if team_lift_req and nearby_persons_count < 2:
            team_lift_ok = False

        has_vest, has_helmet = cls.inspect_ppe(frame_bgr, person_bbox)
        ppe_ok = (has_vest and has_helmet) if enforce_ppe else True

        violations: List[str] = []
        score = 100.0

        if is_hazardous_bend:
            violations.append(f"HAZARDOUS_SPINE_FLEXION: Torso bent at {spine_flexion} deg (limit: 45 deg)")
            score -= 35.0

        if not team_lift_ok:
            violations.append(
                f"TEAM_LIFT_VIOLATION: Solo handling of heavy material ({material_weight_kg:.1f}kg / {material_tier}) "
                f"requires >= 2 workers (active nearby: {nearby_persons_count})"
            )
            score -= 35.0

        if enforce_ppe:
            if not has_vest:
                violations.append("MISSING_PPE: High-Visibility Safety Vest not detected")
                score -= 15.0
            if not has_helmet:
                violations.append("MISSING_PPE: Safety Hard Hat not detected")
                score -= 15.0

        score = max(0.0, min(100.0, round(score, 1)))

        rec = None
        if violations:
            rec = "Instruct worker to bend at knees (squat lift), wear mandatory PPE, and request team assistance for loads > 25kg."

        return ErgonomicAssessment(
            person_box=person_bbox,
            spine_flexion_deg=spine_flexion,
            lift_technique=lift_technique,
            is_hazardous_bend=is_hazardous_bend,
            team_lift_required=team_lift_req,
            team_lift_compliant=team_lift_ok,
            workers_in_proximity=nearby_persons_count,
            ppe_high_vis_vest=has_vest,
            ppe_hard_hat=has_helmet,
            ppe_compliant=ppe_ok,
            ergonomic_safety_score=score,
            violations=violations,
            recommendation=rec,
        )
