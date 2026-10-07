# SEC-OPS 2.0 — PHASE 6 IMPLEMENTATION PLAN: FILE SPLITTING & MODULARIZATION

**Role:** Refactor Agent  
**Authorization:** Authorized by Lead/Coordinator Agent following 100% pass of Functional Phases 1–5 (46/46 tests green).  
**Objective:** Decompose oversized monolithic files (`src/api/cameras.py` ~1830 lines and `src/engine/camera_worker.py` ~1610 lines) into focused, single-responsibility modules while maintaining strict 100% backward compatibility (R2, R5) and zero regressions across the 46 test cases.

---

## 1. Modularization Scope & Decomposition Strategy

### 1.1 `src/api/cameras.py` (~1830 lines) -> Modular Breakdown
`src/api/cameras.py` currently couples HTTP endpoints, socket probing, RTSP normalization, frame decoding, and annotation overlays.
- **Extract to `src/api/camera_prober.py`**:
  - Socket network probing (`probe_camera_endpoint`, `check_port_open`, `ping_camera_host`).
  - RTSP URL normalization and candidate endpoint generation (`build_candidate_rtsp_endpoints`, `parse_rtsp_credentials`).
  - Connection diagnostics reporting (`generate_camera_diagnostic_dossier`).
- **Extract to `src/api/camera_stream_utils.py`**:
  - Live technical standby frame generation.
  - Overlay box formatting and stream visualizer helpers (`_build_overlay_boxes`).
  - Multipart MJPEG boundary stream generator.
- **Maintain in `src/api/cameras.py`**:
  - Clean FastAPI APIRouter definitions and REST route handlers (`router = APIRouter(...)`).
  - Re-export all extracted helper functions to preserve 100% backward compatibility for any existing consumers (R5).

### 1.2 `src/engine/camera_worker.py` (~1610 lines) -> Modular Breakdown
`src/engine/camera_worker.py` currently bundles worker lifecycle, per-camera motion detection, inference dispatch, and DB state persistence into a single file.
- **Extract to `src/engine/motion_detector.py`**:
  - `MotionDetector` class with dynamic OpenCV background subtraction and grayscale thresholding.
  - Per-camera motion cache, bounding box clustering, and event debounce tracking (`_check_motion`).
- **Extract to `src/engine/camera_inference_runner.py`**:
  - Inference watchdog execution (`_run_vision_and_face_inference`).
  - Model telemetry formatting and circuit breaker coordination.
- **Maintain in `src/engine/camera_worker.py`**:
  - `CameraWorker` class (background poller loop, concurrency limits, single-camera transaction isolation).
  - Public singleton `camera_worker = CameraWorker()`.
  - Re-export all classes and functions so external imports (`from src.engine.camera_worker import camera_worker`) remain completely unbroken.

---

## 2. Refactoring Protocol & Invariants (R2, R5, R13, R14)

1. **Pure Structural Refactoring**:
   - Zero modifications to business logic, API route paths, parameter names, or database queries.
   - All extracted functions preserve their exact signatures, type hints, and exception contracts.
2. **Backward-Compatible Re-Exports**:
   - Original modules (`cameras.py`, `camera_worker.py`) will import and expose all symbols from the new submodules.
3. **Step-by-Step PowerShell Execution**:
   - Step 1: Extract motion detection into `src/engine/motion_detector.py` and verify with pytest.
   - Step 2: Extract camera network probing and stream utilities into `src/api/camera_prober.py` and `src/api/camera_stream_utils.py`.
   - Step 3: Run full test suite (all 46 tests) in PowerShell and verify 0 regressions.
   - Step 4: Update `docs/REMEDIATION_TRACKER.md` and `docs/BASELINE.md`.

