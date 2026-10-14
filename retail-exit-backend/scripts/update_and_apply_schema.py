import os
import sys
import asyncio
import asyncpg

SCHEMA_PATH = "retail-exit-backend/scripts/supabase_schema_secops_v8.sql"
HASH_PATH = "retail-exit-backend/scripts/current_hash.txt"
SUPABASE_URL = "postgresql://postgres:Kunnal%40%23123@db.xbxwwqhgyxofkvfnkdlz.supabase.co:5432/postgres"

def build_schema_file():
    with open(HASH_PATH, "r", encoding="utf-8") as f:
        verified_hash = f.read().strip()

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        existing_sql = f.read()

    # Split before "-- 11. AUTOMATIC UPDATED_AT TRIGGERS"
    cutoff_marker = "-- 11. AUTOMATIC UPDATED_AT TRIGGERS"
    if cutoff_marker in existing_sql:
        base_part = existing_sql.split(cutoff_marker)[0].rstrip()
    else:
        raise ValueError("Could not find cutoff marker in existing SQL file")

    new_sections = f"""-- ==============================================================================
-- 11. PLATFORM CONTROL-PLANE TABLES (MULTI-TENANCY & FLEET GOVERNANCE)
-- ==============================================================================
-- Strictly isolated from tenant operational stores (cameras, frames, stock, events).
-- Manages platform billing, store onboarding, super admin access, and company registries.

-- 11.1 Platform Tenant / Company Registry
CREATE TABLE IF NOT EXISTS public.platform_tenant (
    tenant_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    name VARCHAR(255) UNIQUE NOT NULL,
    slug VARCHAR(64) UNIQUE NOT NULL,
    db_identifier VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PROVISIONING' CHECK (status IN ('PROVISIONING', 'ACTIVE', 'SUSPENDED', 'DECOMMISSIONED')),
    timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Kolkata',
    currency VARCHAR(16) NOT NULL DEFAULT 'INR',
    contact_email VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_platform_tenant_slug ON public.platform_tenant(slug);
CREATE INDEX IF NOT EXISTS ix_platform_tenant_status ON public.platform_tenant(status);

-- 11.2 Platform Master Super Admin Account
CREATE TABLE IF NOT EXISTS public.platform_super_admin (
    admin_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    username VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'SUPER_ADMIN',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_platform_super_admin_username ON public.platform_super_admin(username);
CREATE INDEX IF NOT EXISTS ix_platform_super_admin_email ON public.platform_super_admin(email);

-- 11.3 Platform-Level Immutable Audit Log
CREATE TABLE IF NOT EXISTS public.platform_audit_log (
    log_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    actor_id VARCHAR(36) NOT NULL,
    actor_type VARCHAR(32) NOT NULL DEFAULT 'SUPER_ADMIN',
    action VARCHAR(64) NOT NULL,
    tenant_id VARCHAR(36),
    details JSONB,
    ip_address VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_platform_audit_log_action ON public.platform_audit_log(action);
CREATE INDEX IF NOT EXISTS ix_platform_audit_log_tenant_id ON public.platform_audit_log(tenant_id);
CREATE INDEX IF NOT EXISTS ix_platform_audit_log_created_at ON public.platform_audit_log(created_at);

-- 11.4 Platform Subscription Tiers & Quota Definitions
CREATE TABLE IF NOT EXISTS public.platform_subscription_tier (
    tier_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    name VARCHAR(64) UNIQUE NOT NULL,
    max_cameras INTEGER NOT NULL DEFAULT 4,
    price_cents INTEGER NOT NULL DEFAULT 0,
    currency VARCHAR(16) NOT NULL DEFAULT 'INR',
    billing_cycle VARCHAR(16) NOT NULL DEFAULT 'MONTHLY',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 11.5 Store Tenant Subscriptions & Payment Verification
CREATE TABLE IF NOT EXISTS public.platform_store_subscription (
    subscription_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    tenant_id VARCHAR(36) UNIQUE NOT NULL,
    tier_id VARCHAR(36) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'PAST_DUE', 'SUSPENDED', 'CANCELLED')),
    current_period_start TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    current_period_end TIMESTAMPTZ NOT NULL,
    grace_period_days INTEGER NOT NULL DEFAULT 7,
    payment_verified BOOLEAN NOT NULL DEFAULT TRUE,
    auto_renew BOOLEAN NOT NULL DEFAULT TRUE,
    last_payment_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_platform_store_subscription_tenant ON public.platform_store_subscription(tenant_id);
CREATE INDEX IF NOT EXISTS ix_platform_store_subscription_status ON public.platform_store_subscription(status);

-- 11.6 Platform Billing Invoices
CREATE TABLE IF NOT EXISTS public.platform_billing_invoice (
    invoice_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    tenant_id VARCHAR(36) NOT NULL,
    subscription_id VARCHAR(36),
    amount_cents INTEGER NOT NULL DEFAULT 0,
    currency VARCHAR(16) NOT NULL DEFAULT 'INR',
    status VARCHAR(32) NOT NULL DEFAULT 'PAID' CHECK (status IN ('PAID', 'UNPAID', 'DELINQUENT', 'VOID')),
    due_date TIMESTAMPTZ NOT NULL,
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_platform_billing_invoice_tenant ON public.platform_billing_invoice(tenant_id);
CREATE INDEX IF NOT EXISTS ix_platform_billing_invoice_status ON public.platform_billing_invoice(status);

-- ==============================================================================
-- 12. AUTOMATIC UPDATED_AT TRIGGERS
-- ==============================================================================
CREATE OR REPLACE TRIGGER trg_threshold_config_updated_at
BEFORE UPDATE ON public.threshold_config
FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();

CREATE OR REPLACE TRIGGER trg_product_updated_at
BEFORE UPDATE ON public.product
FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();

CREATE OR REPLACE TRIGGER trg_material_updated_at
BEFORE UPDATE ON public.material
FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();

CREATE OR REPLACE TRIGGER trg_tripwire_updated_at
BEFORE UPDATE ON public.virtual_tripwire_config
FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();

CREATE OR REPLACE TRIGGER trg_smart_wall_updated_at
BEFORE UPDATE ON public.smart_wall_layout
FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();

CREATE OR REPLACE TRIGGER trg_mat_balance_updated_at
BEFORE UPDATE ON public.material_inventory_balance
FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();

CREATE OR REPLACE TRIGGER trg_platform_tenant_updated_at
BEFORE UPDATE ON public.platform_tenant
FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();

CREATE OR REPLACE TRIGGER trg_platform_store_sub_updated_at
BEFORE UPDATE ON public.platform_store_subscription
FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();

-- ==============================================================================
-- 13. SEED DATA & USER ACTIVATION
-- ==============================================================================
-- Requirement: ONLY ONE ID ACTIVATED (Software Owner & Store Admin)
-- Email: ces@gmail.com
-- Password: Ces@1234
-- Store Role: ADMIN
-- Platform Role: SUPER_ADMIN
-- Bcrypt Hash (cost factor 12): {verified_hash}
-- ==============================================================================

-- 13.1 Ensure Default Store exists
INSERT INTO public.store (store_id, name, address, timezone)
VALUES (
    '0f8248a3-2947-4f6b-871d-5b6cb219e2c1',
    'Flagship Operations Facility',
    'Main Industrial Estate, Gate 1',
    'UTC'
)
ON CONFLICT (store_id) DO UPDATE 
SET name = EXCLUDED.name,
    address = EXCLUDED.address,
    timezone = EXCLUDED.timezone;

-- 13.2 Ensure Default Threshold Config exists
INSERT INTO public.threshold_config (config_id, store_id, unit_tolerance, pct_tolerance, low_severity_threshold, med_severity_threshold, high_severity_threshold)
VALUES (
    'th_default_001',
    '0f8248a3-2947-4f6b-871d-5b6cb219e2c1',
    0,
    0.0,
    1,
    3,
    6
)
ON CONFLICT (config_id) DO NOTHING;

-- 13.3 Deactivate or Remove any previous demo/test users to guarantee ONLY ONE ACTIVE USER
UPDATE public.app_user
SET is_active = FALSE
WHERE email != 'ces@gmail.com';

-- 13.4 Insert or Activate the single Software Owner account (Store-level Admin)
INSERT INTO public.app_user (
    user_id,
    email,
    username,
    password_hash,
    role,
    store_id,
    mfa_enabled,
    is_active,
    created_at
)
VALUES (
    '9f405af6-751b-44c4-8d27-4734d4a501db',
    'ces@gmail.com',
    'ces',
    '{verified_hash}',
    'ADMIN',
    '0f8248a3-2947-4f6b-871d-5b6cb219e2c1',
    FALSE,
    TRUE,
    NOW()
)
ON CONFLICT (email) DO UPDATE 
SET 
    username = EXCLUDED.username,
    password_hash = EXCLUDED.password_hash,
    role = EXCLUDED.role,
    is_active = TRUE,
    store_id = EXCLUDED.store_id;

-- 13.5 Insert or Activate Platform Super Admin account (Control-plane Owner)
INSERT INTO public.platform_super_admin (
    admin_id,
    username,
    email,
    password_hash,
    role,
    is_active,
    created_at
)
VALUES (
    'admin_root_001',
    'ces',
    'ces@gmail.com',
    '{verified_hash}',
    'SUPER_ADMIN',
    TRUE,
    NOW()
)
ON CONFLICT (email) DO UPDATE 
SET 
    username = EXCLUDED.username,
    password_hash = EXCLUDED.password_hash,
    role = EXCLUDED.role,
    is_active = TRUE;

-- 13.6 Subscription Tiers Setup
INSERT INTO public.platform_subscription_tier (tier_id, name, max_cameras, price_cents, currency, billing_cycle)
VALUES 
    ('tier_starter_01', 'Starter', 4, 499900, 'INR', 'MONTHLY'),
    ('tier_pro_01', 'Professional', 16, 1499900, 'INR', 'MONTHLY'),
    ('tier_enterprise_01', 'Enterprise', 64, 4999900, 'INR', 'MONTHLY')
ON CONFLICT (tier_id) DO UPDATE
SET name = EXCLUDED.name, max_cameras = EXCLUDED.max_cameras, price_cents = EXCLUDED.price_cents;

-- 13.7 Tenant Master Registry Linking
INSERT INTO public.platform_tenant (tenant_id, name, slug, db_identifier, status, timezone, currency, contact_email)
VALUES (
    '0f8248a3-2947-4f6b-871d-5b6cb219e2c1',
    'Flagship Operations Facility',
    'flagship-store',
    'flagship_db',
    'ACTIVE',
    'UTC',
    'INR',
    'ces@gmail.com'
)
ON CONFLICT (tenant_id) DO UPDATE
SET name = EXCLUDED.name, status = EXCLUDED.status, contact_email = EXCLUDED.contact_email;

-- 13.8 Store Subscription Linking
INSERT INTO public.platform_store_subscription (
    subscription_id,
    tenant_id,
    tier_id,
    status,
    current_period_start,
    current_period_end,
    grace_period_days,
    payment_verified,
    auto_renew
)
VALUES (
    'sub_flagship_001',
    '0f8248a3-2947-4f6b-871d-5b6cb219e2c1',
    'tier_enterprise_01',
    'ACTIVE',
    NOW(),
    NOW() + INTERVAL '365 days',
    7,
    TRUE,
    TRUE
)
ON CONFLICT (subscription_id) DO UPDATE
SET status = EXCLUDED.status, payment_verified = EXCLUDED.payment_verified;

-- 13.9 Initial Verified Billing Invoice
INSERT INTO public.platform_billing_invoice (
    invoice_id,
    tenant_id,
    subscription_id,
    amount_cents,
    currency,
    status,
    due_date,
    paid_at
)
VALUES (
    'inv_flagship_001',
    '0f8248a3-2947-4f6b-871d-5b6cb219e2c1',
    'sub_flagship_001',
    4999900,
    'INR',
    'PAID',
    NOW(),
    NOW()
)
ON CONFLICT (invoice_id) DO UPDATE
SET status = EXCLUDED.status, paid_at = EXCLUDED.paid_at;

-- ==============================================================================
-- 14. VERIFICATION QUERIES
-- ==============================================================================
-- Verify Single Active Store Admin
SELECT 'APP_USER' AS source, user_id, email, username, role, is_active FROM public.app_user WHERE is_active = TRUE;

-- Verify Single Active Platform Super Admin
SELECT 'PLATFORM_SUPER_ADMIN' AS source, admin_id, email, username, role, is_active FROM public.platform_super_admin WHERE is_active = TRUE;

-- Verify Total Platform & Store Tables Count
SELECT count(*) AS total_public_tables FROM information_schema.tables WHERE table_schema = 'public';
"""

    complete_sql = base_part + "\n\n" + new_sections
    with open(SCHEMA_PATH, "w", encoding="utf-8") as f:
        f.write(complete_sql)
    print(f"Successfully wrote {len(complete_sql)} characters to {SCHEMA_PATH}")
    return complete_sql

