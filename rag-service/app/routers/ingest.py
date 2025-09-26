"""
入库路由：处理文件上传与文本写入知识库。
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from ..db import get_db
from ..models import Document, DocumentFile
from ..schemas import DocumentResponse, TextIngestRequest
from ..services.llms_gateway_client import LLMsGatewayClient

router = APIRouter(prefix="/kb", tags=["KB"])
logger = logging.getLogger(__name__)


@router.post("/files", response_model=DocumentResponse)
async def ingest_file(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """接收文件，调用解析与向量化后存入数据库（二进制存入独立表）"""
    try:
        content = await file.read()
        client = LLMsGatewayClient()
        parsed = await client.parse_file(content, file.filename, file.content_type or "application/octet-stream")
        summary: Optional[str] = parsed.get("summary") or parsed.get("content_summary")
        keywords: Optional[List[str]] = parsed.get("keywords")

        # 组合用于向量化的文本：summary + keywords
        parts: List[str] = []
        if summary:
            parts.append(summary)
        if keywords:
            parts.append(" ".join(keywords))
        text_for_embedding = " ".join(parts).strip() or (file.filename or "")
        embedding = await client.embed_text(text_for_embedding)
        await client.close()

        # 先写入 Document 元信息
        doc = Document(
            title=parsed.get("title"),
            source_type="file",
            mime_type=file.content_type,
            filename=file.filename,
            size_bytes=len(content),
            content_summary=summary,
            keywords=keywords,
            embedding=embedding,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        # 再写入二进制内容到独立表（与文档一对一）
        doc_file = DocumentFile(file_id=doc.id, binary_data=content)
        db.add(doc_file)
        await db.commit()

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
    except Exception as e:
        logger.exception("文件入库失败: %s", e)
        raise HTTPException(status_code=500, detail=f"文件入库失败: {e}")


@router.post("/texts", response_model=DocumentResponse)
async def ingest_text(payload: TextIngestRequest, db: AsyncSession = Depends(get_db)):
    """接收文本，先调用 chat/completions 处理，再向量化并入库"""
    try:
        client = LLMsGatewayClient()
        processed_text = await client.chat_completions(prompt=payload.text, context=None)
        # 对文本类数据，keywords 通常为空，直接对处理后的文本向量化
        embedding = await client.embed_text(processed_text)
        await client.close()

        doc = Document(
            title=payload.title,
            source_type="text",
            content_summary=processed_text,
            keywords=None,
            embedding=embedding,
        )
        db.add(doc)
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
    except Exception as e:
        logger.exception("文本入库失败: %s", e)
        raise HTTPException(status_code=500, detail=f"文本入库失败: {e}")