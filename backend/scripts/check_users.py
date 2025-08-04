#!/usr/bin/env python3
"""
Script to check users table in production database
"""
import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, select
import logging

# Add the backend directory to Python path
sys.path.append('/app/backend')

from models import User

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
                print("\n=== USERS TABLE IS EMPTY ===")
                print("No users found in the database.")
                print("\n=== SAMPLE USER INSERT CODE ===")
                print_sample_insert_code()
            else:
                logger.info(f"Found {len(users)} users in the database:")
                print("\n=== USERS TABLE CONTENTS ===")
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
    print("""
# SQL INSERT STATEMENT:
INSERT INTO users (id, email, clerk_id, full_name, first_name, last_name, avatar_url, created_at, updated_at)
VALUES (
    'user_test123',
    'test@example.com',
    'user_test123',
    'Test User',
    'Test',
    'User',
    'https://example.com/avatar.jpg',
    NOW(),
    NOW()
);

# PYTHON/SQLALCHEMY INSERT CODE:
from backend.models import User
from datetime import datetime

new_user = User(
    id='user_test123',
    email='test@example.com',
    clerk_id='user_test123',
    full_name='Test User',
    first_name='Test',
    last_name='User',
    avatar_url='https://example.com/avatar.jpg',
    created_at=datetime.utcnow(),
    updated_at=datetime.utcnow()
)

db.add(new_user)
await db.commit()
await db.refresh(new_user)

# OR USE THE EXISTING /auth/sync_user ENDPOINT:
curl -X POST https://backend.retainwiseanalytics.com/auth/sync_user \\
  -H "Content-Type: application/json" \\
  -d '{
    "id": "user_test123",
    "email_addresses": [{"email_address": "test@example.com"}],
    "first_name": "Test",
    "last_name": "User",
    "image_url": "https://example.com/avatar.jpg"
  }'
""")

if __name__ == "__main__":
    asyncio.run(check_users_table()) 