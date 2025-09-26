"""
认证相关数据模型
"""

from pydantic import BaseModel, EmailStr


class VerifyRequest(BaseModel):
    """令牌验证请求"""
    token: str | None = None


class VerifyResponse(BaseModel):
    """令牌验证响应"""
    valid: bool
    user_id: str | None = None
    email: EmailStr | None = None


class CheckAccessRequest(BaseModel):
    """访问权限检查请求"""
    user_id: str
    app_identifier: str


class CheckAccessResponse(BaseModel):
    """访问权限检查响应"""
    has_access: bool
    status: str | None = None


class RegisterRequest(BaseModel):
    """用户注册请求"""
    email: EmailStr
    password: str


class RegisterResponse(BaseModel):
    """用户注册响应"""
    user_id: str
    email: EmailStr


class LoginRequest(BaseModel):
    """用户登录请求"""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """用户登录响应"""
    access_token: str
    token_type: str = "bearer"
    user_id: str | None = None
    email: EmailStr | None = None
    refresh_token: str | None = None


class OAuthLoginResponse(BaseModel):
    """OAuth 登录响应"""
    authorization_url: str


class RefreshRequest(BaseModel):
    """令牌刷新请求"""
    refresh_token: str


class RefreshResponse(BaseModel):
    """令牌刷新响应"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LogoutRequest(BaseModel):
    """用户登出请求"""
    refresh_token: str
    scope: str | None = "global"
