"""认证服务单元测试"""
from unittest.mock import Mock, patch

import pytest

from app.exceptions.handlers import (
    AppValidationError,
    AuthenticationError,
    ExternalServiceError,
)
from app.models.auth import (
    CheckAccessRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    VerifyRequest,
)
from app.services.auth import AuthService


class TestAuthService:
    """认证服务测试类"""

    def test_extract_token_from_header_valid(self):
        """测试从有效Authorization头提取token"""
        authorization = "Bearer test_token_123"
        token = AuthService.extract_token_from_header(authorization)
        assert token == "test_token_123"

    def test_extract_token_from_header_invalid_format(self):
        """测试从无效格式Authorization头提取token"""
        authorization = "Invalid test_token_123"
        token = AuthService.extract_token_from_header(authorization)
        assert token is None

    def test_extract_token_from_header_none(self):
        """测试从空Authorization头提取token"""
        token = AuthService.extract_token_from_header(None)
        assert token is None

    def test_decode_supabase_jwt_valid(self, valid_jwt_token):
        """测试解码有效JWT"""
        payload = AuthService.decode_supabase_jwt(valid_jwt_token)
        assert payload["sub"] == "test_user_id"
        assert payload["email"] == "test@example.com"

    def test_decode_supabase_jwt_expired(self, expired_jwt_token):
        """测试解码过期JWT"""
        with pytest.raises(AuthenticationError) as exc_info:
            AuthService.decode_supabase_jwt(expired_jwt_token)
        assert exc_info.value.code == "TOKEN_EXPIRED"

    def test_decode_supabase_jwt_invalid(self):
        """测试解码无效JWT"""
        with pytest.raises(AuthenticationError) as exc_info:
            AuthService.decode_supabase_jwt("invalid_token")
        assert exc_info.value.code == "INVALID_TOKEN"

    @patch("app.repositories.supabase.SupabaseRepository.get_client")
    def test_verify_token_valid(self, mock_get_client, valid_jwt_token):
        """测试验证有效token"""
        # 模拟Supabase客户端
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.auth.get_user.return_value = Mock(
            user=Mock(id="test_user_id", email="test@example.com")
        )

        request = VerifyRequest()
        response = AuthService.verify_token(request, f"Bearer {valid_jwt_token}")

        assert response.valid is True
        assert response.user_id == "test_user_id"
        assert response.email == "test@example.com"

    def test_verify_token_no_authorization(self):
        """测试验证无Authorization头的token"""
        request = VerifyRequest()
        with pytest.raises(AuthenticationError) as exc_info:
            AuthService.verify_token(request, None)
        assert exc_info.value.code == "MISSING_TOKEN"

    def test_verify_token_invalid_format(self):
        """测试验证格式错误的Authorization头"""
        request = VerifyRequest()
        with pytest.raises(AuthenticationError) as exc_info:
            AuthService.verify_token(request, "Invalid token")
        assert exc_info.value.code == "INVALID_AUTH_HEADER"

    @patch("app.repositories.supabase.SupabaseRepository.query_user_app_access")
    def test_check_access_valid(self, mock_query_access):
        """测试检查用户访问权限"""
        from app.models.auth import CheckAccessResponse

        mock_query_access.return_value = CheckAccessResponse(
            has_access=True,
            access_level="read",
            user_id="test_user_id",
            app_identifier="test_app"
        )

        request = CheckAccessRequest(user_id="test_user_id", app_identifier="test_app")
        response = AuthService.check_access(request)

        assert response.has_access is True
        assert response.access_level == "read"
        assert response.user_id == "test_user_id"

    @patch("app.repositories.supabase.SupabaseRepository.sign_up")
    def test_register_success(self, mock_sign_up, sample_user_data):
        """测试用户注册成功"""
        mock_sign_up.return_value = Mock(
            user=Mock(id="new_user_id", email=sample_user_data["email"]),
            session=Mock(
                access_token="new_access_token",
                refresh_token="new_refresh_token"
            )
        )

        request = RegisterRequest(**sample_user_data)
        response = AuthService.register(request)

        assert response.user_id == "new_user_id"
        assert response.email == sample_user_data["email"]
        assert response.access_token == "new_access_token"
        assert response.refresh_token == "new_refresh_token"

    @patch("app.repositories.supabase.SupabaseRepository.sign_up")
    def test_register_email_exists(self, mock_sign_up, sample_user_data):
        """测试注册已存在邮箱"""
        mock_sign_up.side_effect = Exception("User already registered")

        request = RegisterRequest(**sample_user_data)
        with pytest.raises(ExternalServiceError) as exc_info:
            AuthService.register(request)
        assert exc_info.value.code == "REGISTRATION_FAILED"

    def test_register_invalid_email(self):
        """测试注册无效邮箱"""
        with pytest.raises(AppValidationError):
            RegisterRequest(email="invalid_email", password="Test123!@#")

    def test_register_weak_password(self):
        """测试注册弱密码"""
        with pytest.raises(AppValidationError):
            RegisterRequest(email="test@example.com", password="123")

    @patch("app.repositories.supabase.SupabaseRepository.sign_in")
    def test_login_success(self, mock_sign_in, sample_user_data):
        """测试用户登录成功"""
        mock_sign_in.return_value = Mock(
            user=Mock(id="test_user_id", email=sample_user_data["email"]),
            session=Mock(
                access_token="login_access_token",
                refresh_token="login_refresh_token"
            )
        )

        request = LoginRequest(**sample_user_data)
        response = AuthService.login(request)

        assert response.user_id == "test_user_id"
        assert response.email == sample_user_data["email"]
        assert response.access_token == "login_access_token"
        assert response.refresh_token == "login_refresh_token"

    @patch("app.repositories.supabase.SupabaseRepository.sign_in")
    def test_login_invalid_credentials(self, mock_sign_in, sample_user_data):
        """测试登录无效凭据"""
        mock_sign_in.side_effect = Exception("Invalid login credentials")

        request = LoginRequest(**sample_user_data)
        with pytest.raises(AuthenticationError) as exc_info:
            AuthService.login(request)
        assert exc_info.value.code == "INVALID_CREDENTIALS"

    @patch("app.repositories.supabase.SupabaseRepository.get_oauth_url")
    def test_oauth_login_success(self, mock_get_oauth_url):
        """测试OAuth登录成功"""
        mock_get_oauth_url.return_value = "https://oauth.provider.com/auth"

        response = AuthService.oauth_login("google")

        assert response.provider == "google"
        assert response.auth_url == "https://oauth.provider.com/auth"

    @patch("app.repositories.supabase.SupabaseRepository.get_oauth_url")
    def test_oauth_login_failure(self, mock_get_oauth_url):
        """测试OAuth登录失败"""
        mock_get_oauth_url.side_effect = Exception("OAuth provider error")

        with pytest.raises(ExternalServiceError) as exc_info:
            AuthService.oauth_login("invalid_provider")
        assert exc_info.value.code == "OAUTH_ERROR"

    @patch("app.repositories.supabase.SupabaseRepository.refresh_session")
    def test_refresh_session_success(self, mock_refresh_session):
        """测试刷新会话成功"""
        mock_refresh_session.return_value = Mock(
            session=Mock(
                access_token="refreshed_access_token",
                refresh_token="refreshed_refresh_token"
            )
        )

        request = RefreshRequest(refresh_token="old_refresh_token")
        response = AuthService.refresh_session(request)

        assert response.access_token == "refreshed_access_token"
        assert response.refresh_token == "refreshed_refresh_token"

    @patch("app.repositories.supabase.SupabaseRepository.refresh_session")
    def test_refresh_session_invalid_token(self, mock_refresh_session):
        """测试刷新会话无效token"""
        mock_refresh_session.side_effect = Exception("Invalid refresh token")

        request = RefreshRequest(refresh_token="invalid_refresh_token")
        with pytest.raises(AuthenticationError) as exc_info:
            AuthService.refresh_session(request)
        assert exc_info.value.code == "INVALID_REFRESH_TOKEN"

    @patch("app.repositories.supabase.SupabaseRepository.sign_out")
    def test_logout_success(self, mock_sign_out):
        """测试登出成功"""
        mock_sign_out.return_value = Mock()

        request = LogoutRequest(refresh_token="test_refresh_token")
        response = AuthService.logout(request)

        assert response["message"] == "Logout successful"

    @patch("app.repositories.supabase.SupabaseRepository.sign_out")
    def test_logout_failure(self, mock_sign_out):
        """测试登出失败"""
        mock_sign_out.side_effect = Exception("Logout error")

        request = LogoutRequest(refresh_token="invalid_refresh_token")
        with pytest.raises(ExternalServiceError) as exc_info:
            AuthService.logout(request)
        assert exc_info.value.code == "LOGOUT_FAILED"
