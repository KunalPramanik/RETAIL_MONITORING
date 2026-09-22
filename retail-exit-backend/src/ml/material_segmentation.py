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
        person_boxes: Optional[List[List[int]]] = None,
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

                # Human silhouette rejection: candidate material center must not lie within person body
                cx = global_bx + bw / 2.0
                cy = global_by + bh / 2.0
                if person_boxes:
                    in_person = False
                    for pb in person_boxes:
                        px, py, pw, ph = pb
                        if (px - 15 <= cx <= px + pw + 15) and (py - 15 <= cy <= py + ph + 15):
                            in_person = True
                            break
                        xA = max(global_bx, px)
                        yA = max(global_by, py)
                        xB = min(global_bx + bw, px + pw)
                        yB = min(global_by + bh, py + ph)
                        inter_w = max(0, xB - xA)
                        inter_h = max(0, yB - yA)
                        if inter_w * inter_h > 0.20 * (bw * bh):
                            in_person = True
                            break
                    if in_person:
                        continue

                aspect_ratio = float(bw) / max(1, bh)
                rect_extent = area / float(bw * bh + 1e-6)

                patch_bgr = roi_crop[by:by+bh, bx:bx+bw]
                patch_gray = gray[by:by+bh, bx:bx+bw]
                if patch_gray.size == 0 or patch_bgr.size == 0:
                    continue

                patch_hsv = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2HSV)
                mean_val = float(np.mean(patch_gray))
                std_val = float(np.std(patch_gray))

                # Cardboard kraft paper HSV profile: H in [10, 35], S in [30, 200], V in [40, 220]
                cardboard_mask = (
                    (patch_hsv[:, :, 0] >= 10) & (patch_hsv[:, :, 0] <= 35) &
                    (patch_hsv[:, :, 1] >= 30) & (patch_hsv[:, :, 1] <= 200) &
                    (patch_hsv[:, :, 2] >= 40) & (patch_hsv[:, :, 2] <= 220)
                )
                cardboard_ratio = float(np.sum(cardboard_mask)) / float(bw * bh)

                # Clay brick HSV profile: terracotta / clay / red / orange (H <= 22 or H >= 160, S >= 35, V >= 35)
                clay_mask = (
                    ((patch_hsv[:, :, 0] <= 22) | (patch_hsv[:, :, 0] >= 160)) &
                    (patch_hsv[:, :, 1] >= 35) &
                    (patch_hsv[:, :, 2] >= 35)
                )
                clay_ratio = float(np.sum(clay_mask)) / float(bw * bh)

                # Concrete masonry paver: neutral grey/tan (S <= 25, 50 <= V <= 190)
                concrete_mask = (
                    (patch_hsv[:, :, 1] <= 25) &
                    (patch_hsv[:, :, 2] >= 50) & (patch_hsv[:, :, 2] <= 190)
                )
                concrete_ratio = float(np.sum(concrete_mask)) / float(bw * bh)

                # Horizontal coursing seams / layer joints (Sobel Y gradient peaks)
                sobel_y = cv2.Sobel(patch_gray, cv2.CV_64F, 0, 1, ksize=3)
                row_seams = np.mean(np.abs(sobel_y), axis=1)
                seam_peaks = int(np.sum(row_seams > 22.0))

                mean_sat = float(np.mean(patch_hsv[:, :, 1]))
                is_cement_sack = (cardboard_ratio >= 0.20) or (mean_val >= 150 and mean_sat <= 25)

                # Class determination based on physical geometry, colorimetry, and surface texture
                class_id = None
                class_name = None
                confidence = 0.0

                if aspect_ratio > 3.2 and std_val > 10.0:
                    class_id = "102"  # Iron Rod / Rebar bundle
                    class_name = "Bundled Iron Rods / Rebar"
                    confidence = round(min(0.96, 0.72 + rect_extent * 0.22), 3)
                elif 2.0 <= aspect_ratio <= 3.8 and mean_val > 105:
                    # Corrugated Aluminum Sheets & Tin Panels (bright metallic reflective surface)
                    class_id = "107"
                    class_name = "Corrugated Aluminum Sheets & Tin Panels"
                    confidence = round(min(0.95, 0.72 + rect_extent * 0.22), 3)
                elif 0.85 <= aspect_ratio <= 1.18 and rect_extent >= 0.70 and mean_val > 80:
                    # Ceramic Tile Box (flat square package, high rect extent, glazed brightness)
                    class_id = "106"
                    class_name = "Ceramic Tiles / Tile Box"
                    confidence = round(min(0.95, 0.72 + rect_extent * 0.23), 3)
                elif 0.65 <= aspect_ratio <= 1.85 and rect_extent >= 0.65 and cardboard_ratio >= 0.20:
                    # Heavy Corrugated Master Carton (cardboard kraft color + rectangular box form)
                    class_id = "104"
                    class_name = "Heavy Corrugated Master Carton"
                    confidence = round(min(0.94, 0.70 + rect_extent * 0.25), 3)
                elif (((clay_ratio >= 0.22 and seam_peaks >= 3) or (concrete_ratio >= 0.35 and std_val > 22.0 and seam_peaks >= 4)) and rect_extent >= 0.55):
                    # Brick Stack / Paver Pallet (clay or concrete with verified horizontal coursing seams)
                    class_id = "103"
                    class_name = "Brick Stack / Paver Pallet"
                    confidence = round(min(0.92, 0.68 + rect_extent * 0.20), 3)
                elif 1.15 <= aspect_ratio <= 2.8 and rect_extent >= 0.50 and is_cement_sack:
                    # Cement Bag (50kg) (elongated valve sack: kraft brown or white/light-grey paper valve sack)
                    class_id = "101"
                    class_name = "Cement Bag (50kg)"
                    confidence = round(min(0.96, 0.72 + rect_extent * 0.24), 3)
                else:
                    # Negative rejection: unverified background blobs, furniture, or clothes are discarded
                    continue

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
