import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check_users_schema():
    """Check the data type of users.id column in the live database"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not set")
        return
    
    if "asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    
    engine = create_async_engine(database_url, echo=False)
    
    try:
        async with engine.begin() as conn:
            # Check the data type of users.id column
            result = await conn.execute(text("""
                SELECT data_type, udt_name, character_maximum_length
                FROM information_schema.columns
                WHERE table_name='users' AND column_name='id';
            """))
            row = result.fetchone()
            
            if row:
                print(f"users.id column type: {row[0]}")
                print(f"UDT name: {row[1]}")
                print(f"Max length: {row[2]}")
            else:
                print("No users.id column found")
            
            # Also check current Alembic revision
            try:
                result = await conn.execute(text("SELECT version_num FROM alembic_version;"))
                version = result.scalar()
                print(f"Current Alembic revision: {version}")
            except Exception as e:
                print(f"Could not get Alembic revision: {e}")
                
    except Exception as e:
        print(f"Error checking schema: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_users_schema()) 
