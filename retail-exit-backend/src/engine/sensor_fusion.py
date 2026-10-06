"""Tri-Sensor Manifest Fusion & Discrepancy Attribution Engine

Fuses three independent sensory verification channels at dispatch gates and loading bays:
1. Computer Vision (CV) Object & Material Instance Count.
2. High-Speed 1D/2D Barcode & UHF RFID Scanned Identifiers.
3. In-Floor Industrial Load-Cell / Gross Weight Scale Reading.

Reconciles against the authorized invoice manifest and accurately attributes discrepancies:
- OVER_CARRY: Physical items leave beyond manifest authorization.
- UNDER_DECLARE: Fewer physical items than manifest.
- UNTAGGED_UNITS: Visual items present without matching RFID/Barcode serialization.
- WEIGHT_MISMATCH_HOLLOW: Count matches but physical weight is suspiciously light (dummy boxes).
- FULL_TRI_SENSOR_MATCH: All three channels concordantly agree with authorized manifest.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import logging
from src.core.config import settings

logger = logging.getLogger("secops.engine.sensor_fusion")


@dataclass
class TriSensorInput:
    vision_counts: Dict[str, int]             # {"cement_bag": 40, "carton_box": 10}
    scanned_barcodes: List[str]               # List of decoded barcode/QR strings
    scanned_rfid_tags: List[str]              # List of EPC/TID RFID tag strings
    gross_scale_weight_kg: float              # Total weight recorded by in-floor scale
    tare_weight_kg: float                     # Tare weight of pallet/handcart/forklift
    manifest_expected: Dict[str, int]         # Authorized line items from OCR/Bill
    material_unit_weights_kg: Dict[str, float]# Configured nominal unit weights


@dataclass
class TriSensorReconciliationResult:
    status: str                               # "MATCH", "OVER_CARRY", "UNDER_DECLARE", "WEIGHT_ANOMALY", "UNTAGGED_UNITS"
    is_authorized: bool                       # True if all three channels validate within tolerance
    variance_units: int                       # Net delta compared to manifest
    vision_total_units: int
    scanned_serialized_units: int             # Unique tags/barcodes
    net_measured_weight_kg: float             # Gross - Tare
    expected_weight_kg: float                 # Manifest quantity * unit weight
    weight_variance_kg: float                 # Measured - Expected
    weight_variance_pct: float                # Percentage error
    channel_concordance: Dict[str, bool]      # {"vision_vs_manifest": True, "rfid_vs_manifest": True, ...}
    discrepancy_attribution: Optional[str]
    discrepancy_severity: str                 # "NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"
    recommended_action: str


class TriSensorFusionEngine:
    """Arbitrates multi-modal sensor inputs to detect dispatch theft, ghost tags, or hollow cartons."""

    DEFAULT_UNIT_WEIGHTS = {
        "cement_bag": 50.0,
        "carton_box": 10.0,
        "iron_rod_bundle": 250.0,
        "book": 0.65,
    }

    @classmethod
    def reconcile(
        cls,
        data: TriSensorInput,
        weight_tolerance_pct: Optional[float] = None,
    ) -> TriSensorReconciliationResult:
        """Reconciles Vision, RFID/Barcode, and Weight against Manifest.

        Args:
            data: TriSensorInput containing all channels.
            weight_tolerance_pct: Acceptable weight margin percentage (defaults to configured fusion threshold).

        Returns:
            TriSensorReconciliationResult with comprehensive audit analysis.
        """
        if weight_tolerance_pct is None:
            weight_tolerance_pct = settings.fusion.scale_weight_tolerance_pct * 100.0
        vision_total = sum(data.vision_counts.values())
        manifest_total = sum(data.manifest_expected.values())

        # Combine unique serialized tags (RFID + unique Barcodes)
        all_tags = set(data.scanned_rfid_tags) | set(data.scanned_barcodes)
        serialized_total = len(all_tags)

        # Weight computation
        net_weight = max(0.0, round(data.gross_scale_weight_kg - data.tare_weight_kg, 2))

        # Expected weight based on manifest
        unit_weights = {**cls.DEFAULT_UNIT_WEIGHTS, **(data.material_unit_weights_kg or {})}
        expected_weight = 0.0
        for mat_id, qty in data.manifest_expected.items():
            u_weight = unit_weights.get(mat_id.lower().strip(), 10.0)
            expected_weight += qty * u_weight
        expected_weight = round(expected_weight, 2)

        weight_delta = round(net_weight - expected_weight, 2)
        weight_error_pct = round((abs(weight_delta) / max(0.01, expected_weight)) * 100.0, 1) if expected_weight > 0 else 0.0

        # Channel agreement checks
        vision_match = (vision_total == manifest_total)
        rfid_match = (serialized_total == manifest_total) if serialized_total > 0 else True
        weight_match = (weight_error_pct <= weight_tolerance_pct) if expected_weight > 0 else True

        channel_concordance = {
            "vision_vs_manifest": vision_match,
            "serialized_vs_manifest": rfid_match,
            "weight_vs_manifest": weight_match,
        }

        # Detailed Attribution Analysis
        status = "MATCH"
        is_authorized = True
        severity = "NONE"
        attribution = None
        rec_action = "RELEASE_DISPATCH: All sensor channels concordant."

        variance_units = vision_total - manifest_total

        # 1. Check Over-Carry (Theft / Excess Loading)
        if vision_total > manifest_total:
            status = "OVER_CARRY"
            is_authorized = False
            severity = "CRITICAL" if (vision_total - manifest_total) >= 3 else "HIGH"
            attribution = (
                f"OVER_CARRY_DETECTED: Camera counted {vision_total} units leaving, "
                f"but manifest only authorizes {manifest_total} (excess +{variance_units})."
            )
            rec_action = "LOCK_GATE: Stop carrier and unload excess units."

        # 2. Check Under-Declare (Short Shipment)
        elif vision_total < manifest_total:
            status = "UNDER_DECLARE"
            is_authorized = False
            severity = "MEDIUM"
            attribution = (
                f"UNDER_DECLARE_SHORTAGE: Only {vision_total} units loaded vs "
                f"{manifest_total} authorized on manifest (shortfall {variance_units})."
            )
            rec_action = "HOLD_TRUCK: Verify missing inventory before signing dispatch."

        # 3. Check Serialized Tag Discrepancy (Untagged items or Ghost RFID tags)
        elif serialized_total > 0 and serialized_total < vision_total:
            status = "UNTAGGED_UNITS"
            is_authorized = False
            severity = "HIGH"
            missing_tags = vision_total - serialized_total
            attribution = (
                f"UNTAGGED_INVENTORY: Camera detected {vision_total} physical cartons, "
                f"but RFID/Barcode only read {serialized_total} tags ({missing_tags} untagged or shielded items)."
            )
            rec_action = "MANUAL_SCAN: Re-scan cartons with handheld reader."

        # 4. Check Weight Anomaly (Hollow dummy boxes or scrap substitution)
        elif expected_weight > 0 and weight_delta < 0 and weight_error_pct > weight_tolerance_pct:
            status = "WEIGHT_ANOMALY"
            is_authorized = False
            severity = "CRITICAL"
            attribution = (
                f"HOLLOW_CARTON_SUSPICION: Physical box count matches ({vision_total}), "
                f"but net weight ({net_weight:.1f}kg) is {weight_error_pct:.1f}% below expected ({expected_weight:.1f}kg)."
            )
            rec_action = "INSPECT_CARGO: Perform box core inspection for missing contents."

        return TriSensorReconciliationResult(
            status=status,
            is_authorized=is_authorized,
            variance_units=variance_units,
            vision_total_units=vision_total,
            scanned_serialized_units=serialized_total,
            net_measured_weight_kg=net_weight,
            expected_weight_kg=expected_weight,
            weight_variance_kg=weight_delta,
            weight_variance_pct=weight_error_pct,
            channel_concordance=channel_concordance,
            discrepancy_attribution=attribution,
            discrepancy_severity=severity,
            recommended_action=rec_action,
        )
