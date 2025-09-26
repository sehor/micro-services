"""
配置模块：加载环境变量并提供基础配置。
"""
from dotenv import load_dotenv
import os

# 加载 .env 文件中的环境变量
load_dotenv()

# 数据库连接串
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
)

# 是否在启动时自动建表
DB_AUTO_CREATE: bool = os.getenv("DB_AUTO_CREATE", "true").lower() == "true"

# 环境与调试标记
ENV: str = os.getenv("env", "dev")
DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

# 上游 LLMs 网关基础地址
LLMS_GATEWAY_BASE: str = os.getenv("LLMS_GATEWAY_BASE", "http://localhost:8000")