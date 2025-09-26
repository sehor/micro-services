"""
应用配置管理：基于 Pydantic BaseSettings 的多环境配置体系。
支持 dev/staging/prod 环境区分与密钥安全管理。
"""
from enum import Enum

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Environment(str, Enum):
    """环境枚举：开发、测试、生产。"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """应用配置：基于环境变量与 .env 文件的统一配置管理。"""

    # 应用基础配置
    app_name: str = Field(default="AuthN-Z Service", description="应用名称")
    app_version: str = Field(default="0.1.0", description="应用版本")
    environment: Environment = Field(default=Environment.DEVELOPMENT, description="运行环境")
    debug: bool = Field(default=False, description="调试模式")

    # 服务器配置
    host: str = Field(default="127.0.0.1", description="服务监听地址")
    port: int = Field(default=8000, description="服务监听端口")

    # Supabase 配置
    supabase_url: str = Field(..., description="Supabase 项目 URL")
    supabase_service_role_key: str = Field(..., description="Supabase 服务角色密钥")
    supabase_jwt_secret: str = Field(..., description="Supabase JWT 签名密钥")

    # 安全配置
    allowed_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:8000"],
        description="CORS 允许的源地址"
    )
    cors_origins: list[str] | None = Field(default=None, description="生产环境CORS源地址")
    jwt_algorithm: str = Field(default="HS256", description="JWT 签名算法")

    # Redis 配置（用于限流和缓存）
    redis_host: str = Field(default="localhost", description="Redis 主机地址")
    redis_port: int = Field(default=6379, description="Redis 端口")
    redis_password: str | None = Field(default=None, description="Redis 密码")
    redis_db: int = Field(default=0, description="Redis 数据库编号")

    # 限流配置
    enable_rate_limiting: bool = Field(default=True, description="是否启用API限流")
    global_rate_limit: int = Field(default=1000, description="全局限流：每分钟请求数")

    # 日志配置
    log_level: str = Field(default="INFO", description="日志级别")
    log_format: str = Field(default="json", description="日志格式：json 或 text")

    # 测试页面配置
    enable_test_page: bool = Field(default=True, description="是否启用测试页面")
    
    # OpenTelemetry 追踪配置
    trace_exporter: str = Field(default="jaeger", description="追踪导出器类型：jaeger, otlp, console")
    trace_console_export: bool = Field(default=False, description="是否启用控制台追踪导出")

    @validator("environment", pre=True)
    def validate_environment(cls, v):
        """验证环境变量值。"""
        if isinstance(v, str):
            return Environment(v.lower())
        return v

    @validator("debug", pre=True)
    def set_debug_from_env(cls, v, values):
        """根据环境自动设置调试模式。"""
        if values.get("environment") == Environment.DEVELOPMENT:
            return True
        return v

    @validator("enable_test_page", pre=True)
    def disable_test_page_in_prod(cls, v, values):
        """生产环境禁用测试页面。"""
        if values.get("environment") == Environment.PRODUCTION:
            return False
        return v

    @validator("allowed_origins", pre=True)
    def parse_allowed_origins(cls, v):
        """解析 CORS 允许源（支持逗号分隔字符串）。"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        # 环境变量前缀
        env_prefix = ""


def get_settings() -> Settings:
    """获取应用配置实例（单例模式）。"""
    return Settings()


# 全局配置实例
settings = get_settings()
