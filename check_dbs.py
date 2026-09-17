import sqlite3
import os
import glob

db_paths = [
    os.path.abspath("retail_exit.db"),
    os.path.abspath("retail-exit-backend/retail_exit.db")
]

for db in db_paths:
    if not os.path.exists(db):
        continue
    print(f"\nChecking DB: {db}")
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cur.fetchall() if not r[0].startswith("sqlite_")]
    for t in tables:
        cur.execute(f"SELECT count(*) FROM {t};")
        cnt = cur.fetchone()[0]
        print(f"  {t}: {cnt}")
    conn.close()

