"""
数据库模块：初始化异步引擎与会话工厂，并提供 FastAPI 依赖。
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from .config import DATABASE_URL


class Base(DeclarativeBase):
    """SQLAlchemy Declarative 基类"""
    pass


# 创建异步数据库引擎
engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# 创建异步会话工厂
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：提供数据库会话"""
    async with SessionLocal() as session:
        yield session