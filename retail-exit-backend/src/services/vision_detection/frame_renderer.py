"""Single Source of Truth for OpenCV Frame Annotation & HUD Telemetry

Renders:
1. Object bounding boxes with class name, track ID, and confidence percentage.
2. Dynamic Person Posture: 'Person #12 · Sitting · 91%' (never in/out unless crossing detected).
3. Dynamic Palette: High-contrast class-to-color map generated deterministically from class taxonomy.
4. Collision-free Labels: Computes text bounds and dynamically offsets labels if overlapping.
5. Pixel-perfect consistency between live stream and forensic snapshots.
"""

import colorsys
import hashlib
from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np


class FrameRenderer:
    """Server-side OpenCV rendering engine for camera frames and HUD overlays."""

    _color_cache: Dict[str, Tuple[int, int, int]] = {}

    @classmethod
    def get_class_color(cls, class_name: str) -> Tuple[int, int, int]:
        """Derives a distinct, high-contrast BGR color deterministically from class name."""
        key = (class_name or "object").strip().lower()
        if key in cls._color_cache:
            return cls._color_cache[key]

        # Standard high-visibility anchors for core retail categories
        standard_colors = {
            "person": (0, 235, 140),          # Bright Emerald Green
            "case_full": (0, 210, 255),        # Amber Gold
            "carton / shipping box": (0, 210, 255),
            "vehicle": (255, 170, 0),          # Bright Cyan
            "smartphone": (255, 120, 200),     # Soft Lavender
            "cell phone": (255, 120, 200),
            "laptop": (220, 160, 80),          # Sky Blue
            "bottle": (100, 240, 255),         # Yellow
            "backpack / bag": (180, 120, 255), # Light Purple
            "doorway": (150, 150, 150),        # Muted Slate
            "wall picture frame": (130, 130, 130),
        }
        if key in standard_colors:
            cls._color_cache[key] = standard_colors[key]
            return standard_colors[key]

        # Golden-ratio based hue distribution for any novel / custom SKU class
        hash_val = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:6], 16)
        hue = (hash_val % 360) / 360.0
        # Saturation: 0.85, Value: 0.95 for maximum visibility on surveillance footage
        rgb = colorsys.hsv_to_rgb(hue, 0.85, 0.95)
        bgr = (int(rgb[2] * 255), int(rgb[1] * 255), int(rgb[0] * 255))
        cls._color_cache[key] = bgr
        return bgr

    @classmethod
    def format_box_label(cls, box_data: Dict[str, Any]) -> str:
        """Formats the human-readable label string for a detected entity."""
        raw_label = box_data.get("specific_label") or box_data.get("class_label") or "Object"
        raw_label = raw_label.replace("_", " ").title()
        track_id = box_data.get("track_id")
        conf = box_data.get("confidence", 0.0)
        conf_pct = int(conf * 100) if conf <= 1.0 else int(conf)
        posture = box_data.get("posture")

        # Specific formatting for person entities
        if "person" in raw_label.lower():
            tid_str = f" #{track_id}" if track_id is not None else ""
            posture_str = f" · {posture}" if posture else ""
            return f"Person{tid_str}{posture_str} · {conf_pct}%"

        # General object formatting
        tid_str = f" #{track_id}" if track_id is not None else ""
        return f"{raw_label}{tid_str} · {conf_pct}%"

    @classmethod
    def draw_overlay(
        cls,
        img: np.ndarray,
        boxes: List[Dict[str, Any]],
        status_banner: str = "SURVEILLANCE CV // ACTIVE",
        latency_ms: Optional[float] = None,
    ) -> np.ndarray:
        """Draws bounding boxes, dynamic posture labels, and status telemetry onto the image."""
        if img is None or img.size == 0:
            return img

        orig_h, orig_w = img.shape[:2]
        drawn_label_rects: List[Tuple[int, int, int, int]] = []

        for b in boxes:
            bbox = b.get("bbox", [0, 0, 0, 0])
            x, y, w, h = bbox
            if w <= 0 or h <= 0:
                continue

            # Clamp coordinates to frame boundary
            x1 = max(0, min(orig_w - 1, int(x)))
            y1 = max(0, min(orig_h - 1, int(y)))
            x2 = max(x1 + 1, min(orig_w - 1, int(x + w)))
            y2 = max(y1 + 1, min(orig_h - 1, int(y + h)))
            w_clamped = x2 - x1
            h_clamped = y2 - y1

            # Resolve color
            class_name = b.get("class_label") or b.get("specific_label") or "object"
            color = b.get("color") or cls.get_class_color(class_name)

            # 1. Bounding Box Outline
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

            # 2. Corner Accents for high-end tactical HUD look
            corner_len = max(6, min(14, int(min(w_clamped, h_clamped) * 0.25)))
            thick = 3
            # Top-left
            cv2.line(img, (x1, y1), (x1 + corner_len, y1), color, thick)
            cv2.line(img, (x1, y1), (x1, y1 + corner_len), color, thick)
            # Top-right
            cv2.line(img, (x2, y1), (x2 - corner_len, y1), color, thick)
            cv2.line(img, (x2, y1), (x2, y1 + corner_len), color, thick)
            # Bottom-left
            cv2.line(img, (x1, y2), (x1 + corner_len, y2), color, thick)
            cv2.line(img, (x1, y2), (x1, y2 - corner_len), color, thick)
            # Bottom-right
            cv2.line(img, (x2, y2), (x2 - corner_len, y2), color, thick)
            cv2.line(img, (x2, y2), (x2, y2 - corner_len), color, thick)

            # 3. Label text resolution
            label = b.get("label") or cls.format_box_label(b)
            if not label:
                continue

            font_scale = 0.42
            font_thick = 1
            (lw, lh), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thick)
            badge_w = lw + 8
            badge_h = lh + baseline + 6

            # Desired label position: directly above top-left of box
            lx1 = x1
            ly1 = y1 - badge_h

            # If above frame, position inside or below box
            if ly1 < 2:
                ly1 = y1 + 2

            lx2 = lx1 + badge_w
            ly2 = ly1 + badge_h

            # Dynamic collision resolution against already placed labels
            for ox1, oy1, ox2, oy2 in drawn_label_rects:
                # Check bounding rect intersection
                if not (lx2 < ox1 or lx1 > ox2 or ly2 < oy1 or ly1 > oy2):
                    # Overlap detected! Shift label below box or offset downward
                    ly1 = y2 + 2
                    ly2 = ly1 + badge_h
                    if ly2 > orig_h - 2:
                        # If below bottom edge, shift horizontally
                        lx1 = min(orig_w - badge_w - 2, ox2 + 4)
                        ly1 = y1
                        lx2 = lx1 + badge_w
                        ly2 = ly1 + badge_h
                    break

            # Clamp label bounds to image dimensions
            lx1 = max(0, min(orig_w - badge_w, lx1))
            ly1 = max(0, min(orig_h - badge_h, ly1))
            lx2 = lx1 + badge_w
            ly2 = ly1 + badge_h

            drawn_label_rects.append((lx1, ly1, lx2, ly2))

            # Draw background tag and text
            cv2.rectangle(img, (lx1, ly1), (lx2, ly2), (18, 22, 28), -1)
            cv2.rectangle(img, (lx1, ly1), (lx2, ly2), color, 1)
            cv2.putText(
                img,
                label,
                (lx1 + 4, ly1 + lh + 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                (245, 245, 245),
                font_thick,
                cv2.LINE_AA,
            )

        # 4. Telemetry Header Banner
        if latency_ms is not None:
            full_banner = f"{status_banner} // LATENCY: {latency_ms:.1f}ms"
        else:
            full_banner = status_banner

        (bw_t, bh_t), _ = cv2.getTextSize(full_banner, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
        banner_y = max(24, min(orig_h - 8, 32))
        cv2.rectangle(img, (8, banner_y - bh_t - 6), (min(orig_w - 4, 12 + bw_t + 16), banner_y + 4), (12, 16, 22), -1)
        cv2.rectangle(img, (8, banner_y - bh_t - 6), (min(orig_w - 4, 12 + bw_t + 16), banner_y + 4), (0, 200, 160), 1)
        cv2.putText(
            img,
            full_banner,
            (14, banner_y - 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            (0, 255, 200),
            1,
            cv2.LINE_AA,
        )

        return img
