"""Shadow Deployment Service

Runs candidate vision models in parallel shadow mode on a configurable percentage
of live camera frames. Logs candidate detections side-by-side with production
model outputs to evaluate real-world production performance before promotion.
Guarantees strictly zero interference with turnstiles, database alerts, or verdicts.
"""

from typing import Dict, List, Optional, Any
import time
import random
import logging
import onnxruntime as ort
import numpy as np

from src.ml.model_registry import ModelRegistry

logger = logging.getLogger("secops.ml.shadow")


class ShadowDeploymentService:
    """Orchestrates safe, non-interfering shadow inference for candidate models."""

    _instance: Optional["ShadowDeploymentService"] = None

    def __init__(self):
        self.registry = ModelRegistry.get_instance()
        self._shadow_session: Optional[ort.InferenceSession] = None
        self._current_shadow_version: Optional[str] = None
        self._telemetry_history: List[Dict[str, Any]] = []
        self._max_history: int = 100

    @classmethod
    def get_instance(cls) -> "ShadowDeploymentService":
        if cls._instance is None:
            cls._instance = ShadowDeploymentService()
        return cls._instance

    def _get_shadow_session(self) -> Optional[ort.InferenceSession]:
        shadow_model = self.registry.get_shadow_model()
        if not shadow_model:
            self._shadow_session = None
            self._current_shadow_version = None
            return None

        if self._shadow_session is None or self._current_shadow_version != shadow_model.model_version:
            try:
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 2
                opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                self._shadow_session = ort.InferenceSession(
                    shadow_model.weights_path,
                    sess_options=opts,
                    providers=["CPUExecutionProvider"]
                )
                self._current_shadow_version = shadow_model.model_version
                logger.info("Initialized shadow inference session for %s", shadow_model.model_version)
            except Exception as e:
                logger.error("Failed to load shadow model session: %s", e)
                self._shadow_session = None

        return self._shadow_session

    def should_sample_frame(self) -> bool:
        """Determines whether the current frame should be routed to shadow inference."""
        if not self.registry.active_shadow_version:
            return False
        pct = self.registry.shadow_traffic_pct
        if pct <= 0.0:
            return False
        if pct >= 100.0:
            return True
        return (random.random() * 100.0) <= pct

    def evaluate_shadow_frame(
        self,
        img: np.ndarray,
        production_detections: List[Dict[str, Any]],
        camera_id: str = "CAM-UNKNOWN",
    ) -> Optional[Dict[str, Any]]:
        """Executes candidate model inference in shadow mode and logs side-by-side comparison."""
        if not self.should_sample_frame():
            return None

        session = self._get_shadow_session()
        if session is None:
            return None

        t0 = time.perf_counter()
        try:
            # We import VisionInferenceService dynamically to avoid circular import
            from src.ml.vision_service import VisionInferenceService

            input_tensor, ratio, _ = VisionInferenceService._preprocess_frame(img)
            raw_out = np.asarray(session.run(None, {"images": input_tensor[None, ...]})[0], dtype=np.float32)
            decoded = VisionInferenceService._decode_yolox_grid(raw_out)[0]

            scores = decoded[:, 4:5] * decoded[:, 5:]
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)

            # Extract peak class signals above 0.25
            shadow_candidate_count = int(np.sum(scores.max(axis=1) >= 0.25))

            comparison = {
                "timestamp": time.time(),
                "camera_id": camera_id,
                "production_version": self.registry.active_production_version,
                "shadow_version": self._current_shadow_version,
                "production_detections_count": len(production_detections),
                "shadow_candidates_count": shadow_candidate_count,
                "latency_ms": latency_ms,
                "agreement": abs(len(production_detections) - shadow_candidate_count) <= 1,
            }

            self._telemetry_history.append(comparison)
            if len(self._telemetry_history) > self._max_history:
                self._telemetry_history.pop(0)

            logger.debug(
                "Shadow telemetry [%s]: Prod=%d vs Shadow=%d (latency=%.1fms)",
                camera_id, len(production_detections), shadow_candidate_count, latency_ms
            )
            return comparison
        except Exception as e:
            logger.debug("Shadow evaluation error: %s", e)
            return None

    def get_telemetry(self) -> List[Dict[str, Any]]:
        """Returns recent shadow mode comparison logs."""
        return list(reversed(self._telemetry_history))


shadow_service = ShadowDeploymentService.get_instance()

