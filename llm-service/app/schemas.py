# -*- coding: utf-8 -*-
"""
数据模型：请求与响应的标准结构。
"""
from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel


class MessageContent(BaseModel):
    """消息内容，支持文本、图片和文件"""
    type: str  # "text", "image_url" 或 "file"
    text: Optional[str] = None
    image_url: Optional[Dict[str, str]] = None
    file: Optional[Dict[str, Any]] = None  # 文件内容：{"filename": "name", "file_data": "data_uri"}


class ToolCall(BaseModel):
    """工具调用信息"""
    id: str
    type: str = "function"
    function: Dict[str, Any]


class FunctionDefinition(BaseModel):
    """函数定义"""
    name: str
    description: Optional[str] = None
    parameters: Dict[str, Any]


class Tool(BaseModel):
    """工具定义"""
    type: str = "function"
    function: FunctionDefinition


class Message(BaseModel):
    """单条对话消息，支持多模态和工具调用"""
    role: str
    content: Optional[Union[str, List[MessageContent]]] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


class UsageInfo(BaseModel):
    """使用统计信息"""
    include: Optional[bool] = False


class ChatCompletionRequest(BaseModel):
    """标准化的聊天补全请求，支持流式、工具调用、多模态"""
    provider: str
    model: str
    messages: List[Message]
    temperature: Optional[float] = 1.0
    max_tokens: Optional[int] = 1024
    stream: Optional[bool] = False
    tools: Optional[List[Tool]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    usage: Optional[UsageInfo] = None
    # 新增：web 搜索开关与类型（默认关闭，类型为 "exa"）
    webSearch: Optional[bool] = False
    webSearchType: Optional[str] = "exa"


class Delta(BaseModel):
    """流式响应中的增量内容"""
    role: Optional[str] = None
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    finish_reason: Optional[str] = None


class Usage(BaseModel):
    """API使用统计"""
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost: Optional[float] = None


class ChatCompletionChoice(BaseModel):
    """单条回复选项，支持流式和工具调用"""
    index: int
    message: Optional[Message] = None
    delta: Optional[Delta] = None
    finish_reason: Optional[str] = None


class ChatCompletionResponse(BaseModel):
    """标准化的聊天补全响应，支持流式和工具调用"""
    id: str
    object: str = "chat.completion"
    created: Optional[int] = None
    model: str
    choices: List[ChatCompletionChoice]
    usage: Optional[Usage] = None


class StreamChunk(BaseModel):
    """流式响应数据块"""
    id: str
    object: str = "chat.completion.chunk"
    created: Optional[int] = None
    model: str
    choices: List[ChatCompletionChoice]
    usage: Optional[Usage] = None


# === 语音复刻与合成模型 ===
class VoiceCloneRequest(BaseModel):
    """声音复刻请求模型"""
    audio_url: Optional[str] = None  # 可选：若不传，则从环境变量读取默认URL
    prefix: str


class VoiceCloneResponse(BaseModel):
    """声音复刻响应模型"""
    voice_id: str


class VoiceSynthesizeRequest(BaseModel):
    """语音合成请求模型"""
    voice_id: str
    text: str
    format: Optional[str] = "wav"  # 期望的音频格式（服务器按能力尽力返回）


# === Embedding 模型 ===
class EmbeddingRequest(BaseModel):
    """Embedding 请求：默认 provider=LMStudio，默认模型为 Qwen3 Embedding 0.6B"""
    provider: str = "LMStudio"
    model: str = "text-embedding-qwen3-embedding-0.6b"
    input: Union[str, List[str]]


class EmbeddingItem(BaseModel):
    """单条嵌入向量"""
    embedding: List[float]
    index: int


class EmbeddingResponse(BaseModel):
    """Embedding 响应：支持单文本与多文本的向量返回"""
    model: str
    # 若为单文本返回 vector；多文本则返回 vectors
    vector: Optional[List[float]] = None
    vectors: Optional[List[List[float]]] = None
    usage: Optional[Usage] = None


# === Rerank 模型 ===
class RerankRequest(BaseModel):
    """重排请求：默认 provider=LMStudio，默认模型为 Qwen3 Reranker 0.6B"""
    provider: str = "LMStudio"
    model: str = "qwen3-reranker-0.6b"
    query: str
    documents: List[str]
    top_n: Optional[int] = None


class RerankResult(BaseModel):
    """单条重排结果"""
    index: int
    score: float
    document: str


class RerankResponse(BaseModel):
    """重排响应：返回排序后的文档及其分数"""
    model: str
    results: List[RerankResult]