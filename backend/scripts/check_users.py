#!/usr/bin/env python3
"""
Script to check users table in production database
"""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_users_table():
    """Check all users in the database"""
    try:
        # Get database URL from environment
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            logger.error("DATABASE_URL not found in environment")
            return
        
        logger.info(f"Connecting to database: {database_url}")
        
        # Create async engine
        engine = create_async_engine(database_url, echo=False)
        
        async with engine.begin() as conn:
            # Check if users table exists
            result = await conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'users'
                );
            """))
            table_exists = result.scalar()
            
            if not table_exists:
                logger.error("Users table does not exist!")
                return
            
            logger.info("Users table exists. Checking contents...")
            
            # Get all users
            result = await conn.execute(text("SELECT * FROM users;"))
            users = result.fetchall()
            
            if not users:
                logger.warning("Users table is EMPTY!")
                print("=== USERS TABLE IS EMPTY ===")
                print("No users found in the database.")
                print("\n=== SAMPLE USER INSERT CODE ===")
                print_sample_insert_code()
            else:
                logger.info(f"Found {len(users)} users in the database:")
                print("=== USERS TABLE CONTENTS ===")
                for i, user in enumerate(users, 1):
                    print(f"User {i}:")
                    print(f"  ID: {user[0]}")
                    print(f"  Email: {user[1]}")
                    print(f"  Clerk ID: {user[2]}")
                    print(f"  Full Name: {user[3]}")
                    print(f"  First Name: {user[4]}")
                    print(f"  Last Name: {user[5]}")
                    print(f"  Avatar URL: {user[6]}")
                    print(f"  Created At: {user[7]}")
                    print(f"  Updated At: {user[8]}")
                    print()
        
        await engine.dispose()
        
    except Exception as e:
        logger.error(f"Error checking users table: {e}")
        raise

def print_sample_insert_code():
    """Print sample code to insert a test user"""
    print("SQL INSERT STATEMENT:")
    print("INSERT INTO users (id, email, clerk_id, full_name, first_name, last_name, avatar_url, created_at, updated_at)")
    print("VALUES (")
    print("    'user_test123',")
    print("    'test@example.com',")
    print("    'user_test123',")
    print("    'Test User',")
    print("    'Test',")
    print("    'User',")
    print("    'https://example.com/avatar.jpg',")
    print("    NOW(),")
    print("    NOW()")
    print(");")
    print()
    print("PYTHON/SQLALCHEMY INSERT CODE:")
    print("from sqlalchemy import create_engine, text")
    print("import os")
    print()
    print("database_url = os.getenv('DATABASE_URL')")
    print("engine = create_engine(database_url)")
    print()
    print("with engine.connect() as conn:")
    print("    conn.execute(text('''")
    print("        INSERT INTO users (id, email, clerk_id, full_name, first_name, last_name, avatar_url, created_at, updated_at)")
    print("        VALUES (")
    print("            'user_test123',")
    print("            'test@example.com',")
    print("            'user_test123',")
    print("            'Test User',")
    print("            'Test',")
    print("            'User',")
    print("            'https://example.com/avatar.jpg',")
    print("            NOW(),")
    print("            NOW()")
    print("        )")
    print("    '''))")
    print("    conn.commit()")
    print()
    print("OR USE THE EXISTING /auth/sync_user ENDPOINT:")
    print("curl -X POST https://backend.retainwiseanalytics.com/auth/sync_user \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{")
    print("    \"id\": \"user_test123\",")
    print("    \"email_addresses\": [{\"email_address\": \"test@example.com\"}],")
    print("    \"first_name\": \"Test\",")
    print("    \"last_name\": \"User\",")
    print("    \"image_url\": \"https://example.com/avatar.jpg\"")
    print("  }'")

if __name__ == "__main__":
    asyncio.run(check_users_table()) 
