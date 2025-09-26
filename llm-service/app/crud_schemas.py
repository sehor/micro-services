# -*- coding: utf-8 -*-
"""
ProviderCredential 的 Pydantic 模型。
"""
from pydantic import BaseModel
from typing import Optional


class ProviderCredentialCreate(BaseModel):
    """创建凭证请求"""
    provider: str
    base_url: str
    api_key: str
    description: Optional[str] = None


class ProviderCredentialOut(BaseModel):
    """凭证响应输出"""
    id: int
    provider: str
    base_url: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


# === 阿里发音人模型 ===
class AliVoiceCreate(BaseModel):
    """创建阿里发音人请求模型"""
    scenario: Optional[str] = None
    timbre: Optional[str] = None
    timbre_traits: Optional[str] = None
    voice: str  # 必须唯一
    languages: Optional[str] = None
    is_cloned: Optional[bool] = False


class AliVoiceUpdate(BaseModel):
    """更新阿里发音人请求模型（允许部分字段更新）"""
    scenario: Optional[str] = None
    timbre: Optional[str] = None
    timbre_traits: Optional[str] = None
    languages: Optional[str] = None


class AliVoiceOut(BaseModel):
    """阿里发音人响应模型"""
    id: int
    scenario: Optional[str] = None
    timbre: Optional[str] = None
    timbre_traits: Optional[str] = None
    voice: str
    languages: Optional[str] = None
    is_cloned: bool

    class Config:
        from_attributes = True