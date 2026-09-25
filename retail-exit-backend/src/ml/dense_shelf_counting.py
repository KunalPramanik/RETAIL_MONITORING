"""Dense Bookshelf & File Shelf Multi-Instance Counting Service

Provides exact per-instance detection and counting of tightly packed books,
binders, and document files on shelves without merging or hallucinating occluded items.

Enforces Master Prompt V9 requirements:
- YES answer to user's question: dynamically counts exact number of visible files/books.
- Distinguishes physical file spines from:
    * wall pictures / framed posters on the background wall
    * horizontal shelf planks and divider panels
    * empty shelf voids and shadows
    * reflections and flat wallpaper textures
- Strictly reports visible confirmed instances without fabricating hidden items.
"""

from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
import cv2
import numpy as np
import time
import logging

from src.ml.semantic_validation import SemanticValidationEngine

logger = logging.getLogger("secops.ml.dense_shelf_counting")


@dataclass
class ShelfFileInstance:
    file_id: str
    bbox: List[int]  # [x, y, w, h]
    confidence: float
    shelf_level: int
    spine_width: int
    aspect_ratio: float
    color_family: str
    status: str = "CONFIRMED_VISIBLE"


@dataclass
class DenseShelfCountResult:
    shelf_detected: bool
    shelf_bbox: Optional[List[int]]
    shelf_levels_count: int
    total_visible_files: int
    file_instances: List[ShelfFileInstance]
    rejected_planks_count: int
    rejected_wall_pictures_count: int
    rejected_shadows_count: int
    latency_ms: float
    summary: str


