# -*- coding: utf-8 -*-
"""
适配器注册入口。
"""
from .base import BaseAdapter, ADAPTERS, register_adapter, get_adapter
from .echo import EchoAdapter
from .openai import OpenAIAdapter
from .alibaba import AlibabaAdapter
from .openrouter import OpenRouterAdapter

# 注册内置适配器
register_adapter("echo", EchoAdapter)
register_adapter("openai", OpenAIAdapter)
register_adapter("alibaba", AlibabaAdapter)  # alibaba provider 使用 alibaba 适配器
register_adapter("openrouter", OpenRouterAdapter)
# 新增：LMStudio 作为 OpenAI 兼容端点的别名映射到 OpenAIAdapter
register_adapter("LMStudio", OpenAIAdapter)

__all__ = [
    "BaseAdapter",
    "ADAPTERS",
    "register_adapter",
    "get_adapter",
    "EchoAdapter",
    "OpenAIAdapter",
    "AlibabaAdapter",
    "OpenRouterAdapter",
]