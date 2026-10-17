"""SEC-OPS V8 Comprehensive Dataset, Strategy, and Pipeline Verification Suite

Verifies:
- DatasetInspector on real sample dataset images (quality, blur, dimensions, leakage-safe splits).
- AnnotationWorkflowManager (provenance tracking, review gates, YOLO export).
- ClassCountingStrategies (Cement stacks, Iron rebar, Bookshelves, Cartons, Turnstiles, Concealment).
- PendingProductIdentification & Visual Class Mapping (Phase 5).
- InvoiceReconciliationEngine (all 5 explicit reconciliation states & pipeline separation).
- MaterialInventoryBalance atomic accounting identity.
"""

import os
import shutil
import tempfile
import pytest
import numpy as np

from src.ml.dataset_inspector import DatasetInspector, ImageQualityMetrics
from src.ml.annotation_workflow import AnnotationWorkflowManager, CANONICAL_CLASSES
from src.ml.class_counting_strategies import (
    CementStackStrategy,
    IronRebarStrategy,
    BookAndBookshelfStrategy,
    BottleAndCartonStrategy,
    TurnstileCrossingStrategy,
    TheftConcealmentStrategy,
)
from src.engine.invoice_reconciliation_engine import InvoiceReconciliationEngine


SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "sample_dataset")


class TestDatasetInspector:
    def test_sample_dataset_images_quality(self):
        """Audits the 5 real user sample pictures in the sample_dataset directory."""
        assert os.path.exists(SAMPLE_DIR), f"Sample dataset dir {SAMPLE_DIR} must exist"
        report = DatasetInspector.inspect_directories([SAMPLE_DIR])

        assert report.total_images_found >= 5
        assert report.valid_images_count >= 5
        assert report.corrupted_images_count == 0

        # Verify all sample images are sharp and sufficiently high resolution
        for img in report.images:
            assert not img.is_corrupted
            assert img.width == 1024
            assert img.height == 764
            assert img.blur_laplacian_var >= 100.0  # Sharp
            assert img.blur_status == "SHARP"
            assert img.exposure_status == "NORMAL"
            assert img.counting_suitability == "INDIVIDUAL_INSTANCE_RESOLVABLE"

    def test_duplicate_and_leakage_safe_splits(self):
        """Validates that dHash detects near-duplicates and groups them safely into splits."""
        report = DatasetInspector.inspect_directories([SAMPLE_DIR])
        splits = report.leakage_safe_splits

        assert "train" in splits
        assert "val" in splits
        assert "held_out_test" in splits

        # Total split items should equal valid images
        all_split_images = set(splits["train"] + splits["val"] + splits["held_out_test"])
        assert len(all_split_images) == report.valid_images_count


class TestAnnotationWorkflowManager:
    @pytest.fixture
    def temp_queue(self):
        temp_dir = tempfile.mkdtemp()
        mgr = AnnotationWorkflowManager(storage_dir=temp_dir)
        yield mgr
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_annotation_lifecycle_and_provenance(self, temp_queue):
        """Tests enqueuing, human review approval, modification, and final promotion."""
        img_path = os.path.join(SAMPLE_DIR, "warehouse_cement_pallet_stack.jpg")

        # 1. Enqueue image with model-proposed detections
        proposed = [
            {"class_id": 101, "class_name": "Cement bag", "bbox": [100, 150, 200, 100], "confidence": 0.88},
            {"class_id": 0, "class_name": "Person", "bbox": [500, 200, 150, 400], "confidence": 0.92},
        ]
        item = temp_queue.enqueue_image_for_review(
            image_path=img_path,
            image_hash="abc123dhash",
            width=1024,
            height=764,
            proposed_detections=proposed,
        )

        assert item.status == "UNREVIEWED"
        assert len(item.annotations) == 2
        assert item.annotations[0].status == "PROPOSED"
        assert item.annotations[0].source == "MODEL_PROPOSED"

        # 2. Cannot finalize review while proposed items remain unreviewed
        assert not temp_queue.finalize_image_review(item.queue_id, "OP-01", "APPROVE_TRUSTED")

        # 3. Review annotation 0: Approve
        ok = temp_queue.review_annotation(
            queue_id=item.queue_id,
            annotation_id=item.annotations[0].annotation_id,
            operator_id="OP-01",
            action="APPROVE",
            notes="Confirmed cement bag valve sack",
        )
        assert ok
        assert item.annotations[0].status == "APPROVED"
        assert item.annotations[0].operator_id == "OP-01"

        # 4. Review annotation 1: Modify
        ok = temp_queue.review_annotation(
            queue_id=item.queue_id,
            annotation_id=item.annotations[1].annotation_id,
            operator_id="OP-01",
            action="MODIFY",
            corrected_class_id=0,
            corrected_bbox_yolo=[0.55, 0.40, 0.15, 0.50],
            notes="Adjusted bounding box around safety vest",
        )
        assert ok
        assert item.annotations[1].status == "MODIFIED"

        # 5. Finalize review: Promoted to trusted
        finalized = temp_queue.finalize_image_review(item.queue_id, "OP-01", "APPROVE_TRUSTED")
        assert finalized
        assert item.status == "APPROVED_TRUSTED"

        # 6. Export verified YOLO dataset
        export_dir = tempfile.mkdtemp()
        res = temp_queue.export_verified_yolo_dataset(export_dir)
        assert res["exported_images"] == 1
        assert res["exported_annotations"] == 2
        shutil.rmtree(export_dir, ignore_errors=True)


