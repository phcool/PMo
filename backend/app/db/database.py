import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取数据库URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/dlmonitor")
# 转换为异步URL
ASYNC_DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')

# 创建同步数据库引擎 (用于Alembic等工具)
engine = create_engine(DATABASE_URL)

# 创建异步数据库引擎 (用于应用)
async_engine = create_async_engine(ASYNC_DATABASE_URL)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=async_engine, 
    class_=AsyncSession
)

# 获取Base类的引用（已在models.db_models中定义）
from app.models.db_models import Base

# 获取数据库会话 (同步)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 获取数据库会话 (异步)
async def get_async_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close() 