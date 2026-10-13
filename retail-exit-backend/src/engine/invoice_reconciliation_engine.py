"""SEC-OPS V8 Invoice & Physical Stock Movement Reconciliation Engine

Implements Section 9.3 of the SEC-OPS V8 Master Prompt:
- Reconciles physical stock movement deltas against authorized bills/invoices.
- Produces explicit status codes:
    * MATCHED: Physical count and bill line items match within tolerance.
    * OVERAGE: Physical count exceeds billed quantity (loss prevention alert).
    * SHORTAGE_REVIEW: Physical count is less than billed quantity.
    * NO_AUTHORIZATION_FOUND: Physical goods exit detected with no linked bill or invoice.
    * INCONCLUSIVE: Low vision confidence, severe occlusion, or unresolvable sensor discordance.
- Strictly separates processing pipelines:
    * Person != Material != Discrete Object != Bill
    * Empty-handed person exit NEVER triggers NO_AUTHORIZATION_FOUND
    * Bill/invoice identifiers never confused with person or product IDs
- Produces SHA-256 cryptographic audit hashes for tamper-proof chain of custody.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
import hashlib
import json
import time
import logging

logger = logging.getLogger("secops.engine.invoice_reconciliation")


@dataclass
class InvoiceReconciliationReport:
    status: str  # MATCHED, OVERAGE, SHORTAGE_REVIEW, NO_AUTHORIZATION_FOUND, INCONCLUSIVE
    is_authorized: bool
    event_id: str
    camera_id: str
    invoice_id: Optional[str]
    invoice_number: Optional[str]
    physical_units_count: int
    declared_billed_units: int
    variance_units: int  # physical - billed
    vision_confidence: float
    severity: str  # NONE, LOW, MEDIUM, HIGH, CRITICAL
    discrepancy_explanation: str
    cryptographic_hash: str
    reconciled_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class InvoiceReconciliationEngine:
    """Deterministic, CPU-first invoice manifest reconciliation engine."""

    MIN_VISION_CONFIDENCE = 0.50

    @classmethod
    def reconcile(
        cls,
        event_id: str,
        camera_id: str,
        physical_units_count: int,
        invoice_id: Optional[str] = None,
        invoice_number: Optional[str] = None,
        declared_billed_units: Optional[int] = None,
        vision_confidence: float = 0.90,
        has_occlusion_uncertainty: bool = False,
        person_present: bool = True,
    ) -> InvoiceReconciliationReport:
        """Evaluates physical material exit against billed authorization."""
        t_now = time.time()

        # Pipeline boundary check: empty-handed person exit is NOT an unauthorized material departure
        if physical_units_count == 0:
            status = "MATCHED"
            is_auth = True
            var = 0
            sev = "NONE"
            expl = "Zero physical goods detected exiting; normal authorized pedestrian transit."
            billed = 0

        # Case 1: Physical items detected, but NO invoice linked
        elif not invoice_id and not invoice_number:
            status = "NO_AUTHORIZATION_FOUND"
            is_auth = False
            billed = 0
            var = physical_units_count
            sev = "CRITICAL"
            expl = (
                f"Physical goods detected ({physical_units_count} units) with NO linked invoice or bill. "
                f"Unauthorized stock removal alert."
            )

        # Case 2: Inconclusive vision or severe occlusion
        elif vision_confidence < cls.MIN_VISION_CONFIDENCE or has_occlusion_uncertainty:
            status = "INCONCLUSIVE"
            is_auth = False
            billed = declared_billed_units if declared_billed_units is not None else 0
            var = physical_units_count - billed
            sev = "MEDIUM"
            expl = (
                f"Vision confidence ({vision_confidence:.2f}) or occlusion flag prevents deterministic "
                f"bill reconciliation. Manual gate inspection required."
            )

        # Case 3: Reconcile physical count vs declared bill count
        else:
            billed = declared_billed_units if declared_billed_units is not None else 0
            var = physical_units_count - billed

            if var == 0:
                status = "MATCHED"
                is_auth = True
                sev = "NONE"
                expl = f"Physical exit ({physical_units_count} units) matches billed manifest ({billed} units)."
            elif var > 0:
                status = "OVERAGE"
                is_auth = False
                sev = "HIGH"
                expl = (
                    f"Physical items ({physical_units_count} units) exceed authorized bill ({billed} units) "
                    f"by {var} unit(s). Overage loss prevention alert."
                )
            else:
                status = "SHORTAGE_REVIEW"
                is_auth = False
                sev = "LOW"
                expl = (
                    f"Physical items ({physical_units_count} units) are fewer than billed manifest ({billed} units) "
                    f"by {abs(var)} unit(s). Shortage verification required."
                )

        # Compute SHA-256 tamper-proof chain of custody hash
        payload = f"{event_id}|{camera_id}|{invoice_id}|{physical_units_count}|{billed}|{status}|{t_now}"
        proof_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        return InvoiceReconciliationReport(
            status=status,
            is_authorized=is_auth,
            event_id=event_id,
            camera_id=camera_id,
            invoice_id=invoice_id,
            invoice_number=invoice_number,
            physical_units_count=physical_units_count,
            declared_billed_units=billed,
            variance_units=var,
            vision_confidence=vision_confidence,
            severity=sev,
            discrepancy_explanation=expl,
            cryptographic_hash=proof_hash,
            reconciled_at=t_now,
        )

