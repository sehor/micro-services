# -*- coding: utf-8 -*-
"""
适配器基类与注册表。
"""
from abc import ABC, abstractmethod
from typing import Dict, Type, Optional
from ..schemas import ChatCompletionRequest, ChatCompletionResponse, Message, ChatCompletionChoice


class BaseAdapter(ABC):
    """适配器基类，定义统一接口"""

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, provider_name: Optional[str] = None, tool_registry=None):
        """可选的初始化参数：供具体适配器使用"""
        self.base_url = base_url
        self.api_key = api_key
        self.provider_name = provider_name
        self.tool_registry = tool_registry

    @abstractmethod
    async def chat_completions(self, req: ChatCompletionRequest) -> ChatCompletionResponse:
        """执行聊天补全并返回标准响应"""
        raise NotImplementedError


ADAPTERS: Dict[str, Type[BaseAdapter]] = {}


def register_adapter(name: str, adapter_cls: Type[BaseAdapter]) -> None:
    """在注册表中注册适配器实现"""
    ADAPTERS[name] = adapter_cls


def get_adapter(name: str) -> Type[BaseAdapter]:
    """根据名称获取适配器类，不存在则抛错"""
    if name not in ADAPTERS:
        raise KeyError(f"Adapter '{name}' not found. Available: {list(ADAPTERS.keys())}")
    return ADAPTERS[name]