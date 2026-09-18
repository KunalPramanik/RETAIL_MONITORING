"""Tests for Flame & Fire Hazard Detector Service."""

import cv2
import numpy as np
import pytest
from src.ml.hazard_service import FlameHazardDetector, FlameDetection


def test_flame_detection_on_synthetic_fire():
    """Verifies that high-temperature flame chromatic shapes trigger flame detection."""
    # Create an image with dark background and a bright yellow-red flickering flame shape
    img = np.zeros((400, 400, 3), dtype=np.uint8)
    # Background room floor
    img[250:, :] = (40, 40, 40)

    # Draw simulated flame polygon (yellow core with orange/red fringe)
    # Flame tip at (200, 80), base at (170, 220) to (230, 220)
    pts_outer = np.array([[200, 80], [225, 130], [240, 180], [220, 220], [180, 220], [160, 180], [175, 130]], dtype=np.int32)
    # BGR for fire: High Red, Med/High Green, Low Blue -> (20, 100, 255)
    cv2.fillPoly(img, [pts_outer], (15, 110, 255))

    # Inner bright yellow/white flame core
    pts_inner = np.array([[200, 110], [215, 150], [210, 210], [190, 210], [185, 150]], dtype=np.int32)
    cv2.fillPoly(img, [pts_inner], (80, 230, 255))

    detections = FlameHazardDetector.detect_flames(img, confidence_floor=0.40)
    assert len(detections) >= 1
    d0 = detections[0]
    assert d0.label == "Fire"
    assert d0.confidence >= 0.40
    assert d0.area_pixels >= 80
    assert d0.bbox[2] > 0 and d0.bbox[3] > 0


def test_flame_detector_rejects_neutral_scene():
    """Verifies that non-flame neutral images (office/store) produce zero flame detections."""
    neutral_img = np.full((400, 400, 3), (180, 175, 170), dtype=np.uint8)
    # Add some furniture/box
    cv2.rectangle(neutral_img, (50, 50), (200, 200), (80, 100, 120), -1)

    detections = FlameHazardDetector.detect_flames(neutral_img, confidence_floor=0.45)
    assert len(detections) == 0


def test_empty_or_none_image():
    """Verifies graceful handling of empty or None frame input."""
    assert FlameHazardDetector.detect_flames(None) == []
    assert FlameHazardDetector.detect_flames(np.array([], dtype=np.uint8)) == []
