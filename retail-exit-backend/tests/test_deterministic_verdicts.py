"""Test Deterministic Verdict Engine & Honest Degradation Reason Codes.

Complies strictly with Section 8.3 & Rule 2.3 of the Master Prompt:
- Deterministic verdicts: MATCH, MISMATCH, PARTIAL, UNVERIFIED, REVIEW_REQUIRED.
- Standardized reason codes:
  - EXTRA_UNITS
  - SHORT_DECLARATION
  - SENSOR_DISAGREEMENT
  - LOW_OCR_CONFIDENCE
  - UNVERIFIED_LIVE_SOURCE
  - OCCLUDED_STACK
  - MISSING_CHANNEL
  - UNKNOWN_MATERIAL
"""

import pytest
from src.engine.verdict import VerdictEngine, VerdictResult


def test_verdict_unverified_live_source():
    """Section 7.2 & 8.3: Unverified camera input MUST produce UNVERIFIED and suppress automated clearance."""
    res = VerdictEngine.evaluate(
        consensus_units=10,
        declared_units=10,
        is_live_source_verified=False,
    )

    assert res.verdict == "UNVERIFIED"
    assert res.reason_code == "UNVERIFIED_LIVE_SOURCE"
    assert res.review_required is True
    assert "LIVE_UNVERIFIED" in res.explanation


def test_verdict_occluded_dense_stack():
    """Section 6.2 & 8.3: Heavy occlusion in material stack MUST require operator review."""
    res = VerdictEngine.evaluate(
        consensus_units=10,
        declared_units=10,
        is_live_source_verified=True,
        has_occluded_stack=True,
    )

    assert res.verdict == "REVIEW_REQUIRED"
    assert res.reason_code == "OCCLUDED_STACK"
    assert res.review_required is True
    assert "occluded" in res.explanation.lower()


def test_verdict_unknown_material_detected():
    """Rule 2.2 & Section 8.3: Unidentified material MUST NEVER be silently matched as known material."""
    res = VerdictEngine.evaluate(
        consensus_units=5,
        declared_units=5,
        is_live_source_verified=True,
        has_unknown_material=True,
    )

    assert res.verdict == "REVIEW_REQUIRED"
    assert res.reason_code == "UNKNOWN_MATERIAL"
    assert res.review_required is True
    assert "unknown or unverified material" in res.explanation.lower()


def test_verdict_sensor_disagreement():
    """Section 8.3: Conflicting readings between camera CV and weight scale MUST require review."""
    res = VerdictEngine.evaluate(
        consensus_units=20,
        declared_units=20,
        is_live_source_verified=True,
        sensor_disagreement=True,
    )

    assert res.verdict == "REVIEW_REQUIRED"
    assert res.reason_code == "SENSOR_DISAGREEMENT"
    assert res.review_required is True


def test_verdict_low_ocr_confidence():
    """Section 8.3: Degraded invoice OCR cannot authorize automated dispatch clearance."""
    res = VerdictEngine.evaluate(
        consensus_units=15,
        declared_units=15,
        is_live_source_verified=True,
        ocr_confidence=0.45,
        min_ocr_confidence=0.75,
    )

    assert res.verdict == "REVIEW_REQUIRED"
    assert res.reason_code == "LOW_OCR_CONFIDENCE"
    assert res.review_required is True


def test_verdict_missing_sensor_channel():
    """Section 8.3: When a required multi-sensor channel is offline, output PARTIAL."""
    res = VerdictEngine.evaluate(
        consensus_units=8,
        declared_units=8,
        is_live_source_verified=True,
        missing_channel=True,
    )

    assert res.verdict == "PARTIAL"
    assert res.reason_code == "MISSING_CHANNEL"
    assert "missing" in res.explanation.lower()


def test_verdict_exact_match():
    """Section 8.3: Valid verified live stream and exact counts yields clean MATCH / PASS."""
    res = VerdictEngine.evaluate(
        consensus_units=50,
        declared_units=50,
        is_live_source_verified=True,
        unit_tolerance=0,
    )

    assert res.verdict in ["MATCH", "PASS"]
    assert res.severity == "NONE"
    assert res.delta_units == 0
    assert res.review_required is False


def test_verdict_extra_units_mismatch():
    """Section 8.3: More units detected than declared on invoice/manifest yields MISMATCH (EXTRA_UNITS)."""
    res = VerdictEngine.evaluate(
        consensus_units=55,
        declared_units=50,
        is_live_source_verified=True,
        unit_tolerance=0,
        low_severity_threshold=1,
        med_severity_threshold=3,
        high_severity_threshold=6,
    )

    assert res.verdict == "MISMATCH"
    assert res.reason_code == "EXTRA_UNITS"
    assert res.delta_units == 5
    assert res.severity == "MEDIUM"


def test_verdict_short_declaration_mismatch():
    """Section 8.3: Fewer units detected than declared yields MISMATCH (SHORT_DECLARATION)."""
    res = VerdictEngine.evaluate(
        consensus_units=40,
        declared_units=50,
        is_live_source_verified=True,
        unit_tolerance=0,
        low_severity_threshold=1,
        med_severity_threshold=3,
        high_severity_threshold=6,
    )

    assert res.verdict == "MISMATCH"
    assert res.reason_code == "SHORT_DECLARATION"
    assert res.delta_units == -10
    assert res.severity == "HIGH"

