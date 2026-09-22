"""Industrial Material Instance Segmentation & Stack Counting Service

Performs instance segmentation and watershed-guided mask separation for dense,
touching, and stacked industrial materials (cement bags, bricks, rebar, pallets).
Produces per-instance polygonal masks, individual instance counts, and exact
before/after removal delta calculations.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
import json
import os
import time
import math
import logging
import cv2
import numpy as np

logger = logging.getLogger("secops.ml.material_segmentation")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "material_classes_config.json")


@dataclass
class MaterialInstance:
    """Represents a segmented material instance with polygonal mask coordinates."""
    class_id: str
    class_name: str
    confidence: float
    bbox: List[int]  # [x, y, w, h]
    polygon: List[List[int]]  # [[x1, y1], [x2, y2], ...] contour points
    area_pixels: int
    mask_color_bgr: Tuple[int, int, int] = (0, 212, 255)


@dataclass
class SegmentationCountResult:
    """Result of material stack instance segmentation and counting."""
    total_instances: int
    counts_by_class: Dict[str, int]
    instances: List[MaterialInstance]
    latency_ms: float
    confidence_avg: float
    timestamp: float = field(default_factory=time.time)


class MaterialSegmentationService:
    """Instance segmentation service for stacked construction and industrial goods."""

    _config: Optional[Dict[str, Any]] = None

    @classmethod
    def load_config(cls) -> Dict[str, Any]:
        if cls._config is None:
            cfg: Dict[str, Any] = {}
            if os.path.exists(CONFIG_PATH):
                try:
                    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        if isinstance(loaded, dict):
                            cfg = loaded
                except Exception as e:
                    logger.error("Failed to load material classes config: %s", e)
            cls._config = cfg
        return cls._config if cls._config is not None else {}

    @classmethod
    def segment_materials(
        cls,
        frame: np.ndarray,
        target_roi: Optional[List[int]] = None,
        min_confidence: float = 0.40,
    ) -> SegmentationCountResult:
        """Executes instance segmentation on the frame or within an optional ROI [x, y, w, h].

        Isolates overlapping, touching, and stacked physical materials using multi-scale
        edge gradients, adaptive distance-transform watershedding, and contour polygonization.
        """
        t0 = time.perf_counter()
        h_img, w_img = frame.shape[:2]

        cfg = cls.load_config()
        classes_map = cfg.get("material_classes", {})

        # Crop to ROI if specified
        rx, ry, rw, rh = target_roi if target_roi else (0, 0, w_img, h_img)
        rx = max(0, min(rx, w_img - 1))
        ry = max(0, min(ry, h_img - 1))
        rw = max(1, min(rw, w_img - rx))
        rh = max(1, min(rh, h_img - ry))
        roi_crop = frame[ry:ry+rh, rx:rx+rw]

        # 1. Color and gradient analysis
        gray = cv2.cvtColor(roi_crop, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Bilateral filter to preserve instance boundaries while smoothing internal texture
        bilateral = cv2.bilateralFilter(blurred, 9, 75, 75)

        # 2. Foreground segmentation & edge separation
        _, otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # Invert if background is bright
        corner_mean = (float(otsu[0, 0]) + float(otsu[0, -1]) + float(otsu[-1, 0]) + float(otsu[-1, -1])) / 4.0
        if corner_mean > 127:
            otsu = cv2.bitwise_not(otsu)

        edges = cv2.Canny(bilateral, 30, 100)
        dilated_edges = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1)
        fg_separated = cv2.subtract(otsu, dilated_edges)

        # Morphological opening to clean sub-pixel salt noise
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        opening = cv2.morphologyEx(fg_separated, cv2.MORPH_OPEN, kernel, iterations=1)

        # 3. Distance transform for stacked/touching instances separation
        dist_transform = cv2.distanceTransform(opening, cv2.DIST_L2, 5)
        max_dist = dist_transform.max() if dist_transform.size > 0 else 0.0


        instances: List[MaterialInstance] = []
        counts_by_class: Dict[str, int] = {}

        if max_dist > 5.0:
            # Threshold distance transform to locate distinct instance nuclei
            _, sure_fg = cv2.threshold(dist_transform, 0.28 * max_dist, 255, 0)
            sure_fg_u8 = np.asarray(sure_fg, dtype=np.uint8)

            # Unknown boundary region
            sure_bg = cv2.dilate(opening, kernel, iterations=3)
            unknown = cv2.subtract(sure_bg, sure_fg_u8)

            # Connected components for markers
            _, markers = cv2.connectedComponents(sure_fg_u8)
            markers = markers + 1
            markers[unknown == 255] = 0

            # Watershed instance boundary partition
            roi_color = roi_crop.copy()
            markers = cv2.watershed(roi_color, markers)

            # Extract distinct instances from markers
            unique_markers = np.unique(markers)

            # Palette for distinct instance visualization
            colors = [
                (0, 212, 255), (79, 209, 179), (232, 163, 61), (0, 165, 255),
                (147, 112, 219), (60, 179, 113), (255, 140, 0), (220, 20, 60),
            ]

            idx_color = 0
            for marker_id in unique_markers:
                if marker_id <= 1:  # 0 is boundary (-1 in OpenCV), 1 is background
                    continue

                mask = np.zeros(gray.shape, dtype=np.uint8)
                mask[markers == marker_id] = 255

                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if not contours:
                    continue

                cnt = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(cnt)

                # Filter out microscopic noise (< 250 px) or full-frame blobs (> 85% area)
                min_area = max(250, int(0.002 * rw * rh))
                max_area = int(0.85 * rw * rh)
                if area < min_area or area > max_area:
                    continue

                bx, by, bw, bh = cv2.boundingRect(cnt)

                # Map back to full frame coordinates
                global_bx = rx + bx
                global_by = ry + by
                global_polygon = [[rx + int(pt[0][0]), ry + int(pt[0][1])] for pt in cnt]

                aspect_ratio = float(bw) / max(1, bh)
                rect_extent = area / float(bw * bh + 1e-6)

                patch_gray = gray[by:by+bh, bx:bx+bw]
                mean_val = float(np.mean(patch_gray)) if patch_gray.size > 0 else 0.0

                # Class determination based on aspect ratio, geometry, and texture
                if aspect_ratio > 3.5:
                    class_id = "102"  # Iron Rod / Rebar bundle
                    class_name = "Bundled Iron Rods / Rebar"
                    confidence = round(min(0.96, 0.72 + rect_extent * 0.22), 3)
                elif 2.2 <= aspect_ratio <= 3.5 and mean_val > 110:
                    # Corrugated Aluminum Sheets & Tin Panels (bright metallic surface, planar aspect)
                    class_id = "107"
                    class_name = "Corrugated Aluminum Sheets & Tin Panels"
                    confidence = round(min(0.95, 0.72 + rect_extent * 0.22), 3)
                elif 1.2 <= aspect_ratio <= 2.6 and rect_extent >= 0.55:
                    class_id = "101"  # Cement Bag (elongated sack)
                    class_name = "Cement Bag (50kg)"
                    confidence = round(min(0.96, 0.72 + rect_extent * 0.24), 3)
                elif 0.85 <= aspect_ratio <= 1.18 and rect_extent >= 0.70:
                    # Ceramic Tile Box (flat square package, high rect extent)
                    class_id = "106"
                    class_name = "Ceramic Tiles / Tile Box"
                    confidence = round(min(0.95, 0.72 + rect_extent * 0.23), 3)
                elif 0.65 <= aspect_ratio <= 1.5:
                    class_id = "104"  # Master Carton
                    class_name = "Heavy Corrugated Master Carton"
                    confidence = round(min(0.94, 0.70 + rect_extent * 0.25), 3)
                else:
                    class_id = "103"  # Brick Stack
                    class_name = "Brick Stack / Paver Pallet"
                    confidence = round(min(0.92, 0.68 + rect_extent * 0.20), 3)

                if confidence >= min_confidence:
                    assigned_color = colors[idx_color % len(colors)]
                    idx_color += 1

                    inst = MaterialInstance(
                        class_id=class_id,
                        class_name=class_name,
                        confidence=confidence,
                        bbox=[global_bx, global_by, bw, bh],
                        polygon=global_polygon,
                        area_pixels=int(area),
                        mask_color_bgr=assigned_color,
                    )
                    instances.append(inst)
                    counts_by_class[class_name] = counts_by_class.get(class_name, 0) + 1

        latency = round((time.perf_counter() - t0) * 1000.0, 2)
        avg_conf = (
            round(sum(i.confidence for i in instances) / max(1, len(instances)), 3)
            if instances else 0.0
        )

        return SegmentationCountResult(
            total_instances=len(instances),
            counts_by_class=counts_by_class,
            instances=instances,
            latency_ms=latency,
            confidence_avg=avg_conf,
        )

    @classmethod
    def calculate_stack_removal_delta(
        cls,
        before_counts: Dict[str, int],
        after_counts: Dict[str, int],
    ) -> Dict[str, int]:
        """Calculates exact physical removal delta: before_count - after_count.

        Positive delta means materials were removed (loaded onto truck).
        Negative delta means materials were added (unloaded into dock).
        """
        all_classes = set(before_counts.keys()).union(set(after_counts.keys()))
        deltas: Dict[str, int] = {}
        for c in sorted(all_classes):
            b = before_counts.get(c, 0)
            a = after_counts.get(c, 0)
            deltas[c] = b - a
        return deltas

    @classmethod
    def reconcile_with_manifest(
        cls,
        removed_deltas: Dict[str, int],
        manifest_expected: Dict[str, int],
    ) -> Tuple[str, int, List[Dict[str, Any]]]:
        """Reconciles physical removal delta against declared order manifest.

        Returns:
            (discrepancy_type, total_variance, item_breakdown)
            where discrepancy_type is:
                - 'MATCH': exact count or 0 variance
                - 'OVER_AUTHORIZED': removed > manifest (theft or excess loading)
                - 'UNDER_COUNT': removed < manifest (short shipment)
                - 'UNMANIFESTED_SKU': removed a material class not on manifest
        """
        all_skus = set(removed_deltas.keys()).union(set(manifest_expected.keys()))
        breakdown: List[Dict[str, Any]] = []

        has_over = False
        has_under = False
        has_unmanifested = False
        total_variance = 0

        for sku in sorted(all_skus):
            actual_removed = max(0, removed_deltas.get(sku, 0))
            expected = max(0, manifest_expected.get(sku, 0))
            variance = actual_removed - expected

            status = "MATCH"
            if expected == 0 and actual_removed > 0:
                status = "UNMANIFESTED"
                has_unmanifested = True
            elif variance > 0:
                status = "OVER_AUTHORIZED"
                has_over = True
            elif variance < 0:
                status = "UNDER_COUNT"
                has_under = True

            total_variance += abs(variance)
            breakdown.append({
                "sku": sku,
                "expected": expected,
                "actual_removed": actual_removed,
                "variance": variance,
                "status": status,
            })

        if has_unmanifested:
            primary_type = "UNMANIFESTED_SKU"
        elif has_over:
            primary_type = "OVER_AUTHORIZED"
        elif has_under:
            primary_type = "UNDER_COUNT"
        else:
            primary_type = "MATCH"

        return (primary_type, total_variance, breakdown)

    @classmethod
    def annotate_frame_with_masks(
        cls,
        frame: np.ndarray,
        instances: List[MaterialInstance],
        draw_labels: bool = True,
    ) -> np.ndarray:
        """Renders semi-transparent instance segmentation masks and HUD badges on frame."""
        annotated = frame.copy()
        mask_overlay = np.zeros_like(annotated, dtype=np.uint8)

        for inst in instances:
            pts = np.array(inst.polygon, dtype=np.int32)
            if len(pts) >= 3:
                # Draw translucent filled mask
                cv2.fillPoly(mask_overlay, [pts], inst.mask_color_bgr)
                # Draw sharp outer border
                cv2.polylines(annotated, [pts], isClosed=True, color=inst.mask_color_bgr, thickness=2)

        # Blend mask overlay at 35% opacity
        cv2.addWeighted(mask_overlay, 0.35, annotated, 0.65, 0, annotated)

        if draw_labels:
            for inst in instances:
                bx, by, bw, bh = inst.bbox
                label_text = f"{inst.class_name.split(' (')[0]} · {int(inst.confidence * 100)}%"

                # Background badge
                (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                tag_y = max(th + 4, by - 4)
                cv2.rectangle(
                    annotated,
                    (bx, tag_y - th - 3),
                    (bx + tw + 8, tag_y + 3),
                    (20, 24, 32),
                    -1,
                )
                cv2.rectangle(
                    annotated,
                    (bx, tag_y - th - 3),
                    (bx + tw + 8, tag_y + 3),
                    inst.mask_color_bgr,
                    1,
                )
                cv2.putText(
                    annotated,
                    label_text,
                    (bx + 4, tag_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (235, 240, 245),
                    1,
                    cv2.LINE_AA,
                )

        return annotated
