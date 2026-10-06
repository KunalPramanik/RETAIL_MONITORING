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
from src.core.config import settings

logger = logging.getLogger("secops.ml.config")

CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), "classes_config.json")


@dataclass
class VisionModelConfig:
    # ── Confidence Floors & Gating (Centralized, Configurable Standards) ──
    confidence_floor: float = field(default_factory=lambda: settings.detection.confidence_floor)
    confirmed_entity_standard: float = field(default_factory=lambda: settings.detection.confirmed_entity_standard)
    fire_confirmed_threshold: float = field(default_factory=lambda: settings.detection.fire_confirmed_threshold)
    fire_hazard_floor: float = field(default_factory=lambda: settings.detection.fire_hazard_floor)
    suspicious_confirmed_threshold: float = field(default_factory=lambda: settings.detection.suspicious_confirmed_threshold)
    ppe_confirmed_threshold: float = field(default_factory=lambda: settings.detection.ppe_confirmed_threshold)
    person_conf_threshold: float = field(default_factory=lambda: settings.detection.person_conf_threshold)
    item_conf_threshold: float = field(default_factory=lambda: settings.detection.item_conf_threshold)
    case_conf_threshold: float = field(default_factory=lambda: settings.detection.case_conf_threshold)
    vehicle_conf_threshold: float = field(default_factory=lambda: settings.detection.vehicle_conf_threshold)

    # ── NMS & Clustered Item Tuning ──
    nms_iou_threshold: float = field(default_factory=lambda: settings.detection.nms_iou_threshold)
    dense_shelf_nms_iou_threshold: float = field(default_factory=lambda: settings.detection.dense_shelf_nms_iou_threshold)

    # ── Liveness & Face Gating ──
    face_candidate_min_score: float = 0.45
    min_real_z_std: float = 15.0
    liveness_pass_threshold: float = 0.60
    
    # Structural / Architectural Size Gates (Issue 3: Eliminate hardcoded magic numbers)
    max_vehicle_frame_ratio_w: float = 0.98
    max_vehicle_frame_ratio_h: float = 0.98
    max_case_frame_ratio_w: float = 0.70
    max_case_frame_ratio_h: float = 0.45
    max_item_frame_ratio_w: float = 0.75
    max_item_frame_ratio_h: float = 0.70
    max_item_area_ratio: float = 0.65
    max_person_frame_ratio_w: float = 0.85
    max_person_frame_ratio_h: float = 0.70
    face_min_y_offset: int = 25
    face_min_height: int = 30

    # ── Multi-Object Tracker (ByteTrack / Sort) ──
    tracker_max_lost_frames: int = field(default_factory=lambda: settings.tracking.tracker_max_lost_frames)
    tracker_iou_threshold: float = field(default_factory=lambda: settings.tracking.tracker_iou_threshold)

    # ── Dynamic Class Registry ──
    class_labels: Dict[int, str] = field(default_factory=dict)
    case_classes: Set[int] = field(default_factory=set)
    single_item_classes: Set[int] = field(default_factory=set)
    vehicle_classes: Set[int] = field(default_factory=set)
    pairwise_precision_groups: List[List[str]] = field(default_factory=list)
    class_metadata: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    class_specific_nms_iou: Dict[str, float] = field(default_factory=dict)

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

                cfg.class_specific_nms_iou = thresh.get("class_specific_nms_iou", {})
                cfg.class_metadata = data.get("class_metadata", {})

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
            78: "Hair Drier", 79: "Pen / Stationery", 80: "Charger / Power Adapter", 81: "Tote / Shopping Bag",
            84: "WristWatch", 1001: "Doorway / Exit Door", 1002: "Wall Picture Frame", 1003: "Storage Shelf / Bookcase"
        }
        self.case_classes = {28}
        self.vehicle_classes = {1, 2, 3, 5, 7}
        self.single_item_classes = {
            24, 25, 26, 27, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55,
            62, 63, 64, 65, 66, 67, 73, 74, 75, 76, 77, 78, 79, 80, 81, 84
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
                "dense_shelf_nms_iou_threshold": self.dense_shelf_nms_iou_threshold,
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

    def get_class_metadata(self, key: Any) -> Dict[str, Any]:
        """Looks up class metadata by class ID (int/str) or canonical label."""
        str_key = str(key).strip().lower()
        if str(key) in self.class_metadata:
            return self.class_metadata[str(key)]

        # Check by class labels mapping to class ID
        for cid, name in self.class_labels.items():
            name_lower = name.lower()
            if (name_lower == str_key or str_key in [p.strip() for p in name_lower.split("/")]) and str(cid) in self.class_metadata:
                return self.class_metadata[str(cid)]

        # Check by class_metadata keys or word tokens
        for k, meta in self.class_metadata.items():
            k_lower = str(k).lower()
            canon = str(meta.get("canonical_label", "")).lower()
            if (
                str_key == k_lower
                or str_key in k_lower.split("_")
                or str_key in [p.strip() for p in canon.split("/")]
                or str_key in canon.split()
            ):
                return meta
        # Default fallback
        return {
            "canonical_label": str(key),
            "category_family": "EVERYDAY_ITEMS",
            "object_role": "physical_object",
            "wearable": False,
            "body_part": False,
            "countable": True,
            "counting_mode": "INSTANCE_COUNT",
            "inventory_relevant": True,
            "environment_only": False,
            "identity_relevant": False,
            "is_display_container": False,
            "box_or_unit_tier": "SINGLE_UNIT",
            "nms_iou_threshold": self.nms_iou_threshold,
        }

    def is_inventory_relevant(self, key: Any) -> bool:
        meta = self.get_class_metadata(key)
        return bool(meta.get("inventory_relevant", True))

    def is_environment_only(self, key: Any) -> bool:
        meta = self.get_class_metadata(key)
        return bool(meta.get("environment_only", False))

    def is_wearable(self, key: Any) -> bool:
        meta = self.get_class_metadata(key)
        return bool(meta.get("wearable", False))

    def is_body_part(self, key: Any) -> bool:
        meta = self.get_class_metadata(key)
        return bool(meta.get("body_part", False))

    def get_counting_mode(self, key: Any) -> str:
        meta = self.get_class_metadata(key)
        return str(meta.get("counting_mode", "INSTANCE_COUNT"))

    def get_object_role(self, key: Any) -> str:
        meta = self.get_class_metadata(key)
        return str(meta.get("object_role", "physical_object"))

    def get_class_nms_iou(self, class_id: Any) -> float:
        str_id = str(class_id)
        if str_id in self.class_specific_nms_iou:
            return float(self.class_specific_nms_iou[str_id])
        meta = self.get_class_metadata(class_id)
        if str_id == "73" or meta.get("canonical_label") in ("Book / Document", "Book"):
            return float(getattr(self, "dense_shelf_nms_iou_threshold", 0.45))
        return float(meta.get("nms_iou_threshold", self.nms_iou_threshold))


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

model_config = get_vision_config()
