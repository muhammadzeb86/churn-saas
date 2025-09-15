#!/usr/bin/env python3
"""
Fix Alembic version table to resolve migration conflicts
"""
import asyncio
import logging
import sys
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from backend.api.database import AsyncSessionMaker

logger = logging.getLogger(__name__)

async def fix_alembic_version():
    """Fix the alembic_version table to point to the correct revision"""
    try:
        logger.info("Starting alembic version fix...")
        
        async with AsyncSessionMaker() as db:
            # Check current version
            result = await db.execute(text("SELECT version_num FROM alembic_version"))
            current_version = result.scalar_one_or_none()
            logger.info(f"Current alembic version: {current_version}")
            
            if current_version == 'add_user_fk_001':
                # Update to the correct parent revision
                await db.execute(
                    text("UPDATE alembic_version SET version_num = 'add_predictions_001' WHERE version_num = 'add_user_fk_001'")
                )
                await db.commit()
                logger.info("Successfully updated alembic version to 'add_predictions_001'")
                
                # Verify the change
                result = await db.execute(text("SELECT version_num FROM alembic_version"))
                new_version = result.scalar_one_or_none()
                logger.info(f"New alembic version: {new_version}")
                
            elif current_version == 'add_predictions_001':
                logger.info("Alembic version is already correct")
                
            else:
                logger.warning(f"Unexpected alembic version: {current_version}")
                
    except Exception as e:
        logger.error(f"Error fixing alembic version: {str(e)}")
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(fix_alembic_version()) 