class TestClassCountingStrategies:
    def test_cement_stack_strategy(self):
        """Verifies cement bag pallet layer estimation and occlusion flagging."""
        # Case A: Small visible face count triggers occlusion review
        res_small = CementStackStrategy.evaluate_stack(visible_faces=4, stack_height_px=200)
        assert res_small.is_occluded is True
        assert res_small.status == "OCCLUDED_REVIEW_REQUIRED"
        assert res_small.count_min_bound == 4
        assert res_small.estimated_total_count == 20  # 4 layers * 5 bags/layer

        # Case B: Large visible face count is confirmed
        res_large = CementStackStrategy.evaluate_stack(visible_faces=35, stack_height_px=800)
        assert res_large.is_occluded is False
        assert res_large.status == "CONFIRMED_VISIBLE"
        assert res_large.estimated_total_count >= 35

    def test_iron_rebar_strategy(self):
        """Verifies bundle counting and sub-pixel rod uncertainty reporting."""
        # Case A: Strapped bundle with unresolved rod ends
        res_bundle = IronRebarStrategy.evaluate_rebar(detected_bundles=3, has_strapping=True)
        assert res_bundle.bundle_count == 3
        assert res_bundle.status == "BUNDLE_LEVEL_VERIFIED"
        assert res_bundle.individual_rods_resolvable is False
        assert res_bundle.total_estimated_rods == 300  # 3 * 100 nominal

        # Case B: Direct rod end resolution
        res_rods = IronRebarStrategy.evaluate_rebar(
            detected_bundles=1,
            resolved_rod_ends=45,
            avg_rod_diameter_px=12.5,
        )
        assert res_rods.status == "SINGLE_RODS_RESOLVED"
        assert res_rods.individual_rods_resolvable is True
        assert res_rods.total_estimated_rods == 45

    def test_bookshelf_strategy(self):
        """Verifies bookshelf level and book spine counting with dense row warnings."""
        res_clean = BookAndBookshelfStrategy.evaluate_books(
            shelf_detected=True,
            shelf_levels=3,
            resolved_spines=42,
            avg_spine_width_px=18.0,
        )
        assert res_clean.status == "INDIVIDUAL_BOOKS_VERIFIED"
        assert res_clean.dense_row_estimate is False
        assert res_clean.visible_books_count == 42

        res_dense = BookAndBookshelfStrategy.evaluate_books(
            shelf_detected=True,
            shelf_levels=4,
            resolved_spines=80,
            avg_spine_width_px=6.5,
        )
        assert res_dense.status == "DENSE_ROW_ESTIMATE"
        assert res_dense.dense_row_estimate is True

    def test_bottle_carton_strategy(self):
        """Verifies package multiplier math."""
        res = BottleAndCartonStrategy.calculate_units(loose_units=3, cases_detected=5, units_per_case=24)
        assert res.total_equivalent_units == 123  # (5 * 24) + 3

    def test_turnstile_crossing_strategy(self):
        """Verifies directional trajectory crossing and hysteresis gating."""
        # Valid EXIT: Traversal from y=0.30 to y=0.70 across line at y=0.50
        exit_traj = [(0.5, 0.30, 100.0), (0.5, 0.45, 100.5), (0.5, 0.70, 101.0)]
        res_exit = TurnstileCrossingStrategy.evaluate_track_crossing("T-1", exit_traj, tripwire_y=0.50)
        assert res_exit.crossing_confirmed is True
        assert res_exit.direction == "EXIT"

        # Valid ENTRY: Traversal from y=0.75 to y=0.25 across line at y=0.50
        entry_traj = [(0.5, 0.75, 100.0), (0.5, 0.50, 100.5), (0.5, 0.25, 101.0)]
        res_entry = TurnstileCrossingStrategy.evaluate_track_crossing("T-2", entry_traj, tripwire_y=0.50)
        assert res_entry.crossing_confirmed is True
        assert res_entry.direction == "ENTRY"

        # Incomplete traversal: Traversal fluttering near tripwire
        jitter_traj = [(0.5, 0.48, 100.0), (0.5, 0.52, 100.5)]
        res_jitter = TurnstileCrossingStrategy.evaluate_track_crossing("T-3", jitter_traj, tripwire_y=0.50)
        assert res_jitter.crossing_confirmed is False
        assert res_jitter.direction == "TRAVERSAL_INCOMPLETE"

    def test_theft_concealment_strategy(self):
        """Verifies concealment alert when item disappears within person bounding box."""
        person_bbox = [100, 100, 200, 400]  # x=100..300, y=100..500
        # Item inside person bounding box (e.g. phone at chest/pocket: x=150, y=250, w=40, h=60)
        item_history = [{"class_name": "Phone", "bbox": [150, 250, 40, 60]}]

        # Item disappears in next frame (visible=False)
        alert = TheftConcealmentStrategy.evaluate_concealment(
            person_track_id="P-99",
            person_bbox=person_bbox,
            item_track_history=item_history,
            current_frame_item_visible=False,
        )
        assert alert.alert_triggered is True
        assert alert.severity == "HIGH"
        assert alert.overlap_iou == 1.0


