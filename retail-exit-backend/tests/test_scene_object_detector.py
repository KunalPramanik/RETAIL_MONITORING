"""Automated Test Suite for Dynamic Scene Object Detection (Doorways, Bags, Umbrellas)"""

import pytest
import numpy as np
import cv2
import os
from src.ml.scene_object_detector import SceneObjectDetector
from src.ml.vision_service import VisionInferenceService


@pytest.fixture
def sample_indoor_scene():
    """Generates a synthetic high-resolution indoor scene with a doorway, folded umbrella, and hanging tote bag."""
    # 720x1280 3-channel image with wall background
    img = np.full((720, 1280, 3), (190, 200, 210), dtype=np.uint8)

    # 1. Doorway frame on the left: x=100..450, y=100..720
    # Top lintel (dark wood)
    cv2.rectangle(img, (90, 95), (460, 120), (30, 45, 80), -1)
    # Left jamb
    cv2.rectangle(img, (90, 95), (120, 720), (30, 45, 80), -1)
    # Right jamb
    cv2.rectangle(img, (430, 95), (460, 720), (30, 45, 80), -1)
    # Door panel
    cv2.rectangle(img, (120, 120), (430, 720), (40, 60, 110), -1)

    # 2. Folded umbrella hanging on hook: x=580..610, y=180..420 (aspect ratio ~ 8.0)
    cv2.rectangle(img, (585, 180), (605, 420), (90, 40, 30), -1)
    # Curved handle
    cv2.circle(img, (595, 175), 10, (90, 40, 30), 3)

    # 3. Hanging Tote Bag: x=750..920, y=220..440
    # Bag body
    cv2.rectangle(img, (750, 260), (920, 440), (20, 80, 180), -1)
    # Bag handles
    cv2.ellipse(img, (835, 260), (40, 35), 0, 180, 360, (20, 80, 180), 4)

    return img


def test_detect_doorways(sample_indoor_scene):
    """Verifies that dynamic architectural doorway detection detects the door portal."""
    doors = SceneObjectDetector.detect_doorways(sample_indoor_scene)
    assert len(doors) >= 1
    d = doors[0]
    assert d["class_label"] == "doorway"
    assert d["confidence"] >= 0.70
    bx, by, bw, bh = d["bbox"]
    assert 80 <= bx <= 120
    assert 90 <= by <= 130
    assert 300 <= bw <= 400


def test_detect_hanging_gear_and_bags(sample_indoor_scene):
    """Verifies that hanging umbrellas and tote bags are detected by contour aspect ratio."""
    door_box = [[90, 95, 370, 625]]
    gear = SceneObjectDetector.detect_hanging_gear_and_bags(sample_indoor_scene, exclude_boxes=door_box)
    assert len(gear) >= 2

    labels = [g["specific_label"] for g in gear]
    assert any("Umbrella" in lbl for lbl in labels)
    assert any("Bag" in lbl for lbl in labels)


def test_vision_service_integration_with_scene_objects(sample_indoor_scene):
    """Verifies that VisionInferenceService.analyze_frame_bytes integrates scene objects."""
    _, enc = cv2.imencode(".jpg", sample_indoor_scene)
    res, _ = VisionInferenceService.analyze_frame_bytes(enc.tobytes())
    assert len(res.detections) >= 2

    detected_labels = [d.specific_label or "" for d in res.detections]
    assert any("Doorway" in lbl for lbl in detected_labels)


def test_detect_desktop_screen_and_doorway_rejection():
    """Verifies that an elevated rectangular desktop monitor is detected as a screen and NOT as a doorway."""
    # 480x640 scene with a desk and monitor
    scene = np.full((480, 640, 3), (200, 200, 200), dtype=np.uint8)
    # Desk surface: y=340..480
    cv2.rectangle(scene, (0, 340), (640, 480), (120, 90, 60), -1)
    # Desktop monitor bezel: x=180..460, y=140..340
    cv2.rectangle(scene, (180, 140), (460, 340), (20, 20, 20), -1)
    # Monitor screen interior (darker)
    cv2.rectangle(scene, (190, 150), (450, 330), (35, 35, 35), -1)

    # 1. Doorway detector MUST reject this desk monitor
    doors = SceneObjectDetector.detect_doorways(scene)
    assert len(doors) == 0, f"False doorway detected on desktop monitor: {doors}"

    # 2. Desktop screen detector MUST detect the monitor
    screens = SceneObjectDetector.detect_desktop_monitors_and_screens(scene)
    assert len(screens) >= 1
    assert screens[0]["specific_label"] == "Desktop Screen"
    assert screens[0]["confidence"] >= 0.70


def test_detect_wrist_watches():
    """Verifies that a circular dial near a wrist keypoint is detected as a Wrist Watch."""
    img = np.full((400, 400, 3), (180, 180, 180), dtype=np.uint8)
    # Draw arm segment
    cv2.line(img, (150, 100), (150, 300), (140, 150, 160), 24)
    # Draw watch dial at wrist: center (150, 200), radius 14
    cv2.circle(img, (150, 200), 14, (30, 30, 30), 2)
    # Inner clock face details to trigger edge density
    cv2.circle(img, (150, 200), 10, (50, 50, 50), 1)
    cv2.line(img, (150, 200), (150, 193), (10, 10, 10), 2)
    cv2.line(img, (150, 200), (157, 200), (10, 10, 10), 2)

    wrist_kp = {"right_wrist": (150, 200)}
    watches = SceneObjectDetector.detect_wrist_watches(img, wrist_keypoints=wrist_kp)
    assert len(watches) == 1
    assert watches[0]["specific_label"] == "Wrist Watch"
    assert watches[0]["confidence"] >= 0.60


