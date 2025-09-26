# -*- coding: utf-8 -*-
"""
数据库引擎与会话管理。
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from .config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy 基类"""
    pass


# 创建全局异步引擎与会话工厂
_engine = create_async_engine(get_settings().database_url, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(bind=_engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：提供异步数据库会话"""
    async with AsyncSessionLocal() as session:
        yield session


async def create_all() -> None:
    """创建所有数据表（仅用于开发/初始化）"""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_engine():
    """返回全局 AsyncEngine，供管理后台等模块复用。"""
    return _engine