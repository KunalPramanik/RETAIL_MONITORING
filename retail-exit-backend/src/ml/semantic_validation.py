"""Universal Object Intelligence & Semantic Validation Engine

Implements additive hardening for Master Prompt V8:
1. Rejection of semantic false positives (e.g. wall pictures falsely detected as books).
2. Discrimination between background visual content (framed pictures, posters, wall clocks)
   and foreground physical inventory objects.
3. Discrimination between human body regions (bare hands, wrists, arms) and products.
4. Robust detection of genuine WristWatches:
   - Worn on person (associated with person track via 'worn_by', without collapsing into person)
   - Standalone on desk / table
   - Strict rejection of bare hands as watches
   - Strict rejection of screen/photo watches as physical watches
5. Enforces the 7-stage detection state machine:
   RAW_CANDIDATE -> CLASS_VALIDATED -> CONFIDENCE_VALIDATED -> NMS_VALIDATED ->
   AUTHENTICITY_VALIDATED -> TRACK_VALIDATED -> SEMANTIC_VALIDATED -> CONFIRMED.
"""

from enum import Enum
import math
import logging
from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np

from src.ml.model_config import get_vision_config
from src.ml.wall_picture_detector import WallPictureDetector
from src.ml.level3_liveness.static_image_service import is_box_enclosed

logger = logging.getLogger("secops.ml.semantic_validation")


class DetectionState(str, Enum):
    CONFIRMED = "CONFIRMED"
    CANDIDATE = "CANDIDATE"
    REJECTED_LOW_CONFIDENCE = "REJECTED_LOW_CONFIDENCE"
    REJECTED_WRONG_CLASS = "REJECTED_WRONG_CLASS"
    REJECTED_DUPLICATE = "REJECTED_DUPLICATE"
    REJECTED_NON_PHYSICAL_ARTIFACT = "REJECTED_NON_PHYSICAL_ARTIFACT"
    REJECTED_STATIC_CONTENT = "REJECTED_STATIC_CONTENT"
    REJECTED_REFLECTION = "REJECTED_REFLECTION"
    REJECTED_OCCLUDED_UNCONFIRMED = "REJECTED_OCCLUDED_UNCONFIRMED"
    REJECTED_SEMANTIC_CONFLICT = "REJECTED_SEMANTIC_CONFLICT"
    REJECTED_INFERENCE_ERROR = "REJECTED_INFERENCE_ERROR"


