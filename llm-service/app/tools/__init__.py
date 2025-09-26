# -*- coding: utf-8 -*-
"""
工具调用框架：支持各种外部工具集成。
"""
from .websearch import WebSearchTool
from .registry import ToolRegistry

# 注册所有可用工具
tool_registry = ToolRegistry()
tool_registry.register("web_search", WebSearchTool())

__all__ = ["tool_registry", "WebSearchTool", "ToolRegistry"]