# -*- coding: utf-8 -*-
"""
工具注册表：管理所有可用的工具。
"""
from typing import Dict, Any, List
from abc import ABC, abstractmethod
from ..schemas import Tool, FunctionDefinition


class BaseTool(ABC):
    """工具基类"""
    
    @abstractmethod
    def get_definition(self) -> Tool:
        """获取工具定义"""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """执行工具"""
        pass


class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
    
    def register(self, name: str, tool: BaseTool):
        """注册工具"""
        self._tools[name] = tool
    
    def get_tool(self, name: str) -> BaseTool:
        """获取工具实例"""
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found")
        return self._tools[name]
    
    def get_all_definitions(self) -> List[Tool]:
        """获取所有工具定义"""
        return [tool.get_definition() for tool in self._tools.values()]
    
    def list_tools(self) -> List[str]:
        """列出所有工具名称"""
        return list(self._tools.keys())
    
    async def execute_tool(self, name: str, **kwargs) -> str:
        """执行指定工具"""
        tool = self.get_tool(name)
        return await tool.execute(**kwargs)