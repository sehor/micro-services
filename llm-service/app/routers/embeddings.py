# -*- coding: utf-8 -*-
"""
Embedding 路由：POST /api/v1/embeddings/create
默认使用 provider=LMStudio，model=text-embedding-qwen3-embedding-0.6b。
对接本地 LM Studio 的 OpenAI 兼容 /v1/embeddings 接口，接收文本返回向量。
"""
import logging
from typing import List, Union
import time  # 新增：耗时统计
import json  # 新增：日志中安全打印 payload 大小

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..db import get_db
from ..models import ProviderCredential
from ..schemas import EmbeddingRequest, EmbeddingResponse, Usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/embeddings", tags=["embeddings"])


@router.post("/create", response_model=EmbeddingResponse)
async def create_embedding(req: EmbeddingRequest, db: AsyncSession = Depends(get_db)) -> EmbeddingResponse:
    """创建文本向量：
    - 从数据库读取指定 provider 的 base_url 与 api_key（默认 LMStudio）
    - 调用 OpenAI 兼容的 /v1/embeddings 接口
    - 根据单文本或多文本返回 vector 或 vectors
    """
    t0 = time.perf_counter()
    # 起始日志：请求关键信息
    try:
        is_multi = isinstance(req.input, list)
        logger.info(
            "[Embeddings] start provider=%s model=%s is_multi=%s",
            req.provider, req.model, is_multi,
        )
    except Exception:
        # 防御：日志不影响主流程
        pass

    # 1) 基本校验
    if req.input is None or (isinstance(req.input, str) and req.input.strip() == "") or (isinstance(req.input, list) and len(req.input) == 0):
        raise HTTPException(status_code=400, detail="input 不能为空")

    # 2) 读取凭证（按 provider 最新一条）
    res = await db.execute(
        select(ProviderCredential).where(ProviderCredential.provider == req.provider).order_by(ProviderCredential.id.desc())
    )
    cred = res.scalar_one_or_none()
    if not cred:
        logger.warning("[Embeddings] credential missing for provider=%s", req.provider)
        raise HTTPException(status_code=400, detail=f"No credential configured for provider: {req.provider}")
    # 显式校验 base_url
    if not cred.base_url or not cred.base_url.strip():
        logger.warning("[Embeddings] base_url not configured for provider=%s", req.provider)
        raise HTTPException(status_code=400, detail=f"Provider {req.provider} base_url 未配置，请在数据库中设置后再调用。")

    # 3) 构建 URL（兼容多种 base_url 书写）
    base = (cred.base_url or "").rstrip("/")
    if base.endswith("/embeddings"):
        url = base
    elif base.endswith("/v1"):
        url = f"{base}/embeddings"
    elif base.endswith("/v1/embeddings"):
        url = base
    else:
        url = f"{base}/v1/embeddings"
    logger.info("[Embeddings] upstream url resolved: %s", url)

    # 4) 构建请求
    payload = {"model": req.model, "input": req.input}
    headers = {"Content-Type": "application/json"}
    has_key = bool(cred.api_key)
    if cred.api_key:
        headers["Authorization"] = f"Bearer {cred.api_key}"
    # 打印请求体大小而非明文
    try:
        payload_text = json.dumps(payload, ensure_ascii=False)
        logger.info(
            "[Embeddings] prepared request headers(has_key=%s) payload_size=%d", has_key, len(payload_text)
        )
    except Exception:
        pass

    # 5) 下游调用
    try:
        t1 = time.perf_counter()
        # 单独设置较短的连接超时与总超时，避免长时间卡住
        timeout = httpx.Timeout(connect=5.0, read=55.0, write=10.0, pool=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            logger.info("[Embeddings] posting to upstream ...")
            resp = await client.post(url, json=payload, headers=headers)
            elapsed_upstream = time.perf_counter() - t1
            logger.info(
                "[Embeddings] upstream responded status=%s elapsed=%.3fs",
                getattr(resp, "status_code", "?"), elapsed_upstream,
            )
            resp.raise_for_status()
            text = resp.text
            # 打印最多前 500 字符的响应预览，避免日志过大
            preview = text[:500]
            if len(text) > 500:
                preview += " ...[truncated]"
            logger.info("[Embeddings] upstream body preview: %s", preview)
            data = resp.json()
    except httpx.HTTPStatusError as e:
        logger.exception("Embedding 下游返回错误: %s", getattr(e.response, "text", str(e)))
        raise HTTPException(status_code=e.response.status_code if e.response else 502, detail=f"Embeddings upstream error: {str(e)}")
    except Exception as e:
        logger.exception("Embedding 调用失败")
        raise HTTPException(status_code=502, detail=f"Embeddings request failed: {str(e)}")

    # 6) 解析响应（OpenAI 兼容）
    try:
        items = data.get("data", [])
        vectors: List[List[float]] = []
        for it in items:
            vec = it.get("embedding")
            if not isinstance(vec, list):
                raise ValueError("invalid embedding format")
            vectors.append(vec)

        usage = None
        if "usage" in data:
            u = data["usage"]
            usage = Usage(
                prompt_tokens=u.get("prompt_tokens"),
                completion_tokens=u.get("completion_tokens"),
                total_tokens=u.get("total_tokens"),
                cost=u.get("cost"),
            )

        # 单文本 -> vector；多文本 -> vectors
        if isinstance(req.input, list):
            dims = [len(v) for v in vectors]
            logger.info("[Embeddings] success vectors=%d dims=%s total_elapsed=%.3fs", len(vectors), dims, time.perf_counter()-t0)
            return EmbeddingResponse(model=req.model, vectors=vectors, usage=usage)
        else:
            # 防御：若下游返回多条也取第一条
            vec = vectors[0] if vectors else []
            logger.info("[Embeddings] success vector_dim=%d total_elapsed=%.3fs", len(vec), time.perf_counter()-t0)
            return EmbeddingResponse(model=req.model, vector=vec, usage=usage)
    except Exception as e:
        logger.exception("Embedding 响应解析失败: %s", str(e))
        raise HTTPException(status_code=502, detail=f"Embeddings parse failed: {str(e)}")