# V8 CODEBASE AUDIT

*Status: ACTIVE - Phase 1 (Audit)*

## 1. Initial Structural Discovery
The backend repository is currently structured into the following domains under `src/`:
* `api/` - FastAPI endpoints (REST routes).
* `db/` - SQLAlchemy models and DB lifecycle.
* `engine/` - Core business logic (Stream Management, Dispatch, Journey/Tripwire, Verdicts).
* `hardware/` - Physical integration (e.g., Modbus, GPIO).
* `ml/` - AI Pipelines (YOLOX, Pose, ArcFace).
* `observability/` - Logging, metrics, tracing.
* `realtime/` - WebSockets/SSE Hub.
* `schemas/` - Pydantic DTOs for type-safe validation.
* `tests/` - 290 passing tests (Unit/Integration).
* `scripts/` - Utilities (DB init, data seeding).

## 2. Assessment against V8 Clean Architecture
The current structure is logically sound and maps well to the V7 requirements. However, to meet the V8 Enterprise standard (Section 32), we will enforce a strict domain-driven split in Phase 3.

**Current Issues Identified (Preliminary):**
* `src/ml/training/` is currently mixed into the runtime application directory. Under V8 rules (Section 19), training must be a first-class citizen *physically separated* from production runtime.
* Core engines (`src/engine/`) currently mix media gateway responsibilities (`stream_manager.py`) with domain verdict logic (`dispatch_engine.py`). These will be decoupled into distinct microservice-ready domains (`media-gateway`, `verdict`, `alerts`).

## 3. Pre-Surgery Cleanup (Pending Phase 3)
During Phase 3 (Production Codebase Surgery), the system will scan for and propose removal of:
1. `scripts/seed_dev.py` or any script generating "fake" production rows if it is not explicitly isolated to a `/tests` or `/dev-tools` environment.
2. Any hardcoded mock data inside `api/` or `engine/` (Zero Hallucination Gate).
3. Obsolete ML weights or deprecated Haar-cascade fallbacks.

*Next Step:* A detailed `V8_DELETION_MANIFEST.md` will be compiled before any file is actually deleted.
