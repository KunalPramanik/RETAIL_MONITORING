"""Vision Model & Inference Configuration

Centralized, named, and runtime-configurable settings for object detection,
per-class non-maximum suppression (NMS), liveness evaluation, and tracking.
Strictly zero hardcoded magic numbers scattered across inference code.
"""

from dataclasses import dataclass, field
from typing import Dict, Set, Optional
import os
import json
import logging

logger = logging.getLogger("secops.ml.config")


@dataclass
class VisionModelConfig:
    # ── Confidence Floors & Gating ──
    confidence_floor: float = 0.50  # Hard floor: only detections >= 50% reach DB verdicts & live UI overlays
    person_conf_threshold: float = 0.50
    item_conf_threshold: float = 0.12
    case_conf_threshold: float = 0.45
    vehicle_conf_threshold: float = 0.25

    # ── NMS & Clustered Item Tuning ──
    # Per-class NMS IoU threshold: lower value (0.35) prevents adjacent clustered items (e.g. wall frames)
    # or side-by-side items from suppressing each other.
    nms_iou_threshold: float = 0.35

    # ── Liveness & Face Gating ──
    face_candidate_min_score: float = 0.45  # Gating floor: drops weak non-face textures (< 0.45) on doors/bottles
    min_real_z_std: float = 15.0  # Living human face 3D depth variance floor (mm)
    liveness_pass_threshold: float = 0.60  # Minimum multi-factor consensus to confirm living person

    # ── Multi-Object Tracker (ByteTrack / Sort) ──
    tracker_max_lost_frames: int = 15  # Tolerates ~15 frames (~3-5 seconds) of occlusion without resetting tracklet identity
    tracker_iou_threshold: float = 0.30

    # ── COCO Class ID to Specific Retail & Vehicle Labels ──
    class_labels: Dict[int, str] = field(default_factory=lambda: {
        0: "Person",
        1: "Bicycle",
        2: "Car",
        3: "Motorcycle / Bike",
        5: "Bus",
        7: "Truck",
        24: "Backpack / Bag",
        25: "Umbrella",
        26: "Handbag / Purse",
        27: "Tie",
        28: "Case / Carton",
        39: "Bottle",
        40: "Wine Glass",
        41: "Cup / Mug",
        42: "Fork",
        43: "Knife",
        44: "Spoon",
        45: "Bowl",
        46: "Banana",
        47: "Apple",
        48: "Sandwich",
        49: "Orange",
        50: "Broccoli",
        51: "Carrot",
        52: "Hot Dog",
        53: "Pizza",
        54: "Donut",
        55: "Cake",
        62: "Display / Screen",
        63: "Laptop",
        64: "Computer Mouse",
        65: "Remote Control",
        66: "Keyboard",
        67: "Smartphone",
        73: "Book / Document",
        74: "Clock / Wall Item",
        75: "Vase",
        76: "Scissors",
        77: "Teddy Bear",
        78: "Hair Drier",
        79: "Pen / Stationery",
    })

    case_classes: Set[int] = field(default_factory=lambda: {28})
    single_item_classes: Set[int] = field(default_factory=lambda: {
        24, 25, 26, 27, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55,
        63, 64, 65, 66, 67, 73, 74, 75, 76, 77, 78, 79
    })
    vehicle_classes: Set[int] = field(default_factory=lambda: {1, 2, 3, 5, 7})


# Global singleton instance
_config_instance: Optional[VisionModelConfig] = None


def get_vision_config() -> VisionModelConfig:
    """Returns the active vision configuration singleton."""
    global _config_instance
    if _config_instance is None:
        _config_instance = VisionModelConfig()
    return _config_instance


def update_vision_config(**kwargs) -> VisionModelConfig:
    """Dynamically updates active vision parameters at runtime without restart."""
    cfg = get_vision_config()
    for k, v in kwargs.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
            logger.info("Updated vision configuration parameter: %s = %s", k, v)
    return cfg

