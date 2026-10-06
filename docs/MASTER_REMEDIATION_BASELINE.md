# SEC-OPS 2.0 — MASTER REMEDIATION BASELINE

**Document Version:** 1.0.0  
**Date:** October 6, 2026  
**Status:** Canonical Baseline Established  
**Repository:** `https://github.com/KunalPramanik/RETAIL_MONITORING`

---

## 1. Complete Repository Tree & Organization

```
RETAIL_MONITORING/
├── .gitignore
├── README.md
├── docs/                                  # Centralized Architectural & Audit Documentation
│   ├── MASTER_REMEDIATION_BASELINE.md     # Full architectural baseline and status
│   └── MASTER_REMEDIATION_TRACKER.md      # Itemized problem tracking matrix
├── retail-exit-backend/
│   ├── .env.example                       # Documented environment template (zero secrets)
│   ├── .gitignore                         # Strict exclusion of .env, artifacts, models
│   ├── pyproject.toml                     # Python dependencies & build system (FastAPI, SQLAlchemy, Pytest)
│   ├── Dockerfile                         # Production container image definition
│   ├── docker-compose.yml                 # Multi-service local orchestrator (Postgres, Redis, Backend)
│   ├── migrations/                        # Alembic async migration suite
│   │   ├── env.py
│   │   └── versions/
│   ├── src/
│   │   ├── main.py                        # FastAPI entrypoint, lifespan, duplicate reconciler, correlation ID
│   │   ├── security.py                    # Bcrypt password hashing & JWT token verification
│   │   ├── cache.py                       # Unified caching layer (Redis / async in-memory fallback)
│   │   ├── api/                           # Thin REST route handlers
│   │   │   ├── router.py                  # Master API router aggregation
│   │   │   ├── auth.py                    # OAuth2 registration, dual-handle login, profile /me
│   │   │   ├── cameras.py                 # Camera CRUD, technical standby stream, duplicate merge
│   │   │   ├── events.py                  # Exit event queries, item lines, discrepancy dossiers
│   │   │   ├── alerts.py                  # Real-time alert feed, supervisor resolution
│   │   │   ├── catalog.py                 # Product master & SKU management
│   │   │   ├── discovery.py               # LAN/USB hardware auto-discovery
│   │   │   ├── dispatch.py                # Digital signature & badge re-verification
│   │   │   ├── health.py                  # Subsystem telemetry & active node counting
│   │   │   ├── ingest.py                  # Sensor ingestion & consensus processing
│   │   │   ├── invoices.py                # Billing & carrier declaration ingestion
│   │   │   ├── personnel.py               # Authorized personnel & biometric roster
│   │   │   └── reports.py                 # Audit export (CSV/Excel) & KPI summaries
│   │   ├── core/
│   │   │   └── config.py                  # Fail-fast settings loader with zero hardcoded credentials
│   │   ├── db/
│   │   │   ├── session.py                 # AsyncSessionLocal & SQLAlchemy engine
│   │   │   ├── init_config.py             # Baseline store & configuration seeder
│   │   │   └── models/                    # Canonical ORM models
│   │   │       ├── base.py
│   │   │       ├── alert.py               # AppUser (User alias), Alert
│   │   │       ├── camera.py              # Camera, CameraLog
│   │   │       ├── event.py               # ExitEvent, ExitEventLineItem, VisionDetection
│   │   │       ├── product.py             # Product catalog, packaging definitions
│   │   │       ├── store.py               # Store, Lane, ThresholdConfig
│   │   │       └── personnel.py           # Employee, Biometrics
│   │   ├── engine/
│   │   │   ├── alarm.py                   # AlarmCoordinator (Siren, Strobe, Relay, Audit)
│   │   │   ├── camera_worker.py           # Multi-camera background ingestion loop
│   │   │   ├── stream_manager.py          # Persistent OpenCV sessions & MJPEG generator
│   │   │   ├── tripwire_engine.py         # Directional tripwire & silhouette concealment
│   │   │   ├── fusion.py                  # Consensus fusion & sensor weighting
│   │   │   ├── sensor_fusion.py           # Degraded sensor fusion logic & majority overrides
│   │   │   ├── verdict.py                 # Final exit pass/lock evaluation engine
│   │   │   ├── discovery_service.py       # Network sweep & camera detection
│   │   │   ├── dispatch_engine.py         # Supervisor resolution workflow
│   │   │   └── notification_service.py    # Slack & Telegram dispatching
│   │   ├── hardware/
│   │   │   ├── usb_detector.py            # Serial COM port & USB scale detector
│   │   │   └── turnstile_driver.py        # GPIO relay turnstile actuation
│   │   ├── ml/
│   │   │   ├── model_config.py            # Centralized vision model configuration
│   │   │   ├── model_registry.py          # ONNX checkpoint tracker & metadata
│   │   │   ├── level1_detection/
│   │   │   │   └── vision_service.py      # Real YOLOX forward pass & ByteTrack integration
│   │   │   ├── anti_tailgating/
│   │   │   │   └── concealment_service.py # Person-behind-person silhouette occlusion detector
│   │   │   ├── level2_classification/
│   │   │   │   └── fixture_classifier.py  # Spatial fixture & furniture classifier
│   │   │   ├── level3_liveness/
│   │   │   │   └── static_image_service.py# Poster, reflection, and screen filter
│   │   │   ├── level5_tracking/
│   │   │   │   └── tracker_service.py     # SimpleByteTrack multi-object tracking
│   │   │   ├── face_recognition/
│   │   │   │   └── face_service.py        # Haar & ArcFace biometric matching
│   │   │   ├── ocr/
│   │   │   │   └── invoice_ocr_service.py # Manifest text & invoice table extractor
│   │   │   └── weights/                   # Versioned ONNX models
│   │   ├── observability/
│   │   │   ├── logging.py                 # Structured logging & credential redaction
│   │   │   └── metrics.py                 # Prometheus/OpenTelemetry counter collectors
│   │   └── realtime/
│   │       ├── hub.py                     # WebSocket ConnectionManager
│   │       ├── events.py                  # Strongly typed WebSocket envelopes
│   │       └── mobile_dispatcher.py       # HMAC-signed push alerts for floor guards
│   └── tests/                             # Automated test suite (100% passing)
│       ├── api/test_auth.py
│       ├── test_alarm_coordinator.py
│       ├── test_camera_api.py
│       ├── test_fusion_degraded.py
│       ├── test_no_hardcode_audit.py
│       └── test_websocket_hub.py
└── retail-exit-nextjs/                    # Production Next.js 16 (App Router) Console
    ├── package.json
    ├── next.config.ts
    ├── tsconfig.json
    ├── README.md
    └── src/
        ├── app/
        │   ├── layout.tsx
        │   ├── (dashboard)/
        │   │   ├── page.tsx               # Real-time WebSocket live monitoring dashboard
        │   │   ├── alerts/page.tsx        # Incident triage & siren override UI
        │   │   ├── events/page.tsx        # Event dossiers & multi-sensor evidence
        │   │   ├── products/page.tsx      # Master inventory catalog & packaging
        │   │   ├── employees/page.tsx     # Personnel roster & badge provisioning
        │   │   ├── reports/page.tsx       # Daily loss prevention audit digest & CSV export
        │   │   └── settings/
        │   │       ├── cameras/page.tsx   # Video wall fleet & ROI canvas editor
        │   │       └── thresholds/page.tsx# Dynamic sensor weights & tolerance tuning
        ├── components/
        │   ├── cameras/
        │   │   ├── stream_player.tsx      # MJPEG low-latency streaming component
        │   │   └── roi-canvas.tsx         # Interactive polygon ROI & tripwire drawer
        │   └── dispatch/
        │       └── verify-and-save-modal.tsx # Digital signature pad & supervisor badge check
        └── lib/
            └── api-client.ts              # Safe API fetcher with error normalization
```

