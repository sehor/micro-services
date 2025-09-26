# -*- coding: utf-8 -*-
"""
Alibaba 适配器：阿里巴巴通义千问（OpenAI 兼容风格）。
"""
from .openai import OpenAIAdapter


class AlibabaAdapter(OpenAIAdapter):
    """Alibaba 直接复用 OpenAI 兼容协议"""
    pass