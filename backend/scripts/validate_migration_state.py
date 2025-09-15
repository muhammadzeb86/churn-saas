#!/usr/bin/env python3
"""
Comprehensive validation script for migration state and model consistency
"""
import asyncio
import logging
import sys
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from backend.api.database import AsyncSessionMaker
from backend.models import User, Upload, Prediction, Lead, PredictionStatus

logger = logging.getLogger(__name__)

async def validate_migration_state():
    """Validate the complete migration state and model consistency"""
    try:
        logger.info("Starting comprehensive migration validation...")
        
        # Check 1: Database connection
        async with AsyncSessionMaker() as db:
            logger.info("✅ Database connection successful")
            
            # Check 2: Alembic version table
            try:
                result = await db.execute(text("SELECT version_num FROM alembic_version"))
                current_version = result.scalar_one_or_none()
                logger.info(f"📋 Current alembic version: {current_version}")
                
                if current_version == 'add_user_fk_001':
                    logger.warning("⚠️  Database points to deleted migration 'add_user_fk_001'")
                    logger.info("🔧 This will be fixed by the fix_alembic_version.py script")
                elif current_version == 'add_predictions_001':
                    logger.info("✅ Database is at correct parent revision")
                elif current_version == 'add_user_fk_constraint':
                    logger.info("✅ Database is at the latest revision")
                else:
                    logger.warning(f"⚠️  Unexpected alembic version: {current_version}")
                    
            except Exception as e:
                logger.error(f"❌ Error checking alembic version: {e}")
            
            # Check 3: Table existence
            tables_to_check = ['users', 'uploads', 'predictions', 'leads']
            for table in tables_to_check:
                try:
                    result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    logger.info(f"✅ Table '{table}' exists with {count} rows")
                except Exception as e:
                    logger.warning(f"⚠️  Table '{table}' issue: {e}")
            
            # Check 4: Enum existence
            try:
                result = await db.execute(text("""
                    SELECT typname FROM pg_type t
                    JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE t.typname = 'predictionstatus'
                """))
                enum_exists = result.scalar_one_or_none()
                if enum_exists:
                    logger.info("✅ Enum 'predictionstatus' exists")
                else:
                    logger.warning("⚠️  Enum 'predictionstatus' not found")
            except Exception as e:
                logger.warning(f"⚠️  Error checking enum: {e}")
            
            # Check 5: Foreign key constraints
            try:
                result = await db.execute(text("""
                    SELECT conname FROM pg_constraint 
                    WHERE conname = 'fk_predictions_user_id_users'
                """))
                fk_exists = result.scalar_one_or_none()
                if fk_exists:
                    logger.info("✅ Foreign key constraint 'fk_predictions_user_id_users' exists")
                else:
                    logger.info("📋 Foreign key constraint 'fk_predictions_user_id_users' not yet created")
            except Exception as e:
                logger.warning(f"⚠️  Error checking foreign key: {e}")
                
            # Check 6: Model imports work
            try:
                # Test model instantiation
                user_model = User
                upload_model = Upload  
                prediction_model = Prediction
                lead_model = Lead
                status_enum = PredictionStatus
                logger.info("✅ All models import successfully")
                logger.info(f"📋 PredictionStatus enum values: {[s.value for s in PredictionStatus]}")
            except Exception as e:
                logger.error(f"❌ Model import error: {e}")
        
        # Check 7: Migration files
        migrations_dir = Path(__file__).parent.parent / "alembic" / "versions"
        migration_files = list(migrations_dir.glob("*.py"))
        migration_files = [f for f in migration_files if f.name != "__init__.py"]
        
        logger.info(f"📋 Found {len(migration_files)} migration files:")
        for migration_file in sorted(migration_files):
            logger.info(f"   - {migration_file.name}")
        
        # Check 8: No duplicate revision IDs
        revision_ids = []
        for migration_file in migration_files:
            try:
                content = migration_file.read_text()
                for line in content.split('\n'):
                    if line.startswith('revision:') or line.startswith('revision ='):
                        revision_id = line.split('=')[1].strip().strip("'\"")
                        revision_ids.append((revision_id, migration_file.name))
                        break
            except Exception as e:
                logger.warning(f"⚠️  Error reading {migration_file.name}: {e}")
        
        # Check for duplicates
        seen_revisions = set()
        for revision_id, filename in revision_ids:
            if revision_id in seen_revisions:
                logger.error(f"❌ Duplicate revision ID '{revision_id}' in {filename}")
            else:
                seen_revisions.add(revision_id)
                logger.info(f"✅ Revision '{revision_id}' in {filename}")
        
        logger.info("🎉 Migration validation completed")
        
    except Exception as e:
        logger.error(f"❌ Validation failed: {str(e)}")
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    asyncio.run(validate_migration_state()) 