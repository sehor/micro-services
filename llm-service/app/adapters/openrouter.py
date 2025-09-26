# -*- coding: utf-8 -*-
"""
OpenRouter 适配器：支持流式响应、工具调用、多模态功能。
"""
import httpx
import json
import uuid
import time
from typing import AsyncGenerator, Union
from .base import BaseAdapter
from ..schemas import (
    ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice, 
    Message, StreamChunk, Delta, Usage, ToolCall
)


class OpenRouterAdapter(BaseAdapter):
    """OpenRouter 适配器实现，支持流式、工具调用、多模态"""
    
    def __init__(self, base_url=None, api_key=None, provider_name=None, tool_registry=None):
        """初始化OpenRouter适配器"""
        super().__init__(base_url, api_key, provider_name, tool_registry)

    async def chat_completions(self, req: ChatCompletionRequest) -> Union[ChatCompletionResponse, AsyncGenerator[str, None]]:
        """调用 OpenRouter API，支持流式和非流式响应"""
        if not self.base_url or not self.api_key:
            raise ValueError("OpenRouterAdapter requires base_url and api_key")

        # 智能构建 URL
        base = self.base_url.rstrip('/')
        if base.endswith('/v1/chat/completions'):
            url = base
        else:
            url = f"{base}/v1/chat/completions"

        # 构建请求payload
        payload = self._build_payload(req)
        headers = self._build_headers()

        if req.stream:
            return self._stream_chat_completions(url, payload, headers, req)
        else:
            return await self._non_stream_chat_completions(url, payload, headers, req)

    def _build_payload(self, req: ChatCompletionRequest) -> dict:
        """构建请求负载"""
        # 根据 webSearchType 决定启用方式：online 通过模型后缀，其它默认通过 plugins:web
        model_value = req.model
        if getattr(req, "webSearch", False) and str(getattr(req, "webSearchType", "exa")).lower() == "online":
            if isinstance(model_value, str) and not model_value.endswith(":online"):
                model_value = f"{model_value}:online"
        
        payload = {
            "model": model_value,
            "messages": self._format_messages(req.messages),
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }
        
        if req.stream:
            payload["stream"] = True
            
        if req.tools:
            payload["tools"] = [tool.model_dump() for tool in req.tools]
            
        if req.tool_choice:
            payload["tool_choice"] = req.tool_choice
            
        if req.usage and req.usage.include:
            payload["usage"] = {"include": True}
            
        # 组装 plugins 配置：始终启用文件解析；如果开启 webSearch，则追加 web 插件
        plugins = [
            {
                "id": "file-parser",
                "pdf": {
                    "engine": "native"
                }
            }
        ]
        # 当用户请求开启 web 搜索，且 webSearchType 不是 online 时，通过插件方式启用（不依赖内部 tools/websearch.py）
        if getattr(req, "webSearch", False) and str(getattr(req, "webSearchType", "exa")).lower() != "online":
            plugins.append({"id": "web"})
        payload["plugins"] = plugins
            
        return payload

    def _format_messages(self, messages: list) -> list:
        """格式化消息，支持多模态内容和文件"""
        formatted_messages = []
        for msg in messages:
            formatted_msg = {"role": msg.role}
            
            # 处理内容
            if isinstance(msg.content, str):
                formatted_msg["content"] = msg.content
            elif isinstance(msg.content, list):
                # 多模态内容，包括图片和文件
                formatted_content = []
                for content in msg.content:
                    content_dict = content.model_dump()
                    
                    # 对于文件类型，转换为OpenRouter支持的格式
                    if content_dict.get("type") == "file":
                        file_data = content_dict.get("file", {})
                        # 使用OpenRouter的file格式，支持native模式处理
                        formatted_content.append({
                            "type": "file",
                            "file": {
                                "filename": file_data.get("filename", "unknown"),
                                "file_data": file_data.get("file_data", "")
                            }
                        })
                    else:
                        formatted_content.append(content_dict)
                        
                formatted_msg["content"] = formatted_content
            
            # 处理工具调用
            if msg.tool_calls:
                formatted_msg["tool_calls"] = [tc.model_dump() for tc in msg.tool_calls]
                
            # 处理工具响应
            if msg.tool_call_id:
                formatted_msg["tool_call_id"] = msg.tool_call_id
                
            if msg.name:
                formatted_msg["name"] = msg.name
                
            formatted_messages.append(formatted_msg)
            
        return formatted_messages

    def _prepare_debug_payload(self, payload: dict) -> dict:
        """准备用于调试的payload，将base64数据替换为长度信息"""
        import copy
        debug_payload = copy.deepcopy(payload)
        
        if "messages" in debug_payload:
            for message in debug_payload["messages"]:
                if "content" in message and isinstance(message["content"], list):
                    for content in message["content"]:
                        if content.get("type") == "file" and "file" in content:
                            file_data = content["file"].get("file_data", "")
                            if file_data.startswith("data:"):
                                # 仅打印base64的前10位，保留 data URI 前缀
                                if "," in file_data:
                                    prefix, base64_part = file_data.split(",", 1)
                                else:
                                    prefix, base64_part = "data:;base64", file_data
                                content["file"]["file_data"] = f"{prefix},{base64_part[:10]}...(前10位)"
                        elif content.get("type") == "image_url" and "image_url" in content:
                            url = content["image_url"].get("url", "")
                            if url.startswith("data:"):
                                # 仅打印base64的前10位，保留 data URI 前缀
                                if "," in url:
                                    prefix, base64_part = url.split(",", 1)
                                else:
                                    prefix, base64_part = "data:;base64", url
                                content["image_url"]["url"] = f"{prefix},{base64_part[:10]}...(前10位)"
        
        return debug_payload

    def _build_headers(self) -> dict:
        """构建请求头"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://llm-gateway.local",
            "X-Title": "LLM Gateway"
        }

    async def _non_stream_chat_completions(self, url: str, payload: dict, headers: dict, req: ChatCompletionRequest) -> ChatCompletionResponse:
        """非流式聊天完成"""
        try:
            # 调试：打印发送给OpenRouter的payload（base64只显示长度）
            print(f"\n=== 发送给OpenRouter的完整payload ===")
            debug_payload = self._prepare_debug_payload(payload)
            print(json.dumps(debug_payload, indent=2, ensure_ascii=False))
            print(f"=== 结束 ===\n")
            
            # 打印调试信息
            print(f"[DEBUG] OpenRouter请求URL: {url}")
            print(f"[DEBUG] 请求payload消息数量: {len(payload.get('messages', []))}")
            
            # 检查消息内容中是否有大文件
            for i, msg in enumerate(payload.get('messages', [])):
                if isinstance(msg.get('content'), list):
                    for j, content in enumerate(msg['content']):
                        if content.get('type') == 'image_url':
                            url_data = content.get('image_url', {}).get('url', '')
                            if url_data.startswith('data:'):
                                data_size = len(url_data)
                                print(f"[DEBUG] 消息{i}内容{j}: 数据URI大小 {data_size} 字符")
                                if data_size > 100000:  # 大于100KB
                                    print(f"[WARNING] 数据过大，可能导致API错误")
            
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(url, json=payload, headers=headers)
                
                if resp.status_code != 200:
                    error_text = resp.text
                    print(f"[ERROR] OpenRouter API错误 {resp.status_code}: {error_text}")
                    raise ValueError(f"OpenRouter API错误 {resp.status_code}: {error_text}")
                    
                data = resp.json()
                
        except httpx.HTTPStatusError as e:
            error_text = e.response.text if hasattr(e.response, 'text') else str(e)
            print(f"[ERROR] OpenRouter HTTP错误: {error_text}")
            raise ValueError(f"OpenRouter请求失败: {error_text}")
        except Exception as e:
            print(f"[ERROR] OpenRouter请求异常: {str(e)}")
            raise ValueError(f"OpenRouter请求异常: {str(e)}")
            
        return self._parse_response(data, req.model)

    async def _stream_chat_completions(self, url: str, payload: dict, headers: dict, req: ChatCompletionRequest) -> AsyncGenerator[str, None]:
        """流式聊天补全"""
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream('POST', url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                
                buffer = ""
                async for chunk in resp.aiter_text():
                    buffer += chunk
                    
                    # 处理完整的SSE行
                    while True:
                        line_end = buffer.find('\n')
                        if line_end == -1:
                            break
                            
                        line = buffer[:line_end].strip()
                        buffer = buffer[line_end + 1:]
                        
                        if line.startswith('data: '):
                            data = line[6:]
                            if data == '[DONE]':
                                return
                                
                            try:
                                data_obj = json.loads(data)
                                chunk_response = self._parse_stream_chunk(data_obj, req.model)
                                yield f"data: {chunk_response.model_dump_json()}\n\n"
                            except json.JSONDecodeError:
                                continue

    def _parse_response(self, data: dict, model: str) -> ChatCompletionResponse:
        """解析非流式响应"""
        choices = []
        for choice_data in data.get("choices", []):
            message_data = choice_data.get("message", {})
            
            # 构建消息
            message = Message(
                role=message_data.get("role", "assistant"),
                content=message_data.get("content")
            )
            
            # 处理工具调用
            if "tool_calls" in message_data:
                tool_calls = []
                for tc in message_data["tool_calls"]:
                    tool_call = ToolCall(
                        id=tc["id"],
                        type=tc.get("type", "function"),
                        function=tc["function"]
                    )
                    tool_calls.append(tool_call)
                message.tool_calls = tool_calls
            
            choice = ChatCompletionChoice(
                index=choice_data.get("index", 0),
                message=message,
                finish_reason=choice_data.get("finish_reason")
            )
            choices.append(choice)
        
        # 构建使用统计
        usage = None
        if "usage" in data:
            usage_data = data["usage"]
            usage = Usage(
                prompt_tokens=usage_data.get("prompt_tokens"),
                completion_tokens=usage_data.get("completion_tokens"),
                total_tokens=usage_data.get("total_tokens"),
                cost=usage_data.get("cost")
            )
        
        return ChatCompletionResponse(
            id=data.get("id", str(uuid.uuid4())),
            object="chat.completion",
            created=data.get("created", int(time.time())),
            model=model,
            choices=choices,
            usage=usage
        )

    def _parse_stream_chunk(self, data: dict, model: str) -> StreamChunk:
        """解析流式响应块"""
        choices = []
        for choice_data in data.get("choices", []):
            delta_data = choice_data.get("delta", {})
            
            # 构建增量数据
            delta = Delta(
                role=delta_data.get("role"),
                content=delta_data.get("content"),
                finish_reason=choice_data.get("finish_reason")
            )
            
            # 处理工具调用增量
            if "tool_calls" in delta_data:
                tool_calls = []
                for tc in delta_data["tool_calls"]:
                    tool_call = ToolCall(
                        id=tc.get("id", ""),
                        type=tc.get("type", "function"),
                        function=tc.get("function", {})
                    )
                    tool_calls.append(tool_call)
                delta.tool_calls = tool_calls
            
            choice = ChatCompletionChoice(
                index=choice_data.get("index", 0),
                delta=delta,
                finish_reason=choice_data.get("finish_reason")
            )
            choices.append(choice)
        
        # 构建使用统计
        usage = None
        if "usage" in data:
            usage_data = data["usage"]
            usage = Usage(
                prompt_tokens=usage_data.get("prompt_tokens"),
                completion_tokens=usage_data.get("completion_tokens"),
                total_tokens=usage_data.get("total_tokens"),
                cost=usage_data.get("cost")
            )
        
        return StreamChunk(
            id=data.get("id", str(uuid.uuid4())),
            object="chat.completion.chunk",
            created=data.get("created", int(time.time())),
            model=model,
            choices=choices,
            usage=usage
        )