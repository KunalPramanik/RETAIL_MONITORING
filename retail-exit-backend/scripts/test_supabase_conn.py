import asyncio
import asyncpg

async def check():
    # Direct connection: port 5432
    url = "postgresql://postgres:Kunnal%40%23123@db.xbxwwqhgyxofkvfnkdlz.supabase.co:5432/postgres"
    print("Testing connection to Supabase...")
    try:
        conn = await asyncpg.connect(url, timeout=10)
        res = await conn.fetchval("SELECT version();")
        print("CONNECTED SUCCESS! Version:", res)
        tables = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        print(f"Existing public tables count: {len(tables)}")
        for t in tables[:10]:
            print(" -", t['table_name'])
        await conn.close()
        return True
    except Exception as e:
        print("Direct port 5432 failed:", e)

    # Pooler connection test
    # Supabase pooler default domain: aws-0-[region].pooler.supabase.com port 6543
    print("Testing pooler connection...")
    for region in ["ap-south-1", "eu-central-1", "us-east-1", "us-west-1", "ap-southeast-1"]:
        try:
            pooler_url = f"postgresql://postgres.xbxwwqhgyxofkvfnkdlz:Kunnal%40%23123@aws-0-{region}.pooler.supabase.com:6543/postgres"
            conn = await asyncpg.connect(pooler_url, timeout=5)
            print(f"CONNECTED via pooler in {region}!")
            await conn.close()
            return True
        except Exception:
            pass
    return False

if __name__ == "__main__":
    asyncio.run(check())

