"""监控中间件 - 集成指标收集和追踪"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import Callable
import time
import logging
from ..monitoring import metrics_collector, get_tracing_helper, sentry_helper

logger = logging.getLogger(__name__)


class MonitoringMiddleware(BaseHTTPMiddleware):
    """监控中间件 - 收集请求指标和追踪信息"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.tracing_helper = get_tracing_helper()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并收集监控数据"""
        start_time = time.time()
        
        # 增加活跃连接数
        metrics_collector.increment_active_connections()
        
        # 获取请求信息
        method = request.method
        path = request.url.path
        
        # 设置Sentry请求上下文
        sentry_helper.set_request_context(request)
        
        # 添加追踪上下文
        if self.tracing_helper:
            span = self.tracing_helper.get_current_span()
            if span:
                self.tracing_helper.add_request_context(span, request)
        
        # 添加面包屑
        sentry_helper.add_breadcrumb(
            message=f"{method} {path}",
            category="http.request",
            level="info",
            data={
                "method": method,
                "url": str(request.url),
                "user_agent": request.headers.get("user-agent", "")
            }
        )
        
        response = None
        status_code = 500
        error_type = None
        
        try:
            # 处理请求
            response = await call_next(request)
            status_code = response.status_code
            
            # 检查是否为错误状态码
            if status_code >= 400:
                error_type = f"http_{status_code}"
                
                # 记录错误指标
                metrics_collector.record_error(error_type, path)
                
                # 添加错误上下文到追踪
                if self.tracing_helper:
                    span = self.tracing_helper.get_current_span()
                    if span:
                        span.set_attribute("http.status_code", status_code)
                        span.set_attribute("error", True)
                        span.set_attribute("error.type", error_type)
        
        except Exception as e:
            # 处理异常
            status_code = 500
            error_type = type(e).__name__
            
            # 记录错误指标
            metrics_collector.record_error(error_type, path)
            
            # 捕获异常到Sentry
            sentry_helper.capture_business_logic_error(e, {
                "request_method": method,
                "request_path": path,
                "request_url": str(request.url)
            })
            
            # 添加错误上下文到追踪
            if self.tracing_helper:
                span = self.tracing_helper.get_current_span()
                if span:
                    span.record_exception(e)
                    span.set_attribute("error", True)
                    span.set_attribute("error.type", error_type)
                    span.set_attribute("error.message", str(e))
            
            logger.error(f"Request failed: {method} {path}", exc_info=True)
            raise
        
        finally:
            # 计算请求持续时间
            duration = time.time() - start_time
            
            # 减少活跃连接数
            metrics_collector.decrement_active_connections()
            
            # 记录HTTP请求指标
            metrics_collector.record_http_request(method, path, status_code, duration)
            
            # 检查性能问题
            if duration > 5.0:  # 超过5秒的请求
                sentry_helper.capture_performance_issue(
                    f"Slow request: {method} {path}",
                    f"{method} {path}",
                    duration,
                    5.0
                )
            
            # 添加响应信息到追踪
            if self.tracing_helper:
                span = self.tracing_helper.get_current_span()
                if span:
                    span.set_attribute("http.status_code", status_code)
                    span.set_attribute("http.response_size", 
                                     len(response.body) if response and hasattr(response, 'body') else 0)
            
            # 记录请求日志
            log_level = logging.WARNING if status_code >= 400 else logging.INFO
            logger.log(
                log_level,
                f"{method} {path} - {status_code} - {duration:.3f}s",
                extra={
                    "request_method": method,
                    "request_path": path,
                    "status_code": status_code,
                    "duration": duration,
                    "error_type": error_type,
                    "trace_id": self.tracing_helper.get_trace_id() if self.tracing_helper else None,
                    "span_id": self.tracing_helper.get_span_id() if self.tracing_helper else None
                }
            )
        
        return response


class HealthCheckMiddleware(BaseHTTPMiddleware):
    """健康检查中间件 - 为健康检查端点提供快速响应"""
    
    def __init__(self, app: ASGIApp, health_path: str = "/health"):
        super().__init__(app)
        self.health_path = health_path
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理健康检查请求"""
        if request.url.path == self.health_path:
            # 快速健康检查响应，不经过完整的监控流程
            return Response(
                content='{"status": "healthy", "timestamp": "' + 
                        str(int(time.time())) + '"}',
                media_type="application/json",
                status_code=200
            )
        
        return await call_next(request)


class MetricsMiddleware(BaseHTTPMiddleware):
    """指标中间件 - 为指标端点提供专门处理"""
    
    def __init__(self, app: ASGIApp, metrics_path: str = "/metrics"):
        super().__init__(app)
        self.metrics_path = metrics_path
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理指标请求"""
        if request.url.path == self.metrics_path:
            # 直接返回指标数据，不经过完整的监控流程
            from ..monitoring import get_metrics_response
            return get_metrics_response()
        
        return await call_next(request)