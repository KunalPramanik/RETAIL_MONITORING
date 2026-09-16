"""Tests for Vehicle Entry Intelligence (Car/Bike detection, color recognition, and license plate OCR)"""

import pytest
import numpy as np
import cv2
from src.ml.vehicle_service import VehicleIntelligenceService, vehicle_service
from src.ml.model_config import get_vision_config
from src.ml.vision_service import VisionInferenceService


def test_vehicle_color_detection_white():
    """Test that bright, low-saturation vehicle body is recognized as White."""
    # Create white car crop (H=100, W=100, BGR=(240, 240, 240))
    white_car = np.full((100, 100, 3), 240, dtype=np.uint8)
    color = vehicle_service.detect_vehicle_color(white_car)
    assert color == "White"


def test_vehicle_color_detection_black():
    """Test that dark vehicle body is recognized as Black."""
    black_car = np.full((100, 100, 3), 25, dtype=np.uint8)
    color = vehicle_service.detect_vehicle_color(black_car)
    assert color == "Black"


def test_vehicle_color_detection_blue():
    """Test that saturated blue vehicle body is recognized as Blue."""
    # BGR for strong blue: B=220, G=50, R=30
    blue_car = np.zeros((100, 100, 3), dtype=np.uint8)
    blue_car[:, :] = (220, 50, 30)
    color = vehicle_service.detect_vehicle_color(blue_car)
    assert color == "Blue"


def test_vehicle_color_detection_red():
    """Test that saturated red vehicle body is recognized as Red."""
    # BGR for strong red: B=20, G=20, R=220
    red_car = np.zeros((100, 100, 3), dtype=np.uint8)
    red_car[:, :] = (20, 20, 220)
    color = vehicle_service.detect_vehicle_color(red_car)
    assert color == "Red"


def test_vehicle_color_detection_green():
    """Test that saturated green vehicle body is recognized as Green."""
    # BGR for green: B=30, G=200, R=40
    green_car = np.zeros((100, 100, 3), dtype=np.uint8)
    green_car[:, :] = (30, 200, 40)
    color = vehicle_service.detect_vehicle_color(green_car)
    assert color == "Green"


def test_vehicle_analyze_integration():
    """Test complete vehicle analysis (type, color, license plate, and badge generation)."""
    # Create synthetic full frame with a blue car at [50, 50, 200, 150]
    frame = np.full((400, 600, 3), 180, dtype=np.uint8)
    # Blue car region
    frame[50:200, 50:250] = (220, 50, 30)

    # Draw synthetic white license plate with black text
    cv2.rectangle(frame, (100, 160), (200, 190), (255, 255, 255), -1)
    cv2.putText(frame, "MH12AB1234", (105, 182), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)

    result = vehicle_service.analyze_vehicle(frame, [50, 50, 200, 150], "Car")
    assert result["vehicle_type"] == "Car"
    assert result["color"] == "Blue"
    assert "CAR (BLUE)" in result["badge_text"]
    assert "PLATE:" in result["badge_text"]


def test_vehicle_classes_in_config():
    """Verify that COCO vehicle classes are registered in VisionModelConfig."""
    cfg = get_vision_config()
    assert 2 in cfg.vehicle_classes  # Car
    assert 3 in cfg.vehicle_classes  # Motorcycle / Bike
    assert cfg.class_labels[2] == "Car"
    assert cfg.class_labels[3] == "Motorcycle / Bike"
    assert hasattr(cfg, "vehicle_conf_threshold")


def test_vision_inference_empty_or_zero_state():
    """Verify VisionInferenceService handles blank frames gracefully without errors."""
    blank_frame = np.full((416, 416, 3), 128, dtype=np.uint8)
    success, encoded = cv2.imencode(".jpg", blank_frame)
    assert success

    res, ann_bytes = VisionInferenceService.analyze_frame_bytes(encoded.tobytes())
    assert res is not None
    assert len(ann_bytes) > 0
    assert res.vision_count >= 0
