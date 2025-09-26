import os
import logging
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    String,
    Integer,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# -------------------------------
# 环境与日志
# -------------------------------
load_dotenv()
logger = logging.getLogger("todo-service")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logger.error("环境变量 DATABASE_URL 未配置，无法启动服务")
    raise RuntimeError("DATABASE_URL is required in environment variables")

DB_AUTO_CREATE = os.getenv("DB_AUTO_CREATE", "false").lower() == "true"

# -------------------------------
# 数据库与模型
# -------------------------------
class Base(DeclarativeBase):
    """SQLAlchemy ORM 基类。"""


engine = create_async_engine(DATABASE_URL, echo=logger.level == logging.DEBUG, future=True)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Todo(Base):
    """代办事项实体。"""

    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    # 新增：开始时间与截止时间
    start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # 由 todo 表持有外键 attribute_id
    attribute_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("todo_attributes.id", ondelete="SET NULL"), nullable=True
    )

    # 一对一：指向属性
    attributes: Mapped[Optional["TodoAttribute"]] = relationship(
        back_populates="todo", uselist=False, foreign_keys="Todo.attribute_id"
    )


class TodoAttribute(Base):
    """代办事项属性实体（独立表）。"""

    __tablename__ = "todo_attributes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 注意：按需求文档字段名（包含原文拼写）
    mergency: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    corlor: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # 反向一对一：由 Todo.attribute_id 维护关联
    todo: Mapped[Optional[Todo]] = relationship(back_populates="attributes", uselist=False)


# -------------------------------
# Pydantic Schemas
# -------------------------------
class AttributeBase(BaseModel):
    """代办事项属性请求/基础模型。"""

    mergency: int = Field(default=0, ge=0)
    corlor: Optional[str] = Field(default=None, max_length=32)
    category: Optional[str] = Field(default=None, max_length=64)


class AttributeCreate(AttributeBase):
    """创建属性的入参模型。"""


class AttributeUpdate(BaseModel):
    """更新属性的入参模型（全量/部分字段）。"""

    mergency: Optional[int] = Field(default=None, ge=0)
    corlor: Optional[str] = Field(default=None, max_length=32)
    category: Optional[str] = Field(default=None, max_length=64)


class AttributeRead(AttributeBase):
    """属性的返回模型。"""

    model_config = ConfigDict(from_attributes=True)
    id: int


class TodoBase(BaseModel):
    """代办事项基础模型。"""

    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    is_completed: bool = False
    # 新增：开始时间与截止时间（可选）
    start_at: Optional[datetime] = None
    due_at: Optional[datetime] = None


class TodoCreate(TodoBase):
    """创建代办事项的入参模型。"""


class TodoCreateWithAttr(TodoCreate):
    """创建代办事项时可同时创建属性。"""

    attributes: Optional[AttributeCreate] = None


class TodoUpdate(BaseModel):
    """更新代办事项的入参模型。"""

    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    is_completed: Optional[bool] = None
    # 新增：开始时间与截止时间（可选）
    start_at: Optional[datetime] = None
    due_at: Optional[datetime] = None


class TodoRead(TodoBase):
    """代办事项返回模型。"""

    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
    attributes: Optional[AttributeRead] = None

# 新增：剩余时间查询的返回模型
class TodoRemainingTimeRead(BaseModel):
    """事项剩余时间返回模型。"""

    todo_id: int
    due_at: datetime
    remaining_seconds: float
    is_overdue: bool
 
# -------------------------------
# 依赖与初始化
# -------------------------------
async def get_session() -> AsyncSession:
    """提供数据库会话依赖。"""
    session: AsyncSession = async_session()
    try:
        yield session
    except Exception:
        logger.exception("数据库会话处理异常")
        raise
    finally:
        await session.close()


async def init_db() -> None:
    """按需初始化数据库，并进行一次轻量迁移。"""
    if not DB_AUTO_CREATE:
        return
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # 轻量迁移：添加 todos.attribute_id
            await conn.exec_driver_sql(
                "ALTER TABLE IF EXISTS todos ADD COLUMN IF NOT EXISTS attribute_id INTEGER"
            )
            # 新增列：开始时间与截止时间
            await conn.exec_driver_sql(
                "ALTER TABLE IF EXISTS todos ADD COLUMN IF NOT EXISTS start_at TIMESTAMPTZ"
            )
            await conn.exec_driver_sql(
                "ALTER TABLE IF EXISTS todos ADD COLUMN IF NOT EXISTS due_at TIMESTAMPTZ"
            )
            # 建立外键（若不存在）
            await conn.exec_driver_sql(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'fk_todos_attribute_id'
                    ) THEN
                        ALTER TABLE todos
                        ADD CONSTRAINT fk_todos_attribute_id
                        FOREIGN KEY (attribute_id) REFERENCES todo_attributes(id)
                        ON DELETE SET NULL;
                    END IF;
                END $$;
                """
            )
            # 若老表中仍有 todo_id 且为非空，放宽为可空
            res = await conn.exec_driver_sql(
                """
                SELECT is_nullable FROM information_schema.columns
                WHERE table_name='todo_attributes' AND column_name='todo_id'
                """
            )
            row = res.fetchone()
            if row is not None and str(row[0]).upper() == 'NO':
                await conn.exec_driver_sql("ALTER TABLE todo_attributes ALTER COLUMN todo_id DROP NOT NULL")
        logger.info("数据库表已确保创建并完成轻量迁移")
    except Exception:
        logger.exception("启动建表/迁移失败")
        raise RuntimeError("Failed to create tables or run lightweight migration on startup")