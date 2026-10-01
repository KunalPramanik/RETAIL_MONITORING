import cv2
import numpy as np
from typing import List, Dict, Any, Optional

class FrameRenderer:
    """
    Single Source of Truth for rendering telemetry and bounding boxes onto a camera frame.
    Enforces pixel-perfect visual consistency between live streaming and evidence snapshots.
    """

    @staticmethod
    def draw_overlay(
        img: np.ndarray,
        boxes: List[Dict[str, Any]],
        status_banner: str = "SURVEILLANCE CV // ACTIVE",
        latency_ms: Optional[float] = None
    ) -> np.ndarray:
        """
        Draws bounding boxes and a top-corner telemetry bar on the given frame.
        boxes: List of dictionaries with keys: 'bbox' [x, y, w, h], 'label', 'color' (BGR tuple)
        """
        orig_h, orig_w = img.shape[:2]

        # Draw bounding boxes
        for b in boxes:
            x, y, w, h = b['bbox']
            label = b.get('label', '')
            color = b.get('color', (0, 255, 180)) # Default green
            
            # Box
            cv2.rectangle(img, (int(x), int(y)), (int(x + w), int(y + h)), color, 2)
            
            # Corner Accents
            line_len = min(12, int(w * 0.25))
            thick = 3
            # Top-left
            cv2.line(img, (int(x), int(y)), (int(x + line_len), int(y)), color, thick)
            cv2.line(img, (int(x), int(y)), (int(x), int(y + line_len)), color, thick)
            # Top-right
            cv2.line(img, (int(x + w), int(y)), (int(x + w - line_len), int(y)), color, thick)
            cv2.line(img, (int(x + w), int(y)), (int(x + w), int(y + line_len)), color, thick)
            # Bottom-left
            cv2.line(img, (int(x), int(y + h)), (int(x + line_len), int(y + h)), color, thick)
            cv2.line(img, (int(x), int(y + h)), (int(x), int(y + h - line_len)), color, thick)
            # Bottom-right
            cv2.line(img, (int(x + w), int(y + h)), (int(x + w - line_len), int(y + h)), color, thick)
            cv2.line(img, (int(x + w), int(y + h)), (int(x + w), int(y + h - line_len)), color, thick)

            # Label
            if label:
                (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
                cv2.rectangle(img, (int(x), int(y - lh - 4)), (int(x + lw + 6), int(y)), (20, 25, 30), -1)
                cv2.putText(img, label, (int(x + 3), int(y - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (230, 230, 230), 1, cv2.LINE_AA)

        # Draw Telemetry Banner
        if latency_ms is not None:
            status_banner = f"{status_banner} // {latency_ms:.0f}ms"
            
        (bw_t, bh_t), _ = cv2.getTextSize(status_banner, cv2.FONT_HERSHEY_SIMPLEX, 0.36, 1)
        banner_y = min(orig_h - 12, max(40, 44))
        # Clear a wide background for the banner to prevent overlapping text issues
        cv2.rectangle(img, (8, banner_y - bh_t - 6), (min(orig_w - 4, 8 + bw_t + 20), banner_y + 4), (10, 15, 20), -1)
        cv2.putText(
            img,
            status_banner,
            (13, banner_y - 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.36,
            (0, 255, 200),
            1,
            cv2.LINE_AA,
        )

        return img
