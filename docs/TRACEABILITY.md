# SEC-OPS V8 — Requirements Traceability Matrix

This document tracks all 20 sections of the SEC-OPS V8 Specification, mapping them to Squads, Work Packages, G1 Audit Verdicts, and empirical test evidence.

| Section | Title | Assigned Squads | Main Work Packages | G1 Audit Verdict | Status & Empirical Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | Audit and Cleanup | S0, S11 | WP-S0.1, WP-S11.3 | **ALREADY_FIXED** | Repository cleaned: 244 tracked production files. All markdown audit reports, scratch scripts, batch files, and DB dumps removed from tracking. |
| **2** | CPU-First AI Engine | S4, S5, S8, S10 | WP-S4.3, WP-S5.1, WP-S10.2 | **ALREADY_FIXED** | 100% CPU inference verified (`test_team2_vision_and_tracking.py`, `test_cv_ml.py`). No GPU required. ONNX runtime & CPU fallbacks active. |
| **3** | Software Owner & Control Plane | S3, S1, S2 | WP-S3.1, WP-S1.1, WP-S2.1 | **PARTIALLY_CONFIRMED** | `platform_tenant`, `platform_super_admin`, `platform_subscription_tier` tables live. `ces@gmail.com` active as SUPER_ADMIN. Saga automation queued for Phase 4. |
| **4** | Company & User RBAC | S2 | WP-S2.2, WP-S2.3 | **ALREADY_FIXED** | Deny-by-default RBAC enforced. Roles: Store Admin, Supervisor, Operator, Security, Auditor, Super Admin. Verified in `test_team5_role_dashboards.py`. |
| **5** | Camera Fleet & Health Telemetry | S4 | WP-S4.1 to S4.4 | **ALREADY_FIXED** | Multi-threaded camera workers, RTSP ingestion, telemetry heartbeats (`received_at`, FPS, bitrate), and `DEGRADED` health state handling. |
| **6** | Live Multi-Camera Detection | S5, S9 | WP-S5.2, WP-S9.2 | **ALREADY_FIXED** | Live surveillance grid with continuous frame processing. Annotated bounding boxes, tracking IDs, and traversal vectors verified (`test_camera_api.py`). |
| **7** | Objects & False Positive Control | S5, S8 | WP-S5.3, WP-S5.4 | **ALREADY_FIXED** | Door open/closed state classification separated from object bounding boxes. Static poster/wall decor suppression active (`test_team2_vision_and_tracking.py`). |
| **8** | Snapshots, History & Retention | S4, S6, S9 | WP-S4.5, WP-S9.3 | **ALREADY_FIXED** | Snapshot archiving with 8 categories including `BILL_DOCUMENT`. Person snapshots prohibited from material evidence. 45-day retention active. |
| **9** | Known & Unknown Biometrics | S5 | WP-S5.5 | **ALREADY_FIXED** | Biometrics disabled by default. Strict threshold matching against enrolled staff embeddings. Non-invasive appearance Re-ID fallback. |
| **10** | Initial Stock Baseline Verification | S6 | WP-S6.4 | **ALREADY_FIXED** | Human verification mandatory (`initial_stock_verification`). Auto-accept disabled. Stock balances commit only upon Store Admin approval. |
| **11** | Immutable IN/OUT Ledger | S6 | WP-S6.1, WP-S6.2 | **ALREADY_FIXED** | Append-only `material_movement_ledger` with unique `idempotency_key`. Atomic balance updates tested against simultaneous race conditions (`test_team4_ledger_and_ocr.py`). |
| **12** | Bills & Manifest Reconciliation | S6, S7 | WP-S6.3, WP-S7.1 | **ALREADY_FIXED** | OCR invoice extraction and progressive matching (1/N, 2/N) as items cross lane. Over-carry and under-declare discrepancy flags verified. |
| **13** | Alarms & Hardware Dispatches | S7, S3 | WP-S7.2 | **ALREADY_FIXED** | Physical siren, strobe, and turnstile lock adapters with `is_configured` verification. On-screen alerts separated from hardware alarms. |
| **14** | MLOps & Annotation Workflows | S8 | WP-S8.1 to S8.4 | **ALREADY_FIXED** | Active learning dataset inspector, annotation queue, class counting strategies, and packaging tier classification (`test_v8_dataset_and_counting_suite.py`). |
| **15** | Timezone & Retention Policies | S1, S6 | WP-S1.4 | **ALREADY_FIXED** | UTC storage with IANA timezone display. 45-day routine snapshot cleanup guarantees zero deletion of stock ledgers or audit logs. |
| **16** | Billing, Subscriptions & Suspension | S3, S1 | WP-S3.2, WP-S3.3 | **ALREADY_FIXED** | Configurable payment verification, 7-day grace period, automatic suspension with operational lockdown, billing export access (`test_team1_multi_tenancy_and_billing.py`). |
| **17** | Role-Based Dashboards & UI | S9, S2 | WP-S9.1 | **ALREADY_FIXED** | Next.js 16 role-aware layouts and filtered navigation for Software Owner, Store Admin, Supervisor, Operator, Security, Auditor. |
| **18** | Frontend & API Error Hardening | S9, S2, S4 | WP-S9.4 | **ALREADY_FIXED** | Resolved `Cannot read properties of undefined (reading 'replace')` in date formatting. Standardized empty, loading, and error states across all 17 routes. |
| **19** | Testing, CI/CD & Hygiene | S10, S11 | WP-S10.1, WP-S11.1 to S11.4 | **ALREADY_FIXED** | 111/111 Pytest unit/integration tests passing. Next.js 16 Turbopack build 100% clean. Pushed cleanly to GitHub `main` branch. |
| **20** | Final Outcome & Production Readiness | ALL | Phase 8 Gate | **IN_PROGRESS** | Executing structured multi-agent phase gate delivery according to Master Prompt protocol. |

