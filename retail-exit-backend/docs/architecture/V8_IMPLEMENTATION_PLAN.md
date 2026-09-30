# V8 IMPLEMENTATION PLAN

*Status: ACTIVE - Phase 1 (Audit)*

## Executive Summary
This document governs the 15-Phase V8 transformation of the SEC-OPS 2.0 platform into an enterprise-grade AI Video Management System (VMS) with Hikvision-level centralized monitoring, intelligent video analytics, evidence management, and operations capabilities. 

All execution follows the **V8 Non-Negotiable Rules**: No fake data, no demo streams, zero-speculation identity, no manual database mocking, and strict preservation of working V7 mechanics.

## Phase 1 — FULL AUDIT (Current Phase)
**Objective:** Establish the ground truth of the V7 certified codebase before initiating surgery.
* **Deliverables Generated:**
  * V8_CODEBASE_AUDIT.md
  * V8_FILE_STRUCTURE.md
  * V8_FEATURE_MATRIX.md
  * V8_HIKVISION_PARITY_MATRIX.md
  * V8_DATABASE_AUDIT.md
  * V8_API_AUDIT.md
  * V8_CAMERA_AUDIT.md
  * V8_ML_AUDIT.md
  * V8_TRAINING_PLAN.md
  * V8_PRODUCTION_CLEANUP_PLAN.md
  * V8_DELETION_MANIFEST.md
  * V8_RISK_REGISTER.md
  * V8_TEST_MATRIX.md
  * V8_IMPLEMENTATION_PLAN.md (This document)

## Phase 2 — VERIFY V7
**Objective:** Confirm existing foundational elements are functioning.
* Verify real camera feeds vs pre-recorded feeds.
* Verify MediaMTX integration and H.265 detection.
* Ensure all 290 existing tests are passing.

## Phase 3 — PRODUCTION CODEBASE SURGERY
**Objective:** Clean the repository, enforcing strict separation of concerns.
* Execute deletions approved in `V8_DELETION_MANIFEST.md`.
* Restructure into `/apps`, `/services`, `/packages`, `/ml`, `/db`, and `/tests`.
* Remove all obsolete mock endpoints, demo UI elements, and superseded models.
* **Gate:** Full test suite must pass after surgery.

## Phase 4 — FOUNDATIONAL CONTRACTS
**Objective:** Lock event-driven communication protocols.
* Define standardized JSON schema envelopes for the Kafka/RabbitMQ or WebSocket message bus.
* Implement the centralized configuration service (dynamic tuning without restarts).

## Phase 5 — CAMERA / MEDIA FOUNDATION
**Objective:** Enterprise device management.
* Enhance `stream_manager.py` with ONVIF discovery protocols.
* Implement robust camera health scoring (FPS drop, packet loss, decode failure rates).
* Hardcode conflict-resolution for duplicate device registrations (MAC/IP).

## Phase 6 — ML FOUNDATION
**Objective:** Establish the reproducible ML environment outside the production runtime.
* Ensure `model_registry` schema is active.
* Segregate training scripts (`/ml/training`) from inference workers (`/services/vision-inference`).

## Phase 7 — TRAINING / FINE-TUNING (High Priority)
**Objective:** Establish the active learning and training loop.
* Execute `V8_TRAINING_PLAN.md`.
* Collect real datasets, define annotation specs, conduct hard-negative mining.
* Implement shadow deployment strategy for candidate checkpoints.
* **Gate:** Held-out evaluation required before any promotion.

## Phase 8 — CONTROL ROOM / VIDEO WALL / MAP
**Objective:** Hikvision-parity UI capabilities.
* Build the Smart Wall matrix (dynamic grid 1/4/9/16 based on WebRTC constraints).
* Implement E-Map / GIS overlay with interactive alarm pins.
* Build the Alarm Center with escalation and acknowledgment workflows.

## Phase 9 — FORENSICS / EVIDENCE
**Objective:** Unified search and tamper-proof evidence.
* Build the `Unified Forensic Search` layer (Person, Vehicle, Object, Time, Event).
* Implement cross-camera Re-ID incident timeline reconstruction.
* Secure evidence object-storage with signed expiring URLs and chain-of-custody metadata.

## Phase 10 — ACCESS / VEHICLE / THIRD-PARTY
**Objective:** Extensibility and multi-domain integration.
* Implement modular ANPR (License Plate) models.
* Implement physical access control adapters (card/badge correlations).
* Integrate POS mismatch alerts with real APIs (if hardware is present).

## Phase 11 — RETAIL / WAREHOUSE
**Objective:** Scale the business logic rules.
* Validate V7 capabilities (Chimney pallet, dense shelf count, case conversions).
* Add exception heatmaps and discrepancy trend analytics.

## Phase 12 — OBSERVABILITY / RESILIENCE
**Objective:** SRE metrics and alerting.
* Expose Prometheus metrics (inference p99 latency, DB transaction lag).
* Implement OpenTelemetry tracing for the alert lifecycle.
* Conduct chaos testing (media server restarts, DB transient failures).

## Phase 13 — FINAL CLEANING
**Objective:** Pre-flight checks.
* Run security scans (Bandit), SBOM generation, and container linting.
* Eradicate any dead code introduced during V8.

## Phase 14 — REAL ACCEPTANCE
**Objective:** Physical, multi-camera validation.
* Connect physical hardware.
* Execute `V8_REAL_HARDWARE_ACCEPTANCE.md` protocols.
* Prove 95% target metrics via physical walk-throughs and anomaly simulations.

## Phase 15 — FINAL AUDIT
**Objective:** The hard gate.
* Finalize `V8_FINAL_VERIFICATION_REPORT.md`.
* Ensure ZERO hardcoded logic, ZERO fake identities, and 100% test coverage.
