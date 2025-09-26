"""限流中间件模块"""
import logging
import time
from collections.abc import Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.settings import settings

logger = logging.getLogger(__name__)

# Redis客户端（延迟初始化）
_redis_client = None


def get_redis_client():
    """获取Redis客户端（单例模式）"""
    global _redis_client
    if _redis_client is None:
        try:
            import redis
            _redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password,
                db=settings.redis_db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # 测试连接
            _redis_client.ping()
            logger.info("Redis连接成功")
        except Exception as e:
            logger.warning(f"Redis连接失败，限流功能将被禁用: {e}")
            _redis_client = None
    return _redis_client


class RateLimitMiddleware(BaseHTTPMiddleware):
    """API限流中间件：基于Redis实现滑动窗口限流"""

    def __init__(self, app, default_requests: int = 100, default_window: int = 60):
        super().__init__(app)
        self.default_requests = default_requests  # 默认请求数限制
        self.default_window = default_window      # 默认时间窗口（秒）

        # 不同端点的限流配置
        self.endpoint_limits = {
            "/auth/login": {"requests": 5, "window": 60},      # 登录：5次/分钟
            "/auth/register": {"requests": 3, "window": 60},   # 注册：3次/分钟
            "/auth/refresh": {"requests": 10, "window": 60},   # 刷新：10次/分钟
            "/auth/verify": {"requests": 20, "window": 60},    # 验证：20次/分钟
            "/health": {"requests": 1000, "window": 60},       # 健康检查：1000次/分钟
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 如果Redis不可用，跳过限流
        redis_client = get_redis_client()
        if not redis_client:
            return await call_next(request)

        # 获取客户端标识
        client_id = self._get_client_id(request)
        if not client_id:
            return await call_next(request)

        # 获取限流配置
        path = request.url.path
        limit_config = self.endpoint_limits.get(path, {
            "requests": self.default_requests,
            "window": self.default_window
        })

        # 检查限流
        is_allowed, remaining, reset_time = await self._check_rate_limit(
            redis_client, client_id, path, limit_config
        )

        if not is_allowed:
            # 超出限流，返回429错误
            logger.warning(
                "请求被限流",
                extra={
                    "client_id": client_id,
                    "path": path,
                    "limit": limit_config["requests"],
                    "window": limit_config["window"]
                }
            )
            raise HTTPException(
                status_code=429,
                detail="Too Many Requests",
                headers={
                    "X-RateLimit-Limit": str(limit_config["requests"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(limit_config["window"])
                }
            )

        # 处理请求
        response = await call_next(request)

        # 添加限流信息到响应头
        response.headers["X-RateLimit-Limit"] = str(limit_config["requests"])
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)

        return response

    def _get_client_id(self, request: Request) -> str | None:
        """获取客户端标识（IP地址或用户ID）"""
        # 优先使用认证用户ID
        if hasattr(request.state, "user_id") and request.state.user_id:
            return f"user:{request.state.user_id}"

        # 获取真实IP地址
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # 取第一个IP（客户端真实IP）
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else None

        if client_ip:
            return f"ip:{client_ip}"

        return None

    async def _check_rate_limit(self, redis_client, client_id: str, path: str, config: dict) -> tuple[bool, int, int]:
        """检查限流状态，返回(是否允许, 剩余次数, 重置时间)"""
        try:
            current_time = int(time.time())
            window = config["window"]
            limit = config["requests"]

            # Redis键
            key = f"rate_limit:{client_id}:{path}"

            # 使用Redis管道执行原子操作
            pipe = redis_client.pipeline()

            # 滑动窗口实现：使用有序集合存储请求时间戳
            window_start = current_time - window

            # 删除窗口外的旧记录
            pipe.zremrangebyscore(key, 0, window_start)

            # 获取当前窗口内的请求数
            pipe.zcard(key)

            # 添加当前请求时间戳
            pipe.zadd(key, {str(current_time): current_time})

            # 设置键过期时间
            pipe.expire(key, window + 10)  # 多10秒缓冲

            # 执行管道
            results = pipe.execute()
            current_requests = results[1]  # zcard的结果

            # 检查是否超出限制
            if current_requests >= limit:
                # 超出限制，移除刚添加的请求
                redis_client.zrem(key, str(current_time))
                return False, 0, current_time + window

            # 计算剩余次数
            remaining = limit - current_requests - 1  # -1因为刚添加了一个请求
            reset_time = current_time + window

            return True, remaining, reset_time

        except Exception as e:
            logger.error(f"限流检查失败: {e}")
            # 发生错误时允许请求通过
            return True, config["requests"], int(time.time()) + config["window"]


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """全局限流中间件：防止单个客户端过度使用资源"""

    def __init__(self, app, requests_per_minute: int = 1000):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        redis_client = get_redis_client()
        if not redis_client:
            return await call_next(request)

        # 获取客户端IP
        client_ip = self._get_client_ip(request)
        if not client_ip:
            return await call_next(request)

        # 检查全局限流
        is_allowed = await self._check_global_limit(redis_client, client_ip)

        if not is_allowed:
            logger.warning(f"客户端 {client_ip} 触发全局限流")
            raise HTTPException(
                status_code=429,
                detail="Global rate limit exceeded",
                headers={"Retry-After": "60"}
            )

        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str | None:
        """获取客户端IP地址"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else None

    async def _check_global_limit(self, redis_client, client_ip: str) -> bool:
        """检查全局限流"""
        try:
            key = f"global_rate_limit:{client_ip}"
            current_time = int(time.time())
            window_start = current_time - 60  # 1分钟窗口

            # 清理旧记录并计数
            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {str(current_time): current_time})
            pipe.expire(key, 70)

            results = pipe.execute()
            current_requests = results[1]

            return current_requests < self.requests_per_minute

        except Exception as e:
            logger.error(f"全局限流检查失败: {e}")
            return True  # 发生错误时允许请求
