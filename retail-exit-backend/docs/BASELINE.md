# SEC-OPS 2.0 — ARCHITECTURAL BASELINE (PHASE 0–5 AUDIT & VERIFICATION)

**Generated:** 2026-10-07  
**Auditor / Role:** Lead/Coordinator Agent  
**Objective:** Complete architectural baseline and empirical test verification through Phase 5.

---

## 1. System Architecture & Tech Stack

### 1.1 Backend (`retail-exit-backend`)
- **Runtime:** Python 3.11 (`.venv/Scripts/python.exe`)
- **Web Framework:** FastAPI 0.115.0 with Uvicorn ASGI server
- **Database ORM:** SQLAlchemy 2.0.35 (Async) + aiosqlite / asyncpg
- **Validation & Settings:** Pydantic 2.9.0, Pydantic-Settings 2.5.0
- **Computer Vision & Inference:** OpenCV (cv2 4.10.0), NumPy, SciPy (YOLOX ONNX, MediaPipe / InsightFace ArcFace face embeddings, RapidOCR)
- **Real-Time Communication:** WebSockets + Redis Pub/Sub cluster fan-out (`secops:events:broadcast`)
- **Industrial Automation:** Modbus-TCP PLC gateway driver for physical turnstile locking (`AsyncModbusTCPDriver`)
- **Security:** OAuth2 Password Bearer JWT (`HS256`), bcrypt password hashing, sliding-window rate limiting (`RateLimiter`)

### 1.2 Frontend (`retail-exit-nextjs`)
- **Runtime:** Node.js, Next.js 16.3.8 (React 19, Turbopack)
- **Styling:** Tailwind CSS, Lucide icons
- **State & Streaming:** Real-time WebSocket live feed (`/ws/live`), resilient fallback polling (30s)
- **Pages (13 Total):**
  - `/`: Live Control Room Overview (real-time KPIs, live camera grids, recent alerts)
  - `/alerts`: Loss Prevention Incident Queue & Supervisor Disposition Workflow
  - `/employees`: Staff Face Recognition Directory & Access Logs
  - `/employees/[employeeId]`: Employee Biometric Detail & Crossing History
  - `/events`: Exit Verification Event Ledger
  - `/events/[eventId]`: Event Detail, Multi-Sensor Breakdown, Bill Comparison
  - `/invoices`: Manifest & Invoice Bill OCR Ingestion and Status
  - `/products`: Inventory Catalog, SKU Registry, Nominal Pack Weights
  - `/reports`: Executive Shrinkage, Theft Discrepancy & Fleet Compliance Reports
  - `/settings`: Platform System Configuration
  - `/settings/cameras`: Surveillance Camera Fleet Management & Stream Pairing
  - `/settings/thresholds`: Anomaly Detection, Weight Drift & Alarm Thresholds
  - `/_not-found`: 404 Route

---

## 2. Active vs Dead Modules & Bloat Inventory (F15)

### 2.1 Active Production Modules
- `src/main.py`: Application entrypoint, lifecycle hooks, WebSocket live gateway (`/ws/live`), Prometheus metrics (`/metrics`), health check (`/health`).
- `src/core/config.py`: Centralized environment and subsystem configuration (`DetectionConfig`, `TrackingConfig`, `TripwireConfig`, `FusionConfig`, `RateLimitConfig`, `CameraConfig`, `VerdictConfig`, `BiometricConfig`, `MotionConfig`, `WebSocketConfig`).
- `src/core/rate_limit.py`: Sliding-window rate limiter (Redis + in-memory fallback).
- `src/api/`: REST routing modules (`auth.py`, `cameras.py`, `alerts.py`, `events.py`, `invoices.py`, `products.py`, `employees.py`, `kpis.py`, `lanes.py`, `reports.py`, `discovery.py`, `ingest.py`, `material_flow.py`, `advanced_routes.py`, `dispatch.py`, `forensics_routes.py`).
- `src/engine/`:
  - `camera_worker.py`: Background RTSP capture, motion detection, and periodic camera monitor.
  - `circuit_breaker.py`: 3-state inference circuit breaker (CLOSED, OPEN, HALF-OPEN).
  - `fusion.py` & `sensor_fusion.py`: Tri-sensor consensus (Vision + RFID + Weight scale) with Bayesian degradation.
  - `tripwire_engine.py`: Directional line crossing, biometric gate verification, and anti-tailgating.
  - `alarm.py`: Industrial alarm coordinator (Siren, Strobe, Turnstile interlock, TTS).
  - `hardware_interlock.py`: Modbus TCP relay actuator.
  - `manifest_ingestion_daemon.py`: OCR waybill/bill parsing daemon.
  - `stream_manager.py`: RTSP capture and MJPEG frame pipeline.
  - `verdict.py`: Pure rule-based exit event evaluation engine.
- `src/ml/`:
  - `level1_detection/vision_service.py`: Real frame inference engine (YOLOX ONNX) with dynamic `SimpleByteTrack`.
  - `level5_tracking/tracker.py`: SimpleByteTrack with Hungarian cost matrix matching.
  - `ocr/invoice_ocr_service.py`: RapidOCR document extractor without synthetic fallback text.
  - `face_recognition/`: SCRFD face detection & ArcFace embedding matcher.
  - `model_config.py`: Centralized vision model configuration.
