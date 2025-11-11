#!/usr/bin/env python3
"""
Production-grade Alembic migration script for ECS environment
Features:
- Comprehensive error handling
- Database connectivity validation
- Detailed diagnostics
- Retry logic for transient failures
- Security: Masks sensitive data in logs
"""
import os
import sys
import subprocess
import logging
import time
import re
from pathlib import Path
from typing import Optional, Tuple

# Set up logging with detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def mask_password(url: str) -> str:
    """Mask password in database URL for safe logging"""
    return re.sub(r':([^:@]+)@', ':****@', url)

def validate_environment() -> Tuple[bool, str]:
    """Validate required environment variables and configuration"""
    logger.info("=" * 70)
    logger.info("🔍 VALIDATING ENVIRONMENT")
    logger.info("=" * 70)
    
    # Check DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return False, "DATABASE_URL environment variable is not set"
    
    logger.info(f"✅ DATABASE_URL: {mask_password(database_url)}")
    
    # Validate URL format
    if not database_url.startswith(("postgresql://", "postgresql+asyncpg://")):
        return False, f"Invalid DATABASE_URL format. Expected postgresql:// or postgresql+asyncpg://, got: {database_url.split(':')[0]}"
    
    # Check if alembic is installed
    result = subprocess.run(
        ["which", "alembic"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        return False, "Alembic is not installed or not in PATH"
    
    logger.info(f"✅ Alembic installed: {result.stdout.strip()}")
    
    # Check Python version
    python_version = sys.version
    logger.info(f"✅ Python version: {python_version.split()[0]}")
    
    # Check working directory
    backend_dir = Path(__file__).parent.parent
    alembic_ini = backend_dir / "alembic.ini"
    
    if not alembic_ini.exists():
        return False, f"alembic.ini not found at: {alembic_ini}"
    
    logger.info(f"✅ Working directory: {backend_dir}")
    logger.info(f"✅ Alembic config: {alembic_ini}")
    
    # Check migrations directory
    migrations_dir = backend_dir / "alembic" / "versions"
    if not migrations_dir.exists():
        return False, f"Migrations directory not found: {migrations_dir}"
    
    migration_files = list(migrations_dir.glob("*.py"))
    migration_count = len([f for f in migration_files if not f.name.startswith("__")])
    logger.info(f"✅ Found {migration_count} migration files")
    
    return True, "Environment validation successful"

def test_database_connection() -> Tuple[bool, str]:
    """Test database connectivity before running migrations"""
    logger.info("\n" + "=" * 70)
    logger.info("🔌 TESTING DATABASE CONNECTION")
    logger.info("=" * 70)
    
    try:
        import psycopg2
        
        database_url = os.getenv("DATABASE_URL")
        # Convert asyncpg URL to psycopg2 format
        if database_url.startswith("postgresql+asyncpg://"):
            database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        logger.info("Attempting to connect to database...")
        
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Test query
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()[0]
        logger.info(f"✅ Database connection successful")
        logger.info(f"✅ PostgreSQL version: {db_version.split(',')[0]}")
        
        # Check if alembic_version table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'alembic_version'
            );
        """)
        has_alembic_table = cursor.fetchone()[0]
        
        if has_alembic_table:
            cursor.execute("SELECT version_num FROM alembic_version;")
            current_version = cursor.fetchone()
            if current_version:
                logger.info(f"✅ Current database revision: {current_version[0]}")
            else:
                logger.info("⚠️  alembic_version table exists but is empty")
        else:
            logger.info("ℹ️  alembic_version table does not exist (first migration)")
        
        cursor.close()
        conn.close()
        
        return True, "Database connection test successful"
        
    except ImportError:
        return False, "psycopg2 module not installed (required for migrations)"
    except Exception as e:
        return False, f"Database connection failed: {str(e)}"

def check_current_revision() -> Optional[str]:
    """Check current database revision using Alembic"""
    logger.info("\n" + "=" * 70)
    logger.info("📋 CHECKING CURRENT REVISION")
    logger.info("=" * 70)
    
    try:
        backend_dir = Path(__file__).parent.parent
        
        result = subprocess.run(
            ["alembic", "current"],
            capture_output=True,
            text=True,
            cwd=backend_dir
        )
        
        if result.returncode == 0:
            revision = result.stdout.strip()
            if revision:
                logger.info(f"✅ Current revision: {revision}")
            else:
                logger.info("ℹ️  No current revision (database not initialized)")
            return revision
        else:
            logger.warning(f"⚠️  Could not get current revision: {result.stderr}")
            return None
            
    except Exception as e:
        logger.warning(f"⚠️  Exception checking revision: {str(e)}")
        return None

def run_migration(max_retries: int = 3) -> bool:
    """
    Run Alembic migration to head with retry logic
    
    Args:
        max_retries: Maximum number of retry attempts for transient failures
    
    Returns:
        True if migration successful, False otherwise
    """
    logger.info("\n" + "=" * 70)
    logger.info("🚀 RUNNING DATABASE MIGRATIONS")
    logger.info("=" * 70)
    
    backend_dir = Path(__file__).parent.parent
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Migration attempt {attempt}/{max_retries}")
            logger.info(f"Command: alembic upgrade head")
            logger.info(f"Working directory: {backend_dir}")
            
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                capture_output=True,
                text=True,
                cwd=backend_dir,
                timeout=300  # 5-minute timeout
            )
            
            # Log stdout (migration progress)
            if result.stdout:
                logger.info("Migration output:")
                for line in result.stdout.split('\n'):
                    if line.strip():
                        logger.info(f"  {line}")
            
            # Check result
            if result.returncode == 0:
                logger.info("=" * 70)
                logger.info("✅ MIGRATION COMPLETED SUCCESSFULLY")
                logger.info("=" * 70)
                return True
            else:
                logger.error(f"❌ Migration failed with return code: {result.returncode}")
                
                # Log stderr (errors)
                if result.stderr:
                    logger.error("Migration errors:")
                    for line in result.stderr.split('\n'):
                        if line.strip():
                            logger.error(f"  {line}")
                
                # Check if it's a transient error (retry-able)
                if attempt < max_retries and "connection" in result.stderr.lower():
                    logger.warning(f"⚠️  Transient connection error detected. Retrying in 5 seconds...")
                    time.sleep(5)
                    continue
                else:
                    logger.error("=" * 70)
                    logger.error("❌ MIGRATION FAILED")
                    logger.error("=" * 70)
                    return False
                    
        except subprocess.TimeoutExpired:
            logger.error(f"❌ Migration timed out after 300 seconds")
            if attempt < max_retries:
                logger.warning(f"⚠️  Retrying in 5 seconds...")
                time.sleep(5)
                continue
            return False
            
        except Exception as e:
            logger.error(f"❌ Exception during migration: {str(e)}")
            if attempt < max_retries:
                logger.warning(f"⚠️  Retrying in 5 seconds...")
                time.sleep(5)
                continue
            return False
    
    return False

def main() -> int:
    """Main entry point for migration script"""
    logger.info("\n" + "╔" + "=" * 68 + "╗")
    logger.info("║" + " " * 15 + "RETAINWISE DATABASE MIGRATION" + " " * 24 + "║")
    logger.info("║" + " " * 20 + "Production-Grade Script" + " " * 25 + "║")
    logger.info("╚" + "=" * 68 + "╝\n")
    
    try:
        # Step 1: Validate environment
        is_valid, message = validate_environment()
        if not is_valid:
            logger.error(f"❌ Environment validation failed: {message}")
            return 1
        
        logger.info(f"✅ {message}")
        
        # Step 2: Test database connection
        is_connected, message = test_database_connection()
        if not is_connected:
            logger.error(f"❌ Database connection test failed: {message}")
            return 1
        
        logger.info(f"✅ {message}")
        
        # Step 3: Check current revision
        check_current_revision()
        
        # Step 4: Run migration
        success = run_migration(max_retries=3)
        
        if success:
            logger.info("\n" + "╔" + "=" * 68 + "╗")
            logger.info("║" + " " * 22 + "✅ SUCCESS!" + " " * 33 + "║")
            logger.info("║" + " " * 15 + "Database schema is up to date" + " " * 24 + "║")
            logger.info("╚" + "=" * 68 + "╝\n")
            return 0
        else:
            logger.error("\n" + "╔" + "=" * 68 + "╗")
            logger.error("║" + " " * 22 + "❌ FAILURE!" + " " * 32 + "║")
            logger.error("║" + " " * 12 + "Migration failed. Check logs above." + " " * 20 + "║")
            logger.error("╚" + "=" * 68 + "╝\n")
            return 1
            
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Migration interrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"❌ Unexpected error in migration script: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 