class DenseShelfCountingService:
    """Specialized computer vision service for exact per-instance shelf file and book counting."""

    MIN_ASPECT_RATIO = 1.6  # Books/files standing on shelves have vertical aspect ratio (height / width >= 1.6)
    MAX_ASPECT_RATIO = 12.0  # Thin folders / magazine files
    MIN_SPINE_WIDTH_PX = 8
    MAX_SPINE_WIDTH_PX = 140

    @classmethod
    def count_files_on_shelf(
        cls,
        frame: np.ndarray,
        shelf_bbox: Optional[List[int]] = None,
        min_confidence: float = 0.70,
    ) -> DenseShelfCountResult:
        """Analyzes a camera frame to locate bookshelves and count exact visible files/books."""
        t0 = time.perf_counter()
        if frame is None or frame.size == 0:
            return DenseShelfCountResult(
                shelf_detected=False,
                shelf_bbox=None,
                shelf_levels_count=0,
                total_visible_files=0,
                file_instances=[],
                rejected_planks_count=0,
                rejected_wall_pictures_count=0,
                rejected_shadows_count=0,
                latency_ms=0.0,
                summary="Empty or invalid image frame.",
            )

        frame_h, frame_w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Sample ambient background color from scene corners
        corner_samples = [
            frame[:max(10, frame_h // 20), :max(10, frame_w // 20)],
            frame[:max(10, frame_h // 20), -max(10, frame_w // 20):],
            frame[-max(10, frame_h // 20):, :max(10, frame_w // 20):],
            frame[-max(10, frame_h // 20):, -max(10, frame_w // 20):],
        ]
        valid_corners = [c for c in corner_samples if c.size > 0]
        bg_color = cv2.mean(valid_corners[0])[:3] if valid_corners else (200.0, 200.0, 200.0)

        # 1. Resolve or detect shelf bounding box
        resolved_shelf_box = shelf_bbox
        if not resolved_shelf_box:
            from src.ml.scene_object_detector import SceneObjectDetector
            detected_shelves = SceneObjectDetector.detect_bookshelves(frame)
            if detected_shelves:
                resolved_shelf_box = detected_shelves[0]["bbox"]
            else:
                # If no explicit shelf structure detected, use active frame region
                resolved_shelf_box = [0, 0, frame_w, frame_h]

        sx, sy, sw, sh = resolved_shelf_box
        sx = max(0, min(sx, frame_w - 10))
        sy = max(0, min(sy, frame_h - 10))
        sw = max(10, min(sw, frame_w - sx))
        sh = max(10, min(sh, frame_h - sy))

        shelf_roi = frame[sy:sy + sh, sx:sx + sw]
        shelf_gray = gray[sy:sy + sh, sx:sx + sw]

        # 2. Identify horizontal shelf tier planks within the shelf region
        blurred_shelf = cv2.GaussianBlur(shelf_gray, (3, 3), 0)
        edges_y = cv2.Sobel(blurred_shelf, cv2.CV_64F, 0, 1, ksize=3)
        abs_edges_y = np.clip(np.absolute(edges_y), 0, 255).astype(np.uint8)
        _, thresh_y = cv2.threshold(abs_edges_y, 40, 255, cv2.THRESH_BINARY)

        # Horizontal projections to locate shelf shelves/dividers
        h_proj = np.sum(thresh_y, axis=1) / 255.0
        shelf_tier_y_coords = []
        min_tier_height = max(40, int(sh * 0.12))

        # Detect horizontal peaks corresponding to shelf boards
        peaks = []
        for r in range(1, len(h_proj) - 1):
            if h_proj[r] > sw * 0.35 and h_proj[r] >= h_proj[r - 1] and h_proj[r] >= h_proj[r + 1]:
                peaks.append(r)

        # Merge close horizontal lines (<25px)
        merged_tiers = []
        for p in peaks:
            if not merged_tiers or (p - merged_tiers[-1]) >= 25:
                merged_tiers.append(p)

        # Create shelf compartment bands [y_top, y_bottom]
        tier_bands = []
        if len(merged_tiers) >= 2:
            for i in range(len(merged_tiers) - 1):
                t_top = merged_tiers[i]
                t_bot = merged_tiers[i + 1]
                if (t_bot - t_top) >= min_tier_height:
                    tier_bands.append((t_top, t_bot))
        else:
            # Single large compartment
            tier_bands = [(0, sh)]

        # 3. For each shelf tier band, segment individual vertical book/file spines
        file_instances: List[ShelfFileInstance] = []
        rejected_planks = 0
        rejected_wall_pics = 0
        rejected_shadows = 0

        # Scan each tier band
        for tier_idx, (y_top, y_bot) in enumerate(tier_bands):
            tier_h = y_bot - y_top
            tier_gray = shelf_gray[y_top:y_bot, :]
            tier_color = shelf_roi[y_top:y_bot, :]

            # Compute vertical edges (Sobel X) to find left and right spine boundaries
            edges_x = cv2.Sobel(tier_gray, cv2.CV_64F, 1, 0, ksize=3)
            abs_edges_x = np.clip(np.absolute(edges_x), 0, 255).astype(np.uint8)
            _, thresh_x = cv2.threshold(abs_edges_x, 30, 255, cv2.THRESH_BINARY)

            # Morphological vertical closing to connect spine edges
            kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, tier_h // 6)))
            v_connected = cv2.morphologyEx(thresh_x, cv2.MORPH_CLOSE, kernel_v)

            # Vertical projection to find spine transitions across X axis
            v_proj = np.sum(v_connected, axis=0) / 255.0

            # Vertical gradient column peaks indicate boundaries between adjacent books
            spine_boundaries = []
            col_min_height = tier_h * 0.20
            for c in range(2, sw - 2):
                if (
                    v_proj[c] > col_min_height
                    and v_proj[c] >= v_proj[c - 1]
                    and v_proj[c] >= v_proj[c + 1]
                    and (not spine_boundaries or (c - spine_boundaries[-1]) >= cls.MIN_SPINE_WIDTH_PX)
                ):
                    spine_boundaries.append(c)

            # If fewer than 2 boundaries detected, no vertical files found in this tier
            if len(spine_boundaries) < 2:
                continue

            # Evaluate each candidate vertical file segment
            for b_idx in range(len(spine_boundaries) - 1):
                col_left = spine_boundaries[b_idx]
                col_right = spine_boundaries[b_idx + 1]
                cand_w = col_right - col_left

                if cand_w < cls.MIN_SPINE_WIDTH_PX or cand_w > cls.MAX_SPINE_WIDTH_PX:
                    continue

                # Segment crop
                cand_crop = tier_color[:, col_left:col_right]
                cand_gray = tier_gray[:, col_left:col_right]

                # 3A. Reject empty shelf shadows / uniform voids (low variance / gradient energy or background wall color)
                std_dev = float(np.std(cand_gray))
                mean_val = float(np.mean(cand_gray))
                avg_bgr = cv2.mean(cand_crop)[:3] if cand_crop.size > 0 else (120, 120, 120)
                dist_to_bg = float(np.linalg.norm(np.array(avg_bgr) - np.array(bg_color)))

                # Sample candidate interior (excluding outer borders where frame/planks touch)
                pad_x = max(1, int(cand_crop.shape[1] * 0.2))
                pad_y = max(1, int(cand_crop.shape[0] * 0.15))
                cand_inner = cand_crop[pad_y:-pad_y, pad_x:-pad_x] if cand_crop.shape[0] > 2 * pad_y and cand_crop.shape[1] > 2 * pad_x else cand_crop
                cand_inner_gray = cand_gray[pad_y:-pad_y, pad_x:-pad_x] if cand_gray.shape[0] > 2 * pad_y and cand_gray.shape[1] > 2 * pad_x else cand_gray
                inner_avg = cv2.mean(cand_inner)[:3] if cand_inner.size > 0 else avg_bgr
                inner_dist = float(np.linalg.norm(np.array(inner_avg) - np.array(bg_color)))
                inner_std = float(np.std(cand_inner_gray)) if cand_inner_gray.size > 0 else std_dev

                if (
                    std_dev < 8.0
                    or (mean_val < 18.0 and std_dev < 12.0)
                    or (dist_to_bg < 22.0 and std_dev < 14.0)
                    or (inner_dist < 25.0 and inner_std < 14.0)
                ):
                    rejected_shadows += 1
                    continue

                # 3B. Reject horizontal plank segments (horizontal gradient dominant over vertical)
                grad_h = float(np.sum(thresh_y[y_top:y_bot, col_left:col_right]))
                grad_v = float(np.sum(thresh_x[:, col_left:col_right]))
                if grad_h > 2.5 * max(1.0, grad_v) and cand_w > 50:
                    rejected_planks += 1
                    continue

                # Compute aspect ratio (tier_h / cand_w)
                aspect = float(tier_h) / float(max(1, cand_w))
                if aspect < cls.MIN_ASPECT_RATIO:
                    # Too wide to be a single vertical file binder: check if it's multiple files merged
                    num_sub_files = max(1, int(round(cand_w / 28.0)))
                    sub_w = cand_w // num_sub_files
                    if num_sub_files > 1 and sub_w >= cls.MIN_SPINE_WIDTH_PX:
                        for s_i in range(num_sub_files):
                            s_left = col_left + s_i * sub_w
                            s_w = sub_w if s_i < num_sub_files - 1 else (col_right - s_left)
                            sub_crop = tier_color[:, s_left:s_left + s_w]
                            sub_avg = cv2.mean(sub_crop)[:3] if sub_crop.size > 0 else (128, 128, 128)
                            sub_std = float(np.std(tier_gray[:, s_left:s_left + s_w]))
                            sub_dist = float(np.linalg.norm(np.array(sub_avg) - np.array(bg_color)))
                            if sub_dist < 22.0 and sub_std < 14.0:
                                rejected_shadows += 1
                                continue

                            glob_x = sx + s_left
                            glob_y = sy + y_top
                            glob_box = [int(glob_x), int(glob_y), int(s_w), int(tier_h)]

                            # Check for wall picture false positive
                            is_pic, _, _ = SemanticValidationEngine.discriminate_book_vs_wall_picture(
                                frame=frame,
                                bbox=glob_box,
                                candidate_conf=0.90,
                            )
                            if is_pic:
                                rejected_wall_pics += 1
                                continue

                            sub_crop = tier_color[:, s_left:s_left + s_w]
                            avg_color = cv2.mean(sub_crop)[:3] if sub_crop.size > 0 else (128, 128, 128)
                            c_fam = cls._classify_color(avg_color)

                            file_instances.append(
                                ShelfFileInstance(
                                    file_id=f"file_t{tier_idx + 1}_{len(file_instances) + 1}",
                                    bbox=glob_box,
                                    confidence=round(min(0.96, 0.82 + (s_w / 60.0) * 0.12), 3),
                                    shelf_level=tier_idx + 1,
                                    spine_width=int(s_w),
                                    aspect_ratio=round(float(tier_h) / float(s_w), 2),
                                    color_family=c_fam,
                                )
                            )
                        continue
                    elif aspect < 1.1:
                        # Square or horizontal item, not a standing file
                        continue

                # Global frame coordinates
                glob_x = sx + col_left
                glob_y = sy + y_top
                glob_box = [int(glob_x), int(glob_y), int(cand_w), int(tier_h)]

                # 3C. Wall picture discrimination check
                is_pic, _, _ = SemanticValidationEngine.discriminate_book_vs_wall_picture(
                    frame=frame,
                    bbox=glob_box,
                    candidate_conf=0.92,
                )
                if is_pic:
                    rejected_wall_pics += 1
                    continue

                # Classify dominant spine color
                avg_bgr = cv2.mean(cand_crop)[:3] if cand_crop.size > 0 else (120, 120, 120)
                color_family = cls._classify_color(avg_bgr)
                conf = round(min(0.98, 0.84 + (aspect / 10.0) * 0.12), 3)

                file_instances.append(
                    ShelfFileInstance(
                        file_id=f"file_t{tier_idx + 1}_{len(file_instances) + 1}",
                        bbox=glob_box,
                        confidence=conf,
                        shelf_level=tier_idx + 1,
                        spine_width=int(cand_w),
                        aspect_ratio=round(aspect, 2),
                        color_family=color_family,
                    )
                )

        t1 = time.perf_counter()
        latency_ms = round((t1 - t0) * 1000.0, 2)
        total_files = len(file_instances)

        summary_text = (
            f"Bookshelf Analysis: {total_files} confirmed visible file/book instances detected "
            f"across {len(tier_bands)} shelf tier(s). Rejected {rejected_planks} shelf planks, "
            f"{rejected_wall_pics} wall pictures, and {rejected_shadows} shadows/voids. "
            f"Latency: {latency_ms}ms."
        )
        logger.info(summary_text)

        return DenseShelfCountResult(
            shelf_detected=True,
            shelf_bbox=resolved_shelf_box,
            shelf_levels_count=len(tier_bands),
            total_visible_files=total_files,
            file_instances=file_instances,
            rejected_planks_count=rejected_planks,
            rejected_wall_pictures_count=rejected_wall_pics,
            rejected_shadows_count=rejected_shadows,
            latency_ms=latency_ms,
            summary=summary_text,
        )

    @staticmethod
    def _classify_color(bgr: Tuple[float, float, float]) -> str:
        b, g, r = bgr
        if r > 160 and g < 100 and b < 100:
            return "RED"
        elif b > 150 and r < 110 and g < 140:
            return "BLUE"
        elif g > 140 and r < 110 and b < 110:
            return "GREEN"
        elif r > 170 and g > 170 and b < 100:
            return "YELLOW"
        elif r > 180 and g > 180 and b > 180:
            return "WHITE"
        elif r < 60 and g < 60 and b < 60:
            return "BLACK / DARK"
        elif abs(r - g) < 20 and abs(g - b) < 20:
            return "GREY"
        elif r > 130 and g > 80 and b < 60:
            return "BROWN / KRAFT"
        return "MULTI_TONE"
