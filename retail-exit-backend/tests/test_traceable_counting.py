"""Test Physics-Grounded Traceable Counting, Weight-Formula Estimation, and Packaging Resolution.

Complies strictly with Section 6 & Rule 2.3 of the Master Prompt:
- No silent substitution: formulas and intermediate values are exposed.
- Weight estimation uses: usable_weight_delta / approved_nominal_unit_weight.
- Verifies seal status and tolerance checks; produces REVIEW_REQUIRED on discrepancy.
"""

import pytest
from src.ml.material_segmentation import (
    estimate_quantity_from_weight,
    resolve_case_to_units,
    MaterialSegmentationEngine,
    DenseStackCountingEngine,
)


def test_weight_estimation_clean_nominal():
    """Section 6.3: Clean weight calculation matching nominal specification exactly."""
    # 500kg measured gross, 0kg tare, 50kg bag -> exactly 10 bags
    result = estimate_quantity_from_weight(
        measured_gross_kg=500.0,
        tare_kg=0.0,
        nominal_unit_weight_kg=50.0,
        tolerance_pct=2.0,
    )

    assert result["estimated_units"] == 10
    assert result["within_tolerance"] is True
    assert result["tare_kg"] == 0.0
    assert result["usable_weight_delta_kg"] == 500.0
    assert result["formula"] == "usable_weight_delta / approved_nominal_unit_weight"
    assert result["confidence"] >= 0.95


def test_weight_estimation_with_pallet_tare():
    """Section 6.3: Weight calculation correctly subtracting pallet/crate tare weight."""
    # Gross: 1025 kg, Pallet tare: 25 kg -> Net: 1000 kg. 50kg bags -> 20 bags
    result = estimate_quantity_from_weight(
        measured_gross_kg=1025.0,
        tare_kg=25.0,
        nominal_unit_weight_kg=50.0,
        tolerance_pct=2.0,
    )

    assert result["estimated_units"] == 20
    assert result["usable_weight_delta_kg"] == 1000.0
    assert result["within_tolerance"] is True


def test_weight_estimation_out_of_tolerance():
    """Rule 2.3 & Section 6.3: Weight delta not lining up with unit weight flags tolerance failure."""
    # 123 kg gross, 0 tare, 50 kg nominal -> 2.46 units -> rounds to 2 units (100kg expected, delta 23kg = 23% error > 2%)
    result = estimate_quantity_from_weight(
        measured_gross_kg=123.0,
        tare_kg=0.0,
        nominal_unit_weight_kg=50.0,
        tolerance_pct=2.0,
    )

    assert result["estimated_units"] == 2
    assert result["within_tolerance"] is False
    assert result["confidence"] < 0.8
    assert "Weight variance exceeds tolerance" in result["notes"]


def test_weight_estimation_tare_exceeds_gross():
    """Rule 2.3: Physical impossibility (tare > gross) must not return garbage or crash."""
    result = estimate_quantity_from_weight(
        measured_gross_kg=50.0,
        tare_kg=100.0,
        nominal_unit_weight_kg=10.0,
    )

    assert result["estimated_units"] == 0
    assert result["within_tolerance"] is False
    assert "Tare exceeds or equals gross weight" in result["notes"]


def test_case_resolution_single_unit():
    """Section 6.4: Single loose unit maps 1:1."""
    res = resolve_case_to_units(
        detected_packages=5,
        package_type="single_unit",
        units_per_package=1,
        is_sealed=True,
    )

    assert res["resolved_units"] == 5
    assert res["status"] == "MATCH"
    assert res["review_required"] is False


def test_case_resolution_sealed_case():
    """Section 6.4: Sealed case converts package count to total piece units."""
    res = resolve_case_to_units(
        detected_packages=4,
        package_type="sealed_case",
        units_per_package=12,
        is_sealed=True,
    )

    assert res["resolved_units"] == 48
    assert res["status"] == "MATCH"
    assert res["formula"] == "detected_packages * units_per_package"


def test_case_resolution_unverified_broken_seal():
    """Rule 2.3 & Section 6.4: Broken or unverified case seal must require human review."""
    res = resolve_case_to_units(
        detected_packages=4,
        package_type="sealed_case",
        units_per_package=12,
        is_sealed=False,  # Seal broken or unverified
    )

    assert res["status"] == "REVIEW_REQUIRED"
    assert res["review_required"] is True
    assert res["reason_code"] == "UNVERIFIED_PACKAGE_INTEGRITY"
    assert "Unverified or broken case seal" in res["notes"]


def test_dense_stack_honest_degradation():
    """Section 6.2: Low confidence dense stack triggers honest degradation rather than fake exact counts."""
    # Synthetic boxes with heavy overlap
    boxes = [
        [100, 100, 200, 200],
        [105, 102, 202, 198],  # Almost identical overlap
        [102, 104, 204, 201],
    ]
    scores = [0.45, 0.40, 0.38]  # Low scores below confident threshold

    res = DenseStackCountingEngine.count_dense_stack(
        boxes=boxes,
        scores=scores,
        material_type="iron_rods",
        min_confidence=0.5,
    )

    assert res["uncertainty_flag"] is True
    assert res["reason_code"] in ["COUNT_UNRESOLVED", "LOW_STACK_CONFIDENCE"]
    assert res["honest_explanation"] is not None

