"""pytest配置文件"""
import os
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

# 设置测试环境变量
os.environ["ENVIRONMENT"] = "testing"
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "test_anon_key"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test_service_key"
os.environ["SUPABASE_JWT_SECRET"] = "test_jwt_secret"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["LOG_LEVEL"] = "DEBUG"

from app.logging.config import StructuredLogger
from app.main import app


@pytest.fixture(scope="session")
def setup_test_logging():
    """设置测试日志"""
    StructuredLogger.setup_logging(log_level="DEBUG", enable_json=False)


@pytest.fixture
def client(setup_test_logging):
    """测试客户端"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_supabase_client():
    """模拟Supabase客户端"""
    with patch("app.repositories.supabase.create_client") as mock_create:
        mock_client = Mock()
        mock_create.return_value = mock_client

        # 模拟认证相关方法
        mock_client.auth.sign_up.return_value = Mock(
            user=Mock(id="test_user_id", email="test@example.com"),
            session=Mock(
                access_token="test_access_token",
                refresh_token="test_refresh_token"
            )
        )

        mock_client.auth.sign_in_with_password.return_value = Mock(
            user=Mock(id="test_user_id", email="test@example.com"),
            session=Mock(
                access_token="test_access_token",
                refresh_token="test_refresh_token"
            )
        )

        mock_client.auth.get_user.return_value = Mock(
            user=Mock(id="test_user_id", email="test@example.com")
        )

        mock_client.auth.refresh_session.return_value = Mock(
            session=Mock(
                access_token="new_access_token",
                refresh_token="new_refresh_token"
            )
        )

        mock_client.auth.sign_out.return_value = Mock()

        # 模拟数据库查询
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = Mock(
            data=[{"user_id": "test_user_id", "app_identifier": "test_app", "access_level": "read"}]
        )

        yield mock_client


@pytest.fixture
def mock_redis():
    """模拟Redis客户端"""
    with patch("app.middleware.rate_limit.redis.Redis") as mock_redis_class:
        mock_redis_instance = Mock()
        mock_redis_class.from_url.return_value = mock_redis_instance

        # 模拟Redis操作
        mock_redis_instance.get.return_value = None
        mock_redis_instance.setex.return_value = True
        mock_redis_instance.incr.return_value = 1
        mock_redis_instance.expire.return_value = True
        mock_redis_instance.ping.return_value = True

        yield mock_redis_instance


@pytest.fixture
def valid_jwt_token():
    """有效的JWT token"""
    import jwt

    from app.config import settings

    payload = {
        "sub": "test_user_id",
        "email": "test@example.com",
        "exp": 9999999999  # 远未来的过期时间
    }

    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.fixture
def expired_jwt_token():
    """过期的JWT token"""
    import jwt

    from app.config import settings

    payload = {
        "sub": "test_user_id",
        "email": "test@example.com",
        "exp": 1  # 已过期
    }

    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.fixture
def auth_headers(valid_jwt_token):
    """认证请求头"""
    return {"Authorization": f"Bearer {valid_jwt_token}"}


@pytest.fixture
def sample_user_data():
    """示例用户数据"""
    return {
        "email": "test@example.com",
        "password": "Test123!@#"
    }
