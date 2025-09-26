"""
模型模块：定义知识库文档模型。
"""
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Integer, LargeBinary, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ARRAY
from pgvector.sqlalchemy import Vector
from .db import Base

# 向量维度常量（可根据上游嵌入模型调整）
EMBEDDING_DIMENSION = 1024


class Document(Base):
    """知识库文档模型：存储文件/文本及其向量与元信息"""
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str] = mapped_column(String(20))  # 'file' or 'text'
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 二进制改为独立表存储
    # binary_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    content_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # 使用 pgvector 的向量类型，存储 content_summary + keywords 的向量
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSION), nullable=True
    )

    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DocumentFile(Base):
    """文档二进制内容表：与 documents 一对一，通过 file_id 关联"""
    __tablename__ = "document_files"

    # 使用文档 id 作为主键与外键，保证一对一
    file_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    binary_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)