---

## Decisions Register (D1–D10)

| Decision ID | Topic | Decision Confirmed | Notes & Implementation |
| :--- | :--- | :--- | :--- |
| **D1** | Tenant DB Engine | **PostgreSQL (Supabase / Postgres 15+)** | Dedicated database or schema per tenant, connection pooling enabled. |
| **D2** | Payment Gateway | **Adapter Interface with Manual Audit fallback** | Signature-checked webhook adapter ready; manual verified payment audit trail active. |
| **D3** | Object Storage | **S3-compatible (MinIO / Supabase / AWS S3)** | Per-tenant prefixing: `tenants/{tenant_id}/snapshots/{category}/`. |
| **D4** | Background Jobs | **Asyncio Worker Queue with Watchdog** | Isolated camera threads with restart backoff; Redis job queue integration ready. |
| **D5** | Auto-Accept Stock | **OFF (Default strictly enforced)** | Initial stock must be reviewed and accepted by Store Admin or Supervisor. |
| **D6** | Inactive Tenant Data | **Retain indefinitely** | Never auto-delete tenant data upon non-payment; delete only via explicit owner action after notice. |
| **D7** | Biometrics Status | **OFF (Default strictly enforced)** | Requires explicit administrator activation and local data protection legal review. |
| **D8** | Target Hardware | **CPU-First (100% CPU compatibility)** | YOLOX / OpenCV CPU pipeline benchmarked with zero GPU dependence. |
| **D9** | Store Owner Role | **First Store Admin (`ADMIN`)** | Flagged as primary company owner; distinct from Platform `SUPER_ADMIN`. |
| **D10** | Suspended Store | **Billing & Export Access ONLY** | Operational endpoints return `403 Tenant Suspended`; billing and CSV export permitted. |

---

## Baseline Test Execution Record

- **Pytest Backend Suite**: **111 Passed**, 0 Failed, 1 Warning (`httpx` deprecation in test client) in 204.78 seconds.
- **Next.js Frontend Build**: **17/17 routes compiled**, 0 TypeScript errors, optimized production build in 22.3 seconds.
- **Live Database Audit**: 43 tables in Supabase public schema, exactly 1 active Software Owner account (`ces@gmail.com`), 0 dummy records in transaction ledgers.
- **Code Changes in Phase 0**: **None.** (Audit & Traceability documentation only).

