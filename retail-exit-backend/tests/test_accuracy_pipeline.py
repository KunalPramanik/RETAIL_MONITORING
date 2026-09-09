"""High-Accuracy Multi-Modal Pipeline Tests

Verifies:
1. OCR adaptive preprocessing & Levenshtein fuzzy SKU auto-correction
2. Face recognition multi-frame temporal voting & cosine similarity
3. Vision trajectory IoU & directional vector angle filtering
4. Fusion engine adaptive Bayesian weighting & Faraday attenuation detection
"""

import os
import sys
import pytest
import numpy as np

# Ensure retail-exit-backend root is on sys.path regardless of execution directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ml.ocr_service import OcrService
from src.ml.face_service import FaceRecognitionService
from src.ml.vision_service import VisionInferenceService
from src.engine.fusion import MultiSensorFusionEngine


def test_ocr_fuzzy_sku_correction():
    """Confused OCR glyphs like 'SKU-WAT-5OO' (O instead of 0) should auto-correct to 'SKU-WAT-500'."""
    catalog = ["SKU-WAT-500", "SKU-FLOUR-10K", "SKU-RICE-25K", "SKU-OIL-5L"]

    # Test exact match
    matched, score = OcrService.fuzzy_match_sku("SKU-WAT-500", catalog)
    assert matched == "SKU-WAT-500"
    assert score == 1.0

    # Test confused O instead of 0
    matched, score = OcrService.fuzzy_match_sku("SKU-WAT-5OO", catalog)
    assert matched == "SKU-WAT-500"
    assert score >= 0.85

    # Test minor typo
    matched, score = OcrService.fuzzy_match_sku("SKU-FLOUR-1OK", catalog)
    assert matched == "SKU-FLOUR-10K"
    assert score >= 0.85


def test_ocr_parse_manifest_dynamic_accuracy():
    """Manifest parsing should dynamically correct SKUs and return high confidence."""
    catalog = ["SKU-WAT-500", "SKU-FLOUR-10K"]
    items = [
        {"skuCode": "SKU-WAT-5OO", "description": "Spring Water 500ml", "casesDeclared": 4, "unitsPerCase": 24},
        {"skuCode": "SKU-FLOUR-10K", "description": "Wheat Flour 10kg", "casesDeclared": 2, "unitsPerCase": 6},
    ]

    result = OcrService.parse_manifest(
        invoice_number="BOL-ACC-99",
        carrier_name="BlueDart Logistics",
        line_items_data=items,
        catalog_skus=catalog,
    )
    assert result.declared_total_units == (4 * 24) + (2 * 6)  # 96 + 12 = 108
    assert result.extraction_confidence >= 0.95
    assert result.line_items[0].sku_code == "SKU-WAT-500"  # Corrected!


def test_face_recognition_temporal_voting():
    """Multi-frame temporal voting should pick the peak quality angle and match correctly."""
    # Enrolled staff embedding vector
    np.random.seed(42)
    base_vector = np.random.randn(512).astype(np.float32)
    base_vector = base_vector / np.linalg.norm(base_vector)

    enrolled = [
        {
            "employee_id": "EMP-DEV-001",
            "name": "Dev Sharma",
            "face_embedding": base_vector.tolist(),
        }
    ]

    # Frame sequence: Frame 1 (slight noise), Frame 2 (sharp match), Frame 3 (motion blur)
    frame_1 = (base_vector + np.random.randn(512) * 0.1).tolist()
    frame_2 = (base_vector + np.random.randn(512) * 0.02).tolist()
    frame_3 = (base_vector + np.random.randn(512) * 0.25).tolist()

    # Match with multi-frame temporal voting
    result = FaceRecognitionService.match_carrier(
        probe_embedding=[frame_1, frame_2, frame_3],
        enrolled_employees=enrolled,
    )

    assert result.decision == "MATCHED"
    assert result.matched_employee_id == "EMP-DEV-001"
    assert result.similarity >= 0.85
    assert result.frames_evaluated == 3


def test_vision_directional_validation():
    """Directional validation should accept forward exit and reject parallel walking."""
    # Moving forward down corridor (0, 0) -> (0, 50)
    assert VisionInferenceService.validate_directional_exit(
        p_prev=(100.0, 100.0),
        p_curr=(100.0, 160.0),
        expected_dir=(0.0, 1.0),
    ) is True

    # Walking parallel to door (100, 100) -> (200, 100) (lateral direction, not exiting)
    assert VisionInferenceService.validate_directional_exit(
        p_prev=(100.0, 100.0),
        p_curr=(200.0, 100.0),
        expected_dir=(0.0, 1.0),
    ) is False


def test_fusion_adaptive_bayesian_consensus():
    """Adaptive Bayesian fusion should correctly detect Faraday attenuation with high confidence."""
    result = MultiSensorFusionEngine.fuse(
        vision_count=48,
        vision_confidence=0.98,
        rfid_count=36,  # 12 items shielded in booster bag
        rfid_confidence=0.88,
        weight_estimated_units=48,
        weight_confidence=0.95,
    )
    # Vision (48) + Weight (48) agreement overrides attenuated RFID (36)
    assert result.consensus_units == 48
    assert result.confidence >= 0.95
    assert result.disagreement_detected is True
    assert result.disagreement_type == "RFID_ATTENUATION"

