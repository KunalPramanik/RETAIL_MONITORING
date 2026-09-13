"""Tests for Active Infrared / Night Vision Illumination Filter and Biometric Handling"""

import pytest
import numpy as np
import cv2

from src.ml.vision_service import VisionInferenceService
from src.ml.face_service import FaceRecognitionService


def test_ir_mode_detection_monochrome_and_color():
    """Verify that monochrome / low-saturation frames are recognized as IR, and color frames are not."""
    # 1. Grayscale 2D frame -> must be IR
    gray_frame = np.full((480, 640), 120, dtype=np.uint8)
    assert VisionInferenceService.is_infrared_frame(gray_frame) is True

    # 2. 3-channel monochrome frame (R=G=B, saturation=0) -> must be IR
    mono_3ch = np.zeros((480, 640, 3), dtype=np.uint8)
    mono_3ch[:, :] = [110, 110, 110]
    assert VisionInferenceService.is_infrared_frame(mono_3ch) is True

    # 3. Low-saturation IR frame with slight sensor noise (saturation < 10)
    noisy_ir = np.zeros((480, 640, 3), dtype=np.uint8)
    noisy_ir[:, :, 0] = 120  # B
    noisy_ir[:, :, 1] = 122  # G
    noisy_ir[:, :, 2] = 119  # R
    assert VisionInferenceService.is_infrared_frame(noisy_ir) is True

    # 4. Colorful daylight retail frame (vivid colors, high saturation)
    color_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    color_frame[:, :, 0] = 20   # Blue
    color_frame[:, :, 1] = 180  # Green
    color_frame[:, :, 2] = 230  # Red
    assert VisionInferenceService.is_infrared_frame(color_frame) is False


def test_ir_clahe_preprocessing_adaptation():
    """Verify that IR frames undergo adapted CLAHE contrast enhancement and flag is_ir=True."""
    # Low-contrast monochrome IR frame
    low_contrast_ir = np.full((480, 640, 3), 90, dtype=np.uint8)
    # Add a mock box with faint edge
    cv2.rectangle(low_contrast_ir, (100, 100), (300, 300), (105, 105, 105), -1)

    padded, ratio, is_ir = VisionInferenceService._preprocess_frame(low_contrast_ir)
    assert is_ir is True
    assert padded.shape == (3, 416, 416)

    # Standard daylight frame
    daylight = np.zeros((480, 640, 3), dtype=np.uint8)
    daylight[:, :, 0] = 50
    daylight[:, :, 1] = 120
    daylight[:, :, 2] = 200
    _, _, is_ir_day = VisionInferenceService._preprocess_frame(daylight)
    assert is_ir_day is False


def test_ir_face_recognition_low_confidence_honest_reporting():
    """Under IR night vision, degraded embeddings must report LOW_CONFIDENCE_IR without false alarms."""
    enrolled_roster = [
        {
            "employee_id": "EMP-001",
            "name": "Sarah Connor",
            "face_embedding": [0.05] * 512,
        }
    ]

    # Degraded/mismatched probe embedding in low-light
    degraded_probe = [0.01 if i % 2 == 0 else -0.01 for i in range(512)]

    # 1. Daylight mode -> Should report NO_MATCH and demand unauthorized alert
    res_daylight = FaceRecognitionService.match_carrier(
        probe_embedding=degraded_probe,
        enrolled_employees=enrolled_roster,
        is_ir_mode=False,
    )
    assert res_daylight.decision == "NO_MATCH"
    assert res_daylight.unauthorized_alert_needed is True

    # 2. IR Night Vision mode -> Must honestly report LOW_CONFIDENCE_IR and SUPPRESS false alert!
    res_ir = FaceRecognitionService.match_carrier(
        probe_embedding=degraded_probe,
        enrolled_employees=enrolled_roster,
        is_ir_mode=True,
    )
    assert res_ir.decision == "LOW_CONFIDENCE_IR"
    assert res_ir.unauthorized_alert_needed is False, "IR mode must not fire false intrusion alarms on low confidence!"

    # 3. Enrolled match in IR mode -> Should still MATCH when similarity is above threshold
    matching_probe = [0.05] * 512
    res_ir_match = FaceRecognitionService.match_carrier(
        probe_embedding=matching_probe,
        enrolled_employees=enrolled_roster,
        is_ir_mode=True,
    )
    assert res_ir_match.decision == "MATCHED"
    assert res_ir_match.matched_employee_id == "EMP-001"