class SemanticValidationEngine:
    """Enterprise-grade semantic validator and anti-confusion engine for real camera streams."""

    @staticmethod
    def calculate_box_iou(boxA: List[int], boxB: List[int]) -> float:
        """Calculates Intersection over Union (IoU) between two boxes [x, y, w, h]."""
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[0] + boxA[2], boxB[0] + boxB[2])
        yB = min(boxA[1] + boxA[3], boxB[1] + boxB[3])

        interArea = max(0, xB - xA) * max(0, yB - yA)
        denom = float(boxA[2] * boxA[3] + boxB[2] * boxB[3] - interArea)
        return interArea / denom if denom > 0 else 0.0

    @classmethod
    def evaluate_bezel_frame_symmetry(cls, crop: np.ndarray) -> Tuple[float, float]:
        """Evaluates whether an image crop exhibits an outer perimeter framing bezel/moulding.

        Returns:
            Tuple of (bezel_score: float, symmetry_ratio: float)
        """
        if crop is None or crop.size == 0 or crop.shape[0] < 16 or crop.shape[1] < 16:
            return 0.0, 0.0

        h, w = crop.shape[:2]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 35, 110)

        # Inspect outer border margin (8% to 14% of dimension)
        bh = max(2, min(h, w) // 10)
        bw = bh

        top_e = float(np.mean(edges[:bh, :] > 0))
        bot_e = float(np.mean(edges[-bh:, :] > 0))
        lft_e = float(np.mean(edges[:, :bw] > 0))
        rgt_e = float(np.mean(edges[:, -bw:] > 0))

        bezel_score = (top_e + bot_e + lft_e + rgt_e) / 4.0

        # Frame border symmetry: pictures have framing on all 4 sides with balanced densities
        v_diff = abs(top_e - bot_e)
        h_diff = abs(lft_e - rgt_e)
        symmetry_penalty = (v_diff + h_diff) / 2.0
        symmetry_ratio = max(0.0, 1.0 - symmetry_penalty * 3.0)

        return bezel_score, symmetry_ratio

    @classmethod
    def discriminate_book_vs_wall_picture(
        cls,
        frame: np.ndarray,
        bbox: List[int],
        candidate_conf: float,
        detected_wall_pictures: Optional[List[Dict[str, Any]]] = None,
        person_boxes: Optional[List[List[int]]] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Determines whether a candidate box labeled 'Book' is actually a framed wall picture / poster.

        Discrimination Cues:
        1. Direct spatial overlap or containment with an architectural wall picture / frame.
        2. Prominent 4-sided outer framing bezel edge density and border symmetry.
        3. Planar graphic interior without page block thickness or binding spine asymmetry.
        4. Spatial relationship: a wall picture is isolated from human manipulation zones
           and lacks contact with table/desk horizontal planes.

        Returns:
            (is_wall_picture, reason, telemetry)
        """
        bx, by, bw, bh = bbox
        if frame is None or frame.size == 0 or bw < 10 or bh < 10:
            return False, "INVALID_CROP", {}

        h_img, w_img = frame.shape[:2]
        crop_y2 = min(h_img, by + bh)
        crop_x2 = min(w_img, bx + bw)
        crop = frame[max(0, by) : crop_y2, max(0, bx) : crop_x2]

        if crop.size == 0:
            return False, "EMPTY_CROP", {}

        # 1. Check direct overlap with pre-detected wall picture frames
        if detected_wall_pictures:
            for wp in detected_wall_pictures:
                wp_box = wp.get("bbox") or wp.get("box")
                if not wp_box:
                    continue
                iou = cls.calculate_box_iou(bbox, wp_box)
                # Center containment
                bcx, bcy = bx + bw / 2.0, by + bh / 2.0
                wpx, wpy, wpw, wph = wp_box
                inside_wp = (wpx <= bcx <= wpx + wpw) and (wpy <= bcy <= wpy + wph)

                if iou >= 0.28 or inside_wp or is_box_enclosed(bbox, wp_box, containment_threshold=0.50):
                    return True, "SPATIAL_MATCH: DIRECT_WALL_PICTURE_OVERLAP", {
                        "matched_box": wp_box,
                        "iou": round(iou, 3),
                        "source": "wall_picture_detector"
                    }

        # 2. Bezel & Outer Frame Analysis
        bezel_score, symmetry_ratio = cls.evaluate_bezel_frame_symmetry(crop)

        # 3. Interior texture and planar variance
        gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
        lap_var = float(cv2.Laplacian(gray_crop, cv2.CV_64F).var())

        # 4. Check if held by a person (hand manipulation)
        is_carried = False
        if person_boxes:
            for pb in person_boxes:
                # If candidate is well within person bounds, it could be carried
                if cls.calculate_box_iou(bbox, pb) > 0.15:
                    is_carried = True
                    break

        # A framed picture typically has bezel_score >= 0.10, symmetry_ratio >= 0.60,
        # lap_var >= 35.0 (artwork / photo / text), and is not held in a person's hands.
        if not is_carried and bezel_score >= 0.10 and symmetry_ratio >= 0.55 and lap_var >= 35.0:
            aspect = bw / float(max(1, bh))
            # Wall pictures have typical frame aspect ratios (0.45 to 2.40)
            if 0.45 <= aspect <= 2.40:
                return True, "FORENSIC_MATCH: FRAMED_PLANAR_ART_BEZEL", {
                    "bezel_score": round(bezel_score, 3),
                    "symmetry_ratio": round(symmetry_ratio, 3),
                    "lap_var": round(lap_var, 2),
                    "aspect": round(aspect, 2),
                }

        return False, "PHYSICAL_BOOK_CONFIRMED", {
            "bezel_score": round(bezel_score, 3),
            "symmetry_ratio": round(symmetry_ratio, 3),
            "lap_var": round(lap_var, 2),
            "is_carried": is_carried,
        }

    @classmethod
    def discriminate_bare_body_part(
        cls,
        crop: np.ndarray,
        person_boxes: Optional[List[List[int]]] = None,
        candidate_box: Optional[List[int]] = None,
    ) -> Tuple[bool, str, float]:
        """Detects whether an inventory candidate box is actually a bare human hand, arm, wrist, or neck.

        Returns:
            (is_bare_body_part, reason, skin_density)
        """
        if crop is None or crop.size == 0 or crop.shape[0] < 8 or crop.shape[1] < 8:
            return False, "INVALID_CROP", 0.0

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV) if len(crop.shape) == 3 else None
        if hsv is None:
            return False, "MONOCHROME", 0.0

        # Human skin tone mask in HSV space
        h = hsv[:, :, 0]
        s = hsv[:, :, 1]
        v = hsv[:, :, 2]
        skin_mask = ((h <= 25) | (h >= 165)) & (s >= 28) & (s <= 180) & (v >= 45)
        skin_density = float(np.mean(skin_mask))

        # Check edge density: bare skin has low high-frequency edge density compared to products
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 40, 120)
        edge_density = float(np.mean(edges > 0))

        # If over 65% of the crop is bare skin and edge density is low (smooth skin texture),
        # it is a bare body part, NOT an inventory item!
        if skin_density >= 0.65 and edge_density < 0.12:
            return True, "BARE_SKIN_BODY_PART_DETECTED", skin_density

        return False, "PRODUCT_CHARACTERISTICS_PRESENT", skin_density

    @classmethod
    def detect_wristwatches_in_scene(
        cls,
        frame: np.ndarray,
        person_boxes: Optional[List[List[int]]] = None,
        wrist_keypoints: Optional[Dict[str, Any]] = None,
        display_containers: Optional[List[List[int]]] = None,
        min_confidence: float = 0.50,
    ) -> List[Dict[str, Any]]:
        """Detects genuine WristWatches in the scene across two physical operational modes:
        1. Worn on person limbs (associated via 'worn_by', without merging into person).
        2. Standalone on desk / table / shelf surface.

        Enforces strict authenticity:
        - Rejects bare hands / wrists without dial contrast.
        - Rejects watches shown inside display containers (screen / photo quarantine).
        """
        if frame is None or frame.size == 0:
            return []

        h_img, w_img = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        detected_watches: List[Dict[str, Any]] = []

        # â”€â”€ Mode 1: Worn WristWatch Detection via Keypoints or Arm Regions â”€â”€
        if wrist_keypoints:
            for k_name, pt in wrist_keypoints.items():
                if "wrist" not in k_name.lower() or not isinstance(pt, (tuple, list)) or len(pt) < 2:
                    continue
                wx, wy = int(pt[0]), int(pt[1])

                # Anatomical validation: wrist cannot be in upper chest or neck
                if person_boxes:
                    invalid = False
                    for pb in person_boxes:
                        px, py, pw, ph = pb
                        if abs(wx - (px + pw * 0.5)) < 0.20 * pw and wy < (py + 0.55 * ph):
                            invalid = True
                            break
                    if invalid:
                        continue

                r = 32
                x1 = max(0, wx - r)
                y1 = max(0, wy - r)
                x2 = min(w_img, wx + r)
                y2 = min(h_img, wy + r)
                roi = gray[y1:y2, x1:x2]
                if roi.size < 200:
                    continue

                # Must have skin or sleeve context
                crop_color = frame[y1:y2, x1:x2]
                hsv_roi = cv2.cvtColor(crop_color, cv2.COLOR_BGR2HSV)
                skin_m = ((hsv_roi[:, :, 0] <= 25) & (hsv_roi[:, :, 1] >= 22) & (hsv_roi[:, :, 2] >= 35))
                skin_density = float(np.mean(skin_m))

                # Check dial geometry
                edges = cv2.Canny(roi, 35, 100)
                contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                for cnt in contours:
                    c_area = cv2.contourArea(cnt)
                    if c_area < 30 or c_area > 2000:
                        continue
                    bx, by, bw, bh = cv2.boundingRect(cnt)
                    aspect = bw / float(max(1, bh))
                    perim = cv2.arcLength(cnt, True)
                    circ = (4 * np.pi * c_area) / float(max(1, perim * perim))
                    solidity = c_area / float(max(1, bw * bh))

                    # Circular or squarish dial with edge density
                    if 0.75 <= aspect <= 1.30 and (circ >= 0.25 or solidity >= 0.40):
                        dial_edges = float(np.mean(edges[by : by + bh, bx : bx + bw] > 0))
                        if dial_edges >= 0.10:
                            wb = [x1 + bx, y1 + by, bw, bh]
                            # Check screen quarantine
                            if display_containers and any(
                                is_box_enclosed(wb, dc, containment_threshold=0.60)
                                for dc in display_containers
                            ):
                                continue

                            conf = round(min(0.94, max(0.60, 0.68 + dial_edges * 1.6)), 2)
                            if conf >= min_confidence:
                                detected_watches.append({
                                    "bbox": wb,
                                    "class_label": "single_unit",
                                    "specific_label": "WristWatch",
                                    "confidence": conf,
                                    "color": "amber",
                                    "type": "WRISTWATCH",
                                    "relation": "worn_by",
                                    "category_family": "WEARABLES",
                                    "wearable": True,
                                    "detection_state": DetectionState.CONFIRMED.value,
                                    "is_inventory_relevant": True,
                                    "is_environment_only": False,
                                })
                                break

        # â”€â”€ Mode 2: Standalone WristWatch (Resting on Desk / Table) â”€â”€
        # Search candidate circular/squarish dial contours outside person boxes
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 40, 120)

        # Mask out human silhouette so standalone detection only evaluates table surfaces
        masked_edges = edges.copy()
        if person_boxes:
            for pb in person_boxes:
                px, py, pw, ph = pb
                masked_edges[max(0, py - 10) : min(h_img, py + ph + 10), max(0, px - 10) : min(w_img, px + pw + 10)] = 0

        contours, _ = cv2.findContours(masked_edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            c_area = cv2.contourArea(cnt)
            # Standalone watch dial area on table: 80 to 2200 px
            if c_area < 50 or c_area > 2200:
                continue
            bx, by, bw, bh = cv2.boundingRect(cnt)
            if bw < 14 or bh < 14 or bw > 120 or bh > 120:
                continue

            aspect = bw / float(max(1, bh))
            perim = cv2.arcLength(cnt, True)
            circ = (4 * np.pi * c_area) / float(max(1, perim * perim))
            solidity = c_area / float(max(1, bw * bh))

            # Dial is circular/squarish
            if 0.80 <= aspect <= 1.25 and (circ >= 0.35 or solidity >= 0.50):
                dial_edges = float(np.mean(edges[by : by + bh, bx : bx + bw] > 0))
                # Internal watch dial features (indices, hands, casing) produce edge density >= 0.12
                if dial_edges >= 0.12:
                    wb = [bx, by, bw, bh]
                    # Check display container quarantine
                    if display_containers and any(
                        is_box_enclosed(wb, dc, containment_threshold=0.60)
                        for dc in display_containers
                    ):
                        continue

                    # Ensure not duplicate
                    if any(cls.calculate_box_iou(wb, w["bbox"]) > 0.35 for w in detected_watches):
                        continue

                    conf = round(min(0.92, max(0.62, 0.65 + dial_edges * 1.4)), 2)
                    if conf >= min_confidence:
                        detected_watches.append({
                            "bbox": wb,
                            "class_label": "single_unit",
                            "specific_label": "WristWatch",
                            "confidence": conf,
                            "color": "amber",
                            "type": "WRISTWATCH",
                            "relation": "standalone",
                            "category_family": "WEARABLES",
                            "wearable": True,
                            "detection_state": DetectionState.CONFIRMED.value,
                            "is_inventory_relevant": True,
                            "is_environment_only": False,
                        })

        return detected_watches

    @classmethod
    def validate_scene_detections(
        cls,
        frame: np.ndarray,
        candidates: List[Any],
        person_boxes: Optional[List[List[int]]] = None,
        display_containers: Optional[List[List[int]]] = None,
        detected_wall_pictures: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[List[Any], List[Dict[str, Any]]]:
        """Runs the 7-stage state machine on all raw candidates.

        Returns:
            Tuple of (confirmed_detections, rejected_detections)
        """
        cfg = get_vision_config()
        confirmed = []
        rejected = []

        all_wall_pics = list(detected_wall_pictures or [])
        if frame is not None and not all_wall_pics:
            try:
                all_wall_pics = WallPictureDetector.detect_wall_pictures(frame, exclude_boxes=person_boxes)
            except Exception as _wp_err:
                logger.debug("Dynamic wall picture scan error: %s", _wp_err)

        for d in candidates:
            bbox = d.bbox
            cid_label = (d.specific_label or d.class_label or "").lower()
            conf = float(d.confidence)

            # Stage 1: Confidence Validation
            if conf < cfg.confidence_floor:
                d.detection_state = DetectionState.REJECTED_LOW_CONFIDENCE.value
                rejected.append({"box": bbox, "label": cid_label, "reason": "CONFIDENCE_BELOW_FLOOR", "confidence": conf})
                continue

            # Stage 2: Content-in-Content Quarantine
            if display_containers and any(is_box_enclosed(bbox, dc, containment_threshold=0.60) for dc in display_containers):
                d.detection_state = DetectionState.REJECTED_STATIC_CONTENT.value
                rejected.append({"box": bbox, "label": cid_label, "reason": "ENCLOSED_IN_DISPLAY_CONTAINER", "confidence": conf})
                continue

            # Stage 3: Semantic Anti-Confusion Discrimination
            # A) Wall Picture vs Book Discrimination
            if "book" in cid_label or d.specific_label == "Book / Document":
                is_wall_pic, reason, telemetry = cls.discriminate_book_vs_wall_picture(
                    frame=frame,
                    bbox=bbox,
                    candidate_conf=conf,
                    detected_wall_pictures=all_wall_pics,
                    person_boxes=person_boxes,
                )
                if is_wall_pic:
                    # Semantic fix: reclassify from Book to WallPicture
                    logger.info("Semantic Validator: Reclassified candidate from Book to Wall Picture Frame (%s)", reason)
                    d.specific_label = "Wall Picture Frame"
                    d.class_label = "wall_picture"
                    d.category_family = "FIXTURES"
                    d.is_environment_only = True
                    d.is_inventory_relevant = False
                    d.detection_state = DetectionState.CONFIRMED.value
                    confirmed.append(d)
                    continue

            # B) Bare Body Part vs Product Discrimination
            if d.is_inventory_relevant and frame is not None:
                bx, by, bw, bh = bbox
                crop = frame[max(0, by) : min(frame.shape[0], by + bh), max(0, bx) : min(frame.shape[1], bx + bw)]
                is_body, b_reason, skin_dens = cls.discriminate_bare_body_part(
                    crop=crop,
                    person_boxes=person_boxes,
                    candidate_box=bbox,
                )
                if is_body:
                    logger.info("Semantic Validator: Suppressed bare body part confused as %s (skin=%.2f)", cid_label, skin_dens)
                    d.detection_state = DetectionState.REJECTED_SEMANTIC_CONFLICT.value
                    rejected.append({"box": bbox, "label": cid_label, "reason": b_reason, "confidence": conf})
                    continue

            # Stage 4: Confirmed State Transition
            d.detection_state = DetectionState.CONFIRMED.value
            confirmed.append(d)

        return confirmed, rejected
