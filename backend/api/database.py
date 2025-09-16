from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Get database URL and replace protocol for asyncpg
DATABASE_URL = os.getenv("DATABASE_URL", "").replace("postgresql://", "postgresql+asyncpg://")

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # Set to False in production
    pool_pre_ping=True,  # Enable connection pool pre-ping
    pool_size=10,  # Maximum number of connections in the pool
    max_overflow=20  # Maximum number of connections that can be created beyond pool_size
)

# canonical factory (lowercase snake_case)
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# optional alias for backward compatibility (TitleCase used elsewhere)
AsyncSessionMaker = async_session_maker

# Base class for declarative models
class Base(DeclarativeBase):
    pass

# Dependency to get async database session (for FastAPI)
async def get_db() -> AsyncSession:
    async with AsyncSessionMaker() as session:
        try:
            yield session
        finally:
            await session.close()

# Context manager to get async database session (for workers/services)
def get_async_session():
    """
    Context manager for async database sessions
    Used by workers and services outside of FastAPI request context
    """
    return AsyncSessionMaker()

# Initialize database tables
async def init_db():
    async with engine.begin() as conn:
        # Import all models here to ensure they are registered with Base
        from backend.models import User, Lead  # noqa
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

# Export all the important names
__all__ = [
    "engine", "Base", "async_session_maker", "AsyncSessionMaker", "AsyncSession", 
    "get_db", "get_async_session", "init_db"
]

# Example of how to use the session in FastAPI endpoints:
"""
from fastapi import Depends

@app.get("/items")
async def get_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item))
    items = result.scalars().all()
    return items
"""
