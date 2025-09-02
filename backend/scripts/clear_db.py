import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def clear_database():
    """Drops and recreates the public schema to wipe all tables."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL environment variable is not set.")
        return

    if "asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    logger.info("Connecting to database to clear schema...")
    engine = create_async_engine(db_url)

    try:
        async with engine.begin() as conn:
            logger.info("Dropping public schema...")
            await conn.execute(text("DROP SCHEMA public CASCADE;"))
            logger.info("Creating public schema...")
            await conn.execute(text("CREATE SCHEMA public;"))
            logger.info("Granting permissions...")
            await conn.execute(text("GRANT ALL ON SCHEMA public TO retainwiseuser;"))
            await conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
            logger.info("Database schema cleared successfully.")
    except Exception as e:
        logger.error(f"An error occurred while clearing the database: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(clear_database()) 