- `src/realtime/hub.py`: WebSocket `ConnectionManager` with Redis Pub/Sub cluster fanout, dead connection pruning, and heartbeat telemetry.

### 2.2 Bloat Inventory (F15)
- Prior audit identified 12 zero-byte placeholder files, all purged from git.
- **Current Scan Result:**
  - One 0-byte file detected: `retail-exit-backend/tests/test_phase1_security.py` (0 bytes). Its tests are housed in `tests/test_no_hardcode_audit.py`. Slated for removal/consolidation in Phase 8.

---

## 3. Test Suite Baseline (Phase 0–5 Verification)

- **Test Framework:** `pytest 9.1.1` with `pytest-asyncio 1.4.0`
- **Location:** `retail-exit-backend/tests/`
- **Pass Rate:** **46 / 46 Passing (100%)**
- **Execution Time:** ~116s across complete suite
- **Test Inventory:**
  1. `tests/api/test_auth.py` (2 tests: `test_auth_login_invalid`, `test_auth_registration_and_login_flows`)
  2. `tests/test_alarm_coordinator.py` (2 tests: `test_high_severity_alarm_dispatch`, `test_medium_severity_alarm_dispatch`)
  3. `tests/test_camera_api.py` (2 tests: `test_camera_crud_endpoints`, `test_duplicate_camera_reconciliation`)
  4. `tests/test_fusion_degraded.py` (4 tests: `test_single_channel_vision_degraded_capping`, `test_vision_occlusion_flagged`, `test_rfid_attenuation_majority_override`, `test_full_tri_sensor_parity`)
  5. `tests/test_no_hardcode_audit.py` (4 tests: `test_missing_jwt_secret_fails_startup`, `test_missing_database_url_fails_startup`, `test_missing_mobile_hmac_secret_fails_startup`, `test_zero_insecure_hardcoded_defaults_in_source`)
  6. `tests/test_phase2_security_config.py` (7 tests: `test_centralized_configuration_hierarchy`, `test_rate_limiter_sliding_window_enforcement`, `test_motion_detection_configuration_and_debounce`, `test_camera_schema_validation_and_ssrf_blocking`, `test_verdict_engine_configuration_defaults`, `test_websocket_hub_in_memory_and_cluster_fallback`, `test_authentic_stream_url_no_fake_webrtc`)
  7. `tests/test_phase3_resilience.py` (5 tests: `test_circuit_breaker_state_transitions`, `test_inference_timeout_watchdog_enforcement`, `test_circuit_breaker_open_blocks_execution`, `test_poll_single_camera_degradation_telemetry`, `test_multi_camera_transaction_isolation`)
  8. `tests/test_phase4_realtime_cache.py` (6 tests: `test_websocket_broadcast_parallel_send_timeout_pruning`, `test_websocket_heartbeat_pinger`, `test_websocket_gateway_token_authentication`, `test_websocket_gateway_json_ping_pong`, `test_cache_memory_non_blocking_invalidation`, `test_cache_redis_scan_unlink_invalidation`)
  9. `tests/test_phase5_cv_ml.py` (7 tests: `test_vision_service_blank_frame_zero_detections`, `test_vision_service_corrupted_bytes_resilience`, `test_bytetrack_zero_detection_track_pruning`, `test_face_service_blank_frame_no_match`, `test_invoice_ocr_blank_image_zero_hallucinations`, `test_fusion_engine_vision_absence_degradation`, `test_dynamic_tracking_settings_integration`)
  10. `tests/test_websocket_hub.py` (1 test: `test_websocket_hub_lifecycle_and_broadcast`)
  11. `tests/test_zero_fake_policy.py` (6 tests: `test_empty_frame_produces_zero_fake_detections`, `test_process_frame_batch_refuses_to_fabricate_detections`, `test_manifest_parser_never_hallucinates_on_blank_frame`, `test_hardware_interlock_reports_offline_in_production`, `test_discovery_simulate_endpoint_blocked_in_production`, `test_ingest_scenario_endpoint_blocked_in_production`)

---

## 4. Phase Handoff Matrix

| Phase | Description | Assigned Role | Status |
| :--- | :--- | :--- | :--- |
| **Phase 0** | Baseline Audit & Finding Verification | Lead/Coordinator Agent | **COMPLETE** |
| **Phase 1** | Secrets, Config, and Fake Elimination | Security/Config Agent | **COMPLETE** |
| **Phase 2** | Validation, SSRF, Rate Limiting & Config | Security/Config Agent | **COMPLETE** |
| **Phase 3** | Resilience, Isolation, Inference Watchdog | Reliability/Backend Agent | **COMPLETE** |
| **Phase 4** | WebSocket Gateway & Cache Invalidation | Reliability/Backend Agent | **COMPLETE** |
| **Phase 5** | CV / ML Correctness & Anti-Hallucination | CV/ML Agent | **COMPLETE** |
| **Phase 6** | File Splitting & Code Modularization | Refactor Agent | **COMPLETE** |
| **Phase 7** | Observability, CI/CD, Frontend Resiliency | Observability/DevOps Agent | **COMPLETE** |
| **Phase 8** | Repository Hygiene & No-Bloat Purge | Refactor Agent | **COMPLETE** |
| **Phase 9** | Final Full Verification & Clean Git Push | Lead/Coordinator Agent | **COMPLETE** |
