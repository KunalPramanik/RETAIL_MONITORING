"""Vision Model & Inference Configuration

Centralized, named, and runtime-configurable settings for object detection,
per-class non-maximum suppression (NMS), liveness evaluation, tracking, and
dynamic class registry. Strictly zero hardcoded magic numbers.
"""

from dataclasses import dataclass, field
from typing import Dict, Set, List, Optional, Any
import os
import json
import logging

logger = logging.getLogger("secops.ml.config")

CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), "classes_config.json")


@dataclass
class VisionModelConfig:
    # ── Confidence Floors & Gating (Section 0.5 Two-Tier Standards) ──
    confidence_floor: float = 0.50  # Hard floor: only detections >= 50% reach DB verdicts & live UI overlays
    confirmed_entity_standard: float = 0.90  # Tier 2: >= 90% threshold for confirmed identity, verified presence, high-severity alerts
    fire_confirmed_threshold: float = 0.90   # >= 90%: Confirmed fire hazard alarm dispatch
    fire_hazard_floor: float = 0.45          # 45% - 89%: Unconfirmed flame hazard alert
    suspicious_confirmed_threshold: float = 0.90  # >= 90%: Confirmed suspicious behavior alert
    ppe_confirmed_threshold: float = 0.85    # >= 85%: Confirmed PPE violation
    person_conf_threshold: float = 0.50
    item_conf_threshold: float = 0.45
    case_conf_threshold: float = 0.50
    vehicle_conf_threshold: float = 0.25

    # ── NMS & Clustered Item Tuning ──
    nms_iou_threshold: float = 0.35

    # ── Liveness & Face Gating ──
    face_candidate_min_score: float = 0.45
    min_real_z_std: float = 15.0
    liveness_pass_threshold: float = 0.60

    # ── Multi-Object Tracker (ByteTrack / Sort) ──
    tracker_max_lost_frames: int = 15
    tracker_iou_threshold: float = 0.30

    # ── Dynamic Class Registry ──
    class_labels: Dict[int, str] = field(default_factory=dict)
    case_classes: Set[int] = field(default_factory=set)
    single_item_classes: Set[int] = field(default_factory=set)
    vehicle_classes: Set[int] = field(default_factory=set)
    pairwise_precision_groups: List[List[str]] = field(default_factory=list)

    @classmethod
    def load_from_file(cls, path: str = CONFIG_FILE_PATH) -> "VisionModelConfig":
        """Loads configuration from JSON file or initializes defaults."""
        cfg = cls()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Labels
                labels_raw = data.get("class_labels", {})
                cfg.class_labels = {int(k): str(v) for k, v in labels_raw.items()}

                # Categories
                cats = data.get("categories", {})
                cfg.case_classes = set(int(x) for x in cats.get("case_classes", [28]))
                cfg.vehicle_classes = set(int(x) for x in cats.get("vehicle_classes", [1, 2, 3, 5, 7]))
                cfg.single_item_classes = set(int(x) for x in cats.get("single_item_classes", []))

                # Thresholds
                thresh = data.get("thresholds", {})
                for k, v in thresh.items():
                    if hasattr(cfg, k):
                        setattr(cfg, k, float(v) if isinstance(v, (int, float)) else v)

                # Pairwise groups
                cfg.pairwise_precision_groups = data.get("pairwise_precision_groups", [])

                logger.info("Loaded vision class config with %d classes from %s", len(cfg.class_labels), path)
                return cfg
            except Exception as e:
                logger.error("Failed to load %s, falling back to built-ins: %s", path, e)

        # Fallback defaults if file missing or corrupt
        cfg._init_fallback_defaults()
        return cfg

    def _init_fallback_defaults(self):
        self.class_labels = {
            0: "Person", 1: "Bicycle", 2: "Car", 3: "Motorcycle / Bike", 5: "Bus", 7: "Truck",
            24: "Backpack / Bag", 25: "Umbrella", 26: "Handbag / Purse", 27: "Tie", 28: "Case / Carton",
            39: "Bottle", 40: "Wine Glass", 41: "Cup / Mug", 42: "Fork", 43: "Knife", 44: "Spoon",
            45: "Bowl", 46: "Banana", 47: "Apple", 48: "Sandwich", 49: "Orange", 50: "Broccoli",
            51: "Carrot", 52: "Hot Dog", 53: "Pizza", 54: "Donut", 55: "Cake", 62: "Display / Screen",
            63: "Laptop", 64: "Computer Mouse", 65: "Remote Control", 66: "Keyboard", 67: "Smartphone",
            73: "Book / Document", 74: "Clock / Wall Item", 75: "Vase", 76: "Scissors", 77: "Teddy Bear",
            78: "Hair Drier", 79: "Pen / Stationery", 80: "Charger / Power Adapter", 81: "Tote / Shopping Bag"
        }
        self.case_classes = {28}
        self.vehicle_classes = {1, 2, 3, 5, 7}
        self.single_item_classes = {
            24, 25, 26, 27, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55,
            62, 63, 64, 65, 66, 67, 73, 74, 75, 76, 77, 78, 79, 80, 81
        }
        self.pairwise_precision_groups = [
            ["Backpack / Bag", "Charger / Power Adapter"],
            ["Smartphone", "Charger / Power Adapter"],
            ["Backpack / Bag", "Smartphone"]
        ]

    def register_class(self, class_id: int, label: str, category: str = "single_item"):
        """Dynamically registers or updates a class in the active configuration."""
        self.class_labels[class_id] = label
        if category == "case":
            self.case_classes.add(class_id)
            self.single_item_classes.discard(class_id)
            self.vehicle_classes.discard(class_id)
        elif category == "vehicle":
            self.vehicle_classes.add(class_id)
            self.single_item_classes.discard(class_id)
            self.case_classes.discard(class_id)
        elif category == "single_item":
            self.single_item_classes.add(class_id)
            self.case_classes.discard(class_id)
            self.vehicle_classes.discard(class_id)
        logger.info("Registered dynamic class %d: '%s' (category=%s)", class_id, label, category)

    def save_to_file(self, path: str = CONFIG_FILE_PATH):
        """Persists the active configuration to disk."""
        data = {
            "class_labels": {str(k): v for k, v in self.class_labels.items()},
            "categories": {
                "person_classes": [0],
                "case_classes": sorted(list(self.case_classes)),
                "vehicle_classes": sorted(list(self.vehicle_classes)),
                "single_item_classes": sorted(list(self.single_item_classes))
            },
            "thresholds": {
                "confidence_floor": self.confidence_floor,
                "confirmed_entity_standard": self.confirmed_entity_standard,
                "fire_confirmed_threshold": self.fire_confirmed_threshold,
                "fire_hazard_floor": self.fire_hazard_floor,
                "suspicious_confirmed_threshold": self.suspicious_confirmed_threshold,
                "ppe_confirmed_threshold": self.ppe_confirmed_threshold,
                "person_conf_threshold": self.person_conf_threshold,
                "case_conf_threshold": self.case_conf_threshold,
                "vehicle_conf_threshold": self.vehicle_conf_threshold,
                "item_conf_threshold": self.item_conf_threshold,
                "nms_iou_threshold": self.nms_iou_threshold,
                "face_candidate_min_score": self.face_candidate_min_score,
                "min_real_z_std": self.min_real_z_std,
                "liveness_pass_threshold": self.liveness_pass_threshold,
                "tracker_max_lost_frames": self.tracker_max_lost_frames,
                "tracker_iou_threshold": self.tracker_iou_threshold
            },
            "pairwise_precision_groups": self.pairwise_precision_groups
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("Saved dynamic class config to %s", path)


# Global singleton instance
_config_instance: Optional[VisionModelConfig] = None


def get_vision_config() -> VisionModelConfig:
    """Returns the active vision configuration singleton."""
    global _config_instance
    if _config_instance is None:
        _config_instance = VisionModelConfig.load_from_file()
    return _config_instance


def reload_vision_config() -> VisionModelConfig:
    """Forces reloading configuration from disk."""
    global _config_instance
    _config_instance = VisionModelConfig.load_from_file()
    return _config_instance


def update_vision_config(**kwargs) -> VisionModelConfig:
    """Dynamically updates active vision parameters at runtime without restart."""
    cfg = get_vision_config()
    for k, v in kwargs.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
            logger.info("Updated vision configuration parameter: %s = %s", k, v)
    return cfg
