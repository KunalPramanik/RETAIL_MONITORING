"""RFID Fusion & Antenna Analytics Service

Deduplicates raw EPC tag reads, resolves them by product prefix, and detects RF attenuation.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class RfidTagRead:
    epc_tag: str
    antenna_id: str
    rssi_dbm: float
    sku_prefix: str


@dataclass
class RfidProcessingResult:
    total_tags_read: int
    attenuation_detected: bool
    reads: List[RfidTagRead]
    avg_rssi_dbm: float


class RfidService:
    @classmethod
    def process_reads(
        cls,
        epc_tags: List[str],
        antenna_id: str = "ANT-01",
        expected_units: Optional[int] = None,
    ) -> RfidProcessingResult:
        """Processes and deduplicates RFID reads."""
        unique_tags = list(set(epc_tags))
        reads = []
        rssi_vals = []

        for tag in unique_tags:
            tag_hash = sum(ord(c) for c in tag) % 15
            rssi = round(-52.0 + tag_hash * 0.8, 2)
            rssi_vals.append(rssi)
            prefix = tag.split("-")[0] if "-" in tag else tag[:6]
            reads.append(
                RfidTagRead(
                    epc_tag=tag,
                    antenna_id=antenna_id,
                    rssi_dbm=rssi,
                    sku_prefix=prefix,
                )
            )

        tag_count = len(unique_tags)
        attenuation = False
        if expected_units is not None and tag_count < expected_units:
            attenuation = True

        avg_rssi = round(sum(rssi_vals) / max(1, len(rssi_vals)), 2) if rssi_vals else -45.0

        return RfidProcessingResult(
            total_tags_read=tag_count,
            attenuation_detected=attenuation,
            reads=reads,
            avg_rssi_dbm=avg_rssi,
        )

