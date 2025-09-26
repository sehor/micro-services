"""Sentry错误监控配置"""

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk import configure_scope, capture_exception, capture_message, set_user, set_tag, set_context
from fastapi import Request
from typing import Optional, Dict, Any
import os
import logging


class SentryConfig:
    """Sentry配置类"""
    
    def __init__(self):
        self.dsn = os.getenv("SENTRY_DSN")
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.release = os.getenv("SERVICE_VERSION", "1.0.0")
        self.sample_rate = float(os.getenv("SENTRY_SAMPLE_RATE", "1.0"))
        self.traces_sample_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
        self.profiles_sample_rate = float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1"))
        self.max_breadcrumbs = int(os.getenv("SENTRY_MAX_BREADCRUMBS", "50"))
        self.attach_stacktrace = os.getenv("SENTRY_ATTACH_STACKTRACE", "true").lower() == "true"
        self.send_default_pii = os.getenv("SENTRY_SEND_DEFAULT_PII", "false").lower() == "true"
        self.debug = os.getenv("SENTRY_DEBUG", "false").lower() == "true"


def init_sentry(config: SentryConfig) -> bool:
    """初始化Sentry"""
    if not config.dsn:
        logging.warning("Sentry DSN not configured, error monitoring disabled")
        return False
    
    # 配置日志集成
    logging_integration = LoggingIntegration(
        level=logging.INFO,        # 捕获info及以上级别的日志
        event_level=logging.ERROR  # 将error及以上级别的日志作为事件发送
    )
    
    # 初始化Sentry
    sentry_sdk.init(
        dsn=config.dsn,
        environment=config.environment,
        release=config.release,
        sample_rate=config.sample_rate,
        traces_sample_rate=config.traces_sample_rate,
        profiles_sample_rate=config.profiles_sample_rate,
        max_breadcrumbs=config.max_breadcrumbs,
        attach_stacktrace=config.attach_stacktrace,
        send_default_pii=config.send_default_pii,
        debug=config.debug,
        integrations=[
            FastApiIntegration(auto_enable=True),
            StarletteIntegration(auto_enable=True),
            HttpxIntegration(),
            RedisIntegration(),
            logging_integration
            # SqlAlchemyIntegration 已从新版本的 sentry-sdk 中移除
        ],
        before_send=before_send_filter,
        before_send_transaction=before_send_transaction_filter
    )
    
    # 设置全局标签
    with configure_scope() as scope:
        scope.set_tag("service", "auth-supabase")
        scope.set_tag("environment", config.environment)
        scope.set_tag("version", config.release)
    
    logging.info(f"Sentry initialized for environment: {config.environment}")
    return True


def before_send_filter(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """发送前过滤器 - 过滤敏感信息和不重要的错误"""
    
    # 过滤健康检查相关的错误
    if event.get("request", {}).get("url", "").endswith("/health"):
        return None
    
    # 过滤指标端点的错误
    if event.get("request", {}).get("url", "").endswith("/metrics"):
        return None
    
    # 过滤敏感信息
    if "request" in event:
        request_data = event["request"]
        
        # 移除敏感的请求头
        if "headers" in request_data:
            sensitive_headers = ["authorization", "cookie", "x-api-key"]
            for header in sensitive_headers:
                request_data["headers"].pop(header, None)
        
        # 移除敏感的查询参数
        if "query_string" in request_data:
            sensitive_params = ["token", "password", "secret"]
            query_string = request_data["query_string"]
            for param in sensitive_params:
                if param in query_string:
                    request_data["query_string"] = "[Filtered]"
                    break
    
    # 过滤异常中的敏感信息
    if "exception" in event:
        for exception in event["exception"]["values"]:
            if "value" in exception:
                # 替换可能包含敏感信息的异常消息
                sensitive_patterns = ["password", "token", "secret", "key"]
                for pattern in sensitive_patterns:
                    if pattern in exception["value"].lower():
                        exception["value"] = "[Sensitive information filtered]"
                        break
    
    return event


def before_send_transaction_filter(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """事务发送前过滤器"""
    
    # 过滤健康检查和指标端点的事务
    transaction_name = event.get("transaction", "")
    if transaction_name in ["/health", "/metrics"]:
        return None
    
    return event


class SentryHelper:
    """Sentry辅助类"""
    
    @staticmethod
    def set_user_context(user_id: str, email: Optional[str] = None, username: Optional[str] = None):
        """设置用户上下文"""
        user_data = {"id": user_id}
        if email:
            user_data["email"] = email
        if username:
            user_data["username"] = username
        
        set_user(user_data)
    
    @staticmethod
    def set_request_context(request: Request):
        """设置请求上下文"""
        with configure_scope() as scope:
            scope.set_tag("http.method", request.method)
            scope.set_tag("http.url", str(request.url))
            scope.set_context("request", {
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers),
                "query_params": dict(request.query_params)
            })
            
            # 设置请求ID（如果存在）
            request_id = request.headers.get("x-request-id")
            if request_id:
                scope.set_tag("request.id", request_id)
    
    @staticmethod
    def set_operation_context(operation: str, component: str, **kwargs):
        """设置操作上下文"""
        with configure_scope() as scope:
            scope.set_tag("operation", operation)
            scope.set_tag("component", component)
            
            if kwargs:
                scope.set_context("operation", kwargs)
    
    @staticmethod
    def capture_auth_error(error: Exception, user_id: Optional[str] = None, operation: Optional[str] = None):
        """捕获认证相关错误"""
        with configure_scope() as scope:
            scope.set_tag("error.category", "authentication")
            if user_id:
                scope.set_tag("user.id", user_id)
            if operation:
                scope.set_tag("auth.operation", operation)
            
            capture_exception(error)
    
    @staticmethod
    def capture_database_error(error: Exception, operation: Optional[str] = None, table: Optional[str] = None):
        """捕获数据库相关错误"""
        with configure_scope() as scope:
            scope.set_tag("error.category", "database")
            if operation:
                scope.set_tag("db.operation", operation)
            if table:
                scope.set_tag("db.table", table)
            
            capture_exception(error)
    
    @staticmethod
    def capture_external_service_error(error: Exception, service: str, endpoint: Optional[str] = None):
        """捕获外部服务错误"""
        with configure_scope() as scope:
            scope.set_tag("error.category", "external_service")
            scope.set_tag("external.service", service)
            if endpoint:
                scope.set_tag("external.endpoint", endpoint)
            
            capture_exception(error)
    
    @staticmethod
    def capture_business_logic_error(error: Exception, context: Optional[Dict[str, Any]] = None):
        """捕获业务逻辑错误"""
        with configure_scope() as scope:
            scope.set_tag("error.category", "business_logic")
            if context:
                scope.set_context("business_context", context)
            
            capture_exception(error)
    
    @staticmethod
    def capture_performance_issue(message: str, operation: str, duration: float, threshold: float):
        """捕获性能问题"""
        with configure_scope() as scope:
            scope.set_tag("issue.category", "performance")
            scope.set_tag("operation", operation)
            scope.set_context("performance", {
                "duration": duration,
                "threshold": threshold,
                "exceeded_by": duration - threshold
            })
            
            capture_message(message, level="warning")
    
    @staticmethod
    def add_breadcrumb(message: str, category: str, level: str = "info", data: Optional[Dict[str, Any]] = None):
        """添加面包屑"""
        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data or {}
        )


# 全局Sentry配置和辅助实例
sentry_config = SentryConfig()
sentry_helper = SentryHelper()


def setup_sentry() -> bool:
    """设置Sentry监控"""
    return init_sentry(sentry_config)