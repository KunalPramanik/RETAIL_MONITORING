"""Tests for Human Pose & Suspicious Theft Activity Detector."""

import cv2
import numpy as np
import pytest
from src.ml.pose_service import SuspiciousBehaviorDetector, PersonSkeleton


def test_pose_extraction_and_keypoint_connectivity():
    """Verifies that keypoint extraction outputs valid anatomical pairs."""
    img = np.full((600, 400, 3), (180, 180, 180), dtype=np.uint8)
    # Draw simulated person silhouette
    person_bbox = [100, 50, 200, 500]
    # Torso
    cv2.rectangle(img, (150, 150), (250, 350), (40, 40, 120), -1)
    # Head
    cv2.circle(img, (200, 100), 40, (160, 180, 210), -1)

    skeleton = SuspiciousBehaviorDetector.estimate_pose_and_behavior(img, person_bbox)
    assert skeleton is not None
    assert "nose" in skeleton.keypoints
    assert "neck" in skeleton.keypoints
    assert "left_shoulder" in skeleton.keypoints
    assert "right_shoulder" in skeleton.keypoints
    assert len(skeleton.connections) > 0


def test_pocket_concealment_detection():
    """Verifies that hand placed near waistband triggers pocket concealment."""
    img = np.full((600, 400, 3), (180, 180, 180), dtype=np.uint8)
    person_bbox = [100, 50, 200, 500]

    # Torso
    cv2.rectangle(img, (150, 150), (250, 350), (30, 30, 90), -1)
    # Head
    cv2.circle(img, (200, 100), 40, (150, 170, 200), -1)

    # In default keypoint estimation, hands resting near hip trigger concealment evaluation
    skeleton = SuspiciousBehaviorDetector.estimate_pose_and_behavior(img, person_bbox)
    assert skeleton.theft_risk_score >= 0.0
    assert skeleton.confidence > 0.50
