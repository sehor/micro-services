"""OpenTelemetry分布式追踪配置"""

from opentelemetry import trace
# JaegerExporter已弃用，使用OTLP导出器
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.propagators.jaeger import JaegerPropagator
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.trace import Status, StatusCode
from fastapi import FastAPI, Request
from typing import Optional, Dict, Any
import os
import logging
from contextlib import contextmanager


class TracingConfig:
    """追踪配置类"""
    
    def __init__(self, settings=None):
        if settings:
            # 使用Settings配置
            self.service_name = settings.app_name
            self.service_version = settings.app_version
            self.environment = settings.environment.value
            self.console_export = settings.trace_console_export
            self.exporter_type = settings.trace_exporter
        else:
            # 回退到环境变量
            self.service_name = os.getenv("SERVICE_NAME", "auth-supabase")
            self.service_version = os.getenv("SERVICE_VERSION", "1.0.0")
            self.environment = os.getenv("ENVIRONMENT", "development")
            self.console_export = os.getenv("TRACE_CONSOLE_EXPORT", "false").lower() == "true"
            self.exporter_type = os.getenv("TRACE_EXPORTER", "jaeger")
        
        # Jaeger配置（现在使用OTLP协议）
        self.jaeger_endpoint = os.getenv("JAEGER_ENDPOINT", "http://localhost:4317")
        
        # OTLP配置
        self.otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://localhost:4317")
        
        # 采样率配置
        self.trace_sample_rate = float(os.getenv("TRACE_SAMPLE_RATE", "1.0"))


def setup_tracing(app: FastAPI, config: TracingConfig) -> trace.Tracer:
    """设置OpenTelemetry追踪"""
    
    # 创建资源
    resource = Resource.create({
        SERVICE_NAME: config.service_name,
        SERVICE_VERSION: config.service_version,
        "environment": config.environment,
        "service.instance.id": os.getenv("HOSTNAME", "unknown")
    })
    
    # 创建TracerProvider
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)
    
    # 配置导出器
    exporters = []
    
    if config.exporter_type == "jaeger":
        # 使用OTLP导出器替代已弃用的JaegerExporter
        # Jaeger现在原生支持OTLP协议
        otlp_exporter = OTLPSpanExporter(
            endpoint=config.jaeger_endpoint,
            insecure=True
        )
        exporters.append(otlp_exporter)
    
    elif config.exporter_type == "otlp":
        otlp_exporter = OTLPSpanExporter(
            endpoint=config.otlp_endpoint,
            insecure=True
        )
        exporters.append(otlp_exporter)
    
    elif config.exporter_type == "console" and config.console_export:
        console_exporter = ConsoleSpanExporter()
        exporters.append(console_exporter)
    
    # 添加批处理span处理器（只有在有导出器时才添加）
    for exporter in exporters:
        span_processor = BatchSpanProcessor(exporter)
        tracer_provider.add_span_processor(span_processor)
    
    # 设置传播器
    propagator = CompositePropagator([
        JaegerPropagator(),
        B3MultiFormat()
    ])
    set_global_textmap(propagator)
    
    # 自动仪表化
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    RedisInstrumentor().instrument()
    LoggingInstrumentor().instrument(set_logging_format=True)
    
    # 获取tracer
    tracer = trace.get_tracer(config.service_name, config.service_version)
    
    return tracer


class TracingHelper:
    """追踪辅助类"""
    
    def __init__(self, tracer: trace.Tracer):
        self.tracer = tracer
    
    @contextmanager
    def trace_operation(self, operation_name: str, attributes: Optional[Dict[str, Any]] = None):
        """追踪操作上下文管理器"""
        with self.tracer.start_as_current_span(operation_name) as span:
            try:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                
                yield span
                
                # 设置成功状态
                span.set_status(Status(StatusCode.OK))
                
            except Exception as e:
                # 记录错误
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.set_attribute("error", True)
                span.set_attribute("error.type", type(e).__name__)
                span.set_attribute("error.message", str(e))
                raise
    
    def trace_auth_operation(self, operation: str, user_id: Optional[str] = None):
        """追踪认证操作"""
        attributes = {
            "auth.operation": operation,
            "component": "auth"
        }
        if user_id:
            attributes["user.id"] = user_id
        
        return self.trace_operation(f"auth.{operation}", attributes)
    
    def trace_supabase_operation(self, operation: str, table: str, query_params: Optional[Dict] = None):
        """追踪Supabase操作"""
        attributes = {
            "db.operation": operation,
            "db.table": table,
            "db.system": "supabase",
            "component": "database"
        }
        
        if query_params:
            for key, value in query_params.items():
                if key not in ["password", "token", "secret"]:
                    attributes[f"db.query.{key}"] = str(value)
        
        return self.trace_operation(f"supabase.{operation}", attributes)
    
    def trace_redis_operation(self, operation: str, key: Optional[str] = None):
        """追踪Redis操作"""
        attributes = {
            "cache.operation": operation,
            "cache.system": "redis",
            "component": "cache"
        }
        
        if key:
            attributes["cache.key"] = key
        
        return self.trace_operation(f"redis.{operation}", attributes)
    
    def trace_external_request(self, service: str, method: str, url: str):
        """追踪外部请求"""
        attributes = {
            "http.method": method,
            "http.url": url,
            "external.service": service,
            "component": "http_client"
        }
        
        return self.trace_operation(f"external.{service}", attributes)
    
    def add_user_context(self, span: trace.Span, user_id: str, user_email: Optional[str] = None):
        """添加用户上下文到span"""
        span.set_attribute("user.id", user_id)
        if user_email:
            span.set_attribute("user.email", user_email)
    
    def add_request_context(self, span: trace.Span, request: Request):
        """添加请求上下文到span"""
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.url", str(request.url))
        span.set_attribute("http.route", request.url.path)
        span.set_attribute("http.user_agent", request.headers.get("user-agent", ""))
        
        # 添加请求ID（如果存在）
        request_id = request.headers.get("x-request-id")
        if request_id:
            span.set_attribute("request.id", request_id)
    
    def get_current_span(self) -> Optional[trace.Span]:
        """获取当前span"""
        return trace.get_current_span()
    
    def get_trace_id(self) -> Optional[str]:
        """获取当前trace ID"""
        span = self.get_current_span()
        if span and span.get_span_context().is_valid:
            return format(span.get_span_context().trace_id, '032x')
        return None
    
    def get_span_id(self) -> Optional[str]:
        """获取当前span ID"""
        span = self.get_current_span()
        if span and span.get_span_context().is_valid:
            return format(span.get_span_context().span_id, '016x')
        return None


# 全局追踪配置和辅助实例
tracing_config: Optional[TracingConfig] = None
tracing_helper: Optional[TracingHelper] = None


def init_tracing(app: FastAPI, settings=None) -> TracingHelper:
    """初始化追踪"""
    global tracing_config, tracing_helper
    
    tracing_config = TracingConfig(settings)
    tracer = setup_tracing(app, tracing_config)
    tracing_helper = TracingHelper(tracer)
    
    return tracing_helper


def get_tracing_helper() -> Optional[TracingHelper]:
    """获取追踪辅助实例"""
    return tracing_helper