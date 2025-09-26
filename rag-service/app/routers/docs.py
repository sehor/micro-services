"""
文档 CRUD 路由：单独管理按 id 的获取、更新与删除。
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from ..db import get_db
from ..models import Document
from ..schemas import DocumentResponse, DocumentUpdateRequest

router = APIRouter(prefix="/kb", tags=["KB"])  # 与入库路由保持相同前缀与分组
logger = logging.getLogger(__name__)


@router.get("/docs/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    """按 id 获取文档（不返回二进制）"""
    try:
        stmt = select(Document).where(Document.id == doc_id)
        res = await db.execute(stmt)
        doc = res.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        return DocumentResponse(
            id=doc.id,
            title=doc.title,
            source_type=doc.source_type,
            filename=doc.filename,
            mime_type=doc.mime_type,
            size_bytes=doc.size_bytes,
            content_summary=doc.content_summary,
            keywords=doc.keywords,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取文档失败: %s", e)
        raise HTTPException(status_code=500, detail=f"获取文档失败: {e}")


@router.patch("/docs/{doc_id}", response_model=DocumentResponse)
async def update_document(doc_id: int, payload: DocumentUpdateRequest, db: AsyncSession = Depends(get_db)):
    """按 id 更新文档的标题、摘要与关键词（不改动 embedding 与二进制）"""
    try:
        stmt = select(Document).where(Document.id == doc_id)
        res = await db.execute(stmt)
        doc = res.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")

        if payload.title is not None:
            doc.title = payload.title
        if payload.content_summary is not None:
            doc.content_summary = payload.content_summary
        if payload.keywords is not None:
            doc.keywords = payload.keywords

        await db.commit()
        await db.refresh(doc)
        return DocumentResponse(
            id=doc.id,
            title=doc.title,
            source_type=doc.source_type,
            filename=doc.filename,
            mime_type=doc.mime_type,
            size_bytes=doc.size_bytes,
            content_summary=doc.content_summary,
            keywords=doc.keywords,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("更新文档失败: %s", e)
        raise HTTPException(status_code=500, detail=f"更新文档失败: {e}")


@router.delete("/docs/{doc_id}")
async def delete_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    """按 id 删除文档（级联删除二进制，模型已配置外键级联）"""
    try:
        # 仅检查是否存在
        stmt = select(Document.id).where(Document.id == doc_id)
        res = await db.execute(stmt)
        exists = res.scalar_one_or_none()
        if not exists:
            raise HTTPException(status_code=404, detail="文档不存在")
        # 删除文档（document_files 通过 FK ondelete=cascade 自动删除）
        await db.execute(delete(Document).where(Document.id == doc_id))
        await db.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("删除文档失败: %s", e)
        raise HTTPException(status_code=500, detail=f"删除文档失败: {e}")