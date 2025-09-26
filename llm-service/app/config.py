# -*- coding: utf-8 -*-
"""
配置模块：加载环境变量与基础配置。
"""
from functools import lru_cache
import os
from pydantic import BaseModel
from dotenv import load_dotenv

#  Earlier loading .env
load_dotenv()


class Settings(BaseModel):
    """加载服务运行所需的配置"""
    app_name: str = "llm-gateway"
    env: str = os.getenv("ENV", "dev")
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:pass@localhost:5432/llm_gateway",
    )
    db_auto_create: bool = os.getenv("DB_AUTO_CREATE", "false").lower() == "true"
    admin_enabled: bool = os.getenv("ADMIN_ENABLED", "true").lower() == "true"  # 是否启用 SQLAdmin（默认关闭以避免潜在阻塞）


@lru_cache
def get_settings() -> Settings:
    """返回缓存的全局配置实例"""
    return Settings()