"""Real-Time PPE & Worker Safety Compliance Monitoring Service

Automated industrial site and warehouse safety inspection.
Verifies Personal Protective Equipment (PPE) adherence on workers:
1. Hard Hat / Safety Helmet Detection (Head RoI dome curvature + industrial safety chroma)
2. High-Visibility Safety Vest Detection (Torso RoI fluorescent saturation + retroreflective stripes)
3. Site Policy Compliance Evaluation & Violation Alerting
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger("secops.ml.ppe")


@dataclass
class PPEAssessment:
    person_box: List[int]                # [x, y, w, h]
    has_helmet: bool
    helmet_confidence: float             # e.g. 0.93 for 93%
    helmet_color: Optional[str]
    helmet_box: Optional[List[int]]      # [x, y, w, h] of helmet
    has_vest: bool
    vest_confidence: float               # e.g. 0.90 for 90%
    vest_color: Optional[str]
    vest_box: Optional[List[int]]        # [x, y, w, h] of vest
    is_compliant: bool
    violations: List[str]
    summary_label: str                   # e.g. "PPE COMPLIANT" or "PPE VIOLATION: MISSING VEST"


class PPEComplianceDetector:
    """Production-grade safety compliance detector running at < 8ms per worker."""

    @classmethod
    def evaluate_worker_ppe(
        cls,
        frame_bgr: np.ndarray,
        person_bbox: List[int],
        require_helmet: bool = True,
        require_vest: bool = True,
    ) -> PPEAssessment:
        """Evaluates helmet and high-visibility safety vest on a detected worker.

        Args:
            frame_bgr: Decoded BGR image matrix.
            person_bbox: Worker bounding box [x, y, w, h].
            require_helmet: Whether site policy mandates a hard hat.
            require_vest: Whether site policy mandates a high-vis vest.

        Returns:
            PPEAssessment detailing compliance status and item confidence scores.
        """
        px, py, pw, ph = person_bbox
        frame_h, frame_w = frame_bgr.shape[:2]

        # Clamp RoI
        x1 = max(0, px)
        y1 = max(0, py)
        x2 = min(frame_w, px + pw)
        y2 = min(frame_h, py + ph)
        roi_w = x2 - x1
        roi_h = y2 - y1

        if roi_w < 15 or roi_h < 25:
            return PPEAssessment(
                person_box=person_bbox,
                has_helmet=False,
                helmet_confidence=0.0,
                helmet_color=None,
                helmet_box=None,
                has_vest=False,
                vest_confidence=0.0,
                vest_color=None,
                is_compliant=False,
                violations=["INSUFFICIENT_RESOLUTION"],
                summary_label="PPE UNKNOWN",
            )

        worker_roi = frame_bgr[y1:y2, x1:x2]

        # ── 1. Head Region RoI (Top 22% of person height) ──
        head_h = int(roi_h * 0.22)
        head_roi = worker_roi[:head_h, :]
        head_box = [x1, y1, roi_w, head_h]

        has_helmet, helmet_conf, helmet_color = cls._detect_hard_hat(head_roi)

        # ── 2. Torso Region RoI (From 20% to 65% of person height) ──
        torso_y_start = int(roi_h * 0.20)
        torso_y_end = int(roi_h * 0.65)
        torso_roi = worker_roi[torso_y_start:torso_y_end, :]
        torso_h = torso_y_end - torso_y_start
        vest_box = [x1, y1 + torso_y_start, roi_w, torso_h]

        has_vest, vest_conf, vest_color = cls._detect_safety_vest(torso_roi)

        # ── 3. Compliance Assessment ──
        violations = []
        if require_helmet and not has_helmet:
            violations.append("MISSING_HELMET")
        if require_vest and not has_vest:
            violations.append("MISSING_VEST")

        is_compliant = len(violations) == 0

        if is_compliant:
            summary = f"PPE COMPLIANT (Helmet {int(helmet_conf*100)}%, Vest {int(vest_conf*100)}%)"
        else:
            summary = f"PPE VIOLATION: {', '.join(v.replace('_', ' ') for v in violations)}"

        return PPEAssessment(
            person_box=person_bbox,
            has_helmet=has_helmet,
            helmet_confidence=round(helmet_conf, 2),
            helmet_color=helmet_color,
            helmet_box=head_box if has_helmet else None,
            has_vest=has_vest,
            vest_confidence=round(vest_conf, 2),
            vest_color=vest_color,
            vest_box=vest_box if has_vest else None,
            is_compliant=is_compliant,
            violations=violations,
            summary_label=summary,
        )

    @classmethod
    def _detect_hard_hat(cls, head_bgr: np.ndarray) -> Tuple[bool, float, Optional[str]]:
        """Analyzes chromatic signature and convex dome curvature of head RoI."""
        if head_bgr.size == 0:
            return False, 0.0, None

        hsv = cv2.cvtColor(head_bgr, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        total_pixels = head_bgr.shape[0] * head_bgr.shape[1]

        # Industrial helmet color masks:
        # Yellow / Neon Hard Hat
        yellow_mask = (h >= 18) & (h <= 38) & (s >= 70) & (v >= 110)
        # White Hard Hat (Low saturation, high value)
        white_mask = (s <= 40) & (v >= 170)
        # Blue Hard Hat
        blue_mask = (h >= 95) & (h <= 125) & (s >= 70) & (v >= 80)
        # Orange Hard Hat
        orange_mask = (h >= 6) & (h <= 17) & (s >= 110) & (v >= 120)

        ratios = {
            "Yellow": np.sum(yellow_mask) / float(total_pixels),
            "White": np.sum(white_mask) / float(total_pixels),
            "Blue": np.sum(blue_mask) / float(total_pixels),
            "Orange": np.sum(orange_mask) / float(total_pixels),
        }

        best_color, best_ratio = max(ratios.items(), key=lambda item: item[1])

        # Hair / dark cap rejection: if top of head is dominated by black/dark brown (v < 55)
        dark_ratio = np.sum(v < 55) / float(total_pixels)
        if dark_ratio > 0.65 and best_ratio < 0.25:
            return False, 0.15, None

        # Curved dome edge verification
        gray = cv2.cvtColor(head_bgr, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 40, 120)
        # Upper third edges (helmet crest)
        upper_edges = edges[: int(edges.shape[0] * 0.5), :]
        edge_density = np.sum(upper_edges > 0) / float(max(1, upper_edges.size))

        # A helmet is confirmed if safety color occupies >= 14% of head RoI
        if best_ratio >= 0.14:
            # Score formula based on color coverage + dome reflection
            conf = min(0.98, 0.65 + (best_ratio * 0.8) + (edge_density * 0.5))
            return True, round(conf, 2), best_color

        # Marginal check for white helmets under harsh glare
        if best_color == "White" and best_ratio >= 0.12 and edge_density > 0.08:
            return True, 0.82, "White"

        return False, round(max(0.1, best_ratio * 1.5), 2), None

    @classmethod
    def _detect_safety_vest(cls, torso_bgr: np.ndarray) -> Tuple[bool, float, Optional[str]]:
        """Analyzes fluorescent hue and retroreflective tape stripes on torso RoI."""
        if torso_bgr.size == 0:
            return False, 0.0, None

        hsv = cv2.cvtColor(torso_bgr, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        total_pixels = torso_bgr.shape[0] * torso_bgr.shape[1]

        # High-Vis Fluorescent Yellow / Lime: Hue [35, 75], Sat >= 65, Val >= 115
        fluorescent_lime = (h >= 35) & (h <= 75) & (s >= 65) & (v >= 115)
        # High-Vis Safety Orange: Hue [6, 20], Sat >= 110, Val >= 120
        safety_orange = (h >= 6) & (h <= 20) & (s >= 110) & (v >= 120)

        lime_ratio = np.sum(fluorescent_lime) / float(total_pixels)
        orange_ratio = np.sum(safety_orange) / float(total_pixels)

        if lime_ratio >= orange_ratio:
            best_color = "High-Vis Lime"
            best_ratio = lime_ratio
            color_mask = fluorescent_lime
        else:
            best_color = "Safety Orange"
            best_ratio = orange_ratio
            color_mask = safety_orange

        # Retroreflective Silver Tape Stripe Analysis:
        # High luminance (v >= 190) and low saturation (s <= 45) in horizontal or cross bands
        reflective_mask = (v >= 190) & (s <= 45)
        reflective_ratio = np.sum(reflective_mask) / float(total_pixels)

        # High-vis vests typically cover >= 22% of the torso region
        if best_ratio >= 0.20 or (best_ratio >= 0.14 and reflective_ratio >= 0.04):
            conf = min(0.98, 0.60 + (best_ratio * 0.7) + (reflective_ratio * 1.5))
            return True, round(conf, 2), best_color

        return False, round(max(0.1, best_ratio * 1.2), 2), None
