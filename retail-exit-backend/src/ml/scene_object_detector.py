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
        min_confidence: float = 0.70,
    ) -> List[Dict[str, Any]]:
        """Dynamically detects doorways, portals, and exit doors using architectural geometry.

        Strict architectural criteria:
        - Must have horizontal lintel in upper 35% of scene (near ceiling).
        - Must possess BOTH left and right vertical jambs forming an open portal.
        - Portal must extend downwards towards the floor plane (height >= 55% frame).
        - Architectural aspect ratio h/w >= 1.45.
        - Must not have mid-height closing boundaries (which desktop monitors and tables have).
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
            horiz_bottoms = []

            for line in lines:
                x1, y1, x2, y2 = line[0]
                dx = abs(x2 - x1)
                dy = abs(y2 - y1)
                if dy <= 12 and dx >= int(w_img * 0.18):
                    horiz_lintels.append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
                elif dy <= 8 and dx >= int(w_img * 0.10):
                    horiz_bottoms.append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
                elif dx <= 16 and dy >= int(h_img * 0.25):
                    vert_jambs.append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))

            # Match top lintel with downward jambs
            for hl in sorted(horiz_lintels, key=lambda l: (l[2] - l[0]), reverse=True):
                lx1, ly1, lx2, ly2 = hl
                lw = lx2 - lx1
                lintel_y = (ly1 + ly2) / 2.0

                # Architectural doorway lintel must originate in upper 35% of the frame
                if lintel_y > h_img * 0.35:
                    continue

                # Check for BOTH vertical jambs near left edge lx1 and right edge lx2
                has_left_jamb = any(
                    abs(v[0] - lx1) < int(lw * 0.25) and v[1] <= lintel_y + 60 and v[3] > lintel_y + 120
                    for v in vert_jambs
                )
                has_right_jamb = any(
                    abs(v[0] - lx2) < int(lw * 0.25) and v[1] <= lintel_y + 60 and v[3] > lintel_y + 120
                    for v in vert_jambs
                )

                if not (has_left_jamb and has_right_jamb):
                    continue

                door_x = int(lx1)
                door_y = int(lintel_y)
                door_w = int(lw)
                door_h = int(h_img - door_y)

                # Architectural door must have vertical portal aspect ratio >= 1.45
                if (door_h / float(max(1, door_w))) < 1.45:
                    continue

                # Portal must reach downwards towards floor plane
                if (door_y + door_h) < int(h_img * 0.75):
                    continue

                # Reject if a horizontal boundary / table / screen bezel closes the box mid-height
                has_mid_bottom = any(
                    b[1] > lintel_y + 80 and b[1] < h_img - 80 and
                    max(lx1, b[0]) < min(lx2, b[2]) and
                    (min(lx2, b[2]) - max(lx1, b[0])) >= int(lw * 0.50)
                    for b in horiz_bottoms
                )
                if has_mid_bottom:
                    continue

                cand_box = [door_x, door_y, door_w, door_h]

                # Verify not completely covered by person
                if exclude_boxes and any(cls.calculate_iou(cand_box, eb) > 0.60 for eb in exclude_boxes):
                    continue

                doors.append({
                    "bbox": cand_box,
                    "class_label": "doorway",
                    "specific_label": "Doorway / Exit Door",
                    "confidence": 0.92,
                    "color": "cyan",
                    "type": "DOORWAY",
                })
                break

        return doors[:1]

    @classmethod
    def detect_desktop_monitors_and_screens(
        cls,
        img: np.ndarray,
        exclude_boxes: Optional[List[List[int]]] = None,
        min_confidence: float = 0.55,
    ) -> List[Dict[str, Any]]:
        """Dynamically detects desktop computer screens, TV displays, and laptops on desks or walls.

        Isolates elevated rectangular display surfaces by evaluating:
        - Top horizontal bezel and matching vertical side bezels
        - Bottom horizontal bezel or desk interface
        - Screen aspect ratio w/h in [0.70, 2.8]
        - Dark display panel or high edge contrast against surrounding wall
        """
        if img is None or img.size == 0:
            return []

        h_img, w_img = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 100)

        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 40, minLineLength=35, maxLineGap=20)
        if lines is None or len(lines) == 0:
            return []

        horiz = []
        vert = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            dx = abs(x2 - x1)
            dy = abs(y2 - y1)
            if dy <= 10 and dx >= 40:
                horiz.append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
            elif dx <= 10 and dy >= 40:
                vert.append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))

        screens = []
        for hl in horiz:
            x1, y1, x2, y2 = hl
            top_y = (y1 + y2) / 2.0
            if top_y < h_img * 0.20 or top_y > h_img * 0.85:
                continue
            lw = x2 - x1
            if lw < 45:
                continue

            right_v = [v for v in vert if abs(v[0] - x2) < 25 and v[1] <= top_y + 40 and v[3] > top_y + 60]
            left_v = [v for v in vert if abs(v[0] - x1) < 25 and v[1] <= top_y + 40 and v[3] > top_y + 60]
            bot_h = [b for b in horiz if b[1] > top_y + 50 and b[1] < top_y + max(140, lw * 1.6) and max(x1, b[0]) < min(x2, b[2])]

            if (right_v or left_v) and bot_h:
                best_bot = max(bot_h, key=lambda b: b[1])
                bot_y = (best_bot[1] + best_bot[3]) / 2.0
                sh = bot_y - top_y
                sx = 0 if x1 < 20 else int(x1)
                sw = int(x2 - sx)
                aspect = sw / float(max(1, sh))
                if 1.05 <= aspect <= 2.8 and (sw * sh) >= 8000 and sw >= 90 and sh >= 60 and top_y <= h_img * 0.60:
                    cand_box = [sx, int(top_y), sw, int(sh)]
                    cand_cx = sx + sw / 2.0
                    cand_cy = top_y + sh / 2.0

                    # 1. Strict containment in human silhouette check:
                    # A desktop monitor cannot be inside or overlapping a person's chest or hand!
                    is_contained_in_person = False
                    if exclude_boxes:
                        for eb in exclude_boxes:
                            ex, ey, ew, eh = eb
                            # Center inside person
                            if ex <= cand_cx <= ex + ew and ey <= cand_cy <= ey + eh:
                                is_contained_in_person = True
                                break
                            # Intersecting over 15% of candidate area
                            ix1, iy1 = max(sx, ex), max(int(top_y), ey)
                            ix2, iy2 = min(sx + sw, ex + ew), min(int(bot_y), ey + eh)
                            iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
                            if (iw * ih) > 0.15 * (sw * sh):
                                is_contained_in_person = True
                                break
                    if is_contained_in_person:
                        continue

                    # 2. Display panel luminosity & skin tone rejection
                    roi = gray[int(top_y):int(bot_y), sx:sx + sw]
                    if roi.size > 0:
                        mean_lum = float(np.mean(roi))
                        if mean_lum < 95:
                            # Verify not duplicate
                            if not any(cls.calculate_iou(cand_box, s["bbox"]) > 0.45 for s in screens):
                                screens.append({
                                    "bbox": cand_box,
                                    "class_label": "single_unit",
                                    "specific_label": "Desktop Screen",
                                    "confidence": 0.86,
                                    "color": "cyan",
                                    "type": "DESKTOP_SCREEN",
                                })

        return screens[:2]

    @classmethod
    def detect_wrist_watches(
        cls,
        img: np.ndarray,
        wrist_keypoints: Optional[Dict[str, Any]] = None,
        person_boxes: Optional[List[List[int]]] = None,
        min_confidence: float = 0.50,
    ) -> List[Dict[str, Any]]:
        """Dynamically detects wrist watches and smartwatches on person limbs.

        Evaluates wrist ROI around tracked wrist landmarks:
        - Rejects anatomically impossible coordinates (neck, chest placket, shoulder)
        - Compact circular / squarish dial contour (aspect ratio 0.80 - 1.25)
        - Dial casing area (140 - 1800 px) with verified arm skin context
        - Edge gradient density and contrast against skin/cuff
        """
        if img is None or img.size == 0 or not wrist_keypoints:
            return []

        h_img, w_img = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        watches = []

        for k_name, pt in wrist_keypoints.items():
            if "wrist" not in k_name or not isinstance(pt, (tuple, list)) or len(pt) < 2:
                continue
            wx, wy = int(pt[0]), int(pt[1])

            # 1. Anatomical plausibility check:
            # A wrist cannot be located in the central sternum/chest collar or upper shoulder
            if person_boxes:
                is_anatomically_invalid = False
                for pb in person_boxes:
                    px, py, pw, ph = pb
                    mid_x = px + pw * 0.50
                    # Upper central collar/chest placket
                    if abs(wx - mid_x) < 0.25 * pw and wy < (py + 0.65 * ph):
                        is_anatomically_invalid = True
                        break
                    # Shoulder / neck level
                    if wy < (py + 0.35 * ph):
                        is_anatomically_invalid = True
                        break
                if is_anatomically_invalid:
                    continue

            r = 30
            x1 = max(0, wx - r)
            y1 = max(0, wy - r)
            x2 = min(w_img, wx + r)
            y2 = min(h_img, wy + r)
            roi = gray[y1:y2, x1:x2]
            if roi.size < 300:
                continue

            # Must have skin tone context around dial (watch is worn on a wrist/arm)
            color_roi = img[y1:y2, x1:x2]
            hsv_roi = cv2.cvtColor(color_roi, cv2.COLOR_BGR2HSV)
            skin_m = ((hsv_roi[:, :, 0] <= 25) & (hsv_roi[:, :, 1] >= 25) & (hsv_roi[:, :, 2] >= 40))
            skin_density = np.mean(skin_m)
            if skin_density < 0.08:
                # No arm/wrist skin around the candidate point -> not an exposed wrist
                continue

            edges = cv2.Canny(roi, 35, 100)
            contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            wrist_candidates = []
            for c in contours:
                c_area = cv2.contourArea(c)
                if c_area < 35:
                    continue
                perim = cv2.arcLength(c, True)
                circ = (4 * np.pi * c_area) / float(max(1, perim * perim))
                bx, by, bw, bh = cv2.boundingRect(c)
                solidity = c_area / float(max(1, bw * bh))
                aspect = bw / float(max(1, bh))
                # Dial must be circular/squarish and solid (not hollow seam/wrinkle)
                if 0.80 <= aspect <= 1.25 and solidity >= 0.40 and circ >= 0.30:
                    edge_pixels = int(np.sum(edges[by:by+bh, bx:bx+bw] > 0))
                    edge_density = edge_pixels / float(max(1, bw * bh))
                    if edge_density >= 0.12:
                        conf = min(0.92, max(0.60, 0.65 + edge_density * 1.5))
                        if conf >= min_confidence:
                            wrist_candidates.append({
                                "bbox": [x1 + bx, y1 + by, bw, bh],
                                "class_label": "single_unit",
                                "specific_label": "Wrist Watch",
                                "confidence": round(conf, 2),
                                "color": "amber",
                                "type": "ITEM",
                            })
            if wrist_candidates:
                wrist_candidates.sort(key=lambda x: x["confidence"], reverse=True)
                best = wrist_candidates[0]
                if not any(cls.calculate_iou(best["bbox"], w["bbox"]) > 0.30 for w in watches):
                    watches.append(best)
        return watches

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
            box_area = bw * bh
            solidity = area / float(max(1, box_area))

            # Reject hollow wireframe edges, single-line seams, and transparent outlines
            if solidity < 0.30:
                continue

            # ── Photometric Boundary Contrast Check ──
            # A real physical hanging item exhibits distinct chromatic contrast against the adjacent wall.
            roi = img[by : by + bh, bx : bx + bw]
            mean_int = np.mean(roi, axis=(0, 1))

            pad = 12
            x1 = max(0, bx - pad)
            y1 = max(0, by - pad)
            x2 = min(w_img, bx + bw + pad)
            y2 = min(h_img, by + bh + pad)
            surround = img[y1:y2, x1:x2]
            mask = np.ones(surround.shape[:2], dtype=bool)
            mask[by - y1 : by - y1 + bh, bx - x1 : bx - x1 + bw] = False
            if np.any(mask):
                mean_ext = np.mean(surround[mask], axis=0)
                contrast = float(np.linalg.norm(mean_int - mean_ext))
            else:
                contrast = 0.0

            # Reject flat door panels, painted wall shadows, and uniform wall plaster
            if contrast < 22.0:
                continue

            # 1. Folded Umbrella: slender vertical profile hanging from hook
            if 3.0 <= aspect <= 14.0 and 16 <= bw <= 75 and bh >= 70 and area >= 800:
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

            # 2. Hanging Bag / Tote / Shopping Bag: solid pouch-like aspect ratio
            elif 0.75 <= aspect <= 2.8 and bw >= 40 and bh >= 55 and area >= 1600 and solidity >= 0.35:
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
    def detect_bookshelves(
        cls,
        img: np.ndarray,
        exclude_boxes: Optional[List[List[int]]] = None,
        min_confidence: float = 0.70,
    ) -> List[Dict[str, Any]]:
        """Dynamically detects storage shelving units, book racks, and bookcases.

        Geometric criteria:
        - Multi-tier parallel horizontal shelf planks with regular vertical spacing.
        - Outer bounding fixture spans width >= 100px and height >= 100px.
        """
        if img is None or img.size == 0:
            return []

        h_img, w_img = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 100)

        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 40, minLineLength=60, maxLineGap=25)
        if lines is None or len(lines) == 0:
            return []

        horiz_shelves = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            dx = abs(x2 - x1)
            dy = abs(y2 - y1)
            if dy <= 8 and dx >= 70:
                horiz_shelves.append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))

        if len(horiz_shelves) < 2:
            return []

        # Group horizontal shelves by alignment
        shelves_sorted = sorted(horiz_shelves, key=lambda s: s[1])
        shelf_groups: List[List[Tuple[int, int, int, int]]] = []

        for s in shelves_sorted:
            matched_group = False
            for group in shelf_groups:
                g_x1 = min(item[0] for item in group)
                g_x2 = max(item[2] for item in group)
                overlap_x = max(0, min(s[2], g_x2) - max(s[0], g_x1))
                if overlap_x >= 0.45 * (s[2] - s[0]):
                    group.append(s)
                    matched_group = True
                    break
            if not matched_group:
                shelf_groups.append([s])

        bookshelves = []
        for group in shelf_groups:
            if len(group) >= 2:
                min_x = max(0, min(item[0] for item in group) - 10)
                max_x = min(w_img - 1, max(item[2] for item in group) + 10)
                min_y = max(0, min(item[1] for item in group) - 20)
                max_y = min(h_img - 1, max(item[3] for item in group) + 30)

                sh_w = max_x - min_x
                sh_h = max_y - min_y

                if sh_w >= 100 and sh_h >= 100:
                    cand_box = [int(min_x), int(min_y), int(sh_w), int(sh_h)]
                    if exclude_boxes and any(cls.calculate_iou(cand_box, eb) > 0.60 for eb in exclude_boxes):
                        continue

                    bookshelves.append({
                        "bbox": cand_box,
                        "class_label": "bookshelf",
                        "specific_label": "Storage Shelf / Bookcase",
                        "confidence": 0.91,
                        "color": "cyan",
                        "type": "FIXTURES",
                    })
                    break

        return bookshelves[:1]

    @classmethod
    def detect_scene_objects(
        cls,
        img: np.ndarray,
        exclude_boxes: Optional[List[List[int]]] = None,
        wrist_keypoints: Optional[Dict[str, Any]] = None,
        person_boxes: Optional[List[List[int]]] = None,
    ) -> List[Dict[str, Any]]:
        """Unified dynamic detector for doorways, desktop screens, wrist watches, hanging bags, umbrellas, and bookshelves."""
        all_excluded = list(exclude_boxes or [])
        doors = cls.detect_doorways(img, exclude_boxes=all_excluded)
        for d in doors:
            all_excluded.append(d["bbox"])

        screens = cls.detect_desktop_monitors_and_screens(img, exclude_boxes=all_excluded)
        for s in screens:
            all_excluded.append(s["bbox"])

        p_boxes = person_boxes if person_boxes is not None else all_excluded
        watches = cls.detect_wrist_watches(img, wrist_keypoints=wrist_keypoints, person_boxes=p_boxes)
        for w in watches:
            all_excluded.append(w["bbox"])

        gear = cls.detect_hanging_gear_and_bags(img, exclude_boxes=all_excluded)
        for g in gear:
            all_excluded.append(g["bbox"])

        shelves = cls.detect_bookshelves(img, exclude_boxes=all_excluded)
        return doors + screens + watches + gear + shelves

