# SEC-OPS V8 — Security, RBAC & Biometrics Specification

**Document ID**: `SEC-OPS-V8-DOC-07`  
**Date**: October 11, 2026  
**Status**: **APPROVED SPECIFICATION**  

---

## 1. Authentication & Role-Based Access Control (RBAC)

SEC-OPS V8 implements enterprise zero-trust identity verification across all API routes and UI interfaces.

### Role Hierarchy:
- **`SUPER_ADMIN`**: Full platform control-plane authority. Can provision tenants, manage global subscriptions, and view cross-tenant system metrics.
- **`ADMIN`**: Tenant company administrator. Can manage cameras, adjust stock, onboard employees, configure gate thresholds, and view all audit logs.
- **`SUPERVISOR`**: Operational shift lead. Can review AI opening stock census, approve/reject discrepancy alerts, and manual adjustments.
- **`VIEWER`**: Read-only monitoring dashboard access for security guards and floor observation staff.

Tokens are signed using standard JWT with `HS256`, strictly validated on every request via FastAPI dependency injection (`require_roles`).

---

## 2. Auto-Generated Employee ID Sequence (`EMP-000001`)

To eliminate duplicate key errors, identity spoofing, and human entry blunders, manual input of employee codes has been permanently disabled in V8:
1. When a new employee is onboarded (`POST /api/employees`):
   - The system locks the database sequence and determines the highest assigned employee number.
   - It atomically assigns the next consecutive identifier: `EMP-000001`, `EMP-000002`, `EMP-000003`, etc.
2. The UI explicitly marks the `Employee Code` field as `Auto-Generated Sequenced Code (EMP-000001+)` and disables operator manual typing.
3. Every database record enforces `UNIQUE(employee_code)`.

---

## 3. Biometric Master Switch & Privacy Compliance

To comply with international data privacy laws (e.g. GDPR, DPDP Act 2023):

1. **Default Off Configuration**:
   - `SECOPS_BIOMETRIC_ENABLED` in `src/core/config.py` defaults strictly to `False`.
   - When disabled, face detection and embedding matching are entirely bypassed.
   - The engine logs carrier identities as `UNKNOWN_PERSON` or RFID-identified without storing facial biometric vectors.
2. **Explicit Activation**:
   - Facial recognition (InsightFace ArcFace 512-d embeddings) can only be enabled if company management explicitly sets `SECOPS_BIOMETRIC_ENABLED=true` in environment configuration.
   - Face enrollment requires explicit operator consent and stores normalized float vectors without raw biometric imagery.
   - Anti-spoofing liveness verification (`LivenessDetectionService`) prevents photo and mobile screen replay attacks.

