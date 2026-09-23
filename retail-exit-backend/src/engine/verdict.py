"""Deterministic Verdict & Severity Rules Engine

Pure, fully auditable rule-based decision module implementing:
1. Tolerance checks (unit_tolerance and pct_tolerance)
2. Severity classification bands from database configuration
3. Repeat-offender risk escalation (+1 severity band for carriers with >= 3 recent mismatches)
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple


@dataclass
class VerdictResult:
    verdict: str                  # 'MATCH' | 'MISMATCH' | 'PARTIAL' | 'UNVERIFIED' | 'REVIEW_REQUIRED' | 'PASS'
    severity: str                 # 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH'
    delta_units: int              # consensus_units - declared_units
    escalated_by_repeat_offender: bool
    allowed_tolerance_units: float
    reason: str
    reason_code: str = "EXACT_PARITY"  # EXTRA_UNITS, SHORT_DECLARATION, SENSOR_DISAGREEMENT, LOW_OCR_CONFIDENCE, UNVERIFIED_LIVE_SOURCE, OCCLUDED_STACK, MISSING_CHANNEL, UNKNOWN_MATERIAL
    review_required: bool = False

    @property
    def explanation(self) -> str:
        return self.reason


class VerdictEngine:
    """Evaluates consensus unit counts against declared invoice manifests.
    
    Implements pure, deterministic rules function for multi-modal exit and dispatch verdicts.
    """

    @classmethod
    def evaluate(
        cls,
        consensus_units: int,
        declared_units: Optional[int] = None,
        unit_tolerance: int = 0,
        pct_tolerance: float = 0.0,
        low_severity_threshold: int = 1,
        med_severity_threshold: int = 3,
        high_severity_threshold: int = 6,
        employee_30d_mismatches: int = 0,
        repeat_offender_count_trigger: int = 3,
        live_source_verified: bool = True,
        sensor_disagreement: bool = False,
        occluded_stack: bool = False,
        unknown_material: bool = False,
        missing_channel: bool = False,
        low_ocr_confidence: bool = False,
        # Backward-compatible parameter aliases:
        is_live_source_verified: Optional[bool] = None,
        has_occluded_stack: Optional[bool] = None,
        has_unknown_material: Optional[bool] = None,
        ocr_confidence: Optional[float] = None,
        min_ocr_confidence: Optional[float] = None,
        **kwargs: Any,
    ) -> VerdictResult:
        """Pure evaluation function computing verdict, severity, and standardized reason code."""
        if is_live_source_verified is not None:
            live_source_verified = is_live_source_verified
        if has_occluded_stack is not None:
            occluded_stack = has_occluded_stack
        if has_unknown_material is not None:
            unknown_material = has_unknown_material
        if ocr_confidence is not None and min_ocr_confidence is not None:
            low_ocr_confidence = (ocr_confidence < min_ocr_confidence)

        # 1. Honest Uncertainty Verification Gates
        if not live_source_verified:
            return VerdictResult(
                verdict="UNVERIFIED",
                severity="HIGH",
                delta_units=consensus_units - (declared_units or 0),
                escalated_by_repeat_offender=False,
                allowed_tolerance_units=0.0,
                reason="Camera source is LIVE_UNVERIFIED; high-impact decisions suppressed.",
                reason_code="UNVERIFIED_LIVE_SOURCE",
                review_required=True,
            )

        if unknown_material:
            return VerdictResult(
                verdict="REVIEW_REQUIRED",
                severity="MEDIUM",
                delta_units=consensus_units - (declared_units or 0),
                escalated_by_repeat_offender=False,
                allowed_tolerance_units=0.0,
                reason="Unknown or unverified material detected; requires manual human review.",
                reason_code="UNKNOWN_MATERIAL",
                review_required=True,
            )

        if occluded_stack:
            return VerdictResult(
                verdict="REVIEW_REQUIRED",
                severity="MEDIUM",
                delta_units=consensus_units - (declared_units or 0),
                escalated_by_repeat_offender=False,
                allowed_tolerance_units=0.0,
                reason="Material stack is heavily occluded or touching; instances cannot be cleanly resolved.",
                reason_code="OCCLUDED_STACK",
                review_required=True,
            )

        if sensor_disagreement:
            return VerdictResult(
                verdict="REVIEW_REQUIRED",
                severity="HIGH",
                delta_units=consensus_units - (declared_units or 0),
                escalated_by_repeat_offender=False,
                allowed_tolerance_units=0.0,
                reason="Sensor fusion channels strongly disagree beyond allowed calibration threshold.",
                reason_code="SENSOR_DISAGREEMENT",
                review_required=True,
            )

        if low_ocr_confidence:
            return VerdictResult(
                verdict="REVIEW_REQUIRED",
                severity="LOW",
                delta_units=consensus_units - (declared_units or 0),
                escalated_by_repeat_offender=False,
                allowed_tolerance_units=0.0,
                reason="Document OCR extraction confidence below threshold; manual verification required.",
                reason_code="LOW_OCR_CONFIDENCE",
                review_required=True,
            )

        # 2. If no declaration provided, unmanifested goods
        if declared_units is None:
            delta = consensus_units
            if consensus_units == 0:
                return VerdictResult(
                    verdict="PASS",
                    severity="NONE",
                    delta_units=0,
                    escalated_by_repeat_offender=False,
                    allowed_tolerance_units=0.0,
                    reason="Empty cart traversal verified.",
                    reason_code="EXACT_PARITY",
                    review_required=False,
                )
            
            # Non-declared goods
            base_severity = cls._calculate_base_severity(
                abs(delta),
                low_severity_threshold,
                med_severity_threshold,
                high_severity_threshold,
            )
            final_severity, escalated = cls._apply_repeat_offender_escalation(
                base_severity,
                employee_30d_mismatches,
                repeat_offender_count_trigger,
            )
            return VerdictResult(
                verdict="MISMATCH",
                severity=final_severity,
                delta_units=delta,
                escalated_by_repeat_offender=escalated,
                allowed_tolerance_units=0.0,
                reason=f"Unmanifested movement: {consensus_units} units detected without linked declaration.",
                reason_code="EXTRA_UNITS",
                review_required=False,
            )

        delta = consensus_units - declared_units
        abs_delta = abs(delta)

        # 3. Calculate Allowable Tolerance
        allowed_tolerance = max(
            float(unit_tolerance),
            (float(pct_tolerance) / 100.0) * float(declared_units),
        )

        # 4. Partial Channel check
        if missing_channel and abs_delta <= allowed_tolerance:
            return VerdictResult(
                verdict="PARTIAL",
                severity="NONE",
                delta_units=delta,
                escalated_by_repeat_offender=False,
                allowed_tolerance_units=allowed_tolerance,
                reason=f"Provisional match: within tolerance ±{allowed_tolerance:.1f} but a configured sensor channel was missing.",
                reason_code="MISSING_CHANNEL",
                review_required=False,
            )

        # 5. Parity Check
        if abs_delta <= allowed_tolerance:
            return VerdictResult(
                verdict="PASS",
                severity="NONE",
                delta_units=delta,
                escalated_by_repeat_offender=False,
                allowed_tolerance_units=allowed_tolerance,
                reason=f"Parity verified: detected {consensus_units} vs declared {declared_units} (within tolerance ±{allowed_tolerance:.1f}).",
                reason_code="EXACT_PARITY",
                review_required=False,
            )

        # 6. Discrepancy -> Determine Base Severity
        base_severity = cls._calculate_base_severity(
            abs_delta,
            low_severity_threshold,
            med_severity_threshold,
            high_severity_threshold,
        )

        # 4. Check Repeat Offender Escalation Rule
        final_severity, escalated = cls._apply_repeat_offender_escalation(
            base_severity,
            employee_30d_mismatches,
            repeat_offender_count_trigger,
        )

        direction = "Over-carry" if delta > 0 else "Under-carry"
        reason = f"{direction} discrepancy: detected {consensus_units} units vs declared {declared_units} (Δ {delta:+d} units)."
        if escalated:
            reason += f" Escalated to {final_severity} severity due to carrier repeat offender status ({employee_30d_mismatches} mismatches in 30 days)."

        return VerdictResult(
            verdict="MISMATCH",
            severity=final_severity,
            delta_units=delta,
            escalated_by_repeat_offender=escalated,
            allowed_tolerance_units=allowed_tolerance,
            reason=reason,
            reason_code="EXTRA_UNITS" if delta > 0 else "SHORT_DECLARATION",
            review_required=False,
        )

    @staticmethod
    def _calculate_base_severity(
        abs_delta: int,
        low_thresh: int,
        med_thresh: int,
        high_thresh: int,
    ) -> str:
        """Determines base severity band according to configurable thresholds."""
        if abs_delta >= high_thresh:
            return "HIGH"
        elif abs_delta >= med_thresh:
            return "MEDIUM"
        elif abs_delta >= low_thresh:
            return "LOW"
        return "NONE"

    @staticmethod
    def _apply_repeat_offender_escalation(
        base_severity: str,
        mismatch_count: int,
        trigger_threshold: int,
    ) -> Tuple[str, bool]:
        """Bumps severity by +1 band if carrier is a repeat offender."""
        if mismatch_count < trigger_threshold:
            return base_severity, False

        escalation_ladder = {
            "NONE": ("NONE", False),
            "LOW": ("MEDIUM", True),
            "MEDIUM": ("HIGH", True),
            "HIGH": ("HIGH", True),  # Already maximum
        }
        return escalation_ladder.get(base_severity, (base_severity, False))

