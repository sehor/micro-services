"""日志中间件模块"""
import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging.config import StructuredLogger, get_structured_logger
from app.services.auth import AuthService

logger = get_structured_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """日志中间件 - 自动设置请求上下文和记录请求日志"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并记录日志"""
        # 生成请求ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # 提取用户ID（如果有认证信息）
        user_id = None
        authorization = request.headers.get("authorization")
        if authorization:
            try:
                token = AuthService.extract_token_from_header(authorization)
                if token:
                    payload = AuthService.decode_supabase_jwt(token)
                    user_id = payload.get("sub")
            except Exception:
                # 忽略token解析错误，不影响日志记录
                pass

        # 设置请求上下文
        StructuredLogger.set_request_context(request_id, user_id)

        # 记录请求开始
        start_time = time.time()
        client_ip = self._get_client_ip(request)

        logger.info(
            "请求开始",
            extra={
                "event": "request_start",
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_ip": client_ip,
                "user_agent": request.headers.get("user-agent"),
                "content_type": request.headers.get("content-type"),
                "content_length": request.headers.get("content-length"),
            }
        )

        try:
            # 处理请求
            response = await call_next(request)

            # 计算处理时间
            process_time = time.time() - start_time

            # 记录请求完成
            logger.info(
                "请求完成",
                extra={
                    "event": "request_complete",
                    "method": request.method,
                    "url": str(request.url),
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "process_time_ms": round(process_time * 1000, 2),
                    "response_size": response.headers.get("content-length"),
                }
            )

            # 添加请求ID到响应头
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as exc:
            # 计算处理时间
            process_time = time.time() - start_time

            # 记录请求异常
            logger.error(
                "请求异常",
                extra={
                    "event": "request_error",
                    "method": request.method,
                    "url": str(request.url),
                    "path": request.url.path,
                    "process_time_ms": round(process_time * 1000, 2),
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                },
                exc_info=True
            )

            # 重新抛出异常
            raise exc

        finally:
            # 清除请求上下文
            StructuredLogger.clear_request_context()

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP地址"""
        # 检查代理头
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # 回退到直接连接IP
        if hasattr(request, "client") and request.client:
            return request.client.host

        return "unknown"


class RequestSizeMiddleware(BaseHTTPMiddleware):
    """请求大小限制中间件"""

    def __init__(self, app, max_size: int = 10 * 1024 * 1024):  # 默认10MB
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """检查请求大小"""
        content_length = request.headers.get("content-length")

        if content_length:
            try:
                size = int(content_length)
                if size > self.max_size:
                    logger.warning(
                        "请求体过大",
                        extra={
                            "event": "request_too_large",
                            "content_length": size,
                            "max_size": self.max_size,
                            "url": str(request.url),
                            "method": request.method,
                        }
                    )
                    from fastapi import HTTPException
                    raise HTTPException(status_code=413, detail="Request entity too large")
            except ValueError:
                logger.warning(
                    "无效的Content-Length头",
                    extra={
                        "event": "invalid_content_length",
                        "content_length_header": content_length,
                        "url": str(request.url),
                        "method": request.method,
                    }
                )

        return await call_next(request)
