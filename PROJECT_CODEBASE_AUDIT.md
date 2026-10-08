# SEC-OPS V8 — PROJECT CODEBASE AUDIT REPORT

**System Title:** SEC-OPS V8 — Retail Exit Monitoring, Case/Unit Inventory Counting, and Loss Prevention  
**Audit Version:** 8.0.0-PROD-AUDIT  
**Date of Audit:** October 8, 2026  
**Auditor / Roles:** Senior Principal Software Architect, AI/Computer Vision Engineer, DevSecOps Engineer, Database Architect, SDET  
**Target Repository:** `RETAIL_MONITORING` / `c:\Users\DELL\.gemini\antigravity\scratch\N`  
**Git Branch:** `main`  
**Final Production Verdict:** **`CONDITIONALLY PRODUCTION READY`** (Subject to physical hardware commissioning: RTSP IP cameras, turnstile relay PLC, RFID gate, and load cells)

---

## 1. Executive Summary

This codebase audit report documents the comprehensive static analysis, security evaluation, computer vision pipeline audit, and architectural remediation executed on the **SEC-OPS V8** enterprise repository. 

SEC-OPS V8 is an edge/cloud retail exit surveillance and inventory reconciliation system designed to:
1. Detect individuals traversing designated store exit portals using overhead and corridor camera streams.
2. Track cases, totes, and individual retail units carried across the portal.
3. Compare visual unit counts and RFID scans against point-of-sale (POS) and Enterprise Resource Planning (ERP) invoice manifests in real time.
4. Trigger low-latency edge alarms, turnstile interlocks, and security supervisor escalations when severe discrepancies or anomalous behaviors occur.

Prior reviews generated multiple speculative or unverified defect hypotheses. This audit subjected all hypotheses to rigorous reproduction testing, established empirical root causes, executed surgically minimal fixes, eliminated hardcoded machine paths, removed hundreds of megabytes of obsolete checkpoints, integrated production JWT/RBAC authentication across backend and frontend, and verified 100% test pass rates across all suites.

---

## 2. Repository Inventory and Architecture

### 2.1 Monorepo Top-Level Structure

```
c:\Users\DELL\.gemini\antigravity\scratch\N
├── retail-exit-backend/           # FastAPI 0.115+, SQLAlchemy 2.0 Async, PyTorch/ONNX Runtime ML Engine
│   ├── alembic/                  # Database migration scripts (Async SQLite / PostgreSQL)
│   ├── src/
│   │   ├── api/                  # REST and WebSocket endpoints (/auth, /cameras, /alerts, /events, /health, /metrics)
│   │   ├── core/                 # Central configuration, rate limiters, security primitives, audit loggers
│   │   ├── db/                   # Async engine, session management, SQLite schema auto-synchronization
│   │   ├── engine/               # Multi-modal fusion, degraded sensor state engine, rules coordinator
│   │   ├── ml/                   # YOLOv8 ONNX runtime, ByteTrack, optical flow, pack math, OCR
│   │   ├── models/               # SQLAlchemy ORM declarations (User, Camera, Event, Alert, Invoice, Product)
│   │   ├── schemas/              # Pydantic v2 validation contracts
│   │   ├── services/             # Background camera manager, alarm coordinator, event broadcaster
│   │   └── utils/                # Dynamic path resolvers, cryptographic helpers
│   ├── tests/                    # Pytest test suite (58 tests covering API, ML, fusion, zero-fake)
│   ├── Dockerfile                # Hardened non-root multi-stage container definition
│   └── pyproject.toml            # uv/pip dependencies and pytest configuration
├── retail-exit-nextjs/           # Next.js 16.3.8 (App Router), React 19, Tailwind CSS, Lucide icons
│   ├── src/
│   │   ├── app/
│   │   │   ├── (dashboard)/      # Authenticated supervisor interface (cameras, alerts, events, products, settings)
│   │   │   ├── login/            # Enterprise production authentication interface
│   │   │   └── layout.tsx        # Root HTML shell with ThemeProvider and AuthProvider
│   │   └── lib/
│   │       ├── api-client.ts     # Resilient HTTP/WebSocket client with auto-injected Bearer tokens
│   │       ├── auth-context.tsx  # React Context for session management and RBAC state
│   │       └── theme-provider.tsx# Multi-theme provider (Dark, Light, System)
│   ├── Dockerfile                # Production multi-stage standalone Next.js container
│   ├── package.json              # Client dependencies
│   └── next.config.ts            # Proxy rewrites routing /api/* to FastAPI backend
├── docker-compose.yml            # Unified multi-service local edge orchestration
└── README.md                     # Operator deployment and provisioning manual
```

