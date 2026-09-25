"""Continuous Model Auto-Curation & Shadow Benchmark Evaluator

Automates quality certification and zero-downtime hot-swapping for fine-tuned models:
1. Evaluates candidate model weights against golden validation sets and hard negatives.
2. Enforces the Zero-Regression Gate:
   - Candidate mAP must exceed production baseline by at least +1.5% (Delta mAP >= +0.015).
   - False positive rate on certified hard negatives (blank walls, posters, fixtures) MUST be strictly 0.0.
   - Inference latency must not regress by > 15%.
3. In-memory hot-swapping: updates active model registry without service disruption.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import os
import json
import logging
from datetime import datetime, timezone

from src.ml.model_registry import ModelRegistry

logger = logging.getLogger("secops.ml.autocurator")


@dataclass
class BenchmarkMetrics:
    map_50: float                         # mAP @ IoU 0.50
    map_50_95: float                      # mAP @ IoU 0.50:0.95
    precision: float
    recall: float
    hard_negative_false_positives: int    # Detections on certified background images (MUST BE 0)
    inference_latency_ms: float           # Per-frame inference time


@dataclass
class CurationDecision:
    candidate_version: str
    approved_for_production: bool
    status: str                           # "APPROVED_HOTSWAP", "REJECTED_REGRESSION", "REJECTED_FALSE_POSITIVES", "REJECTED_LATENCY"
    delta_map_50: float
    delta_latency_pct: float
    hard_negatives_passed: bool
    rejection_reasons: List[str]
    evaluation_summary: Dict[str, Any]


class ModelAutoCurator:
    """Shadow-evaluates fine-tuned models and enforces zero-regression promotion gates."""

    @classmethod
    def evaluate_candidate(
        cls,
        candidate_version: str,
        candidate_metrics: BenchmarkMetrics,
        baseline_metrics: Optional[BenchmarkMetrics] = None,
        min_map_improvement: float = 0.015,   # +1.5% mAP threshold
        max_latency_regression_pct: float = 15.0,
    ) -> CurationDecision:
        """Evaluates candidate model against current production baseline.

        Args:
            candidate_version: Version tag of the candidate model (e.g. 'v6.2-epoch10').
            candidate_metrics: Evaluated metrics for candidate.
            baseline_metrics: Metrics of current active production model (or defaults).
            min_map_improvement: Minimum required delta mAP@0.50.
            max_latency_regression_pct: Maximum allowed latency increase percentage.

        Returns:
            CurationDecision with promotion verdict and rejection diagnostics.
        """
        # Default baseline if not supplied
        base = baseline_metrics or BenchmarkMetrics(
            map_50=0.885,
            map_50_95=0.690,
            precision=0.910,
            recall=0.870,
            hard_negative_false_positives=0,
            inference_latency_ms=18.5,
        )

        rejection_reasons: List[str] = []

        # 1. Certified Hard Negative Invariant: Zero False Positives Allowed
        hard_neg_ok = candidate_metrics.hard_negative_false_positives == 0
        if not hard_neg_ok:
            rejection_reasons.append(
                f"HARD_NEGATIVE_FAILURE: Model generated {candidate_metrics.hard_negative_false_positives} "
                f"false positive detections on certified background images (must be strictly 0)."
            )

        # 2. mAP Improvement Gate
        delta_map = round(candidate_metrics.map_50 - base.map_50, 4)
        if delta_map < min_map_improvement:
            rejection_reasons.append(
                f"INSUFFICIENT_MAP_GAIN: Candidate mAP@50 is {candidate_metrics.map_50:.3f} "
                f"(gain {delta_map:+.3f} vs baseline {base.map_50:.3f}, required: >= +{min_map_improvement:.3f})."
            )

        # 3. Latency Regression Gate
        latency_change_pct = round(
            ((candidate_metrics.inference_latency_ms - base.inference_latency_ms) / base.inference_latency_ms) * 100.0,
            1
        )
        if latency_change_pct > max_latency_regression_pct:
            rejection_reasons.append(
                f"LATENCY_REGRESSION: Inference latency increased by {latency_change_pct:.1f}% "
                f"({candidate_metrics.inference_latency_ms:.1f}ms vs baseline {base.inference_latency_ms:.1f}ms, "
                f"threshold: <= +{max_latency_regression_pct:.1f}%)."
            )

        # Determine final decision
        approved = len(rejection_reasons) == 0
        if approved:
            status = "APPROVED_HOTSWAP"
        elif not hard_neg_ok:
            status = "REJECTED_FALSE_POSITIVES"
        elif latency_change_pct > max_latency_regression_pct:
            status = "REJECTED_LATENCY"
        else:
            status = "REJECTED_REGRESSION"

        summary = {
            "candidate_version": candidate_version,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "candidate_map_50": candidate_metrics.map_50,
            "baseline_map_50": base.map_50,
            "delta_map_50": delta_map,
            "candidate_latency_ms": candidate_metrics.inference_latency_ms,
            "baseline_latency_ms": base.inference_latency_ms,
            "latency_change_pct": latency_change_pct,
            "hard_negative_errors": candidate_metrics.hard_negative_false_positives,
        }

        logger.info(
            "AutoCurator evaluated %s: status=%s, delta_map=%+.4f, approved=%s",
            candidate_version, status, delta_map, approved
        )

        return CurationDecision(
            candidate_version=candidate_version,
            approved_for_production=approved,
            status=status,
            delta_map_50=delta_map,
            delta_latency_pct=latency_change_pct,
            hard_negatives_passed=hard_neg_ok,
            rejection_reasons=rejection_reasons,
            evaluation_summary=summary,
        )

    @classmethod
    def apply_hot_swap_if_approved(
        cls,
        decision: CurationDecision,
        candidate_weights_path: str,
        model_name: str = "scene_object_detector",
    ) -> bool:
        """Applies zero-downtime weight hot-swap if decision was APPROVED_HOTSWAP."""
        if not decision.approved_for_production:
            logger.warning("Hot-swap rejected for %s: %s", decision.candidate_version, decision.rejection_reasons)
            return False

        if not os.path.exists(candidate_weights_path):
            logger.error("Weights file does not exist at %s", candidate_weights_path)
            return False

        # Register in ModelRegistry
        registry = ModelRegistry.get_instance()
        mv = registry.register_model(
            model_version=decision.candidate_version,
            model_name=model_name,
            weights_path=candidate_weights_path,
            notes=f"Auto-curated hot-swap model {decision.candidate_version}",
        )
        registry.promote_to_production(mv.model_version, bypass_gate=True)
        logger.info("Successfully hot-swapped production model '%s' to %s", model_name, candidate_weights_path)
        return True
