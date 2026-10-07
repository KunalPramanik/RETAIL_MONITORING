"""Phase 5 CV / ML Pipeline Correctness & Anti-Hallucination Test Suite

Covers:
- Zero fabrication on blank, black, or corrupted frames
- Strict typed zero-state returns (vision_confidence=0.0, detections=[])
- ByteTrack track lifecycle and lost-track pruning
- Face recognition rejection of blank/faceless frames without matching roster
- Invoice OCR unreadable image handling without text hallucination
- Multi-sensor fusion degraded confidence bounding upon visual occlusion
- Dynamic configuration binding across CV/ML inference settings
"""

import cv2
import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from src.core.config import settings
from src.ml.level1_detection.vision_service import VisionInferenceService, DetectedBox
from src.ml.level5_tracking.tracker import SimpleByteTrack
from src.ml.face_recognition.face_service import FaceRecognitionService
from src.ml.ocr.invoice_ocr_service import OcrService
from src.engine.fusion import MultiSensorFusionEngine


def _create_blank_jpeg_bytes(width: int = 640, height: int = 480) -> bytes:
    """Generates an authentic all-black BGR image encoded as JPEG."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    success, encoded = cv2.imencode(".jpg", img)
    assert success
    return encoded.tobytes()


def test_vision_service_blank_frame_zero_detections():
    """F5 / Phase 5: Verifies that a blank black frame yields 0 detections and 0.0 confidence."""
    frame_bytes = _create_blank_jpeg_bytes(640, 480)
    result, annotated_bytes = VisionInferenceService.analyze_frame_bytes(frame_bytes, camera_id="test_cam_01")

    # Invariants under Zero-Fake-Data policy:
    assert result.vision_count == 0
    assert result.cases_detected == 0
    assert result.singles_detected == 0
    assert result.vision_confidence == 0.0
    assert len(result.detections) == 0
    assert result.tracking_accuracy_pct == 0.0
    assert isinstance(annotated_bytes, bytes)


def test_vision_service_corrupted_bytes_resilience():
    """F5 / Phase 5: Corrupted or unparseable frame bytes must return typed zero state without throwing."""
    corrupted_bytes = b"CORRUPTED_NON_IMAGE_GARBAGE_PAYLOAD_12345"
    result, annotated_bytes = VisionInferenceService.analyze_frame_bytes(corrupted_bytes, camera_id="test_cam_02")

    assert result.vision_count == 0
    assert result.vision_confidence == 0.0
    assert len(result.detections) == 0
    assert result.tracking_accuracy_pct == 0.0


def test_bytetrack_zero_detection_track_pruning():
    """F5 / Phase 5: Verifies that ByteTrack terminates stale tracks on lost-frame threshold."""
    tracker = SimpleByteTrack(track_buffer=3, match_thresh=0.8, min_box_area=10)

    # Frame 1: 2 active detections
    det1 = DetectedBox(bbox=[100, 100, 50, 50], class_label="person", product_id=None, sku_code=None, confidence=0.85)
    det2 = DetectedBox(bbox=[200, 200, 40, 40], class_label="single_unit", product_id=None, sku_code=None, confidence=0.75)
    
    tracked = tracker.update([det1, det2])
    assert len(tracked) == 2
    assert det1.track_id == 1
    assert det2.track_id == 2
    assert len(tracker.tracked_objects) == 2

    # Frame 2-4: Consecutive zero-detection frames (subject leaves frame)
    for frame_idx in range(1, 4):
        empty_res = tracker.update([])
        assert empty_res == []
        # Objects still retained within buffer
        assert len(tracker.tracked_objects) == 2
        assert tracker.tracked_objects[1]["lost_frames"] == frame_idx

    # Frame 5: lost_frames reaches 4 > track_buffer (3) -> prune tracks
    empty_res = tracker.update([])
    assert empty_res == []
    assert len(tracker.tracked_objects) == 0, "Tracker failed to prune stale tracks after track_buffer exceeded"


def test_face_service_blank_frame_no_match():
    """F5 / Phase 5: Blank frame must return NO_MATCH and NO_FACE without hallucinating enrolled employee."""
    frame_bytes = _create_blank_jpeg_bytes(320, 240)
    enrolled_mock = [
        {"id": 1, "name": "Alice Security", "embedding": [0.05] * 512},
        {"id": 2, "name": "Bob Warehouse", "embedding": [-0.05] * 512},
    ]

    result, annotated_bytes, boxes = FaceRecognitionService.detect_and_match_faces(
        frame_bytes=frame_bytes,
        enrolled_employees=enrolled_mock,
    )

    assert result.decision == "NO_MATCH"
    assert result.matched_employee_id is None
    assert result.employee_name is None
    assert result.similarity == 0.0
    assert result.liveness_decision == "NO_FACE"
    assert len(boxes) == 0


def test_invoice_ocr_blank_image_zero_hallucinations():
    """F5 / Phase 5: Blank invoice document must return 0.0 confidence and empty items without text hallucination."""
    frame_bytes = _create_blank_jpeg_bytes(800, 600)
    result = OcrService.extract_from_image(frame_bytes)

    assert result.extraction_confidence == 0.0
    assert result.declared_total_units == 0
    assert len(result.line_items) == 0
    assert result.low_confidence_flag is True
    assert "NO_TEXT_DETECTED" in result.raw_ocr_text
    assert result.extracted_invoice_number is None
    assert result.extracted_carrier is None


def test_fusion_engine_vision_absence_degradation():
    """F5 / Phase 5: Tri-sensor consensus properly detects vision absence and flags occlusion."""
    # When vision is 0 count and 0 confidence (camera occluded), but scale & rfid report items
    result = MultiSensorFusionEngine.fuse(
        vision_count=0,
        vision_confidence=0.0,
        rfid_count=10,
        rfid_confidence=0.95,
        weight_estimated_units=10,
        weight_confidence=0.90,
    )

    # Invariants:
    assert result.channel_readings["vision"]["status"] == "OK"
    assert result.channel_readings["vision"]["confidence"] == 0.0
    # Must flag visual occlusion / discrepancy
    assert result.disagreement_detected is True
    assert result.disagreement_type == "VISION_OCCLUSION"
    assert "Vision occlusion detected" in result.notes


def test_dynamic_tracking_settings_integration():
    """F5 / Phase 5: SimpleByteTrack in VisionInferenceService honors centralized TrackingConfig values."""
    cam_id = "test_config_cam_99"
    if cam_id in VisionInferenceService._trackers:
        del VisionInferenceService._trackers[cam_id]

    frame_bytes = _create_blank_jpeg_bytes(320, 240)
    VisionInferenceService.analyze_frame_bytes(frame_bytes, camera_id=cam_id)

    assert cam_id in VisionInferenceService._trackers
    tracker = VisionInferenceService._trackers[cam_id]
    assert tracker.track_buffer == settings.tracking.tracker_max_lost_frames
    assert pytest.approx(tracker.match_thresh, 0.01) == 1.0 - settings.tracking.tracker_iou_threshold
