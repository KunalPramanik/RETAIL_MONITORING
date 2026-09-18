"""Tests for Zero-Shot Open-Vocabulary Grounding Service."""

import cv2
import numpy as np
import pytest
from src.ml.open_vocabulary_service import OpenVocabularyGrounder, GroundedEntity


def test_grounding_fire_extinguisher_prompt():
    """Verifies that a red cylindrical object grounds to prompt 'fire extinguisher'."""
    img = np.full((500, 500, 3), (120, 120, 120), dtype=np.uint8)
    # Draw red cylinder (fire extinguisher)
    # Red in BGR: (20, 20, 220)
    cv2.rectangle(img, (200, 100), (280, 380), (20, 20, 220), -1)

    results = OpenVocabularyGrounder.ground_queries(
        img,
        queries=["fire extinguisher"],
        confidence_floor=0.40,
    )
    assert len(results) >= 1
    r0 = results[0]
    assert "Fire Extinguisher" in r0.matched_class
    assert r0.confidence >= 0.40
    assert r0.bbox[2] > 0 and r0.bbox[3] > 0


def test_grounding_safety_cone_prompt():
    """Verifies that an orange triangle/cone grounds to prompt 'safety cone'."""
    img = np.full((500, 500, 3), (80, 80, 80), dtype=np.uint8)
    # Draw safety orange cone: Hue in [8, 22], Sat >= 130, Val >= 130
    # Safety Orange in BGR: (0, 120, 255)
    pts = np.array([[250, 100], [320, 380], [180, 380]], dtype=np.int32)
    cv2.fillPoly(img, [pts], (0, 130, 255))

    results = OpenVocabularyGrounder.ground_queries(
        img,
        queries=["safety cone"],
        confidence_floor=0.40,
    )
    assert len(results) >= 1
    assert "Safety Cone" in results[0].matched_class


def test_grounding_arbitrary_unseen_prompt():
    """Verifies open-world grounding on arbitrary text prompts via visual saliency."""
    img = np.full((500, 500, 3), (140, 140, 140), dtype=np.uint8)
    # Draw high contrast package/box
    cv2.rectangle(img, (150, 150), (350, 350), (20, 20, 20), -1)

    results = OpenVocabularyGrounder.ground_queries(
        img,
        queries=["shipping crate"],
        confidence_floor=0.35,
    )
    assert len(results) >= 1
    assert results[0].matched_class == "Shipping Crate"
