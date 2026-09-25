"""3D Volumetric & Pallet Density Analysis Service

Analyzes depth maps, LiDAR/RGB-D point clouds, or multi-angle surface geometry to calculate:
1. Physical bounding box dimensions (Width x Length x Height in meters).
2. Pallet gross envelope volume (m^3) and solid occupied volume (m^3).
3. Pallet packing density ratio and expected unit count based on material physical profiles.
4. Chimney-stacking fraud and hollow-center concealment detection.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import numpy as np
import logging

logger = logging.getLogger("secops.ml.volumetric")


@dataclass
class MaterialPhysicalSpec:
    material_id: str
    name: str
    unit_width_m: float
    unit_length_m: float
    unit_height_m: float
    unit_weight_kg: float
    unit_volume_m3: float = field(init=False)
    nominal_packing_density: float = 0.82  # Typical pallet stacking efficiency

    def __post_init__(self):
        self.unit_volume_m3 = round(self.unit_width_m * self.unit_length_m * self.unit_height_m, 5)


# Standard physical specifications for industrial materials
STANDARD_MATERIAL_SPECS: Dict[str, MaterialPhysicalSpec] = {
    "cement_bag": MaterialPhysicalSpec(
        material_id="cement_bag",
        name="Cement Bag 50kg",
        unit_width_m=0.40,
        unit_length_m=0.65,
        unit_height_m=0.15,
        unit_weight_kg=50.0,
        nominal_packing_density=0.85,
    ),
    "carton_box": MaterialPhysicalSpec(
        material_id="carton_box",
        name="Standard Carton Box",
        unit_width_m=0.30,
        unit_length_m=0.40,
        unit_height_m=0.30,
        unit_weight_kg=12.0,
        nominal_packing_density=0.88,
    ),
    "iron_rod_bundle": MaterialPhysicalSpec(
        material_id="iron_rod_bundle",
        name="Iron Rod Bundle (100 pcs)",
        unit_width_m=0.25,
        unit_length_m=3.00,
        unit_height_m=0.25,
        unit_weight_kg=250.0,
        nominal_packing_density=0.75,
    ),
    "book": MaterialPhysicalSpec(
        material_id="book",
        name="Standard Hardcover Book",
        unit_width_m=0.03,
        unit_length_m=0.18,
        unit_height_m=0.24,
        unit_weight_kg=0.65,
        nominal_packing_density=0.92,
    ),
}


@dataclass
class VolumetricAnalysisResult:
    dimensions_m: Dict[str, float]          # {"width": w, "length": l, "height": h}
    bounding_volume_m3: float               # W * L * H envelope
    occupied_solid_volume_m3: float         # Integral volume under depth surface
    packing_density: float                  # Occupied / Bounding
    estimated_units_from_volume: int        # Volume / Unit_Volume * Packing_Density
    visual_detected_units: int              # Surface CV count
    is_hollow_anomaly: bool                 # True if internal cavity or chimney stacking
    anomaly_reason: Optional[str]
    confidence: float
    depth_profile_summary: Dict[str, Any]


class VolumetricPalletAnalyzer:
    """Computes volumetric density and detects structural pallet stacking anomalies."""

    @classmethod
    def get_material_spec(cls, material_id: str) -> MaterialPhysicalSpec:
        """Retrieves or creates default physical spec for a material."""
        clean_id = material_id.lower().strip()
        for k, spec in STANDARD_MATERIAL_SPECS.items():
            if k in clean_id or clean_id in k:
                return spec
        # Default fallback generic packaging carton
        return MaterialPhysicalSpec(
            material_id=material_id,
            name=f"Generic {material_id}",
            unit_width_m=0.35,
            unit_length_m=0.45,
            unit_height_m=0.25,
            unit_weight_kg=15.0,
            nominal_packing_density=0.80,
        )

    @classmethod
    def analyze_depth_surface(
        cls,
        depth_map_meters: np.ndarray,
        pixel_to_meter_scale: float,
        material_id: str,
        visual_detected_units: int = 0,
        ground_plane_height_m: float = 2.50,
    ) -> VolumetricAnalysisResult:
        """Analyzes a 2D depth map (where pixel values represent distance from overhead sensor in meters).

        Args:
            depth_map_meters: 2D array of depth measurements in meters from sensor.
            pixel_to_meter_scale: Real-world meters per pixel width/height.
            material_id: Target material identifier (e.g. 'cement_bag', 'carton_box').
            visual_detected_units: Number of units counted visually by 2D camera.
            ground_plane_height_m: Distance from sensor to empty floor/pallet base.

        Returns:
            VolumetricAnalysisResult with volume, density, and anomaly verdicts.
        """
        if depth_map_meters.size == 0:
            raise ValueError("Depth map is empty")

        spec = cls.get_material_spec(material_id)

        # Height of object above floor: height = ground_plane - depth_value
        height_map = np.clip(ground_plane_height_m - depth_map_meters, 0.0, ground_plane_height_m)

        # Segment pallet footprint (areas where height > 0.05m above floor)
        pallet_mask = height_map > 0.05
        if not np.any(pallet_mask):
            return VolumetricAnalysisResult(
                dimensions_m={"width": 0.0, "length": 0.0, "height": 0.0},
                bounding_volume_m3=0.0,
                occupied_solid_volume_m3=0.0,
                packing_density=0.0,
                estimated_units_from_volume=0,
                visual_detected_units=visual_detected_units,
                is_hollow_anomaly=False,
                anomaly_reason="NO_PALLET_SURFACE_DETECTED",
                confidence=0.95,
                depth_profile_summary={"pallet_pixels": 0},
            )

        y_indices, x_indices = np.where(pallet_mask)
        min_x, max_x = np.min(x_indices), np.max(x_indices)
        min_y, max_y = np.min(y_indices), np.max(y_indices)

        width_m = round((max_x - min_x + 1) * pixel_to_meter_scale, 3)
        length_m = round((max_y - min_y + 1) * pixel_to_meter_scale, 3)
        max_height_m = round(float(np.max(height_map[pallet_mask])), 3)
        mean_height_m = round(float(np.mean(height_map[pallet_mask])), 3)

        # Gross bounding box envelope
        bounding_vol_m3 = round(width_m * length_m * max_height_m, 4)

        # Numerical integration of occupied volume (voxel sum)
        pixel_area_m2 = pixel_to_meter_scale * pixel_to_meter_scale
        occupied_vol_m3 = round(float(np.sum(height_map[pallet_mask])) * pixel_area_m2, 4)

        # Density = occupied / bounding
        packing_density = round(occupied_vol_m3 / max(0.001, bounding_vol_m3), 3)
        packing_density = min(1.0, max(0.0, packing_density))

        # Expected units calculation
        unit_effective_vol = max(0.001, spec.unit_volume_m3)
        estimated_units = int(np.round(occupied_vol_m3 / unit_effective_vol))

        # Hollow / Chimney-Stacking Detection:
        # Check central core vs perimeter height
        center_x = (min_x + max_x) // 2
        center_y = (min_y + max_y) // 2
        core_radius_x = max(2, (max_x - min_x) // 4)
        core_radius_y = max(2, (max_y - min_y) // 4)

        core_slice = height_map[
            max(0, center_y - core_radius_y) : min(height_map.shape[0], center_y + core_radius_y),
            max(0, center_x - core_radius_x) : min(height_map.shape[1], center_x + core_radius_x),
        ]

        is_hollow = False
        anomaly_reason = None

        if core_slice.size > 0:
            core_mean_h = float(np.mean(core_slice))
            # If perimeter is tall (max_height) but central core is significantly sunken (> 40% lower)
            if max_height_m >= 0.40 and core_mean_h < (max_height_m * 0.55):
                is_hollow = True
                anomaly_reason = (
                    f"CHIMNEY_STACKING_DETECTED: Pallet center is hollow (Core H: {core_mean_h:.2f}m "
                    f"vs Outer H: {max_height_m:.2f}m, depression ratio {core_mean_h/max_height_m:.2f})"
                )

        # Also check discrepancy between visually observed outer count and internal solid volume
        if not is_hollow and visual_detected_units > 0:
            # If visual count is significantly higher than physical volume can hold (> 25% excess)
            theoretical_max_units = int(np.ceil(occupied_vol_m3 / (spec.unit_volume_m3 * 0.70)))
            if visual_detected_units > (theoretical_max_units + 3):
                is_hollow = True
                anomaly_reason = (
                    f"INTERNAL_VOIDS_DETECTED: Visual surface count ({visual_detected_units}) exceeds "
                    f"maximum physical solid capacity ({theoretical_max_units}) for volume {occupied_vol_m3:.3f}m3"
                )

        return VolumetricAnalysisResult(
            dimensions_m={"width": width_m, "length": length_m, "height": max_height_m},
            bounding_volume_m3=bounding_vol_m3,
            occupied_solid_volume_m3=occupied_vol_m3,
            packing_density=packing_density,
            estimated_units_from_volume=estimated_units,
            visual_detected_units=visual_detected_units,
            is_hollow_anomaly=is_hollow,
            anomaly_reason=anomaly_reason,
            confidence=0.96 if is_hollow else 0.94,
            depth_profile_summary={
                "mean_height_m": mean_height_m,
                "max_height_m": max_height_m,
                "pallet_pixels": int(np.sum(pallet_mask)),
                "material_spec": spec.name,
                "unit_volume_m3": spec.unit_volume_m3,
            },
        )
