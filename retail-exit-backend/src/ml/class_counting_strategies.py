"""SEC-OPS V8 Class-Specific Counting & Behavior Verification Strategies

Implements Section 7 of the SEC-OPS V8 Master Prompt:
- 7.1 Cement Bags: Visible face counting, layer stacking multipliers, occlusion bounds.
- 7.2 Iron Rods & Rebar: Bundle counting, strapping detection, end-face resolution gate.
- 7.3 Books & Bookshelves: Shelf plank rejection, vertical spine counting, dense shelf warning.
- 7.4 Bottles & Cartons: Single unit vs master carton multiplier.
- 7.5 Turnstile Crossing: Directional line crossing deduplication with hysteresis.
- 7.6 Theft & Concealment: Small item pocketing / bag concealment alert trigger.
"""

from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
import cv2
import numpy as np
import time
import logging

logger = logging.getLogger("secops.ml.class_counting_strategies")


# ============================================================================
# 7.1 Cement Bag Stack Counting Strategy
# ============================================================================

@dataclass
class CementStackCountResult:
    visible_face_count: int
    estimated_layers: int
    bags_per_layer_nominal: int
    estimated_total_count: int
    count_min_bound: int
    count_max_bound: int
    is_occluded: bool
    confidence: float
    status: str  # "CONFIRMED_VISIBLE", "DEPTH_ESTIMATED", "OCCLUDED_REVIEW_REQUIRED"
    explanation: str


class CementStackStrategy:
    """Estimates and verifies physical cement bag stacks on pallets."""

    DEFAULT_BAGS_PER_LAYER = 5  # Standard 5-bag interlocking pallet pattern (1.5m x 1.2m pallet)

    @classmethod
    def evaluate_stack(
        cls,
        visible_faces: int,
        stack_height_px: int,
        pallet_detected: bool = True,
        is_mixed_pallet: bool = False,
    ) -> CementStackCountResult:
        """Calculates visible count and volumetric bounds for palletized cement bags."""
        if visible_faces <= 0:
            return CementStackCountResult(
                visible_face_count=0,
                estimated_layers=0,
                bags_per_layer_nominal=cls.DEFAULT_BAGS_PER_LAYER,
                estimated_total_count=0,
                count_min_bound=0,
                count_max_bound=0,
                is_occluded=False,
                confidence=1.0,
                status="CONFIRMED_VISIBLE",
                explanation="No cement bags detected in region.",
            )

        # Standard bag height is ~15cm; estimate layer count from visible faces
        # In a standard pallet stack viewed from front/side:
        # A single column of 8 layers shows 8 visible faces (front) or ~16 (corner).
        if visible_faces <= 5:
            # Low layer or single row visible
            est_layers = max(1, visible_faces)
            is_occluded = True
            est_total = est_layers * cls.DEFAULT_BAGS_PER_LAYER
            min_bound = visible_faces
            max_bound = est_total + 5
            status = "OCCLUDED_REVIEW_REQUIRED"
            conf = 0.65
            expl = (
                f"Partial front view ({visible_faces} bags visible). Rear rows occluded. "
                f"Estimated {est_total} bags ({est_layers} tiers x {cls.DEFAULT_BAGS_PER_LAYER}/tier). "
                f"Bounds: [{min_bound}, {max_bound}]. Manual review advised."
            )
        elif visible_faces < 20:
            # Typical 2-side or front view of standard 8-10 tier pallet
            est_layers = max(2, int(round(visible_faces / 2.0)))
            is_occluded = True
            est_total = est_layers * cls.DEFAULT_BAGS_PER_LAYER
            min_bound = visible_faces
            max_bound = max(visible_faces, est_total)
            status = "DEPTH_ESTIMATED"
            conf = 0.82
            expl = (
                f"Stack of ~{est_layers} tiers observed with {visible_faces} visible faces. "
                f"Estimated total: {est_total} bags (bounds [{min_bound}, {max_bound}])."
            )
        else:
            # Full pallet or multi-pallet stack
            est_layers = max(4, int(round(visible_faces / 3.0)))
            est_total = max(visible_faces, est_layers * cls.DEFAULT_BAGS_PER_LAYER)
            min_bound = visible_faces
            max_bound = int(est_total * 1.15)
            is_occluded = False
            status = "CONFIRMED_VISIBLE"
            conf = 0.90
            expl = f"Full pallet stack observed: {visible_faces} confirmed visible faces."

        return CementStackCountResult(
            visible_face_count=visible_faces,
            estimated_layers=est_layers,
            bags_per_layer_nominal=cls.DEFAULT_BAGS_PER_LAYER,
            estimated_total_count=est_total,
            count_min_bound=min_bound,
            count_max_bound=max_bound,
            is_occluded=is_occluded,
            confidence=conf,
            status=status,
            explanation=expl,
        )


