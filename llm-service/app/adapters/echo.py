# -*- coding: utf-8 -*-
"""
示例 Echo 适配器：返回最后一条用户消息。
"""
import uuid
from .base import BaseAdapter
from ..schemas import ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice, Message


class EchoAdapter(BaseAdapter):
    """简单回声适配器，便于端到端验证"""

    async def chat_completions(self, req: ChatCompletionRequest) -> ChatCompletionResponse:
        """返回最后一条用户消息作为模型回复"""
        last = req.messages[-1] if req.messages else Message(role="user", content="")
        choice = ChatCompletionChoice(index=0, message=Message(role="assistant", content=last.content))
        return ChatCompletionResponse(id=str(uuid.uuid4()), model=req.model, choices=[choice])