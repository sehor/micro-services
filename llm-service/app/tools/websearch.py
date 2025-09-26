# -*- coding: utf-8 -*-
"""
网络搜索工具：提供网络搜索功能。
"""
import httpx
import json
from typing import Dict, Any
from .registry import BaseTool
from ..schemas import Tool, FunctionDefinition


class WebSearchTool(BaseTool):
    """网络搜索工具实现"""
    
    def __init__(self):
        self.search_engines = {
            "duckduckgo": self._duckduckgo_search,
            "bing": self._bing_search
        }
    
    def get_definition(self) -> Tool:
        """获取工具定义"""
        return Tool(
            type="function",
            function=FunctionDefinition(
                name="web_search",
                description="搜索网络信息，获取最新的网络内容和数据",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索查询词"
                        },
                        "engine": {
                            "type": "string",
                            "enum": ["duckduckgo", "bing"],
                            "default": "duckduckgo",
                            "description": "搜索引擎选择"
                        },
                        "max_results": {
                            "type": "integer",
                            "default": 5,
                            "minimum": 1,
                            "maximum": 10,
                            "description": "最大结果数量"
                        }
                    },
                    "required": ["query"]
                }
            )
        )
    
    async def execute(self, query: str, engine: str = "duckduckgo", max_results: int = 5, **kwargs) -> str:
        """执行网络搜索"""
        if engine not in self.search_engines:
            return f"不支持的搜索引擎: {engine}"
        
        try:
            search_func = self.search_engines[engine]
            results = await search_func(query, max_results)
            
            if not results:
                return "未找到相关搜索结果"
            
            # 格式化搜索结果
            formatted_results = []
            for i, result in enumerate(results, 1):
                formatted_results.append(
                    f"{i}. **{result.get('title', '无标题')}**\n"
                    f"   链接: {result.get('url', '无链接')}\n"
                    f"   摘要: {result.get('snippet', '无摘要')}\n"
                )
            
            return "\n".join(formatted_results)
            
        except Exception as e:
            return f"搜索过程中发生错误: {str(e)}"
    
    async def _duckduckgo_search(self, query: str, max_results: int) -> list:
        """DuckDuckGo 搜索实现"""
        try:
            # 使用 DuckDuckGo Instant Answer API
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1"
            }
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            results = []
            
            # 处理即时答案
            if data.get("Abstract"):
                results.append({
                    "title": data.get("AbstractText", "DuckDuckGo 即时答案"),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data.get("Abstract", "")
                })
            
            # 处理相关主题
            for topic in data.get("RelatedTopics", [])[:max_results-len(results)]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append({
                        "title": topic.get("Text", "").split(" - ")[0] if " - " in topic.get("Text", "") else topic.get("Text", ""),
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", "")
                    })
            
            return results[:max_results]
            
        except Exception as e:
            # 如果 DuckDuckGo API 失败，返回模拟结果
            return [{
                "title": f"搜索结果: {query}",
                "url": "https://duckduckgo.com/?q=" + query.replace(" ", "+"),
                "snippet": f"关于 '{query}' 的搜索结果。由于API限制，这是一个模拟结果。"
            }]
    
    async def _bing_search(self, query: str, max_results: int) -> list:
        """Bing 搜索实现（需要API密钥）"""
        # 这里可以集成 Bing Search API
        # 由于需要API密钥，这里提供一个基础实现
        return [{
            "title": f"Bing搜索: {query}",
            "url": f"https://www.bing.com/search?q={query.replace(' ', '+')}",
            "snippet": f"关于 '{query}' 的Bing搜索结果。需要配置Bing Search API密钥以获取实际结果。"
        }]