# ============================================================================
# 7.2 Iron Rods & Bundled Rebar Counting Strategy
# ============================================================================

@dataclass
class RebarCountResult:
    bundle_count: int
    strapping_detected: bool
    individual_rods_resolvable: bool
    estimated_rods_per_bundle: int
    total_estimated_rods: int
    confidence: float
    status: str  # "BUNDLE_LEVEL_VERIFIED", "SINGLE_RODS_RESOLVED", "ESTIMATE_UNCERTAIN"
    explanation: str


class IronRebarStrategy:
    """Distinguishes rebar bundles from loose individual rods based on resolution and strapping."""

    DEFAULT_RODS_PER_BUNDLE = 100  # Standard 12mm rebar bundle nominal specification

    @classmethod
    def evaluate_rebar(
        cls,
        detected_bundles: int,
        resolved_rod_ends: int = 0,
        avg_rod_diameter_px: float = 0.0,
        has_strapping: bool = True,
        rods_per_bundle_spec: Optional[int] = None,
    ) -> RebarCountResult:
        nominal_per_bundle = rods_per_bundle_spec or cls.DEFAULT_RODS_PER_BUNDLE

        # If camera resolution resolves individual end faces (>= 8 px diameter with clear separation)
        if resolved_rod_ends > 0 and avg_rod_diameter_px >= 8.0:
            return RebarCountResult(
                bundle_count=max(1, detected_bundles),
                strapping_detected=has_strapping,
                individual_rods_resolvable=True,
                estimated_rods_per_bundle=nominal_per_bundle,
                total_estimated_rods=resolved_rod_ends,
                confidence=0.92,
                status="SINGLE_RODS_RESOLVED",
                explanation=f"Directly resolved {resolved_rod_ends} individual rod end faces.",
            )

        # Standard industrial bundle counting
        total_rods = detected_bundles * nominal_per_bundle
        conf = 0.95 if has_strapping else 0.75
        status = "BUNDLE_LEVEL_VERIFIED" if has_strapping else "ESTIMATE_UNCERTAIN"
        expl = (
            f"Observed {detected_bundles} strapped bundles. Rod ends are sub-pixel (<8px); "
            f"reporting verified {detected_bundles} bundle(s) (= ~{total_rods} nominal rods)."
        )

        return RebarCountResult(
            bundle_count=detected_bundles,
            strapping_detected=has_strapping,
            individual_rods_resolvable=False,
            estimated_rods_per_bundle=nominal_per_bundle,
            total_estimated_rods=total_rods,
            confidence=conf,
            status=status,
            explanation=expl,
        )


# ============================================================================
# 7.3 Books vs Bookshelves Counting Strategy
# ============================================================================

@dataclass
class BookshelfCountResult:
    shelf_detected: bool
    shelf_levels_count: int
    visible_books_count: int
    dense_row_estimate: bool
    confidence: float
    status: str  # "INDIVIDUAL_BOOKS_VERIFIED", "DENSE_ROW_ESTIMATE", "EMPTY_SHELF"
    explanation: str


