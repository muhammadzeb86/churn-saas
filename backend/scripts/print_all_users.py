import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Force deployment trigger
async def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise Exception("DATABASE_URL not set")
    if "asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(database_url, echo=False)
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT * FROM users;"))
        rows = result.fetchall()
        print(f"Total users: {len(rows)}")
        for row in rows:
            print(row)
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main()) 