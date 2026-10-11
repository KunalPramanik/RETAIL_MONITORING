# SEC-OPS V8 — SUPER MASTER IMPLEMENTATION CHANGE MAP

**System Title:** SEC-OPS V8 Multi-Tenant Production Platform  
**Target Repository:** `RETAIL_MONITORING` / `c:\Users\DELL\.gemini\antigravity\scratch\N`  
**Date:** October 11, 2026  
**Status:** In Progress — Modular Implementation Execution  

---

## 1. Architectural Module Breakdown

This implementation change map decomposes the **V8 Super Master Implementation Prompt** into 14 cohesive, dependency-aware architectural modules:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   MODULE 1: PLATFORM CONTROL PLANE                     │
│        Master Super Admin, Multi-Tenant Provisioning, Tenant DBs       │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│               MODULE 2: TENANT RBAC & EMPLOYEE IDENTITIES              │
│       Role Provisioning, Auto-Generated EMP-IDs, Identity Isolation    │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│              MODULE 3: TIMEZONE INTEGRITY & DATE HISTORY               │
│          UTC Storage, Local IST/Tenant Display, React Keys Fix         │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│             MODULE 4: CAMERA FLEET & TRIPWIRE SUGGESTIONS              │
│         Stream Health Truthfulness, Gate ROI Discovery & Drawing       │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│               MODULE 5: SEPARATION OF VISION & MOVEMENT                │
│       Tier A: Live Scene │ Tier B: Boundary Crossing │ Tier C: Ledger  │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│             MODULE 6: DEEP LEARNING CV & MULTI-OBJECT FIX              │
│         YOLOX Model Loading, Anti-Confusion, UNKNOWN Shape Fallback    │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│               MODULE 7: TYPED SNAPSHOTS & TRACEABILITY                 │
│         Typed Categorized Evidence, Exact Event FK Links, Proxies      │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│             MODULE 8: HUMAN-VERIFIED OPENING STOCK CENSUS              │
│         Count Sessions, AI Proposed Count, YES/NO Review Workflow      │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│             MODULE 9: AUTOMATIC IN/OUT LEDGER & DASHBOARD              │
│         Idempotent Stock Ledger, IN/OUT Accounting, Stock Dashboard    │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│            MODULE 10: BILL OCR & PERSON-TO-GOODS TRACKING              │
│         Challan Extraction, Progress (1/20), Discrepancy Verdicts      │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│            MODULE 11: SECURITY, PRIVACY & ALERT ENGINE                 │
│         Biometric Switch, Token Hardening, Alert Storm Protection      │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│            MODULE 12: CONTINUOUS TRAINING / FINE-TUNING                │
│         Active Learning, Curated Datasets, Approval & Rollback         │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│            MODULE 13: FRONTEND EXPERIENCE & ZERO-FAKE AUDIT            │
│         Dedicated Dashboards, Functional Actions, ₹ INR Standard      │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│            MODULE 14: QA, AUTOMATED TESTING & FINAL REPORTS            │
│         Pytest Suite (60+ tests), Next.js Build, 11 Master Reports     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Detailed Module Specifications

### Module 1: Multi-Tenant Platform Control Plane & Master Super Admin
* **Scope**: Section 3 (Platform control plane, Master Super Admin, Separate DB provisioning, Tenant isolation).
* **Components to Modify/Create**:
  - `retail-exit-backend/src/core/multi_tenant.py` (Tenant DB session resolver, connection pool manager).
  - `retail-exit-backend/src/db/platform_models.py` (Platform Tenant registry, Platform Audit Log, Platform Super Admin).
  - `retail-exit-backend/src/api/platform_routes.py` (`/api/platform/tenants`, `/api/platform/auth`).
  - `retail-exit-nextjs/src/app/(platform)/master-admin` (Master Admin console).
* **Verification Criteria**:
  - Master Super Admin can create Tenant Company with name, unique slug, and isolated DB.
  - Alembic migrations execute automatically on newly provisioned tenant DB.
  - Company A cannot access Company B data under any circumstance.

### Module 2: Tenant RBAC, Privileged Accounts & Auto-Generated Employee IDs
* **Scope**: Section 4 (Role provisioning, account creation, auto-generated employee IDs).
* **Components to Modify/Create**:
  - `retail-exit-backend/src/db/models/employee.py` (Atomic employee sequence generator `EMP-000001`).
  - `retail-exit-backend/src/api/employee.py` (Enforce auto-generated ID, tenant-scoped uniqueness).
  - `retail-exit-backend/src/api/auth.py` & `deps_auth.py` (Strict RBAC, Master Super Admin provisions tenant Admins).
  - `retail-exit-nextjs/src/app/(dashboard)/employees` (Disabled manual typing of EMP ID, automated sequence badge).
