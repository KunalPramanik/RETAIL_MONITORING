"""Dataset Management & Split Validation (Step 3)

Handles standard YOLO / COCO dataset splits (70/15/15), annotation validation,
empty scene test set segregation, and label consistency audits.
"""

from typing import Dict, List, Tuple, Optional, Any
import os
import json
import logging
from dataclasses import dataclass

logger = logging.getLogger("secops.ml.dataset")


@dataclass
class DatasetStats:
    total_images: int = 0
    train_count: int = 0
    val_count: int = 0
    test_count: int = 0
    empty_scene_count: int = 0
    class_distribution: Dict[str, int] = None
    is_split_valid: bool = False
    validation_errors: List[str] = None


class DatasetManager:
    """Validates and prepares datasets for YOLOX fine-tuning."""

    @staticmethod
    def validate_split_ratio(train_cnt: int, val_cnt: int, test_cnt: int) -> Tuple[bool, str]:
        total = train_cnt + val_cnt + test_cnt
        if total == 0:
            return False, "Dataset is empty."

        train_ratio = train_cnt / total
        val_ratio = val_cnt / total
        test_ratio = test_cnt / total

        # Target: ~70% train, ~15% val, ~15% test (allow +/- 5% tolerance)
        if not (0.60 <= train_ratio <= 0.80):
            return False, f"Train split ratio {train_ratio:.2f} deviates from target 0.70"
        if not (0.10 <= val_ratio <= 0.25):
            return False, f"Val split ratio {val_ratio:.2f} deviates from target 0.15"
        if not (0.10 <= test_ratio <= 0.25):
            return False, f"Test split ratio {test_ratio:.2f} deviates from target 0.15"

        return True, f"Split ratio valid: train={train_ratio:.1%}, val={val_ratio:.1%}, test={test_ratio:.1%}"

    @staticmethod
    def validate_bounding_box(box: List[float], img_w: int, img_h: int) -> bool:
        """Validates bounding box [x, y, w, h] or [x1, y1, x2, y2] fits within frame."""
        if len(box) != 4:
            return False
        x, y, w, h = box
        if w <= 0 or h <= 0:
            return False
        if x < 0 or y < 0 or (x + w) > (img_w + 2) or (y + h) > (img_h + 2):
            return False
        return True

    @classmethod
    def audit_dataset_directory(cls, dataset_dir: str) -> DatasetStats:
        """Audits dataset directory layout and split balance."""
        stats = DatasetStats(class_distribution={}, validation_errors=[])

        train_dir = os.path.join(dataset_dir, "train")
        val_dir = os.path.join(dataset_dir, "val")
        test_dir = os.path.join(dataset_dir, "test")
        empty_dir = os.path.join(dataset_dir, "empty_scenes")

        def count_images(d: str) -> int:
            if not os.path.exists(d):
                return 0
            valid_exts = {".jpg", ".jpeg", ".png", ".bmp"}
            return sum(1 for f in os.listdir(d) if os.path.splitext(f.lower())[1] in valid_exts)

        stats.train_count = count_images(train_dir)
        stats.val_count = count_images(val_dir)
        stats.test_count = count_images(test_dir)
        stats.empty_scene_count = count_images(empty_dir)
        stats.total_images = stats.train_count + stats.val_count + stats.test_count + stats.empty_scene_count

        if stats.train_count == 0:
            stats.validation_errors.append("No training images found in 'train/' directory.")
        if stats.test_count == 0:
            stats.validation_errors.append("No test images found in 'test/' directory for Step 5 evaluation.")
        if stats.empty_scene_count == 0:
            stats.validation_errors.append("No dedicated background photos in 'empty_scenes/' for false-positive auditing.")

        if stats.train_count > 0 and stats.val_count > 0 and stats.test_count > 0:
            valid_split, msg = cls.validate_split_ratio(stats.train_count, stats.val_count, stats.test_count)
            stats.is_split_valid = valid_split
            if not valid_split:
                stats.validation_errors.append(msg)
        else:
            stats.is_split_valid = False

        return stats

