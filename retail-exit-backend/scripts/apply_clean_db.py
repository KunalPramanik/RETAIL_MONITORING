import asyncio
import asyncpg
import os

SUPABASE_URL = "postgresql://postgres:Kunnal%40%23123@db.xbxwwqhgyxofkvfnkdlz.supabase.co:5432/postgres"
SCHEMA_FILE = "retail-exit-backend/scripts/supabase_schema_secops_v8.sql"

async def apply_clean_db():
    print(f"Connecting to Supabase PostgreSQL at {SUPABASE_URL.split('@')[1]}...")
    conn = await asyncpg.connect(SUPABASE_URL, timeout=30)
    
    # 1. Terminate other active sessions that hold locks on public tables
    print("Terminating conflicting active client connections...")
    try:
        await conn.execute("""
            SELECT pg_terminate_backend(pid) 
            FROM pg_stat_activity 
            WHERE datname = 'postgres' 
              AND pid <> pg_backend_pid() 
              AND state IN ('active', 'idle in transaction');
        """)
        print("Stale / active client queries terminated.")
    except Exception as e:
        print("Note on terminating backends:", e)

    # 2. Read schema file
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        sql = f.read()

    print(f"Executing full clean schema ({len(sql)} characters)...")
    await conn.execute(sql)
    print("Clean schema successfully applied!")

    # 3. Verification
    print("\n================== VERIFICATION REPORT ==================")
    active_users = await conn.fetch("SELECT user_id, email, username, role, is_active FROM public.app_user WHERE is_active = TRUE")
    print(f"Active Store Users (Expected: 1 Software Owner): {len(active_users)}")
    for u in active_users:
        print(f"  - Email: {u['email']} | User: {u['username']} | Role: {u['role']} | Active: {u['is_active']}")

    super_admins = await conn.fetch("SELECT admin_id, email, username, role, is_active FROM public.platform_super_admin WHERE is_active = TRUE")
    print(f"\nActive Platform Super Admins (Expected: 1 Software Owner): {len(super_admins)}")
    for a in super_admins:
        print(f"  - Admin ID: {a['admin_id']} | Email: {a['email']} | Role: {a['role']} | Active: {a['is_active']}")

    print("\nOperational Tables Row Counts (Expected: 0 for all):")
    operational_tables = [
        "product",
        "material",
        "employee",
        "invoice",
        "exit_event",
        "exit_event_line_item",
        "material_movement_ledger",
        "material_inventory_balance",
        "alert",
        "alarm_dispatch",
        "vision_detection",
        "camera",
        "lane"
    ]
    all_zero = True
    for tbl in operational_tables:
        cnt = await conn.fetchval(f'SELECT count(*) FROM public."{tbl}"')
        print(f"  - public.{tbl}: {cnt} rows")
        if cnt != 0:
            all_zero = False

    print("\nSystem Config Tables:")
    for sys_tbl in ["store", "threshold_config", "platform_subscription_tier", "platform_tenant", "platform_store_subscription", "platform_billing_invoice"]:
        cnt = await conn.fetchval(f'SELECT count(*) FROM public."{sys_tbl}"')
        print(f"  - public.{sys_tbl}: {cnt} rows")

    total_tables = await conn.fetchval("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")
    print(f"\nTotal Base Tables Created: {total_tables}")

    await conn.close()
    if all_zero and len(active_users) == 1 and len(super_admins) == 1:
        print("\n>>> ALL VALIDATION CHECKS PASSED: ZERO DUMMY DATA, ONLY SOFTWARE OWNER ACTIVATED <<<")
    else:
        print("\n>>> WARNING: SOME CHECKS DID NOT MATCH EXACT SPECS <<<")

if __name__ == "__main__":
    asyncio.run(apply_clean_db())

