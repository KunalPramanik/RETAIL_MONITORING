"""Weight Sensor Fusion Service

Estimates cart unit counts from floor scale weight measurements and tare weight calibration.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class WeightEstimationResult:
    weight_kg: float
    tare_kg: float
    net_weight_kg: float
    estimated_units: int
    confidence: float
    density_verified: bool


class WeightService:
    @classmethod
    def estimate_units(
        cls,
        raw_scale_kg: float,
        avg_unit_weight_g: float = 500.0,
        tare_offset_kg: float = 0.0,
        expected_units: Optional[int] = None,
    ) -> WeightEstimationResult:
        """Calculates estimated units from net weight and nominal unit weight."""
        net_kg = max(0.0, raw_scale_kg - tare_offset_kg)
        
        if avg_unit_weight_g <= 0:
            avg_unit_weight_g = 500.0
            
        unit_kg = avg_unit_weight_g / 1000.0
        calculated_units = int(round(net_kg / unit_kg)) if unit_kg > 0 else 0
        
        density_verified = True
        confidence = 0.90
        
        if expected_units is not None and expected_units > 0:
            discrepancy = abs(calculated_units - expected_units)
            if discrepancy > 5:
                density_verified = False
                confidence = 0.65

        return WeightEstimationResult(
            weight_kg=round(raw_scale_kg, 3),
            tare_kg=round(tare_offset_kg, 3),
            net_weight_kg=round(net_kg, 3),
            estimated_units=calculated_units,
            confidence=confidence,
            density_verified=density_verified,
        )