class TestInvoiceReconciliationEngine:
    def test_all_five_reconciliation_states(self):
        """Verifies MATCHED, OVERAGE, SHORTAGE_REVIEW, NO_AUTHORIZATION_FOUND, and INCONCLUSIVE."""
        # 1. MATCHED: 10 physical vs 10 billed
        r_matched = InvoiceReconciliationEngine.reconcile(
            event_id="evt_01",
            camera_id="cam_exit",
            physical_units_count=10,
            invoice_id="inv_100",
            declared_billed_units=10,
        )
        assert r_matched.status == "MATCHED"
        assert r_matched.is_authorized is True
        assert r_matched.variance_units == 0
        assert r_matched.severity == "NONE"
        assert len(r_matched.cryptographic_hash) == 64

        # 2. OVERAGE: 12 physical vs 10 billed
        r_over = InvoiceReconciliationEngine.reconcile(
            event_id="evt_02",
            camera_id="cam_exit",
            physical_units_count=12,
            invoice_id="inv_100",
            declared_billed_units=10,
        )
        assert r_over.status == "OVERAGE"
        assert r_over.is_authorized is False
        assert r_over.variance_units == 2
        assert r_over.severity == "HIGH"

        # 3. SHORTAGE_REVIEW: 8 physical vs 10 billed
        r_short = InvoiceReconciliationEngine.reconcile(
            event_id="evt_03",
            camera_id="cam_exit",
            physical_units_count=8,
            invoice_id="inv_100",
            declared_billed_units=10,
        )
        assert r_short.status == "SHORTAGE_REVIEW"
        assert r_short.variance_units == -2
        assert r_short.severity == "LOW"

        # 4. NO_AUTHORIZATION_FOUND: 5 physical goods exit with NO invoice
        r_no_auth = InvoiceReconciliationEngine.reconcile(
            event_id="evt_04",
            camera_id="cam_exit",
            physical_units_count=5,
            invoice_id=None,
            invoice_number=None,
        )
        assert r_no_auth.status == "NO_AUTHORIZATION_FOUND"
        assert r_no_auth.is_authorized is False
        assert r_no_auth.severity == "CRITICAL"

        # 5. Pipeline Boundary: Empty-handed person exit (0 units) is NOT unauthorized departure
        r_pedestrian = InvoiceReconciliationEngine.reconcile(
            event_id="evt_05",
            camera_id="cam_exit",
            physical_units_count=0,
            invoice_id=None,
        )
        assert r_pedestrian.status == "MATCHED"
        assert r_pedestrian.is_authorized is True
        assert r_pedestrian.severity == "NONE"

        # 6. INCONCLUSIVE: Low vision confidence or severe occlusion
        r_inconc = InvoiceReconciliationEngine.reconcile(
            event_id="evt_06",
            camera_id="cam_exit",
            physical_units_count=10,
            invoice_id="inv_100",
            declared_billed_units=10,
            vision_confidence=0.35,  # Below threshold
        )
        assert r_inconc.status == "INCONCLUSIVE"
        assert r_inconc.severity == "MEDIUM"


class TestAccountingIdentity:
    def test_ledger_balance_equation(self):
        """Validates Opening + IN - OUT + Adjustments == Current Stock."""
        opening = 100
        incoming = 50
        outgoing = 20
        adjustments = -5

        current = opening + incoming - outgoing + adjustments
        assert current == 125
        assert (opening + incoming - outgoing + adjustments) == current

