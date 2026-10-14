import asyncio
import asyncpg
import bcrypt

async def verify_login():
    url = "postgresql://postgres:Kunnal%40%23123@db.xbxwwqhgyxofkvfnkdlz.supabase.co:5432/postgres"
    conn = await asyncpg.connect(url)
    row = await conn.fetchrow("SELECT email, password_hash, role, is_active FROM public.app_user WHERE email = 'ces@gmail.com'")
    admin_row = await conn.fetchrow("SELECT email, password_hash, role, is_active FROM public.platform_super_admin WHERE email = 'ces@gmail.com'")
    await conn.close()
    
    pwd = b"Ces@1234"
    match1 = bcrypt.checkpw(pwd, row["password_hash"].encode("utf-8"))
    match2 = bcrypt.checkpw(pwd, admin_row["password_hash"].encode("utf-8"))
    print(f"app_user: {row['email']} | Role: {row['role']} | Active: {row['is_active']} | Password Match: {match1}")
    print(f"platform_super_admin: {admin_row['email']} | Role: {admin_row['role']} | Active: {admin_row['is_active']} | Password Match: {match2}")

if __name__ == "__main__":
    asyncio.run(verify_login())

