# -*- coding: utf-8 -*-
"""
聊天与上传业务服务：封装适配器路由、工具合并、凭证加载、文件解析等逻辑。
"""
import base64
from typing import Any, Union
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.schemas import ChatCompletionRequest, Message, MessageContent
from app.schemas import Tool, FunctionDefinition
from app.adapters import get_adapter
from app.models import ProviderCredential
import httpx


async def chat_completions(req: ChatCompletionRequest, db: AsyncSession, tool_registry) -> Any:
    """处理聊天补全：合并工具、加载凭证、调用适配器并返回结果或异步迭代器。"""
    try:
        adapter_cls = get_adapter(req.provider)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 合并工具定义（如请求包含）
    if req.tools:
        available_tools = tool_registry.get_all_definitions()
        req.tools.extend(available_tools)

    # echo 适配器无需凭证
    if req.provider == "echo":
        adapter = adapter_cls(provider_name=req.provider, tool_registry=tool_registry)
        return await adapter.chat_completions(req)

    # 加载数据库凭证
    res = await db.execute(
        select(ProviderCredential).where(ProviderCredential.provider == req.provider).order_by(ProviderCredential.id.desc())
    )
    cred = res.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=400, detail=f"No credential configured for provider: {req.provider}")

    adapter = adapter_cls(base_url=cred.base_url, api_key=cred.api_key, provider_name=req.provider, tool_registry=tool_registry)
    return await adapter.chat_completions(req)


async def chat_completions_from_upload(
    provider: str,
    model: str,
    user_message: str,
    temperature: float,
    max_tokens: int,
    stream: bool,
    tools: Union[str, None],
    tool_choice: Union[str, None],
    files: Union[list[UploadFile], None],
    db: AsyncSession,
    tool_registry,
    # 新增：web 搜索相关参数
    webSearch: bool = False,
    webSearchType: str = "exa",
) -> Any:
    """处理上传表单：构造消息、解析文件、路由到适配器并返回结果或异步迭代器。
    - 阿里云（百炼）统一管道：非图像文件统一先上传至DashScope OpenAI兼容文件接口，获取file_id并以system消息注入，默认使用Qwen-Long进行文档理解。
    - 其他provider保持原有行为；图像文件仍以image_url方式传入。
    """
    # 提前加载数据库凭证（供阿里云文件上传使用，echo无需）
    cred = None
    if provider != "echo":
        res = await db.execute(
            select(ProviderCredential).where(ProviderCredential.provider == provider).order_by(ProviderCredential.id.desc())
        )
        cred = res.scalar_one_or_none()
        if not cred:
            raise HTTPException(status_code=400, detail=f"No credential configured for provider: {provider}")

    # 内部帮助函数：上传到 DashScope 文件接口并返回 file_id
    async def _upload_to_dashscope_file(file_name: str, data_bytes: bytes, mime: str, base_url: str, api_key: str) -> str:
        """上传文件到阿里云百炼 OpenAI 兼容文件接口，返回 file_id"""
        # 构造 /files 端点（兼容传入 base_url 为 /v1 或完整 /v1/chat/completions 两种情况）
        base_url_clean = (base_url or "").rstrip("/")
        if base_url_clean.endswith("/chat/completions"):
            files_url = base_url_clean[: -len("/chat/completions")] + "/files"
        elif base_url_clean.endswith("/v1"):
            files_url = base_url_clean + "/files"
        else:
            files_url = base_url_clean + "/v1/files"

        headers = {"Authorization": f"Bearer {api_key}"}
        data = {"purpose": "file-extract"}
        files_payload = {"file": (file_name, data_bytes, mime or "application/octet-stream")}
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(files_url, headers=headers, data=data, files=files_payload)
                resp.raise_for_status()
                j = resp.json()
                return j.get("id") or ""
        except httpx.HTTPStatusError as e:
            # 明确抛出错误，包含上下文
            raise HTTPException(status_code=e.response.status_code, detail=f"DashScope文件上传失败: {file_name}: {e.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"DashScope文件上传异常: {file_name}: {str(e)}")

    # 1) 构造基础消息
    message_contents: list[MessageContent] = [MessageContent(type="text", text=user_message)]
    file_ids: list[str] = []
    use_file_id_pipeline = (provider == "alibaba") and model.lower().startswith("qwen-long")

    # 2) 处理上传文件
    if files:
        for f in files:
            try:
                data_bytes = await f.read()
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"读取文件失败: {f.filename}: {str(e)}")
            mime = f.content_type or "application/octet-stream"
            file_name = f.filename or "uploaded"

            if mime.startswith("image/"):
                # 图像：统一以 data URI 形式传入
                b64 = base64.b64encode(data_bytes).decode("utf-8")
                message_contents.append(
                    MessageContent(type="image_url", image_url={"url": f"data:{mime};base64,{b64}"})
                )
            else:
                if use_file_id_pipeline and cred:
                    # 阿里云统一管道：非图像走文件上传获取 file_id
                    fid = await _upload_to_dashscope_file(file_name, data_bytes, mime, cred.base_url, cred.api_key)
                    if not fid:
                        raise HTTPException(status_code=500, detail=f"未获取到file_id: {file_name}")
                    file_ids.append(fid)
                    # 统一管道下不再传原始base64内容，避免重复计费与兼容性问题
                else:
                    # 其他provider或非Qwen-Long模型：保留原有行为
                    b64 = base64.b64encode(data_bytes).decode("utf-8")
                    if mime.startswith("text/"):
                        try:
                            decoded_text = data_bytes.decode("utf-8")
                        except UnicodeDecodeError:
                            decoded_text = data_bytes.decode("gb18030", errors="ignore")
                        message_contents.append(MessageContent(type="text", text=decoded_text))
                    message_contents.append(
                        MessageContent(
                            type="file",
                            file={"filename": file_name, "file_data": f"data:{mime};base64,{b64}"},
                        )
                    )

    # 3) 组装标准请求对象
    if use_file_id_pipeline and file_ids:
        # Qwen-Long 文档理解：以 system + fileid 注入长文内容，用户消息仅保留指令
        messages = [
            Message(role="system", content="You are a helpful assistant."),
            *[Message(role="system", content=f"fileid://{fid}") for fid in file_ids],
            Message(role="user", content=user_message),
        ]
    else:
        messages = [Message(role="user", content=message_contents)]

    req = ChatCompletionRequest(
        provider=provider,
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=bool(stream),
        # 传入 web 搜索相关开关
        webSearch=bool(webSearch),
        webSearchType=webSearchType,
    )

    # 附加工具配置（如前端提供）
    if tools:
        try:
            import json as _json
            tool_defs = _json.loads(tools)
            req.tools = [Tool(function=FunctionDefinition(**t["function"])) if isinstance(t, dict) else t for t in tool_defs]
            req.tool_choice = tool_choice or req.tool_choice
        except Exception:
            # 工具解析失败不影响消息处理
            pass

    # 4) 路由到适配器并返回
    try:
        adapter_cls = get_adapter(req.provider)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if req.provider == "echo":
        adapter = adapter_cls(provider_name=req.provider, tool_registry=tool_registry)
        result = await adapter.chat_completions(req)
    else:
        adapter = adapter_cls(base_url=cred.base_url, api_key=cred.api_key, provider_name=req.provider, tool_registry=tool_registry)
        result = await adapter.chat_completions(req)

    return result