"""应用工厂模式：FastAPI应用实例创建与配置"""
from fastapi import FastAPI

from app.config.settings import settings
from app.exceptions.handlers import register_exception_handlers
from app.logging.config import get_structured_logger
from app.middleware.logging import LoggingMiddleware, RequestSizeMiddleware
from app.middleware.rate_limit import GlobalRateLimitMiddleware, RateLimitMiddleware
from app.middleware.security import (
    HTTPSRedirectMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)
from app.middleware.monitoring import MonitoringMiddleware, HealthCheckMiddleware, MetricsMiddleware
from app.monitoring import init_tracing, setup_sentry, get_metrics_response
from app.routers import test

logger = get_structured_logger(__name__)


def create_app() -> FastAPI:
    """创建并配置FastAPI应用实例"""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug
    )
    
    # 初始化监控系统
    setup_monitoring(app)

    # 添加中间件（注意顺序：后添加的先执行）

    # 0. 监控中间件（最外层）
    app.add_middleware(MonitoringMiddleware)
    app.add_middleware(HealthCheckMiddleware)
    app.add_middleware(MetricsMiddleware)

    # 1. 日志中间件
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestSizeMiddleware, max_size=10 * 1024 * 1024)  # 10MB限制

    # 2. 限流中间件
    if settings.enable_rate_limiting:
        app.add_middleware(GlobalRateLimitMiddleware, requests_per_minute=settings.global_rate_limit)
        app.add_middleware(RateLimitMiddleware)
        logger.info("限流中间件已启用")

    # 3. 安全中间件
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(HTTPSRedirectMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # 4. CORS中间件（需要在路由之前添加）
    from fastapi.middleware.cors import CORSMiddleware

    if settings.environment.value == "production":
        # 生产环境：严格的CORS策略
        allowed_origins = settings.cors_origins or []
        allow_credentials = True
        allowed_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        allowed_headers = [
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-Forwarded-For",
            "X-Forwarded-Proto"
        ]
    else:
        # 开发环境：宽松的CORS策略
        allowed_origins = ["*"]
        allow_credentials = False
        allowed_methods = ["*"]
        allowed_headers = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=allow_credentials,
        allow_methods=allowed_methods,
        allow_headers=allowed_headers,
        expose_headers=["X-Request-ID"]
    )

    logger.info("安全中间件已配置")

    # 注册异常处理器
    register_exception_handlers(app)

    # 注册路由
    from app.routers.auth import router as auth_router
    from app.routers.health import router as health_router

    app.include_router(auth_router, tags=["authentication"])
    app.include_router(health_router, tags=["health"])

    # 测试页面路由（仅开发环境）
    if settings.enable_test_page:
        app.include_router(test.router, tags=["测试"])
        logger.info("测试页面已启用")

    # 添加监控端点
    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        """Prometheus指标端点"""
        return get_metrics_response()
    
    logger.info(f"应用已创建 - 环境: {settings.environment}, 调试模式: {settings.debug}")
    return app


def setup_monitoring(app: FastAPI):
    """设置监控系统"""
    try:
        # 初始化Sentry错误监控
        sentry_enabled = setup_sentry()
        if sentry_enabled:
            logger.info("Sentry错误监控已启用")
        
        # 初始化OpenTelemetry分布式追踪
        tracing_helper = init_tracing(app, settings)
        if tracing_helper:
            logger.info("OpenTelemetry分布式追踪已启用")
        
        logger.info("监控系统初始化完成")
        
    except Exception as e:
        logger.error(f"监控系统初始化失败: {e}", exc_info=True)
        # 监控系统失败不应该影响应用启动
        pass