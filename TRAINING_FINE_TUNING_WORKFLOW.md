# SEC-OPS V8 — Continuous Training & Fine-Tuning Pipeline

## 1. Safety & Production Integrity Policy

**CRITICAL RULE**: The SEC-OPS V8 production vision models **NEVER** automatically retrain themselves or auto-deploy unvalidated weights directly into live inference.

Every model deployment follows a strict human-curated and gate-validated lifecycle:

```text
REAL CAMERA DETECTION
          ↓
TRIGGER CONDITION:
- Unknown / Unsupported Class
- Low Confidence (< 0.60)
- Operator Recount Correction (is_correct=False)
- Alert Discrepancy Snapshot
          ↓
CANDIDATE HARVEST (Snapshot + Metadata saved to /data/active_learning/candidates/)
          ↓
HUMAN LABELING & CURATION CONSOLE (/api/ml/active-learning/candidates/{id}/curate)
          ↓
VERSIONED TRAINING DATASET (/data/training/datasets/v{N}/)
          ↓
CONTROLLED FINE-TUNING EXECUTION (/api/ml/training/start)
          ↓
ACCURACY EVALUATOR & PROMOTION GATES:
- mAP@0.50 >= 0.8800
- Case/Unit Recall >= 0.9200
- Empty Scene False Positive Rate <= 0.0150
- Inference Latency <= 45ms
          ↓
SHADOW DEPLOYMENT (25% Traffic Evaluation without Egress Impact)
          ↓
EXECUTIVE APPROVAL GATE (/api/ml/models/promote)
          ↓
LIVE PRODUCTION DEPLOYMENT (Instant Zero-Downtime Hot-Reload)
          ↓
ONE-CLICK ROLLBACK (/api/ml/models/rollback)
```

---

## 2. Active Learning Candidate Harvester (Phases 9 & 28)

When edge inference detects an object whose confidence falls below standard acceptance floors or whose visual features suggest an unsupported category:
1. The raw uncompressed camera frame is stored with high fidelity in `/data/active_learning/candidates/`.
2. A JSON manifest records camera ID, timestamp, model version, and predicted bounding boxes.
3. The candidate is tagged with its trigger reason:
   - `LOW_CONFIDENCE`: Optical ambiguity or unusual lighting.
   - `HUMAN_CORRECTION`: Operator corrected the AI proposed baseline count.
   - `UNKNOWN_OBJECT`: Classification taxonomy gap requiring new class registration.
   - `HARD_NEGATIVE`: Empty scene background where false positives occurred.

---

## 3. Dataset Manager & Class Expansion

New classes are registered dynamically via `POST /api/ml/classes/register` without restarting backend processes:
* Classes belong to specific categories: `single_item`, `case`, or `vehicle`.
* The dataset manager partitions curated samples into standard training, validation, and test splits (70% train / 15% val / 15% test).
* Augmentation pipelines simulate warehouse lighting variations, camera motion blur, and partial occlusions.

---

## 4. Model Registry & Shadow Deployment Architecture

The `ModelRegistry` maintains strict version control over all deployed artifacts:
* **Production Model**: Serves 100% of live exit lane authorization checks.
* **Shadow Model**: Evaluates identical incoming camera frames asynchronously (up to 25% traffic sampling) to measure real-world inference parity and latency without impacting physical turnstiles or customer passage.
* **Instant Rollback**: If a newly promoted model displays drift or unexpected false alarms, `POST /api/ml/models/rollback` atomically reverts the active production pointer to the last verified stable checkpoint.
