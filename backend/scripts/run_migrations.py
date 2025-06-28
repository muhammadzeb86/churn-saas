#!/usr/bin/env python3
"""
Script to run Alembic migrations in ECS environment
"""
import os
import sys
import subprocess
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Run Alembic migration to head"""
    try:
        # Change to backend directory
        backend_dir = Path(__file__).parent.parent
        os.chdir(backend_dir)
        
        logger.info(f"Running migrations from directory: {os.getcwd()}")
        
        # Check if DATABASE_URL is set
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            logger.error("DATABASE_URL environment variable is not set")
            sys.exit(1)
        
        logger.info("DATABASE_URL is configured")
        
        # Run alembic upgrade head
        logger.info("Running: alembic upgrade head")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=backend_dir
        )
        
        if result.returncode == 0:
            logger.info("Migration completed successfully")
            logger.info(f"Output: {result.stdout}")
            return True
        else:
            logger.error(f"Migration failed with return code: {result.returncode}")
            logger.error(f"Error output: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Exception during migration: {str(e)}")
        return False

def check_current_revision():
    """Check current database revision"""
    try:
        backend_dir = Path(__file__).parent.parent
        os.chdir(backend_dir)
        
        logger.info("Checking current database revision...")
        result = subprocess.run(
            ["alembic", "current"],
            capture_output=True,
            text=True,
            cwd=backend_dir
        )
        
        if result.returncode == 0:
            logger.info(f"Current revision: {result.stdout.strip()}")
            return result.stdout.strip()
        else:
            logger.error(f"Failed to get current revision: {result.stderr}")
            return None
            
    except Exception as e:
        logger.error(f"Exception checking revision: {str(e)}")
        return None

if __name__ == "__main__":
    logger.info("Starting database migration process...")
    
    # Check current revision first
    current_rev = check_current_revision()
    
    # Run migration
    success = run_migration()
    
    if success:
        logger.info("Migration process completed successfully")
        sys.exit(0)
    else:
        logger.error("Migration process failed")
        sys.exit(1) 