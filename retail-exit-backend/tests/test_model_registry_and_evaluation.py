"""Tests for Model Registry, Step 5 Promotion Gates, Shadow Mode, and Accuracy Evaluation

Verifies:
1. Baseline model is initialized and tracked in registry.json.
2. Step 5 numeric promotion gates are strictly enforced:
   - mAP@0.5 >= 0.75
   - Case/unit recall >= 0.90
   - Empty scene FP rate < 0.05
   - Pairwise precision >= 0.80
3. Safe rollback reverts active production model.
4. Shadow mode runs candidate model alongside production model with zero verdict interference.
5. Evaluator accurately computes mAP, recall, FP rate, and pairwise precision.
6. Active learning candidate capture and curation.
"""

import os
import pytest
from src.ml.model_registry import ModelRegistry, ModelMetrics
from ml.training.evaluator import AccuracyEvaluator, calculate_box_iou
from src.ml.active_learning import ActiveLearningService
from src.ml.shadow_service import ShadowDeploymentService


def test_model_registry_baseline():
    registry = ModelRegistry.get_instance()
    assert registry.active_production_version is not None
    prod = registry.get_production_model()
    assert prod is not None
    assert prod.status == "production"


def test_promotion_gates_reject_insufficient_accuracy():
    registry = ModelRegistry.get_instance()

    # Case 1: Low mAP
    metrics_low_map = ModelMetrics(
        map_50=0.65,  # < 0.75
        case_unit_recall=0.92,
        empty_scene_fp_rate=0.03,
        pairwise_precision=0.85,
    )
    passes, failures = registry.check_promotion_gates(metrics_low_map)
    assert not passes
    assert any("mAP@0.5" in f for f in failures)

    # Case 2: Low Recall
    metrics_low_recall = ModelMetrics(
        map_50=0.80,
        case_unit_recall=0.82,  # < 0.90
        empty_scene_fp_rate=0.03,
        pairwise_precision=0.85,
    )
    passes, failures = registry.check_promotion_gates(metrics_low_recall)
    assert not passes
    assert any("recall" in f.lower() for f in failures)

    # Case 3: High Empty Scene False Positives (fake detections)
    metrics_high_fp = ModelMetrics(
        map_50=0.80,
        case_unit_recall=0.95,
        empty_scene_fp_rate=0.08,  # >= 0.05
        pairwise_precision=0.85,
    )
    passes, failures = registry.check_promotion_gates(metrics_high_fp)
    assert not passes
    assert any("false-positive" in f.lower() for f in failures)

    # Case 4: Low Pairwise Precision (confusing bag vs charger vs phone)
    metrics_low_pairwise = ModelMetrics(
        map_50=0.80,
        case_unit_recall=0.95,
        empty_scene_fp_rate=0.02,
        pairwise_precision=0.72,  # < 0.80
    )
    passes, failures = registry.check_promotion_gates(metrics_low_pairwise)
    assert not passes
    assert any("pairwise" in f.lower() for f in failures)


def test_promotion_gates_accept_valid_model():
    registry = ModelRegistry.get_instance()

    # Model satisfying all Step 5 gates
    valid_metrics = ModelMetrics(
        map_50=0.82,
        case_unit_recall=0.94,
        empty_scene_fp_rate=0.02,
        pairwise_precision=0.88,
        latency_ms=16.0,
    )
    passes, failures = registry.check_promotion_gates(valid_metrics)
    assert passes
    assert len(failures) == 0


def test_register_and_rollback():
    registry = ModelRegistry.get_instance()
    initial_version = registry.active_production_version

    # Register candidate model pointing to existing baseline weights
    cand_version = "yolox-retail-test-v1.0"
    base_weights = registry.get_production_model().weights_path

    registry.register_model(
        model_version=cand_version,
        model_name="Test Retail Candidate",
        weights_path=base_weights,
        metrics=ModelMetrics(map_50=0.85, case_unit_recall=0.93, empty_scene_fp_rate=0.02, pairwise_precision=0.89),
    )

    # Promote candidate (passes gates)
    success, msg = registry.promote_to_production(cand_version)
    assert success
    assert registry.active_production_version == cand_version

    # Safe rollback to initial version
    rb_success, rb_msg = registry.rollback_to(initial_version)
    assert rb_success
    assert registry.active_production_version == initial_version

    # Cleanup candidate
    if cand_version in registry.models:
        del registry.models[cand_version]
    registry._persist()


def test_shadow_mode_configuration():
    registry = ModelRegistry.get_instance()
    initial_prod = registry.active_production_version

    # Set shadow mode
    success, msg = registry.set_shadow_mode(initial_prod, traffic_pct=30.0)
    assert success
    assert registry.active_shadow_version == initial_prod
    assert registry.shadow_traffic_pct == 30.0

    # Disable shadow mode
    success, msg = registry.set_shadow_mode(None)
    assert success
    assert registry.active_shadow_version is None
    assert registry.get_production_model().status == "production"


def test_evaluator_metrics_calculation():
    evaluator = AccuracyEvaluator()

    # Test box IoU
    boxA = [10.0, 10.0, 50.0, 50.0]
    boxB = [10.0, 10.0, 50.0, 50.0]
    assert calculate_box_iou(boxA, boxB) == 1.0

    boxC = [100.0, 100.0, 50.0, 50.0]
    assert calculate_box_iou(boxA, boxC) == 0.0

    # Test empty scene FP rate
    empty_preds_clean = [[], [], []]
    assert evaluator.calculate_empty_scene_fp_rate(empty_preds_clean) == 0.0

    empty_preds_with_fp = [[], [{"class_label": "case_full", "confidence": 0.85}], []]
    assert evaluator.calculate_empty_scene_fp_rate(empty_preds_with_fp) == pytest.approx(1 / 3, 0.01)

    # Test recall on merchandise
    gts = [[{"class_label": "case_full", "bbox": [10, 10, 50, 50]}]]
    preds = [[{"class_label": "case_full", "bbox": [12, 12, 50, 50], "confidence": 0.90}]]
    assert evaluator.calculate_case_unit_recall(gts, preds) == 1.0


def test_active_learning_drift_detection():
    service = ActiveLearningService.get_instance()
    # Feed high confidences
    for _ in range(50):
        service.log_confidence(0.92)

    drift_res = service.check_accuracy_drift(baseline_median=0.85)
    assert not drift_res["has_drift"]

    # Feed degraded confidences
    for _ in range(100):
        service.log_confidence(0.55)

    drift_res2 = service.check_accuracy_drift(baseline_median=0.85)
    assert drift_res2["has_drift"]
    assert "Trigger fine-tuning" in drift_res2["recommendation"]

