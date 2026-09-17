import os
import glob
import sqlite3

def purge_database(db_path: str):
    if not os.path.exists(db_path):
        print(f"DB not found: {db_path}")
        return
    print(f"Purging DB: {db_path}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cur.fetchall() if not r[0].startswith("sqlite_")]
    
    # Disable foreign keys during purge
    cur.execute("PRAGMA foreign_keys = OFF;")
    for t in tables:
        cur.execute(f"DELETE FROM \"{t}\";")
        print(f"  Cleared table: {t}")
    cur.execute("PRAGMA foreign_keys = ON;")
    conn.commit()
    conn.close()

def purge_snapshots():
    patterns = [
        "snapshots/*.jpg",
        "snapshots/*.png",
        "retail-exit-backend/snapshots/*.jpg",
        "retail-exit-backend/snapshots/*.png"
    ]
    total_removed = 0
    for pat in patterns:
        for f in glob.glob(pat):
            try:
                os.remove(f)
                total_removed += 1
            except Exception as e:
                print(f"Failed removing {f}: {e}")
    print(f"Removed {total_removed} cached snapshots.")

if __name__ == "__main__":
    db1 = os.path.abspath("retail_exit.db")
    db2 = os.path.abspath("retail-exit-backend/retail_exit.db")
    purge_database(db1)
    purge_database(db2)
    purge_snapshots()
    print("Full data purge complete.")

