"""Static Image Discrimination & Content Classification Service

Classifies detected static 2D regions (wall portraits, framed pictures, religious images,
retail signage, digital displays) to prevent false-positive alarms while providing
transparent auditing of suppressed alerts.

Categories:
- RELIGIOUS_IMAGE: Framed deity pictures, idols, sacred art (e.g., Ganesh, Mahadev)
- PERSON_PHOTO: Framed photograph of a person, portrait, ID badge
- POSTER_OR_SIGNAGE: Retail advertising posters, exit signage, commercial prints
- SCREEN_DISPLAY: Television, monitor, or digital signage screen
- UNCLASSIFIED_STATIC: Static object that does not match a specific profile
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple


@dataclass
class StaticImageClassificationResult:
    classification: str           # 'RELIGIOUS_IMAGE' | 'PERSON_PHOTO' | 'POSTER_OR_SIGNAGE' | 'SCREEN_DISPLAY' | 'UNCLASSIFIED_STATIC'
    confidence: float             # 0.0 to 1.0
    liveness_score: float         # From liveness engine
    cues: Dict[str, float]        # Breakdown of individual forensic scores
    friendly_label: str           # Human-readable title for UI badges
    suppressed_alert: bool = True # True = correctly prevented false person/face alarm


class StaticImageClassifier:
    """Classifies static image content using multi-spectral color, contour, texture, and edge cues."""

    MODEL_VERSION = "static-image-classifier-v1.0"

    VALID_CLASSIFICATIONS = (
        "RELIGIOUS_IMAGE",
        "PERSON_PHOTO",
        "POSTER_OR_SIGNAGE",
        "SCREEN_DISPLAY",
        "UNCLASSIFIED_STATIC",
    )

    @classmethod
    def classify_crop(
        cls,
        crop: np.ndarray,
        liveness_score: float = 0.20,
        has_face_geometry: bool = True,
        skin_ratio: float = 0.0,
    ) -> StaticImageClassificationResult:
        """Classifies a cropped static region into one of the 5 canonical categories."""
        if crop is None or crop.size == 0 or crop.shape[0] < 10 or crop.shape[1] < 10:
            return StaticImageClassificationResult(
                classification="UNCLASSIFIED_STATIC",
                confidence=0.50,
                liveness_score=liveness_score,
                cues={"error": 1.0},
                friendly_label="Static: Unclassified (50%)",
                suppressed_alert=True,
            )

        h, w = crop.shape[:2]

        # 1. Color Palette Analysis (HSV Space)
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        h_channel = hsv[:, :, 0]
        s_channel = hsv[:, :, 1]
        v_channel = hsv[:, :, 2]

        # Warm sacred palette: Saffron, orange, vermilion, gold (Hue 0-25 or 165-180 with high saturation S >= 115)
        sacred_mask = ((h_channel <= 25) | (h_channel >= 165)) & (s_channel >= 115) & (v_channel >= 80)
        sacred_color_ratio = float(np.mean(sacred_mask))

        # Gold/yellow tones (Hue 18-35 with high saturation & value)
        gold_mask = (h_channel >= 18) & (h_channel <= 35) & (s_channel >= 120) & (v_channel >= 120)
        gold_color_ratio = float(np.mean(gold_mask))

        # 2. Border & Bezel Edge Detection (Hough lines / rectangular contour)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = float(np.mean(edges > 0))

        # Check for outer frame or bezel (straight lines along border)
        border_px = max(2, min(h, w) // 12)
        top_edge = np.mean(edges[:border_px, :] > 0)
        bottom_edge = np.mean(edges[-border_px:, :] > 0)
        left_edge = np.mean(edges[:, :border_px] > 0)
        right_edge = np.mean(edges[:, -border_px:] > 0)
        frame_edge_score = float((top_edge + bottom_edge + left_edge + right_edge) / 4.0)

        # 3. High-Frequency Texture & Moiré / LCD Grid vs Text/Graphic Signage
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        lap_var = float(lap.var())

        # Signage typically has high horizontal edge frequency and flat uniform background
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        mean_sx = float(np.mean(np.abs(sobel_x)))
        mean_sy = float(np.mean(np.abs(sobel_y)))
        text_edge_energy = float(max(mean_sx, mean_sy) / (min(mean_sx, mean_sy) + 1e-5))

        if text_edge_energy > 1.3 and edge_density > 0.03:
            screen_moire_score = 0.10
            is_signage_ratio = min(1.0, 0.45 + text_edge_energy * 0.15)
        else:
            screen_moire_score = 0.85 if lap_var > 2000 else (0.40 if lap_var > 1200 else 0.10)
            is_signage_ratio = 0.15

        # 5. Photographic Skin & Portrait Lighting
        # Natural human photograph has balanced skin tones without extreme sacred saturation
        photo_skin_score = float(np.clip(skin_ratio / 0.30, 0.0, 1.0))

        # Ornate / Garland / Halos complexity (variance of edges in center vs periphery)
        ornate_complexity = float(np.clip(edge_density * 3.5, 0.0, 1.0))

        # ── Weighted Category Scoring ──
        scores = {
            "RELIGIOUS_IMAGE": 0.0,
            "PERSON_PHOTO": 0.0,
            "POSTER_OR_SIGNAGE": 0.0,
            "SCREEN_DISPLAY": 0.0,
            "UNCLASSIFIED_STATIC": 0.15,
        }

        # Religious Image Score
        # Driven by sacred color palette (saffron, vermilion, gold), ornate complexity, and presence of face/figure
        if sacred_color_ratio > 0.08 or gold_color_ratio > 0.05:
            religious_score = (
                0.50 * (sacred_color_ratio * 3.0)
                + 0.30 * (gold_color_ratio * 4.0)
                + 0.15 * ornate_complexity
                + 0.05 * (1.0 if has_face_geometry else 0.2)
            )
            scores["RELIGIOUS_IMAGE"] = float(np.clip(religious_score, 0.0, 0.98))
        else:
            scores["RELIGIOUS_IMAGE"] = 0.05

        # Person Photo Score
        # Characterized by facial geometry + realistic natural skin + planar/frame cue, but without sacred color saturation
        if has_face_geometry and photo_skin_score > 0.20 and sacred_color_ratio < 0.15:
            photo_score = 0.55 * photo_skin_score + 0.25 * frame_edge_score + 0.20 * (1.0 - sacred_color_ratio)
            scores["PERSON_PHOTO"] = float(np.clip(photo_score, 0.0, 0.95))
        else:
            scores["PERSON_PHOTO"] = float(np.clip(0.20 * photo_skin_score, 0.0, 0.40))

        # Screen Display Score
        screen_score = 0.50 * screen_moire_score + 0.35 * frame_edge_score + 0.15 * (1.0 - sacred_color_ratio)
        scores["SCREEN_DISPLAY"] = float(np.clip(screen_score, 0.0, 0.94))

        # Poster or Signage Score
        # Characterized by high text energy, commercial palette, low skin ratio
        if skin_ratio < 0.15:
            poster_score = 0.45 * is_signage_ratio + 0.35 * frame_edge_score + 0.20 * edge_density
            scores["POSTER_OR_SIGNAGE"] = float(np.clip(poster_score, 0.0, 0.93))
        else:
            scores["POSTER_OR_SIGNAGE"] = 0.10

        # Disambiguate Best Classification
        best_class = max(scores, key=scores.get)
        best_conf = scores[best_class]

        # Minimum confidence threshold for specific classification
        if best_conf < 0.35 or (best_class != "UNCLASSIFIED_STATIC" and best_conf < 0.45):
            best_class = "UNCLASSIFIED_STATIC"
            best_conf = max(0.40, scores["UNCLASSIFIED_STATIC"])

        # Format human-friendly label
        name_map = {
            "RELIGIOUS_IMAGE": "Religious Image",
            "PERSON_PHOTO": "Person Photo",
            "POSTER_OR_SIGNAGE": "Poster",
            "SCREEN_DISPLAY": "Screen Display",
            "UNCLASSIFIED_STATIC": "Unclassified Static",
        }
        friendly = f"Static: {name_map[best_class]} ({int(best_conf * 100)}%)"

        cues_breakdown = {
            "sacred_color_ratio": round(sacred_color_ratio, 3),
            "gold_color_ratio": round(gold_color_ratio, 3),
            "edge_density": round(edge_density, 3),
            "frame_edge_score": round(frame_edge_score, 3),
            "screen_moire_score": round(screen_moire_score, 3),
            "photo_skin_score": round(photo_skin_score, 3),
        }

        return StaticImageClassificationResult(
            classification=best_class,
            confidence=round(best_conf, 4),
            liveness_score=round(liveness_score, 4),
            cues=cues_breakdown,
            friendly_label=friendly,
            suppressed_alert=True,
        )

    @classmethod
    def classify_image_region(
        cls,
        full_image: np.ndarray,
        bbox: List[int],
        liveness_score: float = 0.20,
        has_face_geometry: bool = True,
    ) -> StaticImageClassificationResult:
        """Extracts the specified bbox from full image and performs classification."""
        if full_image is None:
            return StaticImageClassificationResult(
                classification="UNCLASSIFIED_STATIC",
                confidence=0.40,
                liveness_score=liveness_score,
                cues={},
                friendly_label="Static: Unclassified (40%)",
                suppressed_alert=True,
            )

        h_img, w_img = full_image.shape[:2]
        x1, y1, w, h = bbox
        # Support both [x, y, w, h] and [x1, y1, x2, y2]
        if w > x1 and h > y1 and (x1 + w) > w_img:
            # Treated as [x1, y1, x2, y2]
            x2, y2 = w, h
        else:
            x2, y2 = x1 + w, y1 + h

        # Expand region slightly (10%) to capture picture frame borders and halos
        pad_x = int(0.12 * (x2 - x1))
        pad_y = int(0.12 * (y2 - y1))
        x1_pad = max(0, x1 - pad_x)
        y1_pad = max(0, y1 - pad_y)
        x2_pad = min(w_img, x2 + pad_x)
        y2_pad = min(h_img, y2 + pad_y)

        crop = full_image[y1_pad:y2_pad, x1_pad:x2_pad]
        if crop.size == 0:
            return StaticImageClassificationResult(
                classification="UNCLASSIFIED_STATIC",
                confidence=0.40,
                liveness_score=liveness_score,
                cues={},
                friendly_label="Static: Unclassified (40%)",
                suppressed_alert=True,
            )

        # Estimate skin ratio in crop
        ycbcr = cv2.cvtColor(crop, cv2.COLOR_BGR2YCrCb)
        cr = ycbcr[:, :, 1]
        cb = ycbcr[:, :, 2]
        skin_mask = (cr >= 133) & (cr <= 173) & (cb >= 77) & (cb <= 127)
        skin_ratio = float(np.mean(skin_mask))

        return cls.classify_crop(
            crop=crop,
            liveness_score=liveness_score,
            has_face_geometry=has_face_geometry,
            skin_ratio=skin_ratio,
        )

    @staticmethod
    def _extract_xyxy(box_item: Any, box_format: str = "xywh") -> Optional[Tuple[float, float, float, float]]:
        """Normalizes various box representations to [x1, y1, x2, y2]."""
        if box_item is None:
            return None
        raw = None
        if isinstance(box_item, dict):
            raw = box_item.get("box") or box_item.get("bbox")
        elif hasattr(box_item, "box"):
            raw = getattr(box_item, "box")
        elif hasattr(box_item, "bbox"):
            raw = getattr(box_item, "bbox")
        elif isinstance(box_item, (list, tuple, np.ndarray)) and len(box_item) >= 4:
            raw = box_item

        if raw is None or len(raw) < 4:
            return None

        v0, v1, v2, v3 = float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3])
        if box_format == "xyxy":
            return (v0, v1, v2, v3)
        # Default "xywh": v2 is width, v3 is height
        return (v0, v1, v0 + v2, v1 + v3)

    @classmethod
    def is_box_enclosed(
        cls,
        candidate_box: Any,
        container_box: Any,
        containment_threshold: float = 0.65,
        candidate_format: str = "xywh",
        container_format: str = "xywh",
    ) -> bool:
        """Determines if candidate_box is geometrically enclosed inside container_box."""
        c_xy = cls._extract_xyxy(candidate_box, candidate_format)
        cnt_xy = cls._extract_xyxy(container_box, container_format)
        if c_xy is None or cnt_xy is None:
            return False

        c_x1, c_y1, c_x2, c_y2 = c_xy
        cnt_x1, cnt_y1, cnt_x2, cnt_y2 = cnt_xy

        inter_x1 = max(c_x1, cnt_x1)
        inter_y1 = max(c_y1, cnt_y1)
        inter_x2 = min(c_x2, cnt_x2)
        inter_y2 = min(c_y2, cnt_y2)

        inter_w = max(0.0, inter_x2 - inter_x1)
        inter_h = max(0.0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h

        cand_area = max(1.0, (c_x2 - c_x1) * (c_y2 - c_y1))
        ratio = inter_area / cand_area
        return ratio >= containment_threshold

    @classmethod
    def quarantine_enclosed_visual_content(
        cls,
        candidate_boxes: List[Any],
        container_boxes: List[Any],
        containment_threshold: float = 0.65,
        candidate_format: str = "xywh",
        container_format: str = "xywh",
    ) -> List[int]:
        """Identifies candidate boxes (faces/figures) that are geometrically enclosed
        within display containers (WallPicture, Screen, Smartphone, etc.).

        Returns:
            List of integer indices in candidate_boxes that are quarantined.
        """
        if not candidate_boxes or not container_boxes:
            return []

        quarantined_indices = []
        for idx, cand in enumerate(candidate_boxes):
            for cont in container_boxes:
                if cls.is_box_enclosed(
                    candidate_box=cand,
                    container_box=cont,
                    containment_threshold=containment_threshold,
                    candidate_format=candidate_format,
                    container_format=container_format,
                ):
                    quarantined_indices.append(idx)
                    break

        return quarantined_indices


# Expose module-level helper for convenient importing
quarantine_enclosed_visual_content = StaticImageClassifier.quarantine_enclosed_visual_content
is_box_enclosed = StaticImageClassifier.is_box_enclosed


