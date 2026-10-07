# SEC-OPS 2.0 — PHASE 8 IMPLEMENTATION PLAN
## Repository Hygiene & No-Bloat Purge

**Phase:** Phase 8  
**Assigned Agent Role:** Refactor Agent  
**Authorizing Agent:** Lead/Coordinator Agent  
**Goal:** Remove empty stubs, dead artifacts, and repository bloat while preserving 100% of functional capabilities, existing documentation, and the full regression test suite.

---

### 1. Scope & Findings Addressed
- **Finding F15:** Repository bloat: dead files, zero-byte stubs (`tests/test_phase1_security.py`), unused temporary artifacts, and dependency hygiene.

---

### 2. Pre-Conditions & Baseline Verification
- [x] Phases 0–7 completed and verified.
- [x] Full regression test suite passing: 49 / 49 tests (100% pass rate).
- [x] Frontend builds with 0 errors and lints with 0 errors.

---

### 3. Step-by-Step Execution Plan

#### Step 3.1: Zero-Byte Stubs & Dead File Removal
1. Remove `retail-exit-backend/tests/test_phase1_security.py` (0 bytes, redundant with `tests/test_no_hardcode_audit.py`).
2. Audit repository for any dangling `.tmp`, `.swp`, or temporary test dumps and clean them up.

#### Step 3.2: Dependency & Build Hygiene
1. Ensure `retail-exit-backend/pyproject.toml` and `.gitignore` properly exclude build caches (`.pytest_cache`, `__pycache__`, `.next`).
2. Verify frontend `.gitignore` properly excludes Next.js build artifacts (`.next/`, `node_modules/`).

#### Step 3.3: Empirical Regression Verification
1. Run full test suite (`pytest -v`) to confirm 49 / 49 tests pass.
2. Run frontend build (`npm run build`) in `retail-exit-nextjs` to confirm 13 / 13 routes compile cleanly.

#### Step 3.4: Documentation & Handoff
1. Mark Finding F15 as `VERIFIED-FIXED` in `docs/REMEDIATION_TRACKER.md`.
2. Update `docs/BASELINE.md` marking Phase 8 as `COMPLETE` and authorizing Phase 9 (Final Full Verification & Clean Git Push).