* **Verification Criteria**:
  - Operator cannot type employee ID; server assigns collision-safe sequence.
  - Clear separation between User ID, Employee ID, Camera Track ID, and Face Identity.

### Module 3: Timezone Integrity & Day/Month History Filters
* **Scope**: Section 5 & 6 (Accurate timestamps, history filters, duplicate event ID fix).
* **Components to Modify/Create**:
  - `retail-exit-backend/src/db/models/base.py` (Canonical UTC storage).
  - `retail-exit-backend/src/api/events.py` & `cameras.py` (Include ISO timestamps).
  - `retail-exit-nextjs/src/app/(dashboard)/page.tsx` & `events/page.tsx` (Browser/Tenant local timezone formatting).
  - Database unique constraints on `event_id` (ULID/UUID enforcement, eliminate `MOV-EVT-2026`).
* **Verification Criteria**:
  - Zero React duplicate key warnings.
  - Timestamps reflect user's real local time (e.g. IST).
  - History filters by Today, Yesterday, Date Range, Month, Year query real database records.

### Module 4: Camera Fleet Management, Stream Health & Gate/Tripwire Suggestions
* **Scope**: Section 7 & 11 (RTSP pipeline, stream health truthfulness, line suggestions).
* **Components to Modify/Create**:
  - `retail-exit-backend/src/api/camera_prober.py` & `stream_manager.py` (Hardware lock protection, DirectShow/MSMF warmup).
  - `retail-exit-backend/src/engine/tripwire_engine.py` (Gate suggestion from frame contours/motion).
  - `retail-exit-nextjs/src/app/(dashboard)/settings/cameras/page.tsx` (Live preview modal, line configuration).
* **Verification Criteria**:
  - Real status reported (`ONLINE`, `OFFLINE`, `RECONNECTING`).
  - Live webcam preview frame rendered in modal.
  - Gate suggestion proposes coordinates with `ACCEPT` / `ADJUST` / `DRAW MANUALLY`.

### Module 5: Separation of Vision Tiers
* **Scope**: Section 8 (Live scene vs boundary crossing vs material movement vs inventory ledger).
* **Components to Modify/Create**:
  - `retail-exit-backend/src/api/cameras.py` (`/detections/live` — Tier A).
  - `retail-exit-backend/src/api/events.py` (`/crossing-events` — Tier B).
  - `retail-exit-backend/src/api/inventory_routes.py` (`/material-movements` — Tier C & `/ledger` — Tier D).
* **Verification Criteria**:
  - Generic scene detections do NOT create stock transactions.
  - Only confirmed crossings of inventory-mapped products affect stock.

### Module 6: Deep Learning Computer Vision & False Detection Remediation
* **Scope**: Section 9 & 10 (YOLOX inference, semantic discrimination, unknown shapes).
* **Components to Modify/Create**:
  - `retail-exit-backend/src/ml/level1_detection/vision_service.py` (Model coordinate scaling, class taxonomy).
  - `retail-exit-backend/src/ml/semantic_validation.py` (Wall picture, screen, body part discrimination).
  - Unknown object shape fallback (`class_label="unknown"`, `specific_label="UNKNOWN (<Shape> <w>x<h>)"`).
* **Verification Criteria**:
  - Pure deep learning YOLOX inference without synthetic heuristics.
  - Background doorways/posters not classified as products.
  - Multi-object detection active; unmapped items labeled `UNKNOWN` with valid bounding boxes.

### Module 7: Typed Event Snapshots & Defect-Proof Traceability
* **Scope**: Section 12 (Typed snapshots, exact event foreign-key association).
* **Components to Modify/Create**:
  - `retail-exit-backend/src/db/models/misc.py` (`EvidenceArtifact` / `CameraSnapshot` with category enum).
  - `retail-exit-backend/src/api/cameras.py` (`/snapshots/{snapshot_id}`).
  - `retail-exit-nextjs/next.config.ts` (Proxy `/snapshots/*` and `/uploads/*` to FastAPI).
