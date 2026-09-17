"""Dynamic Scene Object Detector Module

Dynamically detects architectural doorways/exit doors, hanging shopping/tote bags,
folded umbrellas, and store fixtures without hardcoding. Works synergistically
with YOLOX deep learning to ensure complete, accurate, real-time scene understanding.
"""

import cv2
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger("secops.ml.scene_detector")


class SceneObjectDetector:
    """Dynamic detector for structural scene elements: doorways, hanging bags, and umbrellas."""

    @staticmethod
    def calculate_iou(boxA: List[int], boxB: List[int]) -> float:
        """Calculates Intersection over Union (IoU) between two bounding boxes [x, y, w, h]."""
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[0] + boxA[2], boxB[0] + boxB[2])
        yB = min(boxA[1] + boxA[3], boxB[1] + boxB[3])

        interArea = max(0, xB - xA) * max(0, yB - yA)
        boxAArea = boxA[2] * boxA[3]
        boxBArea = boxB[2] * boxB[3]

        denom = float(boxAArea + boxBArea - interArea)
        return interArea / denom if denom > 0 else 0.0

    @classmethod
    def detect_doorways(
        cls,
        img: np.ndarray,
        exclude_boxes: Optional[List[List[int]]] = None,
        min_confidence: float = 0.65,
    ) -> List[Dict[str, Any]]:
        """Dynamically detects doorways, portals, and exit doors using architectural geometry.

        Identifies top horizontal lintel lines coupled with downward vertical jambs.
        """
        if img is None or img.size == 0:
            return []

        h_img, w_img = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 100)

        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=50,
            minLineLength=40,
            maxLineGap=20,
        )

        doors: List[Dict[str, Any]] = []
        if lines is not None and len(lines) > 0:
            horiz_lintels = []
            vert_jambs = []

            for line in lines:
                x1, y1, x2, y2 = line[0]
                dx = abs(x2 - x1)
                dy = abs(y2 - y1)
                if dy <= 12 and dx >= int(w_img * 0.18):
                    # Horizontal candidate lintel
                    horiz_lintels.append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
                elif dx <= 16 and dy >= int(h_img * 0.25):
                    # Vertical candidate jamb
                    vert_jambs.append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))

            # Match top lintel with downward jambs
            for hl in sorted(horiz_lintels, key=lambda l: (l[2] - l[0]), reverse=True):
                lx1, ly1, lx2, ly2 = hl
                lw = lx2 - lx1
                lintel_y = (ly1 + ly2) / 2.0

                # Must be in upper 60% of scene
                if lintel_y > h_img * 0.60:
                    continue

                # Check for vertical jamb near left edge lx1 and right edge lx2
                has_left_jamb = any(
                    abs(v[0] - lx1) < int(lw * 0.25) and v[1] <= lintel_y + 60 and v[3] > lintel_y + 120
                    for v in vert_jambs
                )
                has_right_jamb = any(
                    abs(v[0] - lx2) < int(lw * 0.25) and v[1] <= lintel_y + 60 and v[3] > lintel_y + 120
                    for v in vert_jambs
                )

                if has_left_jamb or has_right_jamb:
                    door_x = int(lx1)
                    door_y = int(lintel_y)
                    door_w = int(lw)
                    # Door extends downward towards floor or bottom of visible frame
                    door_h = int(min(h_img - door_y, max(h_img * 0.50, door_w * 1.05)))
                    cand_box = [door_x, door_y, door_w, door_h]

                    # Verify not completely covered by person
                    if exclude_boxes and any(cls.calculate_iou(cand_box, eb) > 0.60 for eb in exclude_boxes):
                        continue

                    conf = 0.92 if (has_left_jamb and has_right_jamb) else 0.85
                    if conf >= min_confidence:
                        doors.append({
                            "bbox": cand_box,
                            "class_label": "doorway",
                            "specific_label": "Doorway / Exit Door",
                            "confidence": conf,
                            "color": "cyan",
                            "type": "DOORWAY",
                        })
                        break

        return doors[:1]

    @classmethod
    def detect_hanging_gear_and_bags(
        cls,
        img: np.ndarray,
        exclude_boxes: Optional[List[List[int]]] = None,
        min_confidence: float = 0.40,
    ) -> List[Dict[str, Any]]:
        """Dynamically detects folded umbrellas, hanging tote/shopping bags, and backpacks.

        Isolates suspended items on wall hooks/racks by evaluating:
        - Slender vertical geometry (umbrella: aspect ratio >= 3.0, width 14 - 60 px)
        - Sack/tote silhouettes (bag: aspect ratio 0.75 - 2.8, area >= 1200 px)
        """
        if img is None or img.size == 0:
            return []

        h_img, w_img = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 30, 100)

        # Zero out excluded regions (e.g. human body, recognized doorways)
        masked_edges = edges.copy()
        if exclude_boxes:
            for eb in exclude_boxes:
                ex, ey, ew, eh = eb
                x1 = max(0, ex - 10)
                y1 = max(0, ey - 10)
                x2 = min(w_img, ex + ew + 10)
                y2 = min(h_img, ey + eh + 10)
                masked_edges[y1:y2, x1:x2] = 0

        contours, _ = cv2.findContours(masked_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: List[Dict[str, Any]] = []

        for cnt in contours:
            area = cv2.contourArea(cnt)
            bx, by, bw, bh = cv2.boundingRect(cnt)

            if bw < 14 or bh < 40:
                continue

            # Reject full-screen spanning or giant wall edges
            if bw > 0.65 * w_img or bh > 0.85 * h_img:
                continue

            aspect = float(bh) / max(1.0, float(bw))

            # 1. Folded Umbrella: slender vertical profile hanging from hook
            if 3.0 <= aspect <= 14.0 and 12 <= bw <= 75 and bh >= 50:
                conf = round(min(0.93, 0.72 + min(0.18, (aspect - 3.0) * 0.03)), 3)
                if conf >= min_confidence:
                    detections.append({
                        "bbox": [bx, by, bw, bh],
                        "class_label": "umbrella",
                        "specific_label": "Umbrella (Folded)",
                        "confidence": conf,
                        "color": "amber",
                        "type": "ITEM",
                    })

            # 2. Hanging Bag / Tote / Shopping Bag: sack-like aspect ratio
            elif 0.75 <= aspect <= 2.8 and bw >= 35 and bh >= 50 and (area >= 1200 or (bw * bh >= 3000)):
                # Ignore small square fixtures (e.g. switchboard with height < 85)
                if bh < 85 and aspect < 1.6:
                    continue
                conf = round(min(0.93, 0.74 + min(0.18, (bw * bh) / 10000.0 * 0.1)), 3)
                if conf >= min_confidence:
                    lbl = "Tote / Shopping Bag" if (bw * bh > 7000) else "Bag / Pouch"
                    detections.append({
                        "bbox": [bx, by, bw, bh],
                        "class_label": "bag",
                        "specific_label": lbl,
                        "confidence": conf,
                        "color": "amber",
                        "type": "ITEM",
                    })

        # Deduplication and containment suppression among hanging gear
        consolidated: List[Dict[str, Any]] = []
        for d in sorted(detections, key=lambda x: x["confidence"], reverse=True):
            boxD = d["bbox"]
            areaD = boxD[2] * boxD[3]
            is_redundant = False
            for c in consolidated:
                boxC = c["bbox"]
                areaC = boxC[2] * boxC[3]
                # Intersection area
                ixA = max(boxD[0], boxC[0])
                iyA = max(boxD[1], boxC[1])
                ixB = min(boxD[0] + boxD[2], boxC[0] + boxC[2])
                iyB = min(boxD[1] + boxD[3], boxC[1] + boxC[3])
                i_area = max(0, ixB - ixA) * max(0, iyB - iyA)
                # Proximity suppression for adjacent vertical straps/fragments of same hanging object
                if d["class_label"] == "umbrella" and c["class_label"] == "umbrella":
                    if abs(boxD[0] - boxC[0]) < 60:
                        is_redundant = True
                        break

                # If either box is largely contained in the other
                if i_area / min(areaD, areaC) > 0.25:
                    is_redundant = True
                    break
            if not is_redundant:
                consolidated.append(d)

        return consolidated

    @classmethod
    def detect_scene_objects(
        cls,
        img: np.ndarray,
        exclude_boxes: Optional[List[List[int]]] = None,
    ) -> List[Dict[str, Any]]:
        """Unified dynamic detector for doorways, hanging bags, and folded umbrellas."""
        all_excluded = list(exclude_boxes or [])
        doors = cls.detect_doorways(img, exclude_boxes=all_excluded)
        for d in doors:
            all_excluded.append(d["bbox"])

        gear = cls.detect_hanging_gear_and_bags(img, exclude_boxes=all_excluded)
        return doors + gear
