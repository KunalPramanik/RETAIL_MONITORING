"""Dense Bookshelf & Shelf Row Unit Segmentation and Counting Engine

Specialized computer vision module for dense inventory counting of books,
documents, and vertically stacked shelf items. Resolves the limitation where
general COCO detectors only catch 1-2 books and miss the rest of the shelf row.
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
import logging

logger = logging.getLogger("secops.ml.dense_bookshelf")


class DenseBookshelfCounter:
    """Detects, segments, and counts individual books and shelf units in dense rows."""

    @classmethod
    def segment_shelf_row(
        cls,
        frame: np.ndarray,
        shelf_bounds: Tuple[int, int, int, int],  # (x1, y1, x2, y2)
        min_book_width_px: int = 12,
        max_book_width_px: int = 65,
        nominal_book_width_px: int = 25,
    ) -> List[Dict[str, Any]]:
        """Segments individual vertical book spines within a confirmed horizontal shelf ROI.

        Uses vertical edge gradients (Sobel-X) combined with colorimetric transitions (HSV)
        to pinpoint individual spine seams and boundaries.
        """
        h_img, w_img = frame.shape[:2]
        x1, y1, x2, y2 = shelf_bounds
        x1 = max(0, min(x1, w_img - 2))
        x2 = max(x1 + 10, min(x2, w_img))
        y1 = max(0, min(y1, h_img - 2))
        y2 = max(y1 + 10, min(y2, h_img))
        shelf_h = y2 - y1
        shelf_w = x2 - x1

        if shelf_w < 20 or shelf_h < 25:
            return []

        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return []

        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(roi_gray, (3, 3), 0)

        # 1. Vertical edge gradient (Sobel-X) for book seams and creases
        sobel_x = np.abs(cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3))
        edge_energy = np.mean(sobel_x, axis=0)

        # 2. Color boundary transitions in HSV
        roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        color_diff = np.zeros(shelf_w)
        for x in range(2, shelf_w - 2):
            c_prev = np.mean(roi_hsv[:, max(0, x - 2):x], axis=(0, 1))
            c_next = np.mean(roi_hsv[:, x:min(shelf_w, x + 2)], axis=(0, 1))
            dh = min(abs(c_next[0] - c_prev[0]), 180 - abs(c_next[0] - c_prev[0])) * 2.0
            ds = abs(c_next[1] - c_prev[1])
            dv = abs(c_next[2] - c_prev[2])
            color_diff[x] = np.sqrt(dh * dh + ds * ds + dv * dv)

        # 3. Fuse edge and color cues into seam likelihood
        norm_edge = edge_energy / (np.max(edge_energy) + 1e-6)
        norm_color = color_diff / (np.max(color_diff) + 1e-6)
        total_seam = 0.5 * norm_edge + 0.5 * norm_color
        total_seam_smooth = cv2.GaussianBlur(total_seam.reshape(1, -1), (1, 11), 0)[0]

        # 4. Find seam peaks (boundary line between adjacent books)
        from scipy.signal import find_peaks
        seams, _ = find_peaks(
            total_seam_smooth,
            distance=max(10, min_book_width_px),
            prominence=0.05,
        )

        all_seams = [0] + list(seams) + [shelf_w]
        books: List[Dict[str, Any]] = []

        for i in range(len(all_seams) - 1):
            xs = all_seams[i]
            xe = all_seams[i + 1]
            wb = xe - xs

            if min_book_width_px <= wb <= max_book_width_px:
                books.append({
                    "bbox": [x1 + xs, y1, wb, shelf_h],
                    "confidence": 0.88,
                    "class_label": "single_unit",
                    "specific_label": "Book / Document",
                    "category_family": "READING_OFFICE",
                    "is_inventory_relevant": True,
                    "is_environment_only": False,
                })
            elif wb > max_book_width_px:
                # Subdivide wide multi-book blocks into estimated individual volumes
                sub_count = max(2, int(round(float(wb) / nominal_book_width_px)))
                sub_w = float(wb) / sub_count
                for s in range(sub_count):
                    cur_x = int(x1 + xs + s * sub_w)
                    cur_w = int(sub_w)
                    books.append({
                        "bbox": [cur_x, y1, cur_w, shelf_h],
                        "confidence": 0.84,
                        "class_label": "single_unit",
                        "specific_label": "Book / Document",
                        "category_family": "READING_OFFICE",
                        "is_inventory_relevant": True,
                        "is_environment_only": False,
                    })

        return books

    @classmethod
    def detect_and_count_bookshelf(
        cls,
        frame: np.ndarray,
        candidate_boxes: Optional[List[List[int]]] = None,
    ) -> List[Dict[str, Any]]:
        """Scans the image for bookshelf rows and performs dense instance counting.

        If candidate_boxes (from initial YOLOX book or shelf detections) are provided,
        expands horizontally across the shelf row.
        If no candidate_boxes provided, scans the frame for dense vertical edge strips.
        """
        if frame is None or frame.size == 0:
            return []

        h_img, w_img = frame.shape[:2]

        # Case 1: Expand from candidate detections (e.g. 1 or 2 sparse books detected by model)
        if candidate_boxes and len(candidate_boxes) > 0:
            y_min = max(0, min(b[1] for b in candidate_boxes) - 10)
            y_max = min(h_img, max(b[1] + b[3] for b in candidate_boxes) + 10)

            # Measure vertical edge energy across columns in this horizontal band
            gray = cv2.cvtColor(frame[y_min:y_max, :], cv2.COLOR_BGR2GRAY)
            sobel_x = np.abs(cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3))
            col_e = np.mean(sobel_x, axis=0)
            smooth_e = cv2.GaussianBlur(col_e.reshape(1, -1), (1, 25), 0)[0]
            cutoff = max(18.0, np.mean(smooth_e) * 0.65)

            init_x_min = min(b[0] for b in candidate_boxes)
            init_x_max = max(b[0] + b[2] for b in candidate_boxes)

            x_left = init_x_min
            while x_left > 15 and smooth_e[x_left - 1] >= cutoff:
                x_left -= 1

            x_right = init_x_max
            while x_right < w_img - 15 and smooth_e[x_right + 1] >= cutoff:
                x_right += 1

            # Ensure minimal valid row
            if (x_right - x_left) >= 30 and (y_max - y_min) >= 30:
                books = cls.segment_shelf_row(frame, (x_left, y_min, x_right, y_max))
                if len(books) >= len(candidate_boxes):
                    return books

        # Case 2: Direct scan for vertical book stripes across the image
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        sobel_x = np.abs(cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3))
        v_density_y = np.mean(sobel_x, axis=1)

        # Locate dense vertical stripe band along Y
        high_y = np.where(v_density_y > 22.0)[0]
        if len(high_y) >= 40:
            y1 = max(0, int(high_y[0]))
            y2 = min(h_img, int(high_y[-1]))

            # Horizontal extent
            col_e = np.mean(sobel_x[y1:y2, :], axis=0)
            smooth_e = cv2.GaussianBlur(col_e.reshape(1, -1), (1, 25), 0)[0]
            dense_cols = np.where(smooth_e > 22.0)[0]
            if len(dense_cols) >= 40:
                x1 = max(0, int(dense_cols[0]))
                x2 = min(w_img, int(dense_cols[-1]))
                books = cls.segment_shelf_row(frame, (x1, y1, x2, y2))
                if len(books) >= 3:
                    return books

        return []

    @classmethod
    def detect_and_count_books(
        cls,
        frame: np.ndarray,
        candidate_boxes: Optional[List[List[int]]] = None,
        min_confidence: float = 0.35,
    ) -> Dict[str, Any]:
        """Detects books on bookshelves and returns summary dictionary with counts and boxes."""
        t0 = cv2.getTickCount()
        books = cls.detect_and_count_bookshelf(frame, candidate_boxes)
        t1 = cv2.getTickCount()
        latency_ms = (t1 - t0) / cv2.getTickFrequency() * 1000.0
        return {
            "total_books": len(books),
            "book_boxes": [b["bbox"] for b in books],
            "book_instances": books,
            "latency_ms": latency_ms,
        }

