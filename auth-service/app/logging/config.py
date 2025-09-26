"""结构化日志配置模块"""
import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import datetime

# 上下文变量用于存储请求ID和用户ID
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


class SensitiveDataFilter:
    """敏感信息脱敏过滤器"""

    # 敏感字段模式
    SENSITIVE_PATTERNS = [
        # 密码相关
        (r'"password"\s*:\s*"[^"]*"', r'"password": "***"'),
        (r'"refresh_token"\s*:\s*"[^"]*"', r'"refresh_token": "***"'),
        (r'"access_token"\s*:\s*"[^"]*"', r'"access_token": "***"'),
        # 邮箱脱敏（保留前3位和@后的域名）
        (r'"email"\s*:\s*"([^@]{1,3})[^@]*(@[^"]+)"', r'"email": "\1***\2"'),
        # JWT token脱敏（只保留前10位）
        (r'"token"\s*:\s*"([^"]{10})[^"]*"', r'"token": "\1***"'),
        # 用户ID部分脱敏
        (r'"user_id"\s*:\s*"([^"]{8})[^"]*"', r'"user_id": "\1***"'),
    ]

    @classmethod
    def sanitize(cls, message: str) -> str:
        """脱敏敏感信息"""
        sanitized = message
        for pattern, replacement in cls.SENSITIVE_PATTERNS:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        return sanitized


class JSONFormatter(logging.Formatter):
    """JSON格式化器"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hostname = "auth-service"  # 服务名称

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为JSON"""
        # 基础日志信息
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "service": self.hostname,
        }

        # 添加请求上下文信息
        request_id = request_id_var.get()
        if request_id:
            log_entry["request_id"] = request_id
            log_entry["correlation_id"] = request_id  # 用作correlation ID

        user_id = user_id_var.get()
        if user_id:
            log_entry["user_id"] = SensitiveDataFilter.sanitize(user_id)

        # 添加额外字段
        if hasattr(record, "extra") and record.extra:
            for key, value in record.extra.items():
                if key not in log_entry:
                    log_entry[key] = value

        # 添加异常信息
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }

        # 转换为JSON并脱敏
        json_str = json.dumps(log_entry, ensure_ascii=False, default=str)
        return SensitiveDataFilter.sanitize(json_str)


class StructuredLogger:
    """结构化日志器"""

    @staticmethod
    def setup_logging(log_level: str = "INFO", enable_json: bool = True) -> None:
        """设置日志配置"""
        # 清除现有处理器
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # 设置日志级别
        level = getattr(logging, log_level.upper(), logging.INFO)
        root_logger.setLevel(level)

        # 创建控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)

        if enable_json:
            # JSON格式化器
            formatter = JSONFormatter()
        else:
            # 开发环境使用简单格式
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # 设置第三方库日志级别
        logging.getLogger("uvicorn").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("fastapi").setLevel(logging.WARNING)

        logging.info("结构化日志已配置", extra={
            "log_level": log_level,
            "json_format": enable_json
        })

    @staticmethod
    def set_request_context(request_id: str, user_id: str = None) -> None:
        """设置请求上下文"""
        request_id_var.set(request_id)
        if user_id:
            user_id_var.set(user_id)

    @staticmethod
    def clear_request_context() -> None:
        """清除请求上下文"""
        request_id_var.set(None)
        user_id_var.set(None)

    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """获取日志器"""
        return logging.getLogger(name)


def get_structured_logger(name: str) -> logging.Logger:
    """获取结构化日志器的便捷函数"""
    return StructuredLogger.get_logger(name)
