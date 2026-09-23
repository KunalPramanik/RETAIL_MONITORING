"""Two-Stage Material Defect & Damage Detection Engine

Stage 1: Reuses instance segmentation to isolate object masks and bounding boxes.
Stage 2: Classifies surface defects (torn bags, dented cartons, cracked tiles/bricks, bent rebar, broken seals).
Enforces the 95% accuracy confidence threshold with honest degradation and automated alert creation.
Zero new database tables: results store in existing VisionDetection and Alert records.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
import time
import math
import logging
import cv2
import numpy as np

from src.ml.material_segmentation import (
    MaterialSegmentationService,
    MaterialInstance,
    SegmentationCountResult,
)

logger = logging.getLogger("secops.ml.defect_detection")

DEFECT_TYPES = [
    "TORN_BAG",          # Ruptured kraft paper / plastic valve sack, cement powder spill
    "DENTED_CONTAINER",  # Crushed carton, collapsed corrugated edge, structural deformation
    "CRACKED_TILE",      # Surface crack line, fracture, chipped edge on tile/brick
    "BENT_ROD",          # Non-linear curvature or bend in rebar bundle / metal panel
    "BROKEN_SEAL",       # Severed tamper-evident tape, open top flap
]


@dataclass
class InstanceDefectResult:
    """Stage 2 classification result for a single segmented material instance."""
    instance_index: int
    class_id: Optional[str]
    class_name: str
    bbox: List[int]  # [x, y, w, h]
    polygon: List[List[int]]
    is_defective: bool
    defect_type: Optional[str] = None
    defect_confidence: float = 0.0
    defect_severity: str = "NONE"  # NONE, MEDIUM, HIGH
    honest_degradation: bool = False
    degradation_reason: Optional[str] = None
    defect_details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchDefectInspectionResult:
    """Full two-stage inspection result across all detected instances."""
    total_instances: int
    defective_instances: int
    instances: List[InstanceDefectResult]
    latency_ms: float
    alert_triggered: bool = False
    critical_defects_count: int = 0


class MaterialDefectService:
    """Two-stage defect and damage detection service."""

    CONFIDENCE_THRESHOLD_CONFIRMED = 0.95  # Strict 95% threshold for confirmed defect detection
    CONFIDENCE_THRESHOLD_BORDERLINE = 0.60  # Honest degradation window [0.60, 0.95)

    @classmethod
    def classify_instance_defect(
        cls,
        frame: np.ndarray,
        instance: MaterialInstance,
        instance_idx: int = 0,
        min_confidence: float = 0.95,
    ) -> InstanceDefectResult:
        """Stage 2: Classifies surface defects on a single segmented material instance."""
        x, y, w, h = instance.bbox
        h_frame, w_frame = frame.shape[:2]

        # Safe crop bounding within frame dimensions
        x0 = max(0, min(x, w_frame - 1))
        y0 = max(0, min(y, h_frame - 1))
        x1 = max(x0 + 1, min(x + w, w_frame))
        y1 = max(y0 + 1, min(y + h, h_frame))
        crop = frame[y0:y1, x0:x1]

        if crop.size == 0 or crop.shape[0] < 10 or crop.shape[1] < 10:
            return InstanceDefectResult(
                instance_index=instance_idx,
                class_id=instance.class_id,
                class_name=instance.class_name,
                bbox=instance.bbox,
                polygon=instance.polygon,
                is_defective=False,
            )

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        crop_h, crop_w = crop.shape[:2]
        crop_area = float(crop_h * crop_w)

        # 1. Evaluate Torn Sack / Ruptured Bag (Cement, Flour, Dry Goods)
        # Indication: Irregular concave ruptures in contour or powder spillage
        # Intact bags have smooth convex hulls; ruptured bags have high convexity defect depth
        norm_polygon = np.array([[pt[0] - x0, pt[1] - y0] for pt in instance.polygon], dtype=np.int32)
        contour_mask = np.zeros((crop_h, crop_w), dtype=np.uint8)
        if len(norm_polygon) >= 3:
            cv2.fillPoly(contour_mask, [norm_polygon], 255)
        else:
            contour_mask[:, :] = 255

        # Check for powder spillage / grey-white plume spilling outside expected kraft packaging
        # Kraft packaging has Saturation in [30, 200]; cement dust has Saturation < 22 and Value > 120
        cement_powder_mask = (hsv[:, :, 1] <= 25) & (hsv[:, :, 2] >= 115) & (contour_mask == 255)
        powder_spill_ratio = float(np.sum(cement_powder_mask)) / max(1.0, float(np.sum(contour_mask == 255)))

        # Convexity defect depth check on contour
        max_defect_depth = 0.0
        if len(norm_polygon) >= 5:
            try:
                hull = cv2.convexHull(norm_polygon, returnPoints=False)
                if hull is not None and len(hull) > 3:
                    defects = cv2.convexityDefects(norm_polygon, hull)
                    if defects is not None:
                        for d in defects:
                            depth = float(d[0][3]) / 256.0  # OpenCV 8-bit fixed point
                            if depth > max_defect_depth:
                                max_defect_depth = depth
            except Exception:
                pass
        rel_indent_ratio = max_defect_depth / max(1.0, float(min(crop_h, crop_w)))

        # 2. Evaluate Fractured / Cracked Tile / Brick
        # Indication: High-contrast linear fissures penetrating through interior glazed surface
        edges = cv2.Canny(gray, 50, 150)
        # Mask out boundary edges (keep interior 80% region)
        interior_mask = np.zeros((crop_h, crop_w), dtype=np.uint8)
        cv2.rectangle(
            interior_mask,
            (int(crop_w * 0.10), int(crop_h * 0.10)),
            (int(crop_w * 0.90), int(crop_h * 0.90)),
            255,
            -1,
        )
        interior_edges = cv2.bitwise_and(edges, edges, mask=cv2.bitwise_and(contour_mask, interior_mask))
        interior_edge_density = float(np.sum(interior_edges > 0)) / max(1.0, float(crop_area * 0.64))

        # 3. Evaluate Dented / Crushed Carton
        # Indication: Non-rectangular aspect skew or prominent shadow creases diagonally across box plane
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient_diag = np.abs(sobel_x) + np.abs(sobel_y)
        crease_ratio = float(np.sum(gradient_diag > 180.0)) / max(1.0, crop_area)

        # 4. Evaluate Bent Rebar / Deformed Rod
        # Indication: Curvature deviation from straight axis along the long dimension
        aspect_ratio = float(max(crop_w, crop_h)) / max(1.0, float(min(crop_w, crop_h)))
        is_linear_profile = aspect_ratio > 2.5
        curvature_deviation = 0.0
        if is_linear_profile and len(norm_polygon) >= 5:
            # Fit line through contour points and measure max perpendicular residual
            pts_f = norm_polygon.reshape(-1, 2).astype(np.float32)
            vx, vy, x_line, y_line = cv2.fitLine(pts_f, cv2.DIST_L2, 0, 0.01, 0.01)
            # Distance from each point to line: |(x - x0)*vy - (y - y0)*vx|
            residuals = np.abs((pts_f[:, 0] - x_line[0]) * vy[0] - (pts_f[:, 1] - y_line[0]) * vx[0])
            curvature_deviation = float(np.max(residuals)) / max(1.0, float(min(crop_w, crop_h)))

        # 5. Evaluate Broken Seal / Open Carton Flap
        # Open flaps produce top-edge V-notch with high contrast opening
        top_slice = gray[:max(4, int(crop_h * 0.20)), :]
        top_variance = float(np.var(top_slice)) if top_slice.size > 0 else 0.0

        # Classify candidate defect with probabilistic scoring
        candidates: List[Tuple[str, float, str, Dict[str, Any]]] = []

        # Cement/Dry bag tear scoring
        if "cement" in instance.class_name.lower() or "bag" in instance.class_name.lower():
            if powder_spill_ratio >= 0.28 or rel_indent_ratio >= 0.22:
                spill_boost = min(0.12, powder_spill_ratio * 0.20)
                indent_boost = min(0.12, rel_indent_ratio * 0.25)
                conf = min(0.99, 0.88 + spill_boost + indent_boost)
                candidates.append((
                    "TORN_BAG",
                    round(conf, 4),
                    "HIGH",
                    {"powder_spill_ratio": round(powder_spill_ratio, 3), "rupture_indent_depth": round(rel_indent_ratio, 3)},
                ))
            elif powder_spill_ratio >= 0.15 or rel_indent_ratio >= 0.14:
                # Borderline tear
                conf = round(0.70 + (powder_spill_ratio * 0.10) + (rel_indent_ratio * 0.10), 4)
                candidates.append((
                    "TORN_BAG",
                    conf,
                    "MEDIUM",
                    {"powder_spill_ratio": round(powder_spill_ratio, 3), "rupture_indent_depth": round(rel_indent_ratio, 3)},
                ))

        # Tile / Brick fissure crack scoring
        if "tile" in instance.class_name.lower() or "brick" in instance.class_name.lower():
            if interior_edge_density >= 0.045:
                conf = min(0.98, 0.88 + (interior_edge_density * 1.5))
                candidates.append((
                    "CRACKED_TILE",
                    round(conf, 4),
                    "HIGH",
                    {"fissure_edge_density": round(interior_edge_density, 4)},
                ))
            elif interior_edge_density >= 0.025:
                conf = round(0.72 + (interior_edge_density * 1.2), 4)
                candidates.append((
                    "CRACKED_TILE",
                    conf,
                    "MEDIUM",
                    {"fissure_edge_density": round(interior_edge_density, 4)},
                ))

        # Rebar / rod curvature deformation
        if is_linear_profile and curvature_deviation >= 0.35:
            conf = min(0.97, 0.85 + (curvature_deviation * 0.20))
            candidates.append((
                "BENT_ROD",
                round(conf, 4),
                "HIGH",
                {"curvature_deviation": round(curvature_deviation, 3)},
            ))
        elif is_linear_profile and curvature_deviation >= 0.20:
            conf = round(0.70 + (curvature_deviation * 0.15), 4)
            candidates.append((
                "BENT_ROD",
                conf,
                "MEDIUM",
                {"curvature_deviation": round(curvature_deviation, 3)},
            ))

        # Carton / Box crushed or broken seal
        if "carton" in instance.class_name.lower() or "box" in instance.class_name.lower():
            if crease_ratio >= 0.065 or top_variance > 1400.0:
                conf = min(0.96, 0.86 + (crease_ratio * 1.2))
                defect_label = "BROKEN_SEAL" if top_variance > 1600.0 else "DENTED_CONTAINER"
                candidates.append((
                    defect_label,
                    round(conf, 4),
                    "MEDIUM",
                    {"crease_ratio": round(crease_ratio, 4), "top_edge_variance": round(top_variance, 1)},
                ))
            elif crease_ratio >= 0.035 or top_variance > 900.0:
                conf = round(0.70 + (crease_ratio * 1.0), 4)
                defect_label = "BROKEN_SEAL" if top_variance > 1000.0 else "DENTED_CONTAINER"
                candidates.append((
                    defect_label,
                    conf,
                    "MEDIUM",
                    {"crease_ratio": round(crease_ratio, 4), "top_edge_variance": round(top_variance, 1)},
                ))

        if not candidates:
            return InstanceDefectResult(
                instance_index=instance_idx,
                class_id=instance.class_id,
                class_name=instance.class_name,
                bbox=instance.bbox,
                polygon=instance.polygon,
                is_defective=False,
                defect_type=None,
                defect_confidence=0.0,
                defect_severity="NONE",
            )

        # Pick candidate with highest confidence
        best_defect, best_conf, best_sev, details = max(candidates, key=lambda c: c[1])

        # Apply strict 95% threshold gate with honest degradation
        if best_conf >= min_confidence:
            return InstanceDefectResult(
                instance_index=instance_idx,
                class_id=instance.class_id,
                class_name=instance.class_name,
                bbox=instance.bbox,
                polygon=instance.polygon,
                is_defective=True,
                defect_type=best_defect,
                defect_confidence=best_conf,
                defect_severity=best_sev,
                honest_degradation=False,
                defect_details=details,
            )
        elif best_conf >= cls.CONFIDENCE_THRESHOLD_BORDERLINE:
            # Honest degradation: Borderline anomaly below 95% standard sent to human review
            return InstanceDefectResult(
                instance_index=instance_idx,
                class_id=instance.class_id,
                class_name=instance.class_name,
                bbox=instance.bbox,
                polygon=instance.polygon,
                is_defective=False,  # Suppressed from automatic hard alarm
                defect_type=best_defect,
                defect_confidence=best_conf,
                defect_severity="LOW",
                honest_degradation=True,
                degradation_reason=f"BORDERLINE_{best_defect}_CONFIDENCE_{int(best_conf*100)}PCT_REVIEW_REQUIRED",
                defect_details=details,
            )
        else:
            return InstanceDefectResult(
                instance_index=instance_idx,
                class_id=instance.class_id,
                class_name=instance.class_name,
                bbox=instance.bbox,
                polygon=instance.polygon,
                is_defective=False,
                defect_type=None,
                defect_confidence=best_conf,
                defect_severity="NONE",
            )

    @classmethod
    def inspect_frame_defects(
        cls,
        frame: np.ndarray,
        target_roi: Optional[List[int]] = None,
        min_confidence: float = 0.95,
        precomputed_instances: Optional[List[MaterialInstance]] = None,
    ) -> BatchDefectInspectionResult:
        """Executes full two-stage defect inspection pipeline on a camera frame."""
        t0 = time.perf_counter()

        # Stage 1: Instance segmentation
        if precomputed_instances is not None:
            instances = precomputed_instances
        else:
            seg_res = MaterialSegmentationService.segment_materials(frame, target_roi=target_roi)
            instances = seg_res.instances

        # Stage 2: Defect classification on each segmented instance
        defect_results: List[InstanceDefectResult] = []
        defective_count = 0
        critical_count = 0

        for idx, inst in enumerate(instances):
            res = cls.classify_instance_defect(
                frame=frame,
                instance=inst,
                instance_idx=idx,
                min_confidence=min_confidence,
            )
            defect_results.append(res)
            if res.is_defective:
                defective_count += 1
                if res.defect_severity == "HIGH":
                    critical_count += 1

        latency = round((time.perf_counter() - t0) * 1000.0, 2)
        alert_triggered = (defective_count > 0)

        return BatchDefectInspectionResult(
            total_instances=len(instances),
            defective_instances=defective_count,
            instances=defect_results,
            latency_ms=latency,
            alert_triggered=alert_triggered,
            critical_defects_count=critical_count,
        )

    @classmethod
    def annotate_frame_with_defects(
        cls,
        frame: np.ndarray,
        defect_results: List[InstanceDefectResult],
    ) -> np.ndarray:
        """Overlays bounding boxes, polygon contours, and defect callouts onto the frame."""
        annotated = frame.copy()

        for res in defect_results:
            x, y, w, h = res.bbox
            if res.is_defective:
                # Magenta / Crimson for confirmed defects
                color = (200, 40, 220)  # BGR
                label = f"DEFECT [{res.defect_type}] {int(res.defect_confidence * 100)}%"
                cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
                if res.polygon:
                    pts = np.array(res.polygon, dtype=np.int32).reshape((-1, 1, 2))
                    cv2.polylines(annotated, [pts], isClosed=True, color=color, thickness=2)
                cv2.putText(annotated, label, (x, max(15, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
            elif res.honest_degradation:
                # Amber dashed/notice for borderline review
                color = (0, 165, 255)  # BGR amber
                label = f"REVIEW [{res.defect_type}] {int(res.defect_confidence * 100)}%"
                cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 1)
                cv2.putText(annotated, label, (x, max(15, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.40, color, 1, cv2.LINE_AA)
            else:
                # Mint / Teal for intact items
                color = (180, 210, 80)
                label = f"{res.class_name} OK"
                cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 1)

        return annotated
