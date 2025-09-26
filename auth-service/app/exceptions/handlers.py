"""统一异常处理模块"""
import logging
import traceback

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class BaseAppException(Exception):
    """应用基础异常类"""

    def __init__(self, message: str, error_code: str = None, details: dict = None):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(BaseAppException):
    """认证失败异常"""
    pass


class AuthorizationError(BaseAppException):
    """授权失败异常"""
    pass


class AppValidationError(BaseAppException):
    """数据验证异常"""
    pass


class BusinessLogicError(BaseAppException):
    """业务逻辑异常"""
    pass


class ExternalServiceError(BaseAppException):
    """外部服务异常"""
    pass


class RateLimitError(BaseAppException):
    """限流异常"""
    pass


class ErrorResponse:
    """统一错误响应模型"""

    def __init__(
        self,
        error_code: str,
        message: str,
        details: dict = None,
        request_id: str = None
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.request_id = request_id

    def to_dict(self) -> dict:
        """转换为字典格式"""
        response = {
            "error": {
                "code": self.error_code,
                "message": self.message
            }
        }

        if self.details:
            response["error"]["details"] = self.details

        if self.request_id:
            response["request_id"] = self.request_id

        return response


def get_request_id(request: Request) -> str:
    """获取请求ID"""
    return getattr(request.state, "request_id", "unknown")


async def app_exception_handler(request: Request, exc: BaseAppException) -> JSONResponse:
    """应用自定义异常处理器"""
    request_id = get_request_id(request)

    # 根据异常类型确定HTTP状态码
    status_code_map = {
        AuthenticationError: 401,
        AuthorizationError: 403,
        AppValidationError: 400,
        BusinessLogicError: 422,
        ExternalServiceError: 502,
        RateLimitError: 429,
    }

    status_code = status_code_map.get(type(exc), 500)

    # 记录异常日志
    logger.error(
        f"应用异常: {exc.error_code}",
        extra={
            "request_id": request_id,
            "error_code": exc.error_code,
            "error_message": exc.message,
            "details": exc.details,
            "url": str(request.url),
            "method": request.method
        },
        exc_info=True if status_code >= 500 else False
    )

    # 构建错误响应
    error_response = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        request_id=request_id
    )

    return JSONResponse(
        status_code=status_code,
        content=error_response.to_dict()
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """HTTP异常处理器"""
    request_id = get_request_id(request)

    # 记录HTTP异常
    logger.warning(
        f"HTTP异常: {exc.status_code}",
        extra={
            "request_id": request_id,
            "status_code": exc.status_code,
            "detail": exc.detail,
            "url": str(request.url),
            "method": request.method
        }
    )

    # 构建错误响应
    error_response = ErrorResponse(
        error_code=f"HTTP_{exc.status_code}",
        message=exc.detail if isinstance(exc.detail, str) else "HTTP Error",
        details=exc.detail if isinstance(exc.detail, dict) else {},
        request_id=request_id
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.to_dict()
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """请求验证异常处理器"""
    request_id = get_request_id(request)

    # 提取验证错误详情
    validation_errors = []
    for error in exc.errors():
        validation_errors.append({
            "field": ".".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })

    logger.warning(
        "请求验证失败",
        extra={
            "request_id": request_id,
            "validation_errors": validation_errors,
            "url": str(request.url),
            "method": request.method
        }
    )

    # 构建错误响应
    error_response = ErrorResponse(
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"validation_errors": validation_errors},
        request_id=request_id
    )

    return JSONResponse(
        status_code=422,
        content=error_response.to_dict()
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """通用异常处理器（兜底）"""
    request_id = get_request_id(request)

    # 记录未捕获的异常
    logger.error(
        "未捕获的异常",
        extra={
            "request_id": request_id,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "url": str(request.url),
            "method": request.method,
            "traceback": traceback.format_exc()
        },
        exc_info=True
    )

    # 构建错误响应（不暴露内部错误详情）
    error_response = ErrorResponse(
        error_code="INTERNAL_SERVER_ERROR",
        message="An internal server error occurred",
        request_id=request_id
    )

    return JSONResponse(
        status_code=500,
        content=error_response.to_dict()
    )


def register_exception_handlers(app):
    """注册所有异常处理器"""
    # 自定义应用异常
    app.add_exception_handler(BaseAppException, app_exception_handler)

    # HTTP异常
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    # 验证异常
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # 通用异常（兜底）
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("异常处理器已注册")
