"""Continuous Improvement & Active Learning Loop

Captures sub-floor near-threshold detections (0.10 - 0.49) and operator-flagged
frames into an active learning dataset queue. Provides curation, labeling,
and accuracy drift monitoring over rolling operational time windows.
"""

from typing import Dict, List, Optional, Any, Tuple
import os
import json
import time
import cv2
import numpy as np
import logging
from datetime import datetime, timezone

logger = logging.getLogger("secops.ml.active_learning")

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "active_learning"))
CANDIDATES_DIR = os.path.join(DATA_DIR, "candidates")
CURATED_DIR = os.path.join(DATA_DIR, "curated")


class ActiveLearningService:
    """Manages active learning candidate extraction and accuracy drift monitoring."""

    _instance: Optional["ActiveLearningService"] = None

    def __init__(self):
        os.makedirs(CANDIDATES_DIR, exist_ok=True)
        os.makedirs(CURATED_DIR, exist_ok=True)
        self._confidence_window: List[float] = []
        self._max_confidence_window: int = 1000

    @classmethod
    def get_instance(cls) -> "ActiveLearningService":
        if cls._instance is None:
            cls._instance = ActiveLearningService()
        return cls._instance

    def log_confidence(self, conf: float):
        """Records confidence score for real-time drift monitoring."""
        if conf > 0:
            self._confidence_window.append(conf)
            if len(self._confidence_window) > self._max_confidence_window:
                self._confidence_window.pop(0)

    def check_accuracy_drift(self, baseline_median: float = 0.85) -> Dict[str, Any]:
        """Detects whether production model confidence is drifting below expected baseline."""
        if len(self._confidence_window) < 30:
            return {
                "has_drift": False,
                "samples": len(self._confidence_window),
                "message": "Insufficient data to evaluate drift (< 30 frames)."
            }

        curr_median = float(np.median(self._confidence_window))
        curr_mean = float(np.mean(self._confidence_window))
        pct_drop = (baseline_median - curr_median) / max(0.01, baseline_median)

        # Drift triggered if median confidence drops by more than 12%
        has_drift = pct_drop > 0.12
        return {
            "has_drift": has_drift,
            "current_median_conf": round(curr_median, 3),
            "current_mean_conf": round(curr_mean, 3),
            "baseline_median": baseline_median,
            "percentage_drop": round(pct_drop * 100, 1),
            "samples": len(self._confidence_window),
            "recommendation": "Trigger fine-tuning review and dataset expansion" if has_drift else "Model performing within normal confidence bounds."
        }

    def capture_candidate_frame(
        self,
        frame_bytes: bytes,
        camera_id: str,
        proposals: List[Dict[str, Any]],
        reason: str = "sub_floor_confidence",
    ) -> Optional[str]:
        """Saves a frame with low-confidence proposals for human review and retraining."""
        if not frame_bytes or len(frame_bytes) < 100:
            return None

        timestamp = int(time.time() * 1000)
        candidate_id = f"cand_{camera_id}_{timestamp}"
        img_filename = f"{candidate_id}.jpg"
        meta_filename = f"{candidate_id}.json"

        img_path = os.path.join(CANDIDATES_DIR, img_filename)
        meta_path = os.path.join(CANDIDATES_DIR, meta_filename)

        try:
            with open(img_path, "wb") as f:
                f.write(frame_bytes)

            meta = {
                "candidate_id": candidate_id,
                "camera_id": camera_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": reason,
                "proposals": proposals,
                "status": "pending_review",
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)

            logger.info("Captured active learning candidate %s (reason: %s)", candidate_id, reason)
            return candidate_id
        except Exception as e:
            logger.error("Failed to capture candidate frame: %s", e)
            return None

    def list_pending_candidates(self) -> List[Dict[str, Any]]:
        """Returns all pending active learning review candidates."""
        candidates = []
        if not os.path.exists(CANDIDATES_DIR):
            return candidates

        for fname in os.listdir(CANDIDATES_DIR):
            if fname.endswith(".json"):
                fpath = os.path.join(CANDIDATES_DIR, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    img_name = f"{data.get('candidate_id')}.jpg"
                    data["image_url"] = f"/api/ml/active-learning/image/{img_name}"
                    candidates.append(data)
                except Exception as e:
                    logger.debug("Error reading %s: %s", fpath, e)

        return sorted(candidates, key=lambda x: x.get("timestamp", ""), reverse=True)

    def submit_annotation(
        self,
        candidate_id: str,
        verified_boxes: List[Dict[str, Any]],
        notes: str = "",
    ) -> Tuple[bool, str]:
        """Submits human-verified bounding boxes and moves sample to curated dataset pool."""
        meta_path = os.path.join(CANDIDATES_DIR, f"{candidate_id}.json")
        img_path = os.path.join(CANDIDATES_DIR, f"{candidate_id}.jpg")

        if not os.path.exists(meta_path) or not os.path.exists(img_path):
            return False, f"Candidate '{candidate_id}' not found."

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            is_hard_neg = len(verified_boxes) == 0
            data["is_hard_negative"] = is_hard_neg
            data["status"] = "curated"
            data["curated_at"] = datetime.now(timezone.utc).isoformat()
            data["verified_boxes"] = verified_boxes
            data["curator_notes"] = notes

            curated_meta_path = os.path.join(CURATED_DIR, f"{candidate_id}.json")
            curated_img_path = os.path.join(CURATED_DIR, f"{candidate_id}.jpg")

            with open(curated_meta_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            # Move image
            os.replace(img_path, curated_img_path)
            os.remove(meta_path)

            tag_msg = "HARD NEGATIVE (zero-box background)" if is_hard_neg else f"{len(verified_boxes)} verified annotations"
            logger.info("Successfully curated candidate %s as %s.", candidate_id, tag_msg)
            return True, f"Successfully curated {candidate_id} for next fine-tuning cycle ({tag_msg})."
        except Exception as e:
            logger.error("Error submitting annotation: %s", e)
            return False, str(e)

    def ingest_hard_negative(
        self,
        frame_bytes: bytes,
        camera_id: str,
        scene_description: str = "Empty scene / background",
    ) -> Optional[str]:
        """Ingests a verified empty scene / background frame as a Hard Negative sample.

        Hard negatives teach the deep-learning model to output 0 detections on bare walls,
        empty shelves, shadows, and posters, completely eliminating fake detections.
        """
        if not frame_bytes or len(frame_bytes) < 100:
            return None

        timestamp = int(time.time() * 1000)
        candidate_id = f"hardneg_{camera_id}_{timestamp}"
        img_filename = f"{candidate_id}.jpg"
        meta_filename = f"{candidate_id}.json"

        img_path = os.path.join(CURATED_DIR, img_filename)
        meta_path = os.path.join(CURATED_DIR, meta_filename)

        try:
            with open(img_path, "wb") as f:
                f.write(frame_bytes)

            meta = {
                "candidate_id": candidate_id,
                "camera_id": camera_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "curated_at": datetime.now(timezone.utc).isoformat(),
                "reason": "hard_negative_background",
                "is_hard_negative": True,
                "verified_boxes": [],
                "curator_notes": f"Hard negative sample: {scene_description}",
                "status": "curated",
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)

            logger.info("Ingested hard negative sample %s for camera %s (%s)",
                        candidate_id, camera_id, scene_description)
            return candidate_id
        except Exception as e:
            logger.error("Failed to ingest hard negative frame: %s", e)
            return None

    def list_reviewed_samples(self) -> List[Dict[str, Any]]:
        """Returns all human-curated and verified samples ready for fine-tuning."""
        curated: List[Dict[str, Any]] = []
        if not os.path.exists(CURATED_DIR):
            return curated
        for fname in os.listdir(CURATED_DIR):
            if fname.endswith(".json"):
                fpath = os.path.join(CURATED_DIR, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    curated.append(data)
                except Exception as e:
                    logger.debug("Error reading %s: %s", fpath, e)
        return sorted(curated, key=lambda x: x.get("curated_at", ""), reverse=True)

    def export_to_yolo_dataset(
        self,
        output_dir: Optional[str] = None,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
    ) -> Dict[str, Any]:
        """Exports all curated samples and hard negatives into standardized YOLO format.

        Structure:
          images/train, images/val, images/test
          labels/train, labels/val, labels/test
          dataset.yaml
        """
        import shutil
        target_root = output_dir or os.path.join(DATA_DIR, "yolo_dataset")
        os.makedirs(target_root, exist_ok=True)

        splits = ["train", "val", "test"]
        for s in splits:
            os.makedirs(os.path.join(target_root, "images", s), exist_ok=True)
            os.makedirs(os.path.join(target_root, "labels", s), exist_ok=True)

        samples = self.list_reviewed_samples()
        if not samples:
            return {"success": False, "message": "No curated samples available to export."}

        # Deterministic split
        n_total = len(samples)
        n_train = max(1, int(n_total * train_ratio))
        n_val = max(1, int(n_total * val_ratio)) if n_total >= 3 else 0

        split_assignment = {}
        for idx, s in enumerate(samples):
            if idx < n_train:
                split_assignment[s["candidate_id"]] = "train"
            elif idx < (n_train + n_val):
                split_assignment[s["candidate_id"]] = "val"
            else:
                split_assignment[s["candidate_id"]] = "test"

        hard_neg_count = 0
        annotated_count = 0

        for s in samples:
            cand_id = s["candidate_id"]
            split = split_assignment.get(cand_id, "train")
            src_img = os.path.join(CURATED_DIR, f"{cand_id}.jpg")
            if not os.path.exists(src_img):
                continue

            dst_img = os.path.join(target_root, "images", split, f"{cand_id}.jpg")
            dst_label = os.path.join(target_root, "labels", split, f"{cand_id}.txt")
            shutil.copyfile(src_img, dst_img)

            # Get image dimensions for normalized coordinates
            img = cv2.imread(src_img)
            h, w = img.shape[:2] if img is not None else (480, 640)

            boxes = s.get("verified_boxes", [])
            is_hn = s.get("is_hard_negative", False) or len(boxes) == 0

            lines = []
            if not is_hn:
                annotated_count += 1
                for b in boxes:
                    cid = int(b.get("class_id", 0))
                    bbox = b.get("bbox", [0, 0, 0, 0])
                    bx, by, bw, bh = bbox
                    cx = (bx + bw / 2.0) / max(1.0, float(w))
                    cy = (by + bh / 2.0) / max(1.0, float(h))
                    norm_w = bw / max(1.0, float(w))
                    norm_h = bh / max(1.0, float(h))
                    lines.append(f"{cid} {cx:.6f} {cy:.6f} {norm_w:.6f} {norm_h:.6f}")
            else:
                hard_neg_count += 1

            with open(dst_label, "w", encoding="utf-8") as lf:
                lf.write("\n".join(lines) + ("\n" if lines else ""))

        # Create dataset.yaml
        from src.ml.model_config import get_vision_config
        cfg = get_vision_config()
        names_dict = {int(k): str(v) for k, v in cfg.class_labels.items()}
        yaml_content = f"""# Auto-generated YOLO dataset definition
path: {target_root}
train: images/train
val: images/val
test: images/test

names:
"""
        for cid, cname in sorted(names_dict.items()):
            yaml_content += f"  {cid}: \"{cname}\"\n"

        yaml_path = os.path.join(target_root, "dataset.yaml")
        with open(yaml_path, "w", encoding="utf-8") as yf:
            yf.write(yaml_content)

        return {
            "success": True,
            "dataset_root": target_root,
            "total_samples": n_total,
            "train_count": n_train,
            "val_count": n_val,
            "test_count": n_total - n_train - n_val,
            "hard_negative_count": hard_neg_count,
            "annotated_count": annotated_count,
            "yaml_config": yaml_path,
        }


active_learning_service = ActiveLearningService.get_instance()

