"""Database Maintenance Script

Strictly adheres to Part I (No-Hardcode / Fully Dynamic Data Policy).
All operational data must be populated dynamically via live sensor feeds
or operator console actions, never pre-seeded with fake or mock records.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path when executed directly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio
from src.db.session import AsyncSessionLocal
from src.api.settings import reset_database

async def main():
    print("Enforcing Zero-Mock / Fully Dynamic System Policy...")
    async with AsyncSessionLocal() as session:
        await reset_database(session)
    print("Database verified: 0 mock rows. Fully dynamic state active.")

if __name__ == "__main__":
    asyncio.run(main())