class BookAndBookshelfStrategy:
    """Separates furniture structure (shelves) from book contents and detects dense packing."""

    @classmethod
    def evaluate_books(
        cls,
        shelf_detected: bool,
        shelf_levels: int,
        resolved_spines: int,
        shelf_width_px: int = 800,
        avg_spine_width_px: float = 20.0,
    ) -> BookshelfCountResult:
        if not shelf_detected and resolved_spines == 0:
            return BookshelfCountResult(
                shelf_detected=False,
                shelf_levels_count=0,
                visible_books_count=0,
                dense_row_estimate=False,
                confidence=1.0,
                status="EMPTY_SHELF",
                explanation="No bookshelf or book instances observed.",
            )

        if shelf_detected and resolved_spines <= 0:
            return BookshelfCountResult(
                shelf_detected=True,
                shelf_levels_count=shelf_levels,
                visible_books_count=0,
                dense_row_estimate=False,
                confidence=0.60,
                status="COUNT_UNCERTAIN",
                explanation=(
                    f"Bookshelf fixture detected ({shelf_levels} level(s)) but individual book spines cannot "
                    f"be resolved optically. MANUAL_COUNT_REQUIRED: Furniture fixture separated from material inventory."
                ),
            )

        # Check if books are packed so densely that spine separation hits optical limit
        # Max theoretical books per shelf = shelf_width / min_spine_width
        dense_row = False
        if shelf_detected and resolved_spines > 0 and avg_spine_width_px < 10.0:
            dense_row = True
            status = "DENSE_ROW_ESTIMATE"
            conf = 0.78
            expl = (
                f"Bookshelf with {shelf_levels} level(s) detected. High book packing density; "
                f"counted {resolved_spines} spines (flagged as dense row estimate)."
            )
        else:
            status = "INDIVIDUAL_BOOKS_VERIFIED"
            conf = 0.91
            expl = (
                f"Bookshelf with {shelf_levels} level(s) detected. Confirmed {resolved_spines} "
                f"individual book instances."
            )

        return BookshelfCountResult(
            shelf_detected=shelf_detected,
            shelf_levels_count=shelf_levels,
            visible_books_count=resolved_spines,
            dense_row_estimate=dense_row,
            confidence=conf,
            status=status,
            explanation=expl,
        )


# ============================================================================
# 7.4 Bottles & Cartons Packaging Multiplier Strategy
# ============================================================================

@dataclass
class BottleCartonCountResult:
    loose_units: int
    cases_detected: int
    units_per_case: int
    total_equivalent_units: int
    confidence: float
    explanation: str


class BottleAndCartonStrategy:
    """Applies package multiplier rules to convert cartons and loose units into verified stock units."""

    @classmethod
    def calculate_units(
        cls,
        loose_units: int,
        cases_detected: int,
        units_per_case: int = 24,
    ) -> BottleCartonCountResult:
        total = (cases_detected * units_per_case) + loose_units
        return BottleCartonCountResult(
            loose_units=loose_units,
            cases_detected=cases_detected,
            units_per_case=units_per_case,
            total_equivalent_units=total,
            confidence=0.96,
            explanation=(
                f"{cases_detected} sealed cases (x{units_per_case}) + {loose_units} loose units "
                f"= {total} total stock units."
            ),
        )


# ============================================================================
# 7.5 Turnstile Crossing Deduplication Strategy
# ============================================================================

@dataclass
class TurnstileCrossingResult:
    track_id: str
    direction: str  # "ENTRY", "EXIT", "TRAVERSAL_INCOMPLETE"
    crossing_confirmed: bool
    y_start: float
    y_end: float
    dwell_time_seconds: float


