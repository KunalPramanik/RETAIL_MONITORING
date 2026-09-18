"""Tests for Industrial PPE & Worker Safety Compliance Detector."""

import cv2
import numpy as np
import pytest
from src.ml.ppe_service import PPEComplianceDetector, PPEAssessment


def test_worker_with_yellow_helmet_and_lime_vest():
    """Verifies that a worker with yellow helmet and lime vest is evaluated as compliant."""
    img = np.full((600, 400, 3), (150, 150, 150), dtype=np.uint8)
    person_bbox = [100, 50, 200, 500]

    # Draw Yellow Hard Hat in head region (top 20% -> y in [50, 150])
    # Yellow in BGR: (0, 220, 240)
    cv2.ellipse(img, (200, 95), (60, 40), 0, 180, 360, (0, 220, 240), -1)

    # Draw Fluorescent Lime-Green Safety Vest in torso region (y in [150, 375])
    # Fluorescent Lime in BGR: (30, 240, 200) -> in HSV H is ~45
    cv2.rectangle(img, (130, 160), (270, 360), (30, 240, 200), -1)
    # Add retroreflective silver stripe (high val, low sat)
    cv2.rectangle(img, (130, 240), (270, 260), (240, 240, 240), -1)

    assessment = PPEComplianceDetector.evaluate_worker_ppe(img, person_bbox)
    assert assessment.has_helmet is True
    assert assessment.helmet_confidence >= 0.65
    assert assessment.helmet_color in ("Yellow", "White")
    assert assessment.has_vest is True
    assert assessment.vest_confidence >= 0.65
    assert assessment.is_compliant is True
    assert len(assessment.violations) == 0
    assert "PPE COMPLIANT" in assessment.summary_label


def test_worker_missing_ppe_gear():
    """Verifies that a worker in plain dark civilian clothes triggers PPE violations."""
    img = np.full((600, 400, 3), (150, 150, 150), dtype=np.uint8)
    person_bbox = [100, 50, 200, 500]

    # Dark hair / no helmet
    cv2.circle(img, (200, 95), 45, (25, 25, 30), -1)
    # Dark blue civilian shirt / no high-vis vest
    cv2.rectangle(img, (130, 160), (270, 360), (90, 40, 30), -1)

    assessment = PPEComplianceDetector.evaluate_worker_ppe(img, person_bbox)
    assert assessment.has_helmet is False
    assert assessment.has_vest is False
    assert assessment.is_compliant is False
    assert "MISSING_HELMET" in assessment.violations
    assert "MISSING_VEST" in assessment.violations
    assert "PPE VIOLATION" in assessment.summary_label