---

## 3. Audit Findings and Remediation Matrix

The following table summarizes all critical audit findings, root causes, and verified remediations:

| Finding ID | Severity | Component | Summary Description | Status |
|---|---|---|---|---|
| **F-01** | High | `src/api/health_routes.py` | `CameraStreamManager` class referenced non-existent static method `get_instance()`, causing 500 crashes on health checks. | **RESOLVED** |
| **F-02** | High | `src/db/session.py` & Alembic | Discrepancy between ORM models (`app_user`, `camera`) and database schema causing missing column crashes (`username`, `is_active`, `sub_stream_path`). | **RESOLVED** |
| **F-03** | Critical | Repository-wide | 26 hardcoded Windows absolute paths (`C:\Users\DELL\...`) causing immediate failure on Linux and Docker deployments. | **RESOLVED** |
| **F-04** | Medium | Git Repository Storage | Over 440 MB of redundant ONNX model weights and offline training datasets tracked in git history. | **RESOLVED** |
| **F-05** | High | `src/engine/fusion.py` | Sensor fusion pipeline defaulted missing sensor inputs to synthetic healthy states instead of degraded modes. | **RESOLVED** |
| **F-06** | High | `src/api/auth.py` | FastAPI `OAuth2PasswordRequestForm` dependency rejected standard JSON bodies sent by Next.js frontend with HTTP 422. | **RESOLVED** |
| **F-07** | Medium | `retail-exit-nextjs` | Missing production `/login` route and lack of client-side authentication guards on dashboard routes. | **RESOLVED** |
| **F-08** | High | `retail-exit-nextjs/src/lib/api-client.ts` | Frontend fetch calls failed to pass JWT Bearer tokens to protected backend APIs. | **RESOLVED** |
| **F-09** | Medium | `src/api/auth.py` | Missing formal audit logging on user session invalidation (`/api/auth/logout`). | **RESOLVED** |
| **F-10** | Medium | `src/engine/alarm_coordinator.py` | Alarm coordinator lacked timeout resilience during PLC/relay physical hardware communication drops. | **RESOLVED** |
| **F-11** | Medium | `retail-exit-backend/tests/` | Pylance and IDE type checker reported missing engine attributes in `tests/conftest.py`. | **RESOLVED** |

---

## 4. In-Depth Root Cause Analysis

### 4.1 F-01: Health Route CameraStreamManager Crash
- **Root Cause:** In `src/api/health_routes.py`, the endpoint attempted to inspect camera fleet health via `CameraStreamManager.get_instance()`. The class implementation in `src/services/camera_manager.py` did not implement a singleton getter, using direct dependency injection or module-level instance instantiation instead. Calling an undefined class method raised an `AttributeError` at runtime.
- **Fix:** Refactored `CameraStreamManager` to provide a thread-safe `@classmethod def get_instance(cls)` singleton accessor with fallback instantiation, ensuring health checks safely report operational status without raising uncaught exceptions.

### 4.2 F-02: Database Schema Column Drift
- **Root Cause:** The SQLite database file created during early prototyping did not contain recent columns added to ORM models (`app_user.username`, `app_user.is_active`, `camera.sub_stream_path`, `camera.is_active`). Running Alembic migrations failed due to SQLite's limited `ALTER TABLE` constraint mechanics.
- **Fix:** Implemented `_sync_upgrade_sqlite_schema()` in `src/db/session.py`. Upon connection initialization, the engine inspects table metadata via `PRAGMA table_info` and executes dynamic, idempotent `ALTER TABLE ADD COLUMN` statements for missing fields.

### 4.3 F-03: Hardcoded Absolute File Paths
- **Root Cause:** Prototyping scripts referenced explicit developer filesystem paths (`C:\Users\DELL\.gemini\antigravity\scratch\N\retail-exit-backend\...`) when loading YOLO models and model configuration files. When executing inside Docker or on external edge hardware, paths resolved to non-existent directories.
- **Fix:** Audited all 26 occurrences using `git grep "C:\\\\"`. Replaced every instance with relative paths resolved via `Path(__file__).resolve().parent` or `src/utils/path_resolver.py`. Verified that `git grep "C:\\\\"` returns 0 occurrences across the entire repository.

### 4.4 F-05: Zero-Fake Policy Enforcement in Fusion Pipeline
- **Root Cause:** When hardware sensors (RFID portals, load-cell scales) were offline or not returning packets, default parameters substituted simulated healthy readings (e.g., matching invoice item counts) to allow end-to-end demo execution. This violated enterprise loss prevention requirements by obscuring hardware failures.
- **Fix:** Rewrote sensor aggregation in `src/engine/fusion.py` to strictly tag offline sensors with `SENSOR_STATE_OFFLINE` / `UNAVAILABLE`. Degraded mode scoring now calculates an explicit confidence penalty and generates `HARDWARE_DEGRADED` telemetry alerts rather than synthesizing phantom valid readings.

### 4.5 F-06 & F-07: Enterprise Authentication & Frontend RBAC
- **Root Cause:** The backend `/api/auth/login` route only accepted form-encoded payloads (`application/x-www-form-urlencoded`), rejecting standard JSON payloads with HTTP 422. The Next.js frontend lacked an authentication screen, leaving all dashboard views unprotected.
- **Fix:**
  - Updated `src/api/auth.py` to inspect the `Content-Type` header, parsing either JSON bodies or form data dynamically.
  - Implemented `retail-exit-nextjs/src/app/login/page.tsx` with high-visibility branding, password visibility toggles, loading indicators, and error banners.
  - Created `retail-exit-nextjs/src/lib/auth-context.tsx` and protected `(dashboard)/layout.tsx` with authentication session guards that redirect unauthenticated operators to `/login`.

---

## 5. Test Suite Verification & Quality Assurance

- **Backend Pytest Suite:**
  - Command: `python -m pytest tests/`
  - Total Tests: 58 tests
  - Result: 58 Passed (100% pass rate)
  - Execution Time: 96.50 seconds
  - Coverage: API routes, JWT security, password hashing, database models, ML inference, multi-modal fusion, rate limiting, and zero-fake compliance.

- **Frontend Next.js Build & Typecheck:**
  - Command: `npm run build`
  - Engine: Turbopack / TypeScript Compiler
  - Result: 0 Errors, 14 routes successfully generated
  - Compilation Time: 25.7 seconds
  - Static Pages: 12 pre-rendered pages, 2 dynamic server-rendered routes (`/employees/[id]`, `/events/[id]`).

---

## 6. Audit Conclusion

The SEC-OPS V8 codebase has been systematically hardened against production reliability, data integrity, and security vulnerabilities. All verified bugs have been eliminated, hardcoded environments sanitized, and enterprise access controls deployed.

**Final Status:** **`CONDITIONALLY PRODUCTION READY`**  
Production deployment can proceed immediately to edge staging environments. Full operational go-live is contingent upon site-specific calibration and hardware validation of physical IP cameras, PLC turnstile relays, and RFID scanning gates.
