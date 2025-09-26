"""安全中间件模块"""
import logging
import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

from app.config.settings import settings

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """安全头中间件：添加安全相关的HTTP头"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # 安全头设置
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # 严格传输安全（仅HTTPS）
        if settings.environment.value == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # 内容安全策略
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        response.headers["Content-Security-Policy"] = csp_policy

        return response


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """HTTPS重定向中间件：在生产环境强制使用HTTPS"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 仅在生产环境启用HTTPS重定向
        if settings.environment.value == "production":
            # 检查是否通过代理（如nginx）转发
            forwarded_proto = request.headers.get("X-Forwarded-Proto")
            if forwarded_proto and forwarded_proto.lower() != "https":
                # 重定向到HTTPS
                url = request.url.replace(scheme="https")
                return RedirectResponse(url=str(url), status_code=301)

            # 直接访问时检查scheme
            if request.url.scheme != "https":
                url = request.url.replace(scheme="https")
                return RedirectResponse(url=str(url), status_code=301)

        return await call_next(request)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """请求ID中间件：为每个请求生成唯一ID用于追踪"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 生成或获取请求ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # 将请求ID添加到请求状态中，供其他组件使用
        request.state.request_id = request_id

        # 记录请求开始
        start_time = time.time()
        logger.info(
            "请求开始",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "user_agent": request.headers.get("User-Agent"),
                "client_ip": request.client.host if request.client else None
            }
        )

        try:
            response = await call_next(request)

            # 添加请求ID到响应头
            response.headers["X-Request-ID"] = request_id

            # 记录请求完成
            duration = time.time() - start_time
            logger.info(
                "请求完成",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2)
                }
            )

            return response

        except Exception as e:
            # 记录请求异常
            duration = time.time() - start_time
            logger.error(
                "请求异常",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                    "duration_ms": round(duration * 1000, 2)
                },
                exc_info=True
            )
            raise


def get_cors_middleware():
    """获取配置好的CORS中间件"""
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

    return CORSMiddleware(
        allow_origins=allowed_origins,
        allow_credentials=allow_credentials,
        allow_methods=allowed_methods,
        allow_headers=allowed_headers,
        expose_headers=["X-Request-ID"]
    )
