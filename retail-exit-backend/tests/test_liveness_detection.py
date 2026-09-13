"""Unit & Integration Tests for Anti-Spoofing & Liveness Detection Pipeline"""

import os
import cv2
import numpy as np
import pytest
from src.ml.liveness_service import LivenessDetectionService, LivenessResult, TemporalFaceTrack
from src.ml.face_service import FaceRecognitionService


def test_ear_calculation():
    """Validates Eye Aspect Ratio (EAR) formula for open vs closed eyes."""
    # Open eye: horizontal distance 30px, vertical distance 10px
    open_eye = np.array([
        [10.0, 20.0],  # p1: outer
        [20.0, 15.0],  # p2: top1
        [30.0, 15.0],  # p3: top2
        [40.0, 20.0],  # p4: inner
        [30.0, 25.0],  # p5: bottom2
        [20.0, 25.0],  # p6: bottom1
    ], dtype=np.float32)

    ear_open = LivenessDetectionService.calculate_ear(open_eye)
    assert ear_open > 0.25, f"Open eye EAR should be > 0.25, got {ear_open}"

    # Closed eye: vertical distance collapses to ~1px
    closed_eye = open_eye.copy()
    closed_eye[1:3, 1] = 20.0
    closed_eye[4:6, 1] = 20.5

    ear_closed = LivenessDetectionService.calculate_ear(closed_eye)
    assert ear_closed < 0.15, f"Closed eye EAR should be < 0.15, got {ear_closed}"


def test_temporal_face_track_motion_and_blink():
    """Validates temporal micro-displacement and eye-blink state machine."""
    track = TemporalFaceTrack(track_id=1, initial_bbox=[100, 100, 80, 80])

    # 1. Static picture simulation (identical landmarks, zero displacement)
    base_lm = np.zeros((68, 2), dtype=np.float32)
    now = 1000.0
    for i in range(5):
        # Only camera sensor jitter (< 0.2px)
        jitter = np.random.normal(0, 0.1, (68, 2)).astype(np.float32)
        track.update([100, 100, 80, 80], base_lm + jitter, ear=0.32, ts=now + i * 0.1)

    motion_score, avg_disp = track.compute_motion_score()
    assert avg_disp < 0.6, f"Static photo displacement should be < 0.6px, got {avg_disp}"
    assert motion_score <= 0.2, f"Static photo motion score should be <= 0.2, got {motion_score}"

    # 2. Living human simulation (physiologic drift >= 1.5px and blink cycle)
    track_live = TemporalFaceTrack(track_id=2, initial_bbox=[100, 100, 80, 80])
    for i in range(5):
        drift = np.random.normal(0, 1.8, (68, 2)).astype(np.float32)
        # Simulate blink on frame 3
        ear_val = 0.12 if i == 2 else 0.32
        track_live.update([100 + i, 100 + i, 80, 80], base_lm + drift, ear=ear_val, ts=now + i * 0.1)

    live_motion_score, live_disp = track_live.compute_motion_score()
    assert live_disp >= 1.0, f"Live human displacement should be >= 1.0px, got {live_disp}"
    assert track_live.blink_count >= 1, "Blink state machine should detect blink cycle"
    assert live_motion_score > 0.6, f"Live human motion score should be > 0.6, got {live_motion_score}"


def test_static_wall_pictures_rejected():
    """Validates that static wall portraits in test footage are rejected by liveness evaluation."""
    app = FaceRecognitionService.get_app()
    wall_img_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "snapshots",
        "preview_cam_105.jpg",
    )
    if not os.path.exists(wall_img_path):
        pytest.skip(f"Test image {wall_img_path} not found")

    with open(wall_img_path, "rb") as f:
        img_bytes = f.read()

    res, annotated, live_boxes = FaceRecognitionService.detect_and_match_faces(
        frame_bytes=img_bytes,
        enrolled_employees=[],
        raw_frame_bytes=img_bytes,
        filter_static=True,
    )

    # In filter_static mode, all static wall pictures/portraits are rejected
    assert res.liveness_decision in ("STATIC_PHOTO", "NO_FACE")
    assert len(live_boxes) == 0, f"Expected 0 live boxes on static wall pictures, got {len(live_boxes)}"


def test_synthetic_living_face_evaluation():
    """Validates that a face with deep 3D relief (z_std >= 20mm) and human skin is classified as LIVE."""
    # Create mock face object with 3D landmarks
    class MockFace:
        def __init__(self):
            self.bbox = np.array([100, 100, 220, 240], dtype=np.float32)
            self.det_score = 0.88
            # 68 3D landmarks with nose protruding (Z span ~150mm, std ~35mm)
            lm = np.zeros((68, 3), dtype=np.float32)
            lm[:, 0] = np.linspace(110, 210, 68)
            lm[:, 1] = np.linspace(110, 230, 68)
            # Nose bridge/tip (landmarks 27-35) has high Z relief
            lm[:27, 2] = np.random.uniform(10, 20, 27)
            lm[27:36, 2] = np.random.uniform(90, 150, 9)
            lm[36:, 2] = np.random.uniform(10, 30, 32)
            self.landmark_3d_68 = lm

    # Create dummy skin patch
    test_img = np.zeros((300, 300, 3), dtype=np.uint8)
    # Human skin tone (BGR: ~140, 170, 220)
    test_img[100:240, 100:220] = [140, 170, 220]

    mock_face = MockFace()
    result = LivenessDetectionService.evaluate_face(test_img, mock_face)

    assert result.is_live is True, f"Mock 3D human face should be LIVE, got reason: {result.reason}"
    assert result.liveness_score >= 0.50
    assert result.z_std >= 15.0

