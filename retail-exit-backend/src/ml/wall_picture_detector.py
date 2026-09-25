"""Dynamic Real-Time Wall Picture & Frame Detection Service

Dynamically detects planar wall pictures, framed photos, posters, and wall art
in real time using geometric contour analysis, boundary bezel edge gradients,
and interior texture variance, without hardcoding.
"""

import cv2
import numpy as np
import logging
from typing import List, Dict, Any, Optional
from src.ml.static_image_service import StaticImageClassifier

logger = logging.getLogger("secops.ml.wall_picture_detector")


class WallPictureDetector:
    """Detects framed prints, wall posters, photographs, and planar wall art in CCTV scenes."""

    MIN_DIM = 24             # Minimum pixel dimension
    MAX_AREA_RATIO = 0.35    # At most 35% of total frame area
    MIN_ASPECT_RATIO = 0.35  # Vertical portrait frame
    MAX_ASPECT_RATIO = 2.80  # Horizontal panoramic frame

    @classmethod
    def detect_wall_pictures(
        cls,
        frame: np.ndarray,
        exclude_boxes: Optional[List[List[int]]] = None,
        max_detections: int = 6,
    ) -> List[Dict[str, Any]]:
        """Detects planar wall picture frames, posters, and wall art in the given frame.

        Args:
            frame: Full BGR frame (numpy array).
            exclude_boxes: Optional list of bounding boxes [x, y, w, h] to exclude (e.g. persons).
            max_detections: Maximum number of static wall frames to return.

        Returns:
            List of detected static picture dictionaries.
        """
        if frame is None or frame.size == 0 or frame.shape[0] < 60 or frame.shape[1] < 60:
            return []

        h_img, w_img = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 30, 100)

        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        candidates = []

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            # Filter candidate size: bounded between min dimension and 45% of frame dimensions
            if w < cls.MIN_DIM or h < cls.MIN_DIM or w > 0.45 * w_img or h > 0.45 * h_img:
                continue
            # Wall pictures are mounted on the wall (upper 75% of scene, not on floor/desk base)
            if (y + 0.5 * h) > 0.75 * h_img:
                continue
            aspect = float(w) / max(1.0, float(h))
            if not (cls.MIN_ASPECT_RATIO <= aspect <= cls.MAX_ASPECT_RATIO):
                continue

            # Exclude if overlapping with an excluded box (e.g. human body, face, bottles, monitors)
            if exclude_boxes:
                cx, cy = x + w * 0.5, y + h * 0.5
                overlap = False
                for eb in exclude_boxes:
                    ex, ey, ew, eh = eb
                    # Center inside an excluded box (e.g. collar inside human torso/face)
                    if ex <= cx <= ex + ew and ey <= cy <= ey + eh:
                        overlap = True
                        break
                    ix1, iy1 = max(x, ex), max(y, ey)
                    ix2, iy2 = min(x + w, ex + ew), min(y + h, ey + eh)
                    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
                    if (iw * ih) > 0.15 * (w * h):
                        overlap = True
                        break
                if overlap:
                    continue

            # Evaluate boundary bezel edge density (frames have straight perimeter lines)
            crop_edges = edges[y : y + h, x : x + w]
            border = max(2, min(h, w) // 10)
            top_e = np.mean(crop_edges[:border, :] > 0)
            bot_e = np.mean(crop_edges[-border:, :] > 0)
            lft_e = np.mean(crop_edges[:, :border] > 0)
            rgt_e = np.mean(crop_edges[:, -border:] > 0)
            bezel_score = float((top_e + bot_e + lft_e + rgt_e) / 4.0)

            # Evaluate interior texture variance (wall frames have graphics, text quotes, or photo detail)
            crop_gray = gray[y : y + h, x : x + w]
            inner_var = float(cv2.Laplacian(crop_gray, cv2.CV_64F).var())

            # Wall picture frames typically have bezel score >= 0.12 and interior variance >= 45.0
            if bezel_score >= 0.11 and inner_var >= 40.0:
                rank_score = bezel_score * inner_var
                candidates.append((x, y, w, h, rank_score, bezel_score, inner_var))

        if not candidates:
            return []

        # Non-Maximum Suppression to eliminate redundant nested frames
        boxes_for_nms = [[c[0], c[1], c[2], c[3]] for c in candidates]
        scores_for_nms = [float(c[4]) for c in candidates]
        indices = cv2.dnn.NMSBoxes(boxes_for_nms, scores_for_nms, 5.0, 0.35)

        results: List[Dict[str, Any]] = []
        if len(indices) > 0:
            for idx in np.array(indices).flatten():
                bx, by, bw, bh = boxes_for_nms[idx]
                crop = frame[by : by + bh, bx : bx + bw]
                if crop.size == 0:
                    continue

                # Run through StaticImageClassifier for forensic categorization
                cls_res = StaticImageClassifier.classify_crop(
                    crop=crop,
                    liveness_score=0.15,
                    has_face_geometry=False,
                    skin_ratio=0.0,
                )

                cat = cls_res.classification
                if cat == "POSTER_OR_SIGNAGE":
                    friendly_name = "Wall Picture / Poster"
                elif cat == "PERSON_PHOTO":
                    friendly_name = "Framed Photo"
                elif cat == "RELIGIOUS_IMAGE":
                    friendly_name = "Framed Sacred Art"
                elif cat == "SCREEN_DISPLAY":
                    friendly_name = "Screen / Display"
                else:
                    friendly_name = "Wall Picture Frame"

                conf = max(0.70, cls_res.confidence)
                display_label = f"Static: {friendly_name} ({int(conf * 100)}%)"

                results.append({
                    "box": [int(bx), int(by), int(bw), int(bh)],
                    "type": "STATIC_IMAGE",
                    "label": display_label,
                    "confidence": round(float(conf), 4),
                    "color": "static",
                    "entity": cat,
                    "classification": cat,
                    "friendly_label": display_label,
                    "cues": cls_res.cues,
                })

                if len(results) >= max_detections:
                    break

        return results

    @classmethod
    def annotate_frame(cls, img: np.ndarray, wall_frames: List[Dict[str, Any]]) -> np.ndarray:
        """Draws subtle slate/gray bounding boxes and labels for detected wall pictures on an image."""
        if img is None or not wall_frames:
            return img

        out = img.copy()
        color = (161, 147, 139)  # Slate / subtle gray in BGR
        h_img, w_img = out.shape[:2]

        for wf in wall_frames:
            bx, by, bw, bh = wf["box"]
            lbl = wf.get("friendly_label", "Static: Wall Frame")

            # Draw outer rectangle
            cv2.rectangle(out, (bx, by), (bx + bw, by + bh), color, 2)

            # Draw technical label badge
            (tw, th), _ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.36, 1)
            lbl_x = max(2, min(bx, w_img - tw - 8))
            lbl_y = max(th + 6, by)
            cv2.rectangle(out, (lbl_x, max(0, lbl_y - th - 6)), (lbl_x + tw + 6, lbl_y), (35, 40, 48), -1)
            cv2.rectangle(out, (lbl_x, max(0, lbl_y - th - 6)), (lbl_x + tw + 6, lbl_y), color, 1)
            cv2.putText(
                out,
                lbl,
                (lbl_x + 3, lbl_y - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.36,
                (230, 235, 240),
                1,
                cv2.LINE_AA,
            )

        return out