async def execute_on_supabase(sql_text: str):
    print("Connecting to live Supabase PostgreSQL database...")
    conn = await asyncpg.connect(SUPABASE_URL, timeout=30)
    print("Connected! Executing complete schema migration...")
    
    # asyncpg execute can run multi-statement SQL strings
    await conn.execute(sql_text)
    print("Schema applied successfully!")

    print("\n--- AUDIT & VERIFICATION ---")
    active_users = await conn.fetch("SELECT user_id, email, username, role, is_active FROM public.app_user WHERE is_active = TRUE")
    print(f"Active Store Users ({len(active_users)}):")
    for u in active_users:
        print(f"  - Email: {u['email']} | User: {u['username']} | Role: {u['role']} | Active: {u['is_active']}")

    super_admins = await conn.fetch("SELECT admin_id, email, username, role, is_active FROM public.platform_super_admin WHERE is_active = TRUE")
    print(f"Active Platform Super Admins ({len(super_admins)}):")
    for a in super_admins:
        print(f"  - Email: {a['email']} | Admin: {a['username']} | Role: {a['role']} | Active: {a['is_active']}")

    tables = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name")
    print(f"Total Base Tables in Supabase public schema: {len(tables)}")
    for i, t in enumerate(tables, 1):
        print(f"  {i:2d}. {t['table_name']}")

    views = await conn.fetch("SELECT table_name FROM information_schema.views WHERE table_schema='public'")
    print(f"Total Views: {len(views)}")
    for v in views:
        print(f"  - {v['table_name']}")

    await conn.close()

if __name__ == "__main__":
    sql = build_schema_file()
    asyncio.run(execute_on_supabase(sql))

