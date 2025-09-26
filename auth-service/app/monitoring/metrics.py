"""Prometheus指标收集模块"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
from typing import Dict, Any
import time
import psutil
import os

# HTTP请求指标
http_requests_total = Counter(
    "http_requests_total",
    "HTTP请求总数",
    ["method", "endpoint", "status_code"]
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP请求持续时间（秒）",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)
)

# 认证相关指标
auth_operations_total = Counter(
    "auth_operations_total",
    "认证操作总数",
    ["operation", "status"]
)

auth_token_validation_duration = Histogram(
    "auth_token_validation_duration_seconds",
    "Token验证持续时间（秒）",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
)

# 数据库连接指标
supabase_operations_total = Counter(
    "supabase_operations_total",
    "Supabase操作总数",
    ["operation", "table", "status"]
)

supabase_operation_duration = Histogram(
    "supabase_operation_duration_seconds",
    "Supabase操作持续时间（秒）",
    ["operation", "table"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

# Redis缓存指标
redis_operations_total = Counter(
    "redis_operations_total",
    "Redis操作总数",
    ["operation", "status"]
)

redis_cache_hits_total = Counter(
    "redis_cache_hits_total",
    "Redis缓存命中总数"
)

redis_cache_misses_total = Counter(
    "redis_cache_misses_total",
    "Redis缓存未命中总数"
)

# 系统资源指标
system_cpu_usage = Gauge(
    "system_cpu_usage_percent",
    "系统CPU使用率"
)

system_memory_usage = Gauge(
    "system_memory_usage_bytes",
    "系统内存使用量（字节）"
)

system_memory_total = Gauge(
    "system_memory_total_bytes",
    "系统总内存（字节）"
)

process_cpu_usage = Gauge(
    "process_cpu_usage_percent",
    "进程CPU使用率"
)

process_memory_usage = Gauge(
    "process_memory_usage_bytes",
    "进程内存使用量（字节）"
)

active_connections = Gauge(
    "active_connections_total",
    "活跃连接数"
)

# 错误指标
error_count_total = Counter(
    "error_count_total",
    "错误总数",
    ["error_type", "endpoint"]
)


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self._active_requests = 0
    
    def record_http_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """记录HTTP请求指标"""
        http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).inc()
        
        http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def record_auth_operation(self, operation: str, status: str, duration: float = None):
        """记录认证操作指标"""
        auth_operations_total.labels(
            operation=operation,
            status=status
        ).inc()
        
        if duration is not None and operation == "token_validation":
            auth_token_validation_duration.observe(duration)
    
    def record_supabase_operation(self, operation: str, table: str, status: str, duration: float):
        """记录Supabase操作指标"""
        supabase_operations_total.labels(
            operation=operation,
            table=table,
            status=status
        ).inc()
        
        supabase_operation_duration.labels(
            operation=operation,
            table=table
        ).observe(duration)
    
    def record_redis_operation(self, operation: str, status: str, is_hit: bool = None):
        """记录Redis操作指标"""
        redis_operations_total.labels(
            operation=operation,
            status=status
        ).inc()
        
        if is_hit is not None:
            if is_hit:
                redis_cache_hits_total.inc()
            else:
                redis_cache_misses_total.inc()
    
    def record_error(self, error_type: str, endpoint: str):
        """记录错误指标"""
        error_count_total.labels(
            error_type=error_type,
            endpoint=endpoint
        ).inc()
    
    def update_system_metrics(self):
        """更新系统指标"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=None)
            system_cpu_usage.set(cpu_percent)
            
            # 内存使用情况
            memory = psutil.virtual_memory()
            system_memory_usage.set(memory.used)
            system_memory_total.set(memory.total)
            
            # 进程指标
            process_cpu = self.process.cpu_percent()
            process_memory = self.process.memory_info().rss
            
            process_cpu_usage.set(process_cpu)
            process_memory_usage.set(process_memory)
            
        except Exception as e:
            # 记录系统指标收集错误，但不影响主要功能
            print(f"Error collecting system metrics: {e}")
    
    def increment_active_connections(self):
        """增加活跃连接数"""
        self._active_requests += 1
        active_connections.set(self._active_requests)
    
    def decrement_active_connections(self):
        """减少活跃连接数"""
        self._active_requests = max(0, self._active_requests - 1)
        active_connections.set(self._active_requests)
    
    def get_metrics(self) -> str:
        """获取所有指标的Prometheus格式输出"""
        self.update_system_metrics()
        return generate_latest()


# 全局指标收集器实例
metrics_collector = MetricsCollector()


def get_metrics_response() -> Response:
    """获取指标响应"""
    metrics_data = metrics_collector.get_metrics()
    return Response(
        content=metrics_data,
        media_type=CONTENT_TYPE_LATEST
    )