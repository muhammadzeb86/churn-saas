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

# Create async session maker
AsyncSessionMaker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# Base class for declarative models
class Base(DeclarativeBase):
    pass

# Dependency to get async database session
async def get_db() -> AsyncSession:
    async with AsyncSessionMaker() as session:
        try:
            yield session
        finally:
            await session.close()

# Initialize database tables
async def init_db():
    async with engine.begin() as conn:
        # Import all models here to ensure they are registered with Base
        from models import User  # noqa
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

# Example of how to use the session in FastAPI endpoints:
"""
from fastapi import Depends

@app.get("/items")
async def get_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item))
    items = result.scalars().all()
    return items
""" 