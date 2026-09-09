"""Unit Tests for Deterministic Verdict & Severity Rules Engine"""

import pytest
from src.engine.verdict import VerdictEngine, VerdictResult


def test_verdict_clean_pass():
    """100% consensus match should yield PASS with NONE severity."""
    result = VerdictEngine.evaluate(
        consensus_units=72,
        declared_units=72,
        unit_tolerance=0,
        pct_tolerance=0.0,
    )
    assert result.verdict == "PASS"
    assert result.severity == "NONE"
    assert result.delta_units == 0
    assert result.escalated_by_repeat_offender is False


def test_verdict_unit_tolerance():
    """Delta within absolute unit tolerance should yield PASS."""
    # Declared 50, detected 51, tolerance = 1
    result = VerdictEngine.evaluate(
        consensus_units=51,
        declared_units=50,
        unit_tolerance=1,
        pct_tolerance=0.0,
    )
    assert result.verdict == "PASS"
    assert result.severity == "NONE"
    assert result.delta_units == 1


def test_verdict_pct_tolerance():
    """Delta within percentage tolerance should yield PASS."""
    # Declared 100, detected 103, pct_tolerance = 5.0% (tolerance = 5 units)
    result = VerdictEngine.evaluate(
        consensus_units=103,
        declared_units=100,
        unit_tolerance=0,
        pct_tolerance=5.0,
    )
    assert result.verdict == "PASS"
    assert result.severity == "NONE"
    assert result.delta_units == 3


def test_verdict_low_severity_mismatch():
    """Small discrepancy should trigger LOW severity."""
    result = VerdictEngine.evaluate(
        consensus_units=74,
        declared_units=72,
        low_severity_threshold=1,
        med_severity_threshold=3,
        high_severity_threshold=6,
    )
    assert result.verdict == "MISMATCH"
    assert result.severity == "LOW"
    assert result.delta_units == 2


def test_verdict_medium_severity_mismatch():
    """Medium discrepancy should trigger MEDIUM severity."""
    result = VerdictEngine.evaluate(
        consensus_units=52,
        declared_units=48,
        low_severity_threshold=1,
        med_severity_threshold=3,
        high_severity_threshold=6,
    )
    assert result.verdict == "MISMATCH"
    assert result.severity == "MEDIUM"
    assert result.delta_units == 4


def test_verdict_high_severity_mismatch():
    """Large discrepancy should trigger HIGH severity."""
    result = VerdictEngine.evaluate(
        consensus_units=36,
        declared_units=24,
        low_severity_threshold=1,
        med_severity_threshold=3,
        high_severity_threshold=6,
    )
    assert result.verdict == "MISMATCH"
    assert result.severity == "HIGH"
    assert result.delta_units == 12


def test_repeat_offender_escalation_low_to_medium():
    """Carrier with >= 3 prior mismatches should escalate LOW to MEDIUM."""
    result = VerdictEngine.evaluate(
        consensus_units=74,
        declared_units=72,
        low_severity_threshold=1,
        med_severity_threshold=3,
        high_severity_threshold=6,
        employee_30d_mismatches=4,  # Repeat offender
        repeat_offender_count_trigger=3,
    )
    assert result.verdict == "MISMATCH"
    assert result.severity == "MEDIUM"  # Escalated from LOW
    assert result.escalated_by_repeat_offender is True


def test_repeat_offender_escalation_medium_to_high():
    """Carrier with >= 3 prior mismatches should escalate MEDIUM to HIGH."""
    result = VerdictEngine.evaluate(
        consensus_units=52,
        declared_units=48,
        low_severity_threshold=1,
        med_severity_threshold=3,
        high_severity_threshold=6,
        employee_30d_mismatches=3,  # Repeat offender
        repeat_offender_count_trigger=3,
    )
    assert result.verdict == "MISMATCH"
    assert result.severity == "HIGH"  # Escalated from MEDIUM
    assert result.escalated_by_repeat_offender is True


def test_unmanifested_cart():
    """Unmanifested goods without declared units should trigger MISMATCH."""
    result = VerdictEngine.evaluate(
        consensus_units=20,
        declared_units=None,
        high_severity_threshold=6,
    )
    assert result.verdict == "MISMATCH"
    assert result.severity == "HIGH"
    assert result.delta_units == 20

