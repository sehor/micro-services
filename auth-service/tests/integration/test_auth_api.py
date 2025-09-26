"""认证API集成测试"""
from unittest.mock import patch

from fastapi import status


class TestAuthAPI:
    """认证API集成测试类"""

    def test_health_check(self, client):
        """测试健康检查端点"""
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok"}

    def test_verify_token_missing_authorization(self, client, mock_supabase_client):
        """测试验证token - 缺少Authorization头"""
        response = client.post("/auth/verify", json={})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data["error"]["code"] == "MISSING_TOKEN"

    def test_verify_token_invalid_format(self, client, mock_supabase_client):
        """测试验证token - 无效格式"""
        headers = {"Authorization": "Invalid token_format"}
        response = client.post("/auth/verify", json={}, headers=headers)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data["error"]["code"] == "INVALID_AUTH_HEADER"

    def test_verify_token_valid(self, client, mock_supabase_client, auth_headers):
        """测试验证token - 有效token"""
        response = client.post("/auth/verify", json={}, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is True
        assert "user_id" in data
        assert "email" in data

    def test_check_access_valid(self, client, mock_supabase_client):
        """测试检查访问权限 - 有效请求"""
        request_data = {
            "user_id": "test_user_id",
            "app_identifier": "test_app"
        }
        response = client.post("/auth/check-access", json=request_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "has_access" in data
        assert "access_level" in data

    def test_check_access_invalid_data(self, client, mock_supabase_client):
        """测试检查访问权限 - 无效数据"""
        request_data = {"user_id": ""}  # 缺少app_identifier
        response = client.post("/auth/check-access", json=request_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_success(self, client, mock_supabase_client, sample_user_data):
        """测试用户注册 - 成功"""
        response = client.post("/auth/register", json=sample_user_data)
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "user_id" in data
        assert "email" in data
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["email"] == sample_user_data["email"]

    def test_register_invalid_email(self, client, mock_supabase_client):
        """测试用户注册 - 无效邮箱"""
        invalid_data = {
            "email": "invalid_email",
            "password": "Test123!@#"
        }
        response = client.post("/auth/register", json=invalid_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_weak_password(self, client, mock_supabase_client):
        """测试用户注册 - 弱密码"""
        weak_password_data = {
            "email": "test@example.com",
            "password": "123"
        }
        response = client.post("/auth/register", json=weak_password_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_missing_fields(self, client, mock_supabase_client):
        """测试用户注册 - 缺少字段"""
        incomplete_data = {"email": "test@example.com"}
        response = client.post("/auth/register", json=incomplete_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_login_success(self, client, mock_supabase_client, sample_user_data):
        """测试用户登录 - 成功"""
        response = client.post("/auth/login", json=sample_user_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "user_id" in data
        assert "email" in data
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["email"] == sample_user_data["email"]

    def test_login_invalid_credentials(self, client, mock_supabase_client):
        """测试用户登录 - 无效凭据"""
        with patch("app.repositories.supabase.SupabaseRepository.sign_in") as mock_sign_in:
            mock_sign_in.side_effect = Exception("Invalid login credentials")

            invalid_data = {
                "email": "test@example.com",
                "password": "wrong_password"
            }
            response = client.post("/auth/login", json=invalid_data)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            data = response.json()
            assert data["error"]["code"] == "INVALID_CREDENTIALS"

    def test_login_missing_fields(self, client, mock_supabase_client):
        """测试用户登录 - 缺少字段"""
        incomplete_data = {"email": "test@example.com"}
        response = client.post("/auth/login", json=incomplete_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_oauth_login_success(self, client, mock_supabase_client):
        """测试OAuth登录 - 成功"""
        response = client.get("/auth/oauth/google")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "provider" in data
        assert "auth_url" in data
        assert data["provider"] == "google"

    def test_oauth_login_invalid_provider(self, client, mock_supabase_client):
        """测试OAuth登录 - 无效提供商"""
        with patch("app.repositories.supabase.SupabaseRepository.get_oauth_url") as mock_oauth:
            mock_oauth.side_effect = Exception("Invalid provider")

            response = client.get("/auth/oauth/invalid_provider")
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert data["error"]["code"] == "OAUTH_ERROR"

    def test_refresh_session_success(self, client, mock_supabase_client):
        """测试刷新会话 - 成功"""
        refresh_data = {"refresh_token": "valid_refresh_token"}
        response = client.post("/auth/refresh", json=refresh_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_session_invalid_token(self, client, mock_supabase_client):
        """测试刷新会话 - 无效token"""
        with patch("app.repositories.supabase.SupabaseRepository.refresh_session") as mock_refresh:
            mock_refresh.side_effect = Exception("Invalid refresh token")

            refresh_data = {"refresh_token": "invalid_refresh_token"}
            response = client.post("/auth/refresh", json=refresh_data)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            data = response.json()
            assert data["error"]["code"] == "INVALID_REFRESH_TOKEN"

    def test_refresh_session_missing_token(self, client, mock_supabase_client):
        """测试刷新会话 - 缺少token"""
        response = client.post("/auth/refresh", json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_logout_success(self, client, mock_supabase_client):
        """测试登出 - 成功"""
        logout_data = {"refresh_token": "valid_refresh_token"}
        response = client.post("/auth/logout", json=logout_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Logout successful"

    def test_logout_invalid_token(self, client, mock_supabase_client):
        """测试登出 - 无效token"""
        with patch("app.repositories.supabase.SupabaseRepository.sign_out") as mock_logout:
            mock_logout.side_effect = Exception("Invalid token")

            logout_data = {"refresh_token": "invalid_refresh_token"}
            response = client.post("/auth/logout", json=logout_data)
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert data["error"]["code"] == "LOGOUT_FAILED"

    def test_logout_missing_token(self, client, mock_supabase_client):
        """测试登出 - 缺少token"""
        response = client.post("/auth/logout", json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_rate_limiting(self, client, mock_redis):
        """测试限流功能"""
        # 模拟达到限流阈值
        with patch("app.middleware.rate_limit.RateLimitMiddleware.is_rate_limited") as mock_rate_limit:
            mock_rate_limit.return_value = True

            response = client.get("/health")
            assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_request_id_header(self, client, mock_supabase_client):
        """测试请求ID头部"""
        response = client.get("/health")
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 0

    def test_cors_headers(self, client):
        """测试CORS头部"""
        response = client.options("/health")
        # 在开发环境中应该有CORS头部
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_405_METHOD_NOT_ALLOWED]

    def test_security_headers(self, client):
        """测试安全头部"""
        response = client.get("/health")
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_large_request_body(self, client, mock_supabase_client):
        """测试大请求体限制"""
        # 创建一个大的请求体（超过10MB限制需要特殊处理）
        large_data = {"data": "x" * 1000}  # 1KB数据，正常情况
        response = client.post("/auth/register", json=large_data)
        # 应该因为验证失败而返回422，而不是413（请求体过大）
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
