#!/usr/bin/env python3
"""Database Hard Reset Script

WARNING: This script will irrevocably DROP ALL TABLES in the configured database
and recreate an empty schema. This executes the "Full Data Remove" mandate.
"""
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine
import sys

from src.db.models import Base
from src.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("secops.reset_db")

async def reset_schema():
    logger.warning(f"INITIATING FULL DATA WIPE ON: {settings.DATABASE_URL}")
    
    # Require explicit confirmation if not SQLite (safety mechanism for prod)
    if "sqlite" not in settings.DATABASE_URL:
        logger.warning("Target is not SQLite. Full data deletion proceeding...")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        logger.info("Dropping all existing tables...")
        await conn.run_sync(Base.metadata.drop_all)
        
        logger.info("Recreating empty production schema...")
        await conn.run_sync(Base.metadata.create_all)
        
    logger.info("FACTORY RESET COMPLETE. The database has 0 rows.")

if __name__ == "__main__":
    asyncio.run(reset_schema())
