"""
搜索路由：并行进行关键词与向量检索，调用重排与对话生成答案。
"""
import logging
import math
import asyncio
from typing import List, Tuple
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from ..db import get_db
from ..models import Document
from ..schemas import SearchRequest, SearchResponse, SearchItem
from ..services.llms_gateway_client import LLMsGatewayClient

router = APIRouter(prefix="/search", tags=["Search"])
logger = logging.getLogger(__name__)


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """计算两个向量的余弦相似度"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@router.post("", response_model=SearchResponse)
async def search(payload: SearchRequest, db: AsyncSession = Depends(get_db)):
    """并行执行关键词与向量搜索，重排并生成最终答案"""
    try:
        client = LLMsGatewayClient()
        query_emb = await client.embed_text(payload.query)

        # 关键词查询（模糊匹配摘要）
        stmt_kw = select(Document).where(Document.content_summary.ilike(f"%{payload.query}%"))

        # 数据库 KNN（使用 pgvector + HNSW + L2 距离）
        # 将查询向量序列化为 pgvector 字面量字符串，例如: "[0.12345678,-0.00001234,...]"
        query_vec_str = "[" + ",".join(f"{x:.8f}" for x in query_emb) + "]"
        stmt_vec = text(
            """
            SELECT id, content_summary, keywords,
                   (embedding <-> :query_vec::vector) AS distance
            FROM documents
            WHERE embedding IS NOT NULL
            ORDER BY distance ASC
            LIMIT :top_k
            """
        )

        # 并行执行两类数据库查询
        res_kw_task = asyncio.create_task(db.execute(stmt_kw))
        res_vec_task = asyncio.create_task(db.execute(stmt_vec, {"query_vec": query_vec_str, "top_k": payload.top_k}))
        res_kw, res_vec = await asyncio.gather(res_kw_task, res_vec_task)

        # 关键词结果
        kw_docs: List[Document] = list(res_kw.scalars())
        kw_items: List[SearchItem] = [
            SearchItem(id=d.id, score=0.5, summary=d.content_summary, keywords=d.keywords)
            for d in kw_docs
        ]

        # 向量 KNN 结果（距离越小越相似，将其映射为 (1 / (1 + distance)) 作为分数）
        vec_rows = res_vec.all()
        vec_items: List[SearchItem] = [
            SearchItem(
                id=row._mapping["id"],
                score=1.0 / (1.0 + float(row._mapping["distance"])),
                summary=row._mapping["content_summary"],
                keywords=row._mapping["keywords"],
            )
            for row in vec_rows
        ]

        # 合并并去重（保留最高分）
        merged: dict[int, SearchItem] = {}
        for item in kw_items + vec_items:
            if item.id not in merged or merged[item.id].score < item.score:
                merged[item.id] = item
        items = list(merged.values())

        # 调用重排
        reranked_raw = await client.rerank(
            query=payload.query,
            items=[item.model_dump() for item in items],
        )
        # 将重排结果映射回 SearchItem
        reranked_items = [
            SearchItem(
                id=it.get("id"),
                score=float(it.get("score", 0.0)),
                summary=it.get("summary"),
                keywords=it.get("keywords"),
            )
            for it in reranked_raw
        ]

        # 调用对话生成最终答案
        answer = await client.chat_completions(
            prompt=payload.query,
            context=[item.model_dump() for item in reranked_items],
        )
        await client.close()

        return SearchResponse(answer=answer or "", items=reranked_items)
    except Exception as e:
        logger.exception("搜索流程失败: %s", e)
        raise HTTPException(status_code=500, detail=f"搜索流程失败: {e}")