"""Model Accuracy Evaluator & Promotion Gate Validator (Step 5)

Calculates the exact, published-benchmark numeric targets required before
any fine-tuned checkpoint can be promoted to production:
1. mAP@0.5 >= 0.75 (75%)
2. Case/unit recall >= 0.90 (90%)
3. False positive rate on empty scenes < 0.05 (5%)
4. Pairwise precision on visually similar pairs (Bag vs Charger vs Phone) >= 0.80 (80%)
"""

from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import logging
from datetime import datetime, timezone

from src.ml.model_registry import (
    ModelMetrics,
    GATE_MIN_MAP_50,
    GATE_MIN_CASE_RECALL,
    GATE_MAX_EMPTY_FP_RATE,
    GATE_MIN_PAIRWISE_PRECISION,
)

logger = logging.getLogger("secops.ml.evaluator")


def calculate_box_iou(boxA: List[float], boxB: List[float]) -> float:
    """Calculates Intersection over Union for [x, y, w, h] format."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[0] + boxA[2], boxB[0] + boxB[2])
    yB = min(boxA[1] + boxA[3], boxB[1] + boxB[3])

    inter_w = max(0.0, xB - xA)
    inter_h = max(0.0, yB - yA)
    inter_area = inter_w * inter_h

    boxA_area = boxA[2] * boxA[3]
    boxB_area = boxB[2] * boxB[3]
    union = boxA_area + boxB_area - inter_area

    if union <= 0:
        return 0.0
    return float(inter_area / union)


class AccuracyEvaluator:
    """Evaluates detection accuracy metrics across held-out test datasets."""

    @staticmethod
    def calculate_map50(
        ground_truths: List[List[Dict[str, Any]]],
        predictions: List[List[Dict[str, Any]]],
        iou_threshold: float = 0.50,
    ) -> float:
        """Computes mean Average Precision (mAP) at IoU 0.50 across all classes."""
        if not ground_truths or len(ground_truths) != len(predictions):
            return 0.0

        all_classes = set()
        for frame_gts in ground_truths:
            for gt in frame_gts:
                all_classes.add(gt.get("class_label"))

        if not all_classes:
            return 1.0  # No GT items to miss

        aps = []
        for cls_name in all_classes:
            total_gts = 0
            tp_list = []
            fp_list = []
            conf_list = []

            for frame_gts, frame_preds in zip(ground_truths, predictions):
                gts = [g for g in frame_gts if g.get("class_label") == cls_name]
                preds = [p for p in frame_preds if p.get("class_label") == cls_name]
                total_gts += len(gts)

                matched_gt = set()
                # Sort predictions by confidence descending
                preds_sorted = sorted(preds, key=lambda x: x.get("confidence", 0.0), reverse=True)

                for p in preds_sorted:
                    p_box = p.get("bbox", [0, 0, 0, 0])
                    conf = p.get("confidence", 0.0)
                    conf_list.append(conf)

                    best_iou = 0.0
                    best_gt_idx = -1
                    for g_idx, g in enumerate(gts):
                        if g_idx in matched_gt:
                            continue
                        iou = calculate_box_iou(p_box, g.get("bbox", [0, 0, 0, 0]))
                        if iou > best_iou:
                            best_iou = iou
                            best_gt_idx = g_idx

                    if best_iou >= iou_threshold and best_gt_idx >= 0:
                        tp_list.append(1)
                        fp_list.append(0)
                        matched_gt.add(best_gt_idx)
                    else:
                        tp_list.append(0)
                        fp_list.append(1)

            if total_gts == 0:
                continue

            if not tp_list:
                aps.append(0.0)
                continue

            # Calculate AP curve
            tp_cum = np.cumsum(tp_list)
            fp_cum = np.cumsum(fp_list)
            recalls = tp_cum / max(1, total_gts)
            precisions = tp_cum / np.maximum(1, (tp_cum + fp_cum))

            # 11-point interpolation or area under PR curve
            ap = float(np.trapz(precisions, recalls)) if len(recalls) > 1 else float(precisions[0] * recalls[0])
            aps.append(max(0.0, min(1.0, ap)))

        return round(float(np.mean(aps)), 4) if aps else 0.0

    @staticmethod
    def calculate_case_unit_recall(
        ground_truths: List[List[Dict[str, Any]]],
        predictions: List[List[Dict[str, Any]]],
        target_labels: Optional[List[str]] = None,
        iou_threshold: float = 0.40,
    ) -> float:
        """Calculates recall on operational retail merchandise (cases and retail single units)."""
        if target_labels is None:
            target_labels = ["case_full", "case_open", "single_unit", "Case / Carton", "Bottle", "Smartphone", "Backpack / Bag", "Charger / Power Adapter"]

        total_target_gts = 0
        detected_target_gts = 0

        for frame_gts, frame_preds in zip(ground_truths, predictions):
            target_gts = [g for g in frame_gts if any(t.lower() in str(g.get("class_label", "")).lower() for t in target_labels)]
            total_target_gts += len(target_gts)

            for gt in target_gts:
                g_box = gt.get("bbox", [0, 0, 0, 0])
                matched = False
                for p in frame_preds:
                    p_box = p.get("bbox", [0, 0, 0, 0])
                    if calculate_box_iou(g_box, p_box) >= iou_threshold:
                        matched = True
                        break
                if matched:
                    detected_target_gts += 1

        if total_target_gts == 0:
            return 1.0

        return round(detected_target_gts / total_target_gts, 4)

    @staticmethod
    def calculate_empty_scene_fp_rate(
        empty_scene_predictions: List[List[Dict[str, Any]]],
    ) -> float:
        """Calculates false positive rate on dedicated empty/background scenes (walls, empty tables)."""
        if not empty_scene_predictions:
            return 0.0

        frames_with_false_positives = 0
        for preds in empty_scene_predictions:
            if len(preds) > 0:
                frames_with_false_positives += 1

        return round(frames_with_false_positives / len(empty_scene_predictions), 4)

    @staticmethod
    def calculate_pairwise_precision(
        ground_truths: List[List[Dict[str, Any]]],
        predictions: List[List[Dict[str, Any]]],
        pair_labels: Optional[List[Tuple[str, str]]] = None,
        iou_threshold: float = 0.40,
    ) -> float:
        """Evaluates discrimination precision across visually-similar object pairs (e.g. Bag vs Charger vs Phone)."""
        if pair_labels is None:
            pair_labels = [
                ("Backpack / Bag", "Charger / Power Adapter"),
                ("Smartphone", "Charger / Power Adapter"),
                ("Backpack / Bag", "Smartphone"),
                ("Case / Carton", "Backpack / Bag"),
            ]

        pair_precisions = []

        for cls_a, cls_b in pair_labels:
            confusions = 0
            correct_classifications = 0

            for frame_gts, frame_preds in zip(ground_truths, predictions):
                for gt in frame_gts:
                    gt_lbl = str(gt.get("class_label", ""))
                    if cls_a.lower() not in gt_lbl.lower() and cls_b.lower() not in gt_lbl.lower():
                        continue

                    g_box = gt.get("bbox", [0, 0, 0, 0])
                    for p in frame_preds:
                        p_box = p.get("bbox", [0, 0, 0, 0])
                        if calculate_box_iou(g_box, p_box) >= iou_threshold:
                            pred_lbl = str(p.get("class_label", ""))
                            # If GT was A and predicted as B (or vice versa), count confusion
                            if (cls_a.lower() in gt_lbl.lower() and cls_b.lower() in pred_lbl.lower()) or \
                               (cls_b.lower() in gt_lbl.lower() and cls_a.lower() in pred_lbl.lower()):
                                confusions += 1
                            elif (cls_a.lower() in gt_lbl.lower() and cls_a.lower() in pred_lbl.lower()) or \
                                 (cls_b.lower() in gt_lbl.lower() and cls_b.lower() in pred_lbl.lower()):
                                correct_classifications += 1

            total_pair_evals = correct_classifications + confusions
            if total_pair_evals > 0:
                p_prec = correct_classifications / total_pair_evals
                pair_precisions.append(p_prec)

        if not pair_precisions:
            return 1.0

        return round(float(np.mean(pair_precisions)), 4)

    @classmethod
    def evaluate_test_suite(
        cls,
        ground_truths: List[List[Dict[str, Any]]],
        predictions: List[List[Dict[str, Any]]],
        empty_scene_predictions: List[List[Dict[str, Any]]],
        avg_latency_ms: float = 16.5,
    ) -> ModelMetrics:
        """Executes full evaluation and returns complete Step 5 ModelMetrics."""
        map_50 = cls.calculate_map50(ground_truths, predictions)
        recall = cls.calculate_case_unit_recall(ground_truths, predictions)
        empty_fp = cls.calculate_empty_scene_fp_rate(empty_scene_predictions)
        pair_prec = cls.calculate_pairwise_precision(ground_truths, predictions)

        now_str = datetime.now(timezone.utc).isoformat()
        total_eval_frames = len(ground_truths) + len(empty_scene_predictions)

        metrics = ModelMetrics(
            map_50=map_50,
            case_unit_recall=recall,
            empty_scene_fp_rate=empty_fp,
            pairwise_precision=pair_prec,
            latency_ms=avg_latency_ms,
            eval_dataset_size=total_eval_frames,
            evaluated_at=now_str,
        )

        logger.info(
            "Evaluation complete: mAP@0.5=%.3f (>=%.2f), Recall=%.3f (>=%.2f), EmptyFP=%.3f (<%.2f), PairPrec=%.3f (>=%.2f)",
            map_50, GATE_MIN_MAP_50, recall, GATE_MIN_CASE_RECALL, empty_fp, GATE_MAX_EMPTY_FP_RATE, pair_prec, GATE_MIN_PAIRWISE_PRECISION
        )
        return metrics

