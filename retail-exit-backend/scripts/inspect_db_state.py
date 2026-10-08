import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "..", "retail_secops.db")
con = sqlite3.connect(db_path)
cur = con.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall() if not r[0].startswith("sqlite_") and not r[0].startswith("alembic_")]

print(f"{'Table':<35} | {'Count':<8}")
print("-" * 46)
for t in sorted(tables):
    try:
        cnt = cur.execute(f"SELECT count(*) FROM [{t}]").fetchone()[0]
        print(f"{t:<35} | {cnt:<8}")
    except Exception as e:
        print(f"{t:<35} | ERROR: {e}")
