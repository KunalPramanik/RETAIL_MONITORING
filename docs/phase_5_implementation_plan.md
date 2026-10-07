# SEC-OPS 2.0 — PHASE 5 IMPLEMENTATION PLAN: CV / ML PIPELINE CORRECTNESS & ANTI-HALLUCINATION

**Role:** CV/ML Agent  
**Coordinator Authorization:** Phase 4 Complete, Phase 5 Authorized to Begin  
**Objective:** Audit and harden all Computer Vision and Machine Learning inference pipelines against hallucination, fabricated detections, and hardcoded confidence values. Ensure full compliance with R4 (zero simulation) and R6 (typed error states) across vision, tracking, face recognition, OCR, and multi-sensor fusion.

---

## 1. Targeted Subsystems & Scope

### 1.1 `src/ml/level1_detection/vision_service.py` (Object Detection)
- **Invariant:** When passed a blank, black, corrupted, or all-zero frame matrix, the detection pipeline MUST return `detections = []`, `vision_confidence = 0.0`, and NO synthetic bounding boxes or labels.
- **Dynamic Thresholds:** Confidence threshold must strictly follow `settings.detection.min_confidence` (default 0.40) and NMS threshold must follow `settings.detection.nms_threshold`.

### 1.2 `src/ml/level5_tracking/tracker_service.py` & `tracker.py` (Multi-Object Tracking)
- **Invariant:** ByteTrack tracker must handle sequences of zero-detection frames gracefully. Lost tracks must be pruned when `lost_frame_count >= settings.tracking.max_lost_frames`.
- **Dynamic Thresholds:** `track_thresh`, `match_thresh`, and `track_buffer` must load from `settings.tracking` rather than hardcoded magic numbers.

### 1.3 `src/ml/face_recognition/face_service.py` (Biometrics)
- **Invariant:** When presented with blank or faceless frames, face candidate detection must return empty candidates, `face_confidence = 0.0`, and never match against enrolled employee database.
- **Dynamic Thresholds:** Match threshold must use `settings.biometric.face_match_threshold` (default 0.65).

### 1.4 `src/ml/ocr/invoice_ocr_service.py` (Document OCR)
- **Invariant:** Blank or non-text document images must return `extraction_confidence = 0.0`, empty SKU line items, and typed status `OCR_UNCERTAIN` or `UNREADABLE_IMAGE`. Zero hallucinated vendors (e.g. "Rajesh Kumar") or synthetic line items.

### 1.5 `src/engine/fusion.py` (Multi-Sensor Consensus)
- **Invariant:** When vision returns `vision_confidence = 0.0` or empty detections, fusion must operate in degraded single/dual-channel mode with bounded confidence ($\le 0.75$), without injecting default 0.95 fallback confidence.

---

## 2. Step-by-Step Execution Plan

### Step 1: Codebase Audit & Hardening
1. Inspect `src/ml/level1_detection/vision_service.py` for any remaining fallback confidence assignments or synthetic boxes. Ensure settings integration.
2. Inspect `src/ml/level5_tracking/tracker_service.py` for track lifecycle management and settings linkage.
3. Inspect `src/ml/face_recognition/face_service.py` for blank-image safety and `settings.biometric` integration.
4. Inspect `src/ml/ocr/invoice_ocr_service.py` for blank image handling and zero synthetic fallback text.
5. Inspect `src/engine/fusion.py` to ensure vision degradation does not hallucinate default operational confidence.

### Step 2: Implementation of Comprehensive Test Suite
Create `tests/test_phase5_cv_ml.py` covering:
- `test_vision_service_blank_frame_zero_detections`: Blank numpy frame returns 0 detections and 0.0 confidence.
- `test_vision_service_dynamic_threshold_filtering`: Threshold filter respects dynamic `settings.detection.min_confidence`.
- `test_bytetrack_zero_detection_track_pruning`: Tracker prunes tracks after `max_lost_frames` without ghosting.
- `test_face_service_blank_frame_no_match`: Face service on blank frame returns 0 detections and no enrolled match.
- `test_invoice_ocr_blank_image_zero_hallucinations`: Invoice OCR returns 0 confidence and empty items on blank input.
- `test_fusion_engine_vision_absence_degradation`: Consensus fusion with 0 vision confidence gracefully degrades and flags discrepancy.

### Step 3: PowerShell Execution & Regression Verification
- Run `tests/test_phase5_cv_ml.py` in PowerShell.
- Run the full test suite (`pytest -v`) to ensure 100% pass rate with zero regressions.

### Step 4: Documentation & Status Updates
- Update `docs/REMEDIATION_TRACKER.md` with Phase 5 completion.
- Update `docs/BASELINE.md` with new test counts.
- Report Phase 5 completion to Lead/Coordinator Agent.