* **Verification Criteria**:
  - Snapshot in movement table belongs strictly to that movement event.
  - Zero 404s or broken image cards when snapshot exists.

### Module 8: Automated Initial Stock Census with Human YES/NO Verification
* **Scope**: Section 13 (Count sessions, AI proposals, human review).
* **Components to Modify/Create**:
  - `retail-exit-backend/src/db/models/misc.py` (`InitialStockVerification` model).
  - `retail-exit-backend/src/api/inventory_routes.py` (`/stock-census/start`, `/verify`, `/correct`).
  - `retail-exit-nextjs/src/app/(dashboard)/inventory/baseline` (YES/NO review modal).
* **Verification Criteria**:
  - Opening stock proposal marked `PENDING_VERIFICATION`.
  - Operator `YES — ACCEPT` locks baseline without retyping.
  - Operator `NO — EDIT` records correction with reason and audit trail.

### Module 9: Automated IN/OUT Movement Accounting & Admin Stock Dashboard
* **Scope**: Section 14, 15, 17 (Ledger updates, pack conversion, admin stock dashboard).
* **Components to Modify/Create**:
  - `retail-exit-backend/src/engine/dispatch_engine.py` (Idempotent ledger posting).
  - `retail-exit-backend/src/api/inventory_routes.py` (`/stock/summary`, `/stock/adjust`).
  - `retail-exit-nextjs/src/app/(dashboard)/inventory` (Stock dashboard by SKU/zone).
* **Verification Criteria**:
  - `Current Stock = Baseline + IN - OUT + Adjustments`.
  - No double deductions across overlapping camera fields.

### Module 10: Bill OCR Verification & Person-to-Goods Association
* **Scope**: Section 16 (OCR extraction, authorization comparison, progress tracking).
* **Components to Modify/Create**:
  - `retail-exit-backend/src/ml/ocr/ocr_service.py` (Challan/invoice field confidence).
  - `retail-exit-backend/src/api/invoice.py` (Progress tracking against authorized items).
  - `retail-exit-nextjs/src/app/(dashboard)/invoices` (Authorization progress 1/20).
* **Verification Criteria**:
  - Unit movement decrements authorized quota incrementally.
  - Discrepancy verdicts: `CORRECT`, `WRONG_ITEM`, `OVER_QUANTITY`, `UNDER_QUANTITY`.

### Module 11: Security Hardening, Privacy Controls & Alert Engine
* **Scope**: Section 18, 19, 23 (Biometric switch, alert grouping, security audit).
* **Components to Modify/Create**:
  - `retail-exit-backend/src/core/config.py` (`SECOPS_BIOMETRIC_ENABLED` master switch).
  - `retail-exit-backend/src/engine/alarm_coordinator.py` (Alert cooldown and deduplication).
  - `retail-exit-backend/src/api/deps_auth.py` (Cryptographic JWT verification).
* **Verification Criteria**:
  - Biometric inference disabled by default unless explicitly turned on.
  - No alert storms from oscillating detection frames.

### Module 12: Continuous Model Training & Fine-Tuning Pipeline
* **Scope**: Section 20 (Controlled training workflow).
* **Components to Modify/Create**:
  - `retail-exit-backend/src/ml/training/curator.py` (Snapshot routing, human annotation queue).
  - `retail-exit-backend/src/api/training_routes.py` (Dataset management, model versioning).
* **Verification Criteria**:
  - Strict human-in-the-loop: no automatic self-retraining or unapproved weight replacement.

### Module 13: End-to-End Frontend Experience & Repository Hygiene
* **Scope**: Section 21 & 24 (UI navigation, dead button removal, ₹ INR standard).
* **Components to Modify/Create**:
  - `retail-exit-nextjs/src/app/(dashboard)/` (All tabs, cards, exports, and buttons).
  - Elimination of all mock arrays and hardcoded operational values.
* **Verification Criteria**:
  - Every button executes an authenticated API call.
  - All prices and totals formatted in Indian Rupees (`₹` / INR).

### Module 14: Quality Assurance, Automated Regression & Compliance Reporting
* **Scope**: Section 25, 26, 27 (Test suite execution, 11 production audit reports).
* **Components to Modify/Create**:
  - All 11 markdown audit reports mandated by Section 27.
  - 100% passing backend tests (`pytest`) and clean Turbopack build (`npm run build`).
* **Verification Criteria**:
  - Zero test regressions; honest `CONDITIONALLY PRODUCTION READY` status.

