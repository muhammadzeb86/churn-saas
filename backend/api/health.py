"""
Database health check utilities
"""
from sqlalchemy import text
from api.database import AsyncSessionMaker

async def db_ping_ok() -> bool:
    """Test database connectivity with a simple ping query"""
    try:
        async with AsyncSessionMaker() as session:
            res = await session.execute(text("SELECT 1"))
            row = res.fetchone()  # no await
            return bool(row and row[0] == 1)
    except Exception:
        return False 