---

## 2. Technology Stack

- **Backend Framework:** FastAPI 0.115+ (Python 3.11)
- **Database & ORM:** PostgreSQL 16+ via SQLAlchemy 2.0 (AsyncIO / `asyncpg` / `aiosqlite`)
- **Caching & Message Broker:** Redis 7+ via `redis.asyncio` (with in-memory dictionary fallback)
- **Inference Runtime:** ONNX Runtime 1.20+ with YOLOX-tiny backbone
- **Tracking Algorithm:** ByteTrack with Kalman filters and spatial bounding matching
- **Frontend Framework:** Next.js 16.3.8 (React 19 / App Router / Turbopack)
- **Frontend Styling:** Tailwind CSS 3.4 with dark security console theme
- **Video Transport:** Multipart MJPEG (`multipart/x-mixed-replace; boundary=frame`) + WebSockets (`/ws/live`)
- **Testing Engine:** Pytest 9.1 with `pytest-asyncio` and `anyio`

---

## 3. Execution & Subsystem Architecture

### 3.1 Authentication & Security Architecture
- **Fail-Fast Boot:** `validate_mandatory_env()` executes upon module load in `src/core/config.py`. Halts execution if `DATABASE_URL`, `JWT_SECRET_KEY`, or `MOBILE_HMAC_SECRET` are not set.
- **Unified Identity:** `AppUser` model supports both email and username handles (`or_()` query) with bcrypt password derivation.
- **Log Sanitization:** Sensitive credentials (RTSP passwords, tokens, API keys) are masked via regex in `src/observability/logging.py`.

