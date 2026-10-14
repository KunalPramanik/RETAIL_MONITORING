# ROLE AND ACCOUNT MAPPING REPORT — SEC-OPS V8

**Module:** Authentication, Multi-Tenant Hierarchy & RBAC Governance  
**Target Identity:** `ces@gmail.com`  
**Execution Context:** FastAPI Authentication Service + Supabase PostgreSQL + Next.js Session Provider  

---

## 1. Identity Provisioning & Credential Synchronization

### 1.1 Root Problem
Prior to remediation, the user record for `ces@gmail.com` in the PostgreSQL database possessed an incompatible bcrypt hash prefix (`$2y$` generated under PHP-compatible tooling), which resulted in `ValueError: Invalid salt` when evaluated by Python's `bcrypt.checkpw()` implementation. Furthermore, `ces@gmail.com` was not registered in the multi-tenant `PlatformSuperAdmin` table, causing access to platform-level routes to be denied.

### 1.2 Remediation Applied
1. **Multi-Tenant Bootstrap (`src/core/multi_tenant.py`):**
   - Bootstraps `ces@gmail.com` into `PlatformSuperAdmin` with `role = "SUPER_ADMIN"`, `is_active = True`.
   - Encodes password `Ces@1234` using native Python bcrypt key derivation (`bcrypt.hashpw` with 12 rounds of salt).
2. **Store User Bootstrap (`src/db/init_config.py`):**
   - Bootstraps or updates `AppUser` for `ces@gmail.com` with `username = "ces"`, `role = "ADMIN"`, and `store_id = store.store_id`.
   - Verified directly against live Supabase PostgreSQL database:
     ```
     Updated DB Row: ces@gmail.com ces ADMIN True
     Verification with Ces@1234: True
     ```
3. **Token & Profile Endpoints (`src/api/auth.py`):**
   - `/api/auth/login`: Issues standard signed JWT bearer token containing claims:
     ```json
     {
       "sub": "ces@gmail.com",
       "role": "SUPER_ADMIN",
       "exp": 1729000000
     }
     ```
   - `/api/auth/me`: Detects platform super admin status and returns:
     ```json
     {
       "id": "9f405af6-751b-44c4-8d27-4734d4a501db",
       "user_id": "9f405af6-751b-44c4-8d27-4734d4a501db",
       "email": "ces@gmail.com",
       "username": "ces",
       "role": "SUPER_ADMIN",
       "isPlatformOwner": true,
       "store_id": "store-main-exit"
     }
     ```

---

## 2. Role-Based Access Control (RBAC) Hierarchy

| Role | Scope | Permitted Endpoints | UI Features Accessible |
|---|---|---|---|
| **SUPER_ADMIN** | Global Platform & All Stores | `/api/platform/*`, `/api/cameras/*`, `/api/settings/*`, `/api/events/*`, `/api/inventory/*` | Full Access: Platform Overview, Tenant Creation, Camera Configuration, System Settings, Audit Logs |
| **ADMIN** | Store-Level Management | `/api/cameras/*`, `/api/settings/*`, `/api/events/*`, `/api/inventory/*` | Camera Pairing, Zone Calibration, Threshold Tuning, Employee Rosters |
| **SUPERVISOR** | Shift Operations & Review | `/api/events/*`, `/api/alerts/*`, `/api/dispatches/*` | Event Review, Manual Item Reconciliation, Turnstile Release Override |
| **VIEWER** | Read-Only Monitoring | `GET /api/cameras`, `GET /api/events`, `GET /api/alerts` | Live Camera Grid, Historical Event Log, Telemetry Gauges |

---

## 3. Frontend Token Hydration Flow

1. User submits identifier `ces@gmail.com` and password `Ces@1234` on `/login`.
2. `safeFetch("/api/auth/login")` transmits payload to backend.
3. Upon receiving HTTP 200 with `access_token`, `auth-context.tsx` stores token in `localStorage("secops_token")`.
4. Client executes immediate `fetchProfile` call to `GET /api/auth/me` with `Authorization: Bearer <token>`.
5. Global auth state updates `isAuthenticated = true`, `role = "SUPER_ADMIN"`, redirecting user to `/` dashboard.

---
**Report Status:** VERIFIED & SYNCHRONIZED  
**Database Table:** `app_user` & `platform_super_admins`  
**Supabase PostgreSQL Host:** `db.xbxwwqhgyxofkvfnkdlz.supabase.co`

