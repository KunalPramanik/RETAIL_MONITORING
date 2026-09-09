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
    verdict: str                  # 'PASS' | 'MISMATCH'
    severity: str                 # 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH'
    delta_units: int              # consensus_units - declared_units
    escalated_by_repeat_offender: bool
    allowed_tolerance_units: float
    reason: str


class VerdictEngine:
    """Evaluates consensus unit counts against declared invoice manifests."""

    @classmethod
    def evaluate(
        cls,
        consensus_units: int,
        declared_units: Optional[int],
        unit_tolerance: int = 0,
        pct_tolerance: float = 0.0,
        low_severity_threshold: int = 1,
        med_severity_threshold: int = 3,
        high_severity_threshold: int = 6,
        employee_30d_mismatches: int = 0,
        repeat_offender_count_trigger: int = 3,
    ) -> VerdictResult:
        """Pure evaluation function computing verdict and severity."""
        # If no declaration provided, assume unmanifested goods -> MISMATCH
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
                reason=f"Unmanifested cart: {consensus_units} units detected without linked invoice.",
            )

        delta = consensus_units - declared_units
        abs_delta = abs(delta)

        # 1. Calculate Allowable Tolerance: max(unit_tolerance, pct_tolerance * declared_units)
        allowed_tolerance = max(
            float(unit_tolerance),
            (float(pct_tolerance) / 100.0) * float(declared_units),
        )

        # 2. Check if within tolerance
        if abs_delta <= allowed_tolerance:
            return VerdictResult(
                verdict="PASS",
                severity="NONE",
                delta_units=delta,
                escalated_by_repeat_offender=False,
                allowed_tolerance_units=allowed_tolerance,
                reason=f"100% manifest parity: detected {consensus_units} units vs declared {declared_units} (within tolerance ±{allowed_tolerance:.1f}).",
            )

        # 3. Discrepancy -> Determine Base Severity
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