### 3.2 Real-Time Video & Inference Pipeline
- **Continuous Ingestion:** `CameraStreamSession` maintains persistent background thread captures via OpenCV with reconnection backoff and thread-safe frame buffers.
- **Standby Mode:** When a camera is disconnected, an authentic technical standby frame is generated (`src/engine/stream_manager.py`). Zero fake pre-recorded loop injection.
- **Inference Forward Pass:** Camera frames decoded as BGR matrices are processed through YOLOX-tiny ONNX session (`src/ml/level1_detection/vision_service.py`), generating dynamic bounding boxes, class labels, and confidence metrics.

### 3.3 Consensus Multi-Sensor Fusion Engine
- **Three Modalities:**
  1. Computer Vision (YOLO + ByteTrack)
  2. UHF RFID Gate Portal (antenna reads)
  3. Load-Cell Floor Scale (physical weight vs catalog unit weights)
- **Degraded Operation:** Under visual occlusion or RFID tag shielding, weights dynamically shift, and confidence is bounded to $\le 0.75$. Sensor disagreements raise structured alerts (`DISCREPANCY_FLAG`).

### 3.4 Hardware Interlocks & Alarms
- **AlarmCoordinator:** Triggers hardware GPIO relays (`turnstile_driver.py`) to lock gates on HIGH/CRITICAL discrepancies, sound sirens, fire strobe relays, and dispatch SMS/Push alerts. Every dispatch persists an immutable `AlarmDispatch` audit record.

---

## 4. Current Verification Status & Defects Addressed

| Subsystem | Baseline State | Audit Remediation Performed |
| :--- | :--- | :--- |
| **Secrets & Config** | Insecure fallback strings in 3 files | **REMEDIATED**: Fail-fast startup; 0 fallback credentials; `.env` strictly ignored. |
| **Auth Models** | `AppUser` vs `User` field mismatch | **REMEDIATED**: Unified fields (`username`, `email`, aliases), passing integration test. |
| **Scaffold Files** | 12 empty files present | **REMEDIATED**: All 12 deleted via Git; zero empty files remain. |
| **Realtime Updates** | 5s frontend polling | **REMEDIATED**: Event-driven via WebSocket `/ws/live`; 30s background resilience fallback. |
| **Hardware Discovery** | Simulated `/simulate` endpoint | **TARGET FOR PHASE 1**: Remove or gate simulation routes from production paths. |
| **Manifest Parsing** | Hardcoded OCR text fallback | **TARGET FOR PHASE 1**: Replace synthetic fallback text with `OCR_UNCERTAIN` result. |
| **Vision Inference** | Synthetic `process_frame_batch` | **TARGET FOR PHASE 1**: Remove fabricated detections; return 0 conf on empty frames. |

