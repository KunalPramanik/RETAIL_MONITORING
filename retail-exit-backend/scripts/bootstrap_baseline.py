import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.db.session import AsyncSessionLocal
from src.db.init_config import init_baseline_configuration

async def main():
    async with AsyncSessionLocal() as session:
        await init_baseline_configuration(session)
    print("Baseline configuration bootstrapped successfully.")

if __name__ == "__main__":
    asyncio.run(main())