class TurnstileCrossingStrategy:
    """Analyzes trajectory vectors across a virtual gate line with hysteresis to prevent duplicate counts."""

    HYSTERESIS_THRESHOLD = 0.08  # Normalized distance hysteresis to commit crossing

    @classmethod
    def evaluate_track_crossing(
        cls,
        track_id: str,
        trajectory: List[Tuple[float, float, float]],  # List of (x, y, timestamp)
        tripwire_y: float = 0.50,
    ) -> TurnstileCrossingResult:
        if len(trajectory) < 2:
            return TurnstileCrossingResult(
                track_id=track_id,
                direction="TRAVERSAL_INCOMPLETE",
                crossing_confirmed=False,
                y_start=trajectory[0][1] if trajectory else 0.0,
                y_end=trajectory[-1][1] if trajectory else 0.0,
                dwell_time_seconds=0.0,
            )

        y_start = trajectory[0][1]
        y_end = trajectory[-1][1]
        t_start = trajectory[0][2]
        t_end = trajectory[-1][2]
        dwell = max(0.0, t_end - t_start)

        # Check if trajectory cleanly crosses tripwire_y with hysteresis
        if (y_start < (tripwire_y - cls.HYSTERESIS_THRESHOLD)) and (y_end > (tripwire_y + cls.HYSTERESIS_THRESHOLD)):
            return TurnstileCrossingResult(
                track_id=track_id,
                direction="EXIT",
                crossing_confirmed=True,
                y_start=y_start,
                y_end=y_end,
                dwell_time_seconds=dwell,
            )
        elif (y_start > (tripwire_y + cls.HYSTERESIS_THRESHOLD)) and (y_end < (tripwire_y - cls.HYSTERESIS_THRESHOLD)):
            return TurnstileCrossingResult(
                track_id=track_id,
                direction="ENTRY",
                crossing_confirmed=True,
                y_start=y_start,
                y_end=y_end,
                dwell_time_seconds=dwell,
            )
        else:
            return TurnstileCrossingResult(
                track_id=track_id,
                direction="TRAVERSAL_INCOMPLETE",
                crossing_confirmed=False,
                y_start=y_start,
                y_end=y_end,
                dwell_time_seconds=dwell,
            )


# ============================================================================
# 7.6 Retail Theft & Concealment Detection Strategy
# ============================================================================

@dataclass
class ConcealmentAlertResult:
    alert_triggered: bool
    person_track_id: str
    target_item_class: str
    overlap_iou: float
    severity: str  # "HIGH", "CRITICAL", "NONE"
    explanation: str


class TheftConcealmentStrategy:
    """Detects pocketing or bag-concealment behavior when items disappear near a person's body."""

    @classmethod
    def evaluate_concealment(
        cls,
        person_track_id: str,
        person_bbox: List[int],  # [x, y, w, h]
        item_track_history: List[Dict[str, Any]],  # Frame detections of the item
        current_frame_item_visible: bool,
    ) -> ConcealmentAlertResult:
        if not item_track_history or current_frame_item_visible:
            return ConcealmentAlertResult(
                alert_triggered=False,
                person_track_id=person_track_id,
                target_item_class="",
                overlap_iou=0.0,
                severity="NONE",
                explanation="Item is either still visible or no track history exists.",
            )

        last_item_det = item_track_history[-1]
        ibox = last_item_det.get("bbox", [0, 0, 0, 0])
        iclass = last_item_det.get("class_name", "item")

        # Check if item's last visible position was inside/overlapping the person's bounding box
        px, py, pw, ph = person_bbox
        ix, iy, iw, ih = ibox

        # Compute intersection over item area
        x_left = max(px, ix)
        y_top = max(py, iy)
        x_right = min(px + pw, ix + iw)
        y_bottom = min(py + ph, iy + ih)

        if x_right > x_left and y_bottom > y_top:
            inter_area = (x_right - x_left) * (y_bottom - y_top)
            item_area = max(1, iw * ih)
            containment_ratio = inter_area / float(item_area)

            # If item was >= 70% inside the person box right before disappearing
            if containment_ratio >= 0.70:
                return ConcealmentAlertResult(
                    alert_triggered=True,
                    person_track_id=person_track_id,
                    target_item_class=iclass,
                    overlap_iou=round(containment_ratio, 2),
                    severity="HIGH",
                    explanation=(
                        f"Potential concealment detected: {iclass} disappeared while contained "
                        f"({int(containment_ratio * 100)}%) inside Person {person_track_id}'s body/pocket/bag zone."
                    ),
                )

        return ConcealmentAlertResult(
            alert_triggered=False,
            person_track_id=person_track_id,
            target_item_class=iclass,
            overlap_iou=0.0,
            severity="NONE",
            explanation="Item vanished outside person zone (occlusion or out-of-frame).",
        )

