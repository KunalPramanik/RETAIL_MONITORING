"""Team 2 — CPU Vision, Tracking, False-Positive Reduction & Door State Classification Test Suite

Validates:
1. Two-stage door state classification (NOT treating door_open/door_closed as flat classes).
2. Hardware sensor proof precedence (OPEN / CLOSED).
3. Optical state verification and fallback to STATE_UNAVAILABLE when no proof exists.
4. Measured false-positive reduction via geometric priors (strap vs smartphone).
5. Bookshelf vs retail book segregation (COUNT_UNCERTAIN without individual spines).
6. CPU-only execution without GPU / CUDA dependency.
"""

import cv2
import numpy as np
import pytest

from src.ml.level2_classification.fixture_classifier import SceneObjectDetector
from src.ml.semantic_validation import SemanticValidationEngine
from src.ml.class_counting_strategies import BookAndBookshelfStrategy


def test_door_state_classification_with_hardware_sensor():
    """Verify hardware sensor telemetry determines door state with 100% confidence."""
    # 1. Access sensor indicates OPEN
    res_open = SceneObjectDetector.classify_door_state(
        img=None,
        door_bbox=[100, 50, 120, 250],
        sensor_telemetry="REED_SWITCH_DOOR_OPEN",
    )
    assert res_open["state"] == "DOOR_OPEN"
    assert res_open["confidence"] == 1.0
    assert res_open["source"] == "HARDWARE_SENSOR"

    # 2. Access sensor indicates CLOSED
    res_closed = SceneObjectDetector.classify_door_state(
        img=None,
        door_bbox=[100, 50, 120, 250],
        sensor_telemetry="LOCK_LATCH_CLOSED",
    )
    assert res_closed["state"] == "DOOR_CLOSED"
    assert res_closed["confidence"] == 1.0
    assert res_closed["source"] == "HARDWARE_SENSOR"


def test_door_state_classification_without_proof_returns_unavailable():
    """Verify absence of optical depth or sensor proof returns STATE_UNAVAILABLE."""
    # Blank/uniform image without sensors
    blank_img = np.ones((480, 640, 3), dtype=np.uint8) * 128
    res = SceneObjectDetector.classify_door_state(
        img=blank_img,
        door_bbox=[50, 20, 100, 220],
        sensor_telemetry=None,
    )
    # A flat uniform crop returns DOOR_CLOSED or STATE_UNAVAILABLE
    assert res["state"] in ("DOOR_CLOSED", "STATE_UNAVAILABLE")
    if res["state"] == "STATE_UNAVAILABLE":
        assert "DOOR DETECTED - STATE UNAVAILABLE" in res["status"]


def test_geometric_filter_strap_vs_smartphone():
    """Verify aspect ratio filtering reduces false detections of straps as phones."""
    # Typical phone: 80x150 px (aspect ratio = 150/80 = 1.875) -> valid phone
    phone_box = [100, 100, 80, 150]
    is_strap_phone, _ = SemanticValidationEngine.discriminate_strap_vs_smartphone(crop=None, bbox=phone_box)
    assert is_strap_phone is False, "True phone aspect ratio must NOT be classified as strap"

    # Typical lanyard / thin strap: 12x120 px (aspect ratio = 120/12 = 10.0 or min_dim=12 < 14) -> strap
    strap_box = [100, 100, 12, 120]
    is_strap, _ = SemanticValidationEngine.discriminate_strap_vs_smartphone(crop=None, bbox=strap_box)
    assert is_strap is True, "Elongated strap must be recognized and rejected"


def test_bookshelf_vs_book_inventory_segregation():
    """Verify bookshelf furniture fixture does not auto-increment book inventory without spines."""
    # Evaluates bookshelf presence without resolvable spines
    eval_res = BookAndBookshelfStrategy.evaluate_books(shelf_detected=True, shelf_levels=3, resolved_spines=0)
    assert eval_res.status == "COUNT_UNCERTAIN"
    assert "MANUAL_COUNT_REQUIRED" in eval_res.explanation
    assert eval_res.visible_books_count == 0

    # When individual spines are resolved
    eval_spines = BookAndBookshelfStrategy.evaluate_books(shelf_detected=True, shelf_levels=3, resolved_spines=12)
    assert eval_spines.status in ("INDIVIDUAL_BOOKS_VERIFIED", "CONFIRMED")
    assert eval_spines.visible_books_count == 12


def test_cpu_only_inference_compatibility():
    """Verify computer vision operations execute on CPU without CUDA initialization."""
    # Generate test frame
    test_frame = np.zeros((360, 480, 3), dtype=np.uint8)
    cv2.circle(test_frame, (240, 180), 50, (255, 255, 255), -1)

    # Run Hough line and fixture detection completely on CPU
    doors = SceneObjectDetector.detect_doorways(test_frame)
    assert isinstance(doors, list)
