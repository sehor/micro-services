# -*- coding: utf-8 -*-
"""
凭证与供应商配置的数据模型。
"""
from sqlalchemy import String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class ProviderCredential(Base):
    """存储供应商的 base_url、api_key 与可选描述"""
    __tablename__ = "provider_credentials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(50), index=True)
    base_url: Mapped[str] = mapped_column(String(255))
    api_key: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class AliVoice(Base):
    """阿里发音人（包含内置与复刻）模型。voice 必须唯一。"""
    __tablename__ = "ali_voices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 适用场景，如：童声（标杆音色）
    scenario: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 音色名称，如：龙呼呼
    timbre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 音色特质，如：天真烂漫女童
    timbre_traits: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 唯一的 voice 标识；内置音色为名称，复刻音色通常为返回的 voice_id
    voice: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    # 支持语言，如：中、英
    languages: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 是否为复刻音色（删除时需要调用远端注销）
    is_cloned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)