"""Continuous Improvement & Active Learning Loop (Step 6)

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

            logger.info("Successfully curated candidate %s with %d verified annotations.",
                        candidate_id, len(verified_boxes))
            return True, f"Successfully curated {candidate_id} for next fine-tuning cycle."
        except Exception as e:
            logger.error("Error submitting annotation: %s", e)
            return False, str(e)


active_learning_service = ActiveLearningService.get_instance()

