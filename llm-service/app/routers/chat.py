# -*- coding: utf-8 -*-
"""
聊天路由：POST /api/v1/chat/completions
支持流式响应、工具调用、多模态等功能
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Union
from ..schemas import ChatCompletionRequest, ChatCompletionResponse, StreamChunk
from ..adapters import get_adapter
from ..db import get_db
from ..models import ProviderCredential
from ..tools import tool_registry
import base64
from ..schemas import Message, MessageContent
from app.services.chat_service import (
    chat_completions as svc_chat_completions,
    chat_completions_from_upload as svc_chat_completions_from_upload,
)
 
router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
 
 
@router.post("/completions", response_model=None)
async def create_chat_completion(req: ChatCompletionRequest, db: AsyncSession = Depends(get_db)):
    """根据 provider 路由到对应适配器并返回响应；支持流式响应、工具调用等功能"""
    result = await svc_chat_completions(req, db, tool_registry)
    if req.stream and hasattr(result, '__aiter__'):
        return StreamingResponse(
            result,
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
    return result
 
@router.post("/completions/upload", response_model=None)
async def create_chat_completion_upload(
    provider: str = Form(...),
    model: str = Form(...),
    user_message: str = Form(...),
    temperature: float = Form(1.0),
    max_tokens: int = Form(1024),
    stream: bool = Form(False),
    # 新增：web 搜索相关可选参数
    webSearch: bool = Form(False),
    webSearchType: str = Form("exa"),
    tools: Union[str, None] = Form(None),
    tool_choice: Union[str, None] = Form(None),
    files: Union[list[UploadFile], None] = File(None),
    db: AsyncSession = Depends(get_db),
):
    """接收multipart/form-data文件流并根据文件类型构造消息。"""
    result = await svc_chat_completions_from_upload(
        provider,
        model,
        user_message,
        temperature,
        max_tokens,
        stream,
        tools,
        tool_choice,
        files,
        db,
        tool_registry,
        # 传递 web 搜索参数
        webSearch=webSearch,
        webSearchType=webSearchType,
    )
    if stream and hasattr(result, '__aiter__'):
        return StreamingResponse(
            result,
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
    return result
 
# === 新增：文档解析专用接口（默认 provider=alibaba，不与原有 upload 混用） ===
@router.post("/doc/parse", response_model=None)
async def parse_document(
    file: UploadFile = File(...),
    # 默认 provider/model
    provider: str = Form("alibaba"),
    model: str = Form("qwen-long"),
    # 可选参数
    doc_address: Union[str, None] = Form(None),
    user_message: Union[str, None] = Form(None),
    temperature: float = Form(0.2),
    max_tokens: int = Form(1536),
    stream: bool = Form(False),
    db: AsyncSession = Depends(get_db),
):
    """文档解析专用接口：
    - 输入单文件与可选元数据（doc_address），默认使用阿里云 Qwen-Long 做摘要/关键信息提取。
    - 输出由模型生成的摘要/要点（严格 JSON），便于直接入库到 RAG。
    """
    # 构造默认提示词（严格 JSON，无额外文本）
    if not user_message:
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

    # 复用统一文件上传解析管道，确保阿里云下非图像文件走 file_id 注入
    result = await svc_chat_completions_from_upload(
        provider=provider,
        model=model,
        user_message=user_message,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=stream,
        tools=None,
        tool_choice=None,
        files=[file],
        db=db,
        tool_registry=tool_registry,
        webSearch=False,
        webSearchType="exa",
    )

    if stream and hasattr(result, '__aiter__'):
        return StreamingResponse(
            result,
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
    return result