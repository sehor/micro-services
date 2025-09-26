# -*- coding: utf-8 -*-
"""
OpenAI 适配器：使用 OpenAI 兼容的 /v1/chat/completions 接口。
"""
import httpx
from .base import BaseAdapter
from ..schemas import ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice, Message
import uuid
import logging

# 配置日志
logger = logging.getLogger(__name__)


class OpenAIAdapter(BaseAdapter):
    """OpenAI 适配器实现"""

    async def chat_completions(self, req: ChatCompletionRequest) -> ChatCompletionResponse:
        """调用下游 OpenAI 兼容接口并返回标准响应"""
        if not self.base_url or not self.api_key:
            raise ValueError("OpenAIAdapter requires base_url and api_key")

        # 智能处理URL构建
        base_url_clean = self.base_url.rstrip('/')
        if base_url_clean.endswith('/chat/completions'):
            # 已经是完整的聊天接口URL
            url = base_url_clean
        elif base_url_clean.endswith('/v1'):
            # 阿里云格式：需要添加 /chat/completions
            url = f"{base_url_clean}/chat/completions"
        elif base_url_clean.endswith('/v1/chat/completions'):
            # OpenRouter格式：已经完整
            url = base_url_clean
        else:
            # 标准OpenAI格式：需要添加完整路径
            url = f"{base_url_clean}/v1/chat/completions"
        payload = {
            "model": req.model,
            "messages": self._format_messages(req.messages),
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # 打印调试信息：base_url 和 API key 前5位
        api_key_preview = self.api_key[:5] + "..." if len(self.api_key) > 5 else self.api_key
        print(f"[DEBUG] Base URL: {self.base_url}")
        print(f"[DEBUG] API Key (前5位): {api_key_preview}")
        print(f"[DEBUG] 请求URL: {url}")
        
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # 容错：若下游为纯 OpenAI 响应结构，尽量解析
        try:
            first = data["choices"][0]["message"]["content"]
        except Exception:
            # 回退：用原始文本或空字符串
            first = str(data)

        choice = ChatCompletionChoice(index=0, message=Message(role="assistant", content=first))
        return ChatCompletionResponse(id=str(uuid.uuid4()), model=req.model, choices=[choice])
    
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
                    
                    # 对于文件类型，转换为OpenAI支持的格式
                    if content_dict.get("type") == "file":
                        file_data = content_dict.get("file", {})
                        # 将文件转换为image_url格式，使用data URI
                        formatted_content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{file_data.get('type', 'application/octet-stream')};base64,{file_data.get('data', '')}"
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