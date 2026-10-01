#!/usr/bin/env python3
"""Database Initialization Script

Bootstraps the production database schema. 
Does not inject mock data or demo fixtures.
"""
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine

from src.db.models import Base
from src.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("secops.init_db")

async def init_schema():
    logger.info(f"Initializing database schema at {settings.DATABASE_URL}")
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    logger.info("Database schema initialized successfully.")

if __name__ == "__main__":
    asyncio.run(init_schema())
