"""
认证业务服务
"""

import jwt

from app.config import settings
from app.exceptions.handlers import (
    AppValidationError,
    AuthenticationError,
    AuthorizationError,
    BusinessLogicError,
    ExternalServiceError,
)
from app.logging.config import get_structured_logger
from app.models.auth import (
    CheckAccessRequest,
    CheckAccessResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    OAuthLoginResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
    VerifyRequest,
    VerifyResponse,
)
from app.repositories.supabase import SupabaseRepository

logger = get_structured_logger(__name__)


class AuthService:
    """认证业务服务"""

    @staticmethod
    def extract_token_from_header(authorization: str | None) -> str | None:
        """从 Authorization 头中提取 Bearer token"""
        if not authorization:
            return None
        if not authorization.startswith("Bearer "):
            return None
        return authorization[7:]  # 去掉 "Bearer " 前缀

    @staticmethod
    def decode_supabase_jwt(token: str) -> dict:
        """使用配置的 JWT 密钥校验并解码 JWT，返回载荷"""
        try:
            payload = jwt.decode(token, settings.supabase_jwt_secret, algorithms=[settings.jwt_algorithm])
            return payload
        except jwt.ExpiredSignatureError as e:
            logger.warning("JWT已过期: %s", str(e))
            raise AuthenticationError("Token expired", "TOKEN_EXPIRED")
        except jwt.InvalidTokenError as e:
            logger.warning("JWT无效: %s", str(e))
            raise AuthenticationError("Invalid token", "INVALID_TOKEN")

    @staticmethod
    def verify_token(request: VerifyRequest, authorization: str | None = None) -> VerifyResponse:
        """验证 JWT 令牌有效性"""
        token = request.token or AuthService.extract_token_from_header(authorization)
        if not token:
            return VerifyResponse(valid=False)

        try:
            payload = AuthService.decode_supabase_jwt(token)
            user_id = payload.get("sub")
            email = payload.get("email")
            return VerifyResponse(valid=True, user_id=user_id, email=email)
        except AuthenticationError:
            return VerifyResponse(valid=False)

    @staticmethod
    def check_access(request: CheckAccessRequest) -> CheckAccessResponse:
        """检查用户应用访问权限"""
        if not request.user_id or not request.app_identifier:
            raise AppValidationError("user_id and app_identifier are required", "MISSING_REQUIRED_FIELDS")
        return SupabaseRepository.query_user_app_access(request.user_id, request.app_identifier)

    @staticmethod
    def register(request: RegisterRequest) -> RegisterResponse:
        """用户注册"""
        try:
            resp = SupabaseRepository.sign_up(request.email, request.password)
            user = getattr(resp, "user", None)
            session = getattr(resp, "session", None)

            if user is None:
                logger.error("注册失败：未返回用户对象 email=%s resp=%s", request.email, str(resp))
                raise ExternalServiceError("Sign up failed", "SUPABASE_SIGNUP_FAILED")

            user_id = getattr(user, "id", None) or (user.get("id") if isinstance(user, dict) else None)
            email_val = getattr(user, "email", None) or (user.get("email") if isinstance(user, dict) else request.email)
            email_confirmed = getattr(user, "email_confirmed_at", None) or (user.get("email_confirmed_at") if isinstance(user, dict) else None)

            if not user_id:
                logger.error("注册失败：未返回用户ID email=%s resp=%s", request.email, str(resp))
                raise ExternalServiceError("Sign up failed: no user id", "SUPABASE_NO_USER_ID")

            # 检查是否需要邮箱验证
            if session is None and email_confirmed is None:
                logger.info("用户注册成功但需要邮箱验证 email=%s user_id=%s", request.email, user_id)
                raise BusinessLogicError(
                    "Registration successful. Please check your email to verify your account before logging in.",
                    "EMAIL_VERIFICATION_REQUIRED"
                )

            return RegisterResponse(user_id=user_id, email=email_val)
        except (AuthenticationError, AuthorizationError, AppValidationError, BusinessLogicError, ExternalServiceError):
            raise
        except Exception as e:
            logger.error("注册失败 email=%s err=%s", request.email, str(e))
            raise ExternalServiceError(f"Register failed: {str(e)}", "REGISTER_FAILED")

    @staticmethod
    def login(request: LoginRequest) -> LoginResponse:
        """用户登录"""
        try:
            resp = SupabaseRepository.sign_in(request.email, request.password)
            session = getattr(resp, "session", None)
            user = getattr(resp, "user", None)

            if session is None:
                logger.error("登录失败：未返回会话 email=%s resp=%s", request.email, str(resp))
                raise AuthenticationError("Invalid credentials", "INVALID_CREDENTIALS")

            access_token = getattr(session, "access_token", None) or (session.get("access_token") if isinstance(session, dict) else None)
            refresh_token = getattr(session, "refresh_token", None) or (session.get("refresh_token") if isinstance(session, dict) else None)

            if not access_token:
                logger.error("登录失败：未返回访问令牌 email=%s resp=%s", request.email, str(resp))
                raise ExternalServiceError("Login failed: no access token", "SUPABASE_NO_ACCESS_TOKEN")

            user_id = None
            email_val = None
            if user:
                user_id = getattr(user, "id", None) or (user.get("id") if isinstance(user, dict) else None)
                email_val = getattr(user, "email", None) or (user.get("email") if isinstance(user, dict) else None)

            return LoginResponse(
                access_token=access_token,
                user_id=user_id,
                email=email_val,
                refresh_token=refresh_token
            )
        except (AuthenticationError, AuthorizationError, AppValidationError, BusinessLogicError, ExternalServiceError):
            raise
        except Exception as e:
            logger.error("登录失败 email=%s err=%s", request.email, str(e))
            raise AuthenticationError(f"Login failed: {str(e)}", "LOGIN_FAILED")

    @staticmethod
    def oauth_login(provider: str) -> OAuthLoginResponse:
        """获取第三方登录授权 URL"""
        try:
            auth_url = SupabaseRepository.get_oauth_url(provider)
            return OAuthLoginResponse(authorization_url=auth_url)
        except Exception as e:
            logger.error(f"获取 {provider} OAuth URL 失败: {e}")
            raise ExternalServiceError(f"Could not get OAuth URL for {provider}", "OAUTH_URL_FAILED")

    @staticmethod
    def refresh_session(request: RefreshRequest) -> RefreshResponse:
        """刷新访问令牌"""
        try:
            resp = SupabaseRepository.refresh_session(request.refresh_token)
            session = getattr(resp, "session", None)

            if session is None:
                logger.error("刷新令牌失败：未返回会话 refresh_token=%s resp=%s", str(request.refresh_token)[:10] + "...", str(resp))
                raise AuthenticationError("Invalid refresh token", "INVALID_REFRESH_TOKEN")

            access_token = getattr(session, "access_token", None) or (session.get("access_token") if isinstance(session, dict) else None)
            expires_in = getattr(session, "expires_in", None) or (session.get("expires_in") if isinstance(session, dict) else settings.jwt_access_token_expire_minutes * 60)

            if not access_token:
                logger.error("刷新令牌失败：未返回访问令牌 refresh_token=%s resp=%s", str(request.refresh_token)[:10] + "...", str(resp))
                raise ExternalServiceError("Refresh failed: no access token", "SUPABASE_REFRESH_NO_TOKEN")

            return RefreshResponse(
                access_token=access_token,
                expires_in=expires_in
            )
        except (AuthenticationError, AuthorizationError, AppValidationError, BusinessLogicError, ExternalServiceError):
            raise
        except Exception as e:
            logger.error("刷新令牌失败 refresh_token=%s err=%s", str(request.refresh_token)[:10] + "...", str(e))
            raise AuthenticationError(f"Refresh failed: {str(e)}", "REFRESH_FAILED")

    @staticmethod
    def logout(request: LogoutRequest) -> dict:
        """用户登出"""
        try:
            SupabaseRepository.sign_out(request.refresh_token)
            logger.info("用户登出成功 refresh_token=%s scope=%s", str(request.refresh_token)[:10] + "...", request.scope)
            return {"message": "Logout successful"}
        except Exception as e:
            logger.error("登出失败 refresh_token=%s err=%s", str(request.refresh_token)[:10] + "...", str(e))
            raise ExternalServiceError(f"Logout failed: {str(e)}", "LOGOUT_FAILED")
