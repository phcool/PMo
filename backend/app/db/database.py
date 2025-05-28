import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL
DATABASE_URL = os.getenv("DATABASE_URL", "")
# Convert to async URL
ASYNC_DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')

# Create synchronous database engine(for alembic)
engine = create_engine(DATABASE_URL)

# Create asynchronous database engine (for application)
async_engine = create_async_engine(ASYNC_DATABASE_URL)

# Create session factories
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=async_engine, 
    class_=AsyncSession
)

from app.models.db_models import Base


# Get database session (asynchronous)
async def get_async_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close() 