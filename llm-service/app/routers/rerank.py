# -*- coding: utf-8 -*-
"""
Rerank 路由：POST /api/v1/rerank
- 当 provider=LMStudio 时：后端本地执行 MMR（Maximal Marginal Relevance）重排：
  通过 /v1/embeddings 获取向量并计算排序，返回 {index, score, document}
- 当 provider!=LMStudio 时：按正常流程，通过 /v1/chat/completions 以提示词方式执行重排，
  要求模型严格返回 JSON 数组，后端具备健壮解析能力。
"""
import logging
from typing import List
import math
import re
import json as _json

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..db import get_db
from ..models import ProviderCredential
from ..schemas import RerankRequest, RerankResponse, RerankResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rerank", tags=["rerank"])


def _cosine_sim(a: List[float], b: List[float]) -> float:
    """计算余弦相似度；若向量模为 0 或维度不一致则返回 0。"""
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for i in range(len(a)):
        ai = float(a[i])
        bi = float(b[i])
        dot += ai * bi
        na += ai * ai
        nb += bi * bi
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _mmr_rank(query_vec: List[float], doc_vecs: List[List[float]], docs: List[str], k: int, lam: float = 0.7) -> List[RerankResult]:
    """执行 MMR 重排，返回选中的前 k 个结果（包含 score）。"""
    n = len(doc_vecs)
    if n != len(docs):
        raise ValueError("doc_vecs 与 docs 数量不一致")
    if k <= 0:
        return []
    k = min(k, n)

    # 预计算与查询的相似度
    rel = [_cosine_sim(query_vec, doc_vecs[i]) for i in range(n)]

    selected: List[int] = []
    remaining = set(range(n))
    results: List[RerankResult] = []

    for _ in range(k):
        best_idx = None
        best_score = -1e9
        for i in list(remaining):
            # 与已选集合的最大相似度（多样性项）
            if selected:
                max_sim_to_selected = max(_cosine_sim(doc_vecs[i], doc_vecs[j]) for j in selected)
            else:
                max_sim_to_selected = 0.0
            score = lam * rel[i] - (1.0 - lam) * max_sim_to_selected
            if score > best_score:
                best_score = score
                best_idx = i
        if best_idx is None:
            break
        selected.append(best_idx)
        remaining.discard(best_idx)
        results.append(RerankResult(index=best_idx, score=float(best_score), document=docs[best_idx]))

    return results


def _build_embeddings_url(base_url: str) -> str:
    """构建 /v1/embeddings 端点 URL，兼容多种 base_url 写法。"""
    base = (base_url or "").rstrip("/")
    if base.endswith("/v1/embeddings") or base.endswith("/embeddings"):
        return base
    if base.endswith("/v1"):
        return f"{base}/embeddings"
    return f"{base}/v1/embeddings"


def _build_chat_url(base_url: str) -> str:
    """构建 /v1/chat/completions 端点 URL，兼容多种 base_url 写法。"""
    base = (base_url or "").rstrip("/")
    if base.endswith("/v1/chat/completions") or base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _extract_json_array(text: str) -> List[dict]:
    """从模型输出中提取 JSON 数组；优先直接解析，否则提取代码块或最后一个括号匹配的数组片段。"""
    # 1) 直接解析
    try:
        val = _json.loads(text)
        if isinstance(val, list):
            return val
    except Exception:
        pass
    # 2) 去除 think 栏及多余前缀
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    # 3) 从 ```json 或 ``` 代码块中找数组
    fences = re.findall(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", cleaned, flags=re.I)
    candidates = list(fences) if fences else []
    # 4) 扫描提取最后一个完整的 [ ... ] 片段
    start = None
    depth = 0
    last = None
    for i, ch in enumerate(cleaned):
        if ch == '[':
            if depth == 0:
                start = i
            depth += 1
        elif ch == ']':
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    last = cleaned[start:i + 1]
    if last:
        candidates.append(last)
    # 5) 逐个尝试解析候选
    for cand in reversed(candidates):
        try:
            val = _json.loads(cand)
            if isinstance(val, list):
                return val
        except Exception:
            continue
    raise ValueError("rerank response not JSON array; 请调整提示词确保返回 JSON 数组")


@router.post("", response_model=RerankResponse)
async def rerank(req: RerankRequest, db: AsyncSession = Depends(get_db)) -> RerankResponse:
    """对文档进行重排：
    - provider=LMStudio：使用 embeddings+MMR 在后端重排
    - provider!=LMStudio：调用 chat/completions，以提示词方式让上游模型完成重排
    """
    # 0) 基本校验
    if not req.query or req.query.strip() == "":
        raise HTTPException(status_code=400, detail="query 不能为空")
    if not req.documents or len(req.documents) == 0:
        raise HTTPException(status_code=400, detail="documents 不能为空")

    # 1) 读取凭证（按 provider 最新一条）
    res = await db.execute(
        select(ProviderCredential).where(ProviderCredential.provider == req.provider).order_by(ProviderCredential.id.desc())
    )
    cred = res.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=400, detail=f"No credential configured for provider: {req.provider}")
    if not cred.base_url or not cred.base_url.strip():
        raise HTTPException(status_code=400, detail=f"Provider {req.provider} base_url 未配置，请在数据库中设置后再调用。")

    provider_lower = (req.provider or "").strip().lower()

    # 2) 分支：LMStudio -> embeddings+MMR
    if provider_lower == "lmstudio":
        url_emb = _build_embeddings_url(cred.base_url)
        # 构建请求体：一次性获取 query + documents 的向量
        embed_model = req.model if (req.model and ("embedding" in req.model.lower())) else "text-embedding-qwen3-embedding-0.6b"
        inputs: List[str] = [req.query] + list(req.documents)
        payload = {"model": embed_model, "input": inputs}

        headers = {"Content-Type": "application/json"}
        if cred.api_key:
            headers["Authorization"] = f"Bearer {cred.api_key}"

        # 下游调用 Embeddings
        try:
            timeout = httpx.Timeout(connect=5.0, read=55.0, write=10.0, pool=5.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url_emb, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code if e.response else 502, detail=f"Embeddings upstream error: {getattr(e.response, 'text', str(e))}")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Embeddings request failed: {str(e)}")

        # 解析向量并执行 MMR
        try:
            items = data.get("data", [])
            if not items or len(items) < len(inputs):
                raise ValueError("embeddings 返回数量不足")
            vecs: List[List[float]] = []
            for it in items:
                emb = it.get("embedding")
                if not isinstance(emb, list):
                    raise ValueError("invalid embedding format")
                vecs.append(emb)
            query_vec = vecs[0]
            doc_vecs = vecs[1:]
            k = req.top_n if (req.top_n and req.top_n > 0) else len(doc_vecs)
            results = _mmr_rank(query_vec, doc_vecs, req.documents, k=k, lam=0.7)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"MMR 计算失败: {str(e)}")

        return RerankResponse(model=req.model, results=results)

    # 3) 其他 provider：chat/completions 提示词重排
    url_chat = _build_chat_url(cred.base_url)
    payload = {
        "model": req.model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一个文档重排助手。给定查询与一组文档，请为每个文档计算相关性分数(0-1)，"
                    "并仅以严格的 JSON 数组返回，数组项形如 {index, score, document}；"
                    "绝对不要输出除 JSON 以外的任何解释、思考、标注或文本（包括 think/analysis/utterance 等）。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "查询:" + req.query
                    + "\n\n文档列表:" + "\n".join([f"[{i}] " + d for i, d in enumerate(req.documents)])
                    + ("\n\ntop_n:" + str(req.top_n) if req.top_n is not None else "")
                ),
            },
        ],
        "temperature": 0,
        "stream": False,
    }

    headers = {"Content-Type": "application/json"}
    if cred.api_key:
        headers["Authorization"] = f"Bearer {cred.api_key}"

    try:
        timeout = httpx.Timeout(connect=5.0, read=55.0, write=10.0, pool=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url_chat, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code if e.response else 502, detail=f"Rerank upstream error: {getattr(e.response, 'text', str(e))}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Rerank request failed: {str(e)}")

    try:
        # OpenAI 风格：从 choices[0].message.content 提取 JSON 数组
        content = None
        if isinstance(data.get("choices"), list) and data["choices"]:
            msg = data["choices"][0].get("message") or {}
            content = msg.get("content")
        if not content:
            raise ValueError("no content in chat response")

        items = _extract_json_array(content)
        results: List[RerankResult] = []
        for it in items:
            idx = it.get("index")
            score = it.get("score")
            doc = it.get("document")
            if idx is None or score is None or doc is None:
                raise ValueError("invalid rerank item")
            results.append(RerankResult(index=int(idx), score=float(score), document=str(doc)))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Invalid rerank response format: {str(e)}")

    model = data.get("model") or req.model
    return RerankResponse(model=model, results=results)