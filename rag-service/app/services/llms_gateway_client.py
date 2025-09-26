"""
上游 LLMs 网关客户端：封装解析、向量化、重排与对话接口调用。
"""
import httpx
from typing import List, Dict, Any, Optional
from ..config import LLMS_GATEWAY_BASE


class LLMsGatewayClient:
    """与上游 llms-gateway 通讯的异步 HTTP 客户端"""
    def __init__(self, base_url: str = LLMS_GATEWAY_BASE, timeout: float = 30.0):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def close(self) -> None:
        """关闭底层 HTTP 连接"""
        await self._client.aclose()

    async def parse_file(self, file_bytes: bytes, filename: str, mime_type: str) -> Dict[str, Any]:
        """调用文件解析接口，返回摘要与关键词"""
        files = {"file": (filename, file_bytes, mime_type)}
        resp = await self._client.post("/llms-gateway/paresing", files=files)
        resp.raise_for_status()
        return resp.json()

    async def embed_text(self, text: str) -> List[float]:
        """调用向量化接口，返回向量数组"""
        payload = {"input": text}
        resp = await self._client.post("/llms-gateway/embedding", json=payload)
        resp.raise_for_status()
        data = resp.json()
        emb = data.get("embedding") or (data.get("data", [{}])[0].get("embedding"))
        if emb is None:
            raise ValueError("Embedding not found in response")
        return emb

    async def rerank(self, query: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """调用重排接口，返回重排后的条目"""
        payload = {"query": query, "items": items}
        resp = await self._client.post("/llms-gateway/reranker", json=payload)
        resp.raise_for_status()
        return resp.json().get("items", items)

    async def chat_completions(self, prompt: str, context: Optional[List[Dict[str, Any]]] = None) -> str:
        """调用对话接口，返回生成的文本内容"""
        payload = {"prompt": prompt, "context": context or []}
        resp = await self._client.post("/llms-gateway/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("content") or (data.get("choices", [{}])[0].get("message", {}).get("content"))