# SEC-OPS 2.0 — PHASE 7 IMPLEMENTATION PLAN
## Observability, CI/CD, and Frontend Resiliency

**Phase:** Phase 7  
**Assigned Agent Role:** Observability/DevOps Agent  
**Authorizing Agent:** Lead/Coordinator Agent  
**Goal:** Deliver complete CI/CD automation, verify Prometheus observability & correlation tracing, and guarantee zero synthetic fallbacks and resilient error handling across the frontend.

---

### 1. Scope & Findings Addressed
- **Finding F13:** Missing tests, CI pipeline (`.github/workflows/ci.yml`), structured logging, metrics, and correlation ID tracing.
- **Finding F14:** Frontend error handling, resilient fallback behavior, zero hardcoded hosts/KPIs, and clean compilation.

---

### 2. Pre-Conditions & Baseline Verification
- [x] Phases 0–6 complete and verified (all 46 backend tests passing, 100% pass rate).
- [x] Refactor Agent completed Phase 6 modularization (`motion_detector.py`, `camera_prober.py`, `camera_stream_utils.py`).
- [x] Zero regressions introduced in functional endpoints.

---

### 3. Step-by-Step Execution Plan

#### Step 3.1: CI Pipeline Creation (`.github/workflows/ci.yml`)
1. Create `.github/workflows/ci.yml` with dual parallel jobs:
   - `backend-test`: Ubuntu runner, Python 3.11, pip cache, OpenCV dependencies, test env secrets, and full `pytest -v` run.
   - `frontend-build`: Ubuntu runner, Node.js 20, npm cache, `npm ci`, `npm run lint`, and `npm run build`.

#### Step 3.2: Automated Observability & Tracing Test Suite (`tests/test_phase7_observability.py`)
1. Write `tests/test_phase7_observability.py` testing:
   - `/health` endpoint returning HTTP 200, status `HEALTHY`, and database status.
   - `/metrics` endpoint returning HTTP 200 with valid Prometheus metric format (`# HELP`, `# TYPE`, counter/gauge lines).
   - `X-Correlation-ID` header middleware propagating client IDs and auto-generating missing IDs.
   - Structured error format responses across standard HTTP error paths.

#### Step 3.3: Frontend Audit & Resiliency Verification
1. Verify `npm run lint` passes with 0 errors across all 13 Next.js pages.
2. Verify `npm run build` succeeds with 0 errors and generates all static/dynamic routes.
3. Verify `api-client.ts` uses relative rewrites and `process.env.NEXT_PUBLIC_API_URL` without hardcoded domains.

#### Step 3.4: Full Test Suite Baseline Run
1. Run full test suite (`pytest -v`) in PowerShell to ensure all existing and new tests pass.

#### Step 3.5: Documentation & Handoff
1. Update `docs/REMEDIATION_TRACKER.md` (mark F13 and F14 as `VERIFIED-FIXED`).
2. Update `docs/BASELINE.md` (mark Phase 7 as `COMPLETE`).
3. Hand off to Coordinator Agent to authorize Phase 8 (Repository Hygiene & No-Bloat Purge).

