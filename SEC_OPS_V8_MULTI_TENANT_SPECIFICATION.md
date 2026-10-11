# SEC-OPS V8 — Multi-Tenant Specification & Isolation Architecture

**Document ID**: `SEC-OPS-V8-DOC-03`  
**Date**: October 11, 2026  
**Status**: **APPROVED SPECIFICATION**  

---

## 1. Overview & Separation Principles

The SEC-OPS V8 architecture mandates complete physical and logical isolation between:
1. **Platform Control Plane**: Global management of company tenants, subscriptions, master administrator credentials, and platform audit logging.
2. **Tenant Data Planes**: Isolated databases containing proprietary company cameras, employees, inventory, bills of lading, and exit traversal records.

A breach or operational failure in one tenant database has **zero cross-contamination impact** on other company accounts or the platform control plane.

---

## 2. Platform Control Plane Architecture

### 2.1 Database Location & Engine
- **Engine**: Dedicated SQLite/PostgreSQL instance managed via `PlatformAsyncSessionLocal`.
- **Path**: `data/platform/control_plane.db`
- **Models**: Defined in `src/db/platform_models.py`

### 2.2 Core Control Plane Entities

```
+-----------------------------------------------------------+
|                     PLATFORM_SUPER_ADMIN                  |
| - admin_id: String(64) [PK]                               |
| - username: String(64) [UNIQUE]                           |
| - email: String(128) [UNIQUE]                             |
| - password_hash: String(255)                              |
| - role: String(32) ['SUPER_ADMIN', 'PLATFORM_OPS']        |
| - is_active: Boolean                                      |
+-----------------------------------------------------------+
                              |
                              | Manages
                              v
+-----------------------------------------------------------+
|                       PLATFORM_TENANT                     |
| - tenant_id: String(64) [PK]                              |
| - name: String(255)                                       |
| - slug: String(128) [UNIQUE]                              |
| - db_identifier: String(128) [UNIQUE]                     |
| - status: String(32) ['ACTIVE', 'SUSPENDED', 'DECOMM']    |
| - timezone: String(64) ['Asia/Kolkata', ...]              |
| - currency: String(16) ['INR', ...]                       |
| - created_at: DateTime                                    |
+-----------------------------------------------------------+
                              |
                              | Produces
                              v
+-----------------------------------------------------------+
|                     PLATFORM_AUDIT_LOG                    |
| - log_id: String(64) [PK]                                 |
| - tenant_id: String(64) [Nullable]                        |
| - actor_id: String(64)                                    |
| - action: String(64) ['PROVISION_TENANT', 'STATUS_CHANGE']|
| - payload: JSON                                           |
| - created_at: DateTime                                    |
+-----------------------------------------------------------+
```

---

## 3. Tenant Provisioning Workflow

1. Master Super Admin logs into `/platform` with global credentials.
2. Form submission to `POST /api/platform/tenants`:
   - Validates uniqueness of company slug and database identifier.
   - Creates the tenant database file or schema (`data/tenants/{tenant_slug}.db`).
   - Automatically executes all Alembic schema migrations on the new tenant database.
   - Seeds the tenant's primary company administrator user (`ADMIN` role).
   - Generates an immutable audit trail entry in `platform_audit_log`.
3. Tenant administrator logs into the company-specific portal using their assigned credentials.
4. Tenant queries are routed exclusively to the tenant's dedicated database session using `get_tenant_session_maker(db_identifier)`.

---

## 4. Tenant Suspension & Decommissioning Security Controls

When a tenant is marked as `SUSPENDED` or `DECOMMISSIONED` via `PATCH /api/platform/tenants/{id}/status`:
- The platform control plane immediately revokes authentication tokens for all users under that tenant.
- Background camera workers associated with that tenant are signaled to terminate their ingestion threads.
- Edge API requests return `403 Forbidden: Tenant Account Suspended`.

