"""
Schema 模块：定义请求与响应模型。
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class TextIngestRequest(BaseModel):
    """文本入库请求"""
    title: Optional[str] = None
    text: str = Field(..., min_length=1)


class DocumentResponse(BaseModel):
    """单个文档响应"""
    id: int
    title: Optional[str]
    source_type: str
    filename: Optional[str]
    mime_type: Optional[str]
    size_bytes: Optional[int]
    content_summary: Optional[str]
    keywords: Optional[List[str]]


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str = Field(..., min_length=1)
    top_k: int = 5


class SearchItem(BaseModel):
    """搜索项（用于重排与响应）"""
    id: int
    score: float
    summary: Optional[str]
    keywords: Optional[List[str]]


class SearchResponse(BaseModel):
    """搜索响应：返回答案与候选项"""
    answer: str
    items: List[SearchItem]


class DocumentUpdateRequest(BaseModel):
    """文档更新请求：允许更新标题、摘要与关键词"""
    title: Optional[str] = None
    content_summary: Optional[str] = None
    keywords: Optional[List[str]] = None