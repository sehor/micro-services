# -*- coding: utf-8 -*-
"""
一个简单的本地 Mock Embeddings 上游服务，兼容 OpenAI /v1/embeddings 接口。
- 监听 127.0.0.1:8088
- POST /v1/embeddings
  请求体: {"model": "...", "input": "..." | ["..."]}
  响应体: {"data": [{"embedding": [...], "index": i}], "model": "...", "usage": {...}}
"""
from typing import Any, Dict, List, Union
from fastapi import FastAPI
from pydantic import BaseModel
import hashlib
import math

app = FastAPI(title="Mock Embeddings Upstream", version="0.1.0")


class EmbRequest(BaseModel):
    """请求模型: 兼容 OpenAI Embeddings 接口"""
    model: str
    input: Union[str, List[str]]


def _gen_vector(text: str, dim: int = 8) -> List[float]:
    """根据文本生成一个可重复的伪随机向量"""
    h = hashlib.md5(text.encode("utf-8")).digest()
    vec = []
    for i in range(dim):
        b = h[i % len(h)]
        # 映射到 [-1, 1] 的浮点数
        x = (b / 127.5) - 1.0
        # 做一个平滑处理
        vec.append(round(math.tanh(x) * 0.9, 6))
    return vec


@app.post("/v1/embeddings")
async def create_embeddings(req: EmbRequest) -> Dict[str, Any]:
    """生成嵌入向量，返回 OpenAI 兼容格式"""
    inputs = req.input if isinstance(req.input, list) else [req.input]
    data = [{"embedding": _gen_vector(t or ""), "index": i} for i, t in enumerate(inputs)]
    usage = {"prompt_tokens": max(1, sum(len(t or "") for t in inputs) // 4), "total_tokens": max(1, len(inputs))}
    return {"data": data, "model": req.model, "usage": usage}


@app.get("/")
async def root() -> Dict[str, Any]:
    """健康检查端点"""
    return {"status": "ok", "service": "mock-embeddings"}