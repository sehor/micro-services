# -*- coding: utf-8 -*-
"""
llms-gateway 兼容路由：为 rag-service 提供统一的解析/向量化/重排/对话接口。
- POST /llms-gateway/paresing    -> 文件解析，返回 {title?, summary, keywords?, content_summary?}
- POST /llms-gateway/embedding   -> 文本向量化，返回 {embedding}
- POST /llms-gateway/reranker    -> 文档重排，返回 {items: [...]}（沿用入参结构，更新分数与顺序）
- POST /llms-gateway/chat/completions -> 生成最终答案，返回 {content}
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..schemas import EmbeddingRequest, RerankRequest, ChatCompletionRequest, Message
from ..routers.embeddings import create_embedding as _create_embedding
from ..routers.rerank import rerank as _rerank
from ..services.chat_service import (
    chat_completions as _svc_chat_completions,
    chat_completions_from_upload as _svc_chat_completions_from_upload,
)
from ..tools import tool_registry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/llms-gateway", tags=["llms-gateway"])


@router.post("/paresing", response_model=None)
async def parse_file(
    file: UploadFile = File(...),
    provider: str = Form("alibaba"),
    model: str = Form("qwen-long"),
    doc_address: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """文件解析：复用上传管道（默认 Alibaba Qwen-Long），返回简化 JSON。"""
    # 构造严格 JSON 的默认提示词
    fname = getattr(file, "filename", None) or "uploaded"
    _doc_address = doc_address or ""
    user_message = (
        "你将基于我上传的文档，生成严格的 JSON 输出。\n"
        "字段为：{\"title\": string, \"summary\": string, \"key_points\": string[], \"keywords\": string[], \"meta\": {\"doc_address\": string, \"filename\": string}}。\n"
        "规则：\n"
        "1) 必须输出合法 JSON，不要包含任何多余文本或注释；\n"
        "2) summary 200-600字，覆盖核心要点；\n"
        "3) key_points 8-12条，每条尽量简短；\n"
        "4) keywords 3-10个；\n"
        "5) 所有内容均来自文档本身，避免臆测。\n"
        f"请将 meta.doc_address 设为 \"{_doc_address}\"，meta.filename 设为 \"{fname}\"。"
    )
    try:
        result = await _svc_chat_completions_from_upload(
            provider=provider,
            model=model,
            user_message=user_message,
            temperature=0.2,
            max_tokens=1536,
            stream=False,
            tools=None,
            tool_choice=None,
            files=[file],
            db=db,
            tool_registry=tool_registry,
            webSearch=False,
            webSearchType="exa",
        )
        # 解析模型输出（严格 JSON）
        if not getattr(result, "choices", None):
            raise HTTPException(status_code=502, detail="解析服务未返回有效内容")
        msg = result.choices[0].message
        content = getattr(msg, "content", None)
        if not isinstance(content, str):
            raise HTTPException(status_code=502, detail="解析结果格式异常：应为字符串 JSON")
        import json as _json
        j = _json.loads(content)
        summary = j.get("summary") or j.get("content_summary")
        keywords = j.get("keywords") or j.get("key_points")
        title = j.get("title")
        if not summary:
            raise HTTPException(status_code=502, detail="解析结果缺少 summary/content_summary")
        # 返回简化结构，兼容 rag-service 的消费
        return {
            "title": title,
            "summary": summary,
            "keywords": keywords,
            "content_summary": summary,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("文件解析失败: %s", e)
        raise HTTPException(status_code=500, detail=f"文件解析失败: {e}")


@router.post("/embedding", response_model=None)
async def gateway_embedding(payload: Dict[str, Any], db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """文本向量化：转换为内部 /api/v1/embeddings/create 请求并适配响应。"""
    text = payload.get("input")
    if text is None or (isinstance(text, str) and text.strip() == ""):
        raise HTTPException(status_code=400, detail="input 不能为空")
    try:
        # 使用默认 provider/model（LMStudio/Qwen3 Embedding 0.6B）
        req = EmbeddingRequest(input=text)
        resp = await _create_embedding(req, db)
        vec = resp.vector or (resp.vectors[0] if resp.vectors else None)
        if not isinstance(vec, list):
            raise HTTPException(status_code=502, detail="Embedding 响应缺少向量")
        return {"embedding": vec}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Embedding 处理失败: %s", e)
        raise HTTPException(status_code=500, detail=f"Embedding 处理失败: {e}")


@router.post("/reranker", response_model=None)
async def gateway_reranker(payload: Dict[str, Any], db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """重排：提取 items.summary 作为文档，调用内部重排并按原结构返回 items。"""
    query = payload.get("query")
    items = payload.get("items") or []
    if not query or not isinstance(items, list) or len(items) == 0:
        raise HTTPException(status_code=400, detail="query/items 不合法或为空")
    try:
        # 构造文档列表（以 summary 为主，缺失则串行化为字符串）
        docs: List[str] = []
        for it in items:
            doc = it.get("summary") if isinstance(it, dict) else None
            if not doc:
                doc = str(it)
            docs.append(doc)
        req = RerankRequest(query=query, documents=docs)
        resp = await _rerank(req, db)
        # 将重排结果映射回原 items，更新分数并调整顺序
        ordered: List[Dict[str, Any]] = []
        for r in resp.results:
            if r.index < 0 or r.index >= len(items):
                continue
            orig = dict(items[r.index])  # 复制一份
            try:
                orig["score"] = float(r.score)
            except Exception:
                orig["score"] = r.score
            ordered.append(orig)
        return {"items": ordered}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Reranker 处理失败: %s", e)
        raise HTTPException(status_code=500, detail=f"Reranker 处理失败: {e}")


@router.post("/chat/completions", response_model=None)
async def gateway_chat(payload: Dict[str, Any], db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """对话：使用 echo 适配器生成内容，避免下游凭证依赖。"""
    prompt = payload.get("prompt") or ""
    context = payload.get("context") or []
    if not isinstance(prompt, str) or prompt.strip() == "":
        raise HTTPException(status_code=400, detail="prompt 不能为空")
    try:
        # 将 context 作为 system 消息注入（echo 最终会回显用户消息）
        sys_content = "context: " + (str(context) if context else "")
        req = ChatCompletionRequest(
            provider="echo",
            model="echo",
            messages=[
                Message(role="system", content=sys_content),
                Message(role="user", content=prompt),
            ],
            temperature=0.0,
            max_tokens=1024,
            stream=False,
        )
        result = await _svc_chat_completions(req, db, tool_registry)
        if not getattr(result, "choices", None):
            raise HTTPException(status_code=502, detail="chat 未返回有效内容")
        msg = result.choices[0].message
        content = getattr(msg, "content", None)
        if isinstance(content, list):
            # 若返回为多模态内容，尝试提取文本
            try:
                text_parts = [c.get("text") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                content = "\n".join([t for t in text_parts if t])
            except Exception:
                content = None
        if not isinstance(content, str):
            raise HTTPException(status_code=502, detail="chat 内容格式异常")
        return {"content": content}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Chat 处理失败: %s", e)
        raise HTTPException(status_code=500, detail=f"Chat 处理失败: {e}")