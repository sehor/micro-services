"""
认证相关路由
"""
import logging

from fastapi import APIRouter, Body, Header
from fastapi.responses import HTMLResponse

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
from app.services.auth import AuthService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["认证"])


@router.get("/email-confirmed", response_class=HTMLResponse)
def email_confirmed():
    """邮箱确认成功页面"""
    return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>邮箱确认成功</title>
            <meta charset="utf-8">
        </head>
        <body>
            <h1>邮箱确认成功！</h1>
            <p>您的邮箱已成功确认，现在可以正常使用所有功能。</p>
        </body>
        </html>
    """, status_code=200)


@router.get("/callback", response_class=HTMLResponse)
def auth_callback():
    """OAuth 回调页面"""
    return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>登录成功</title>
            <meta charset="utf-8">
        </head>
        <body>
            <h1>登录成功！</h1>
            <p>正在跳转...</p>
            <script>
                // 从 URL 中提取 token 参数
                const urlParams = new URLSearchParams(window.location.hash.substring(1));
                const accessToken = urlParams.get('access_token');
                const refreshToken = urlParams.get('refresh_token');
                
                if (accessToken) {
                    // 将 token 传递给父窗口或进行其他处理
                    if (window.opener) {
                        window.opener.postMessage({
                            type: 'auth_success',
                            access_token: accessToken,
                            refresh_token: refreshToken
                        }, '*');
                        window.close();
                    } else {
                        // 如果没有父窗口，可以重定向到主应用
                        window.location.href = '/test?token=' + accessToken;
                    }
                } else {
                    document.body.innerHTML = '<h1>登录失败</h1><p>未能获取到有效的访问令牌。</p>';
                }
            </script>
        </body>
        </html>
    """, status_code=200)


@router.post("/verify", response_model=VerifyResponse)
def verify_token(
    request: VerifyRequest = Body(default=VerifyRequest()),
    authorization: str | None = Header(None)
):
    """验证 JWT 令牌有效性"""
    return AuthService.verify_token(request, authorization)


@router.post("/check-access", response_model=CheckAccessResponse)
def check_access(request: CheckAccessRequest):
    """检查用户应用访问权限"""
    return AuthService.check_access(request)


@router.post("/register", response_model=RegisterResponse)
def register(request: RegisterRequest):
    """用户注册"""
    return AuthService.register(request)


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest):
    """用户登录"""
    return AuthService.login(request)


@router.get("/oauth/{provider}", response_model=OAuthLoginResponse)
def oauth_login(provider: str):
    """获取第三方登录授权 URL"""
    return AuthService.oauth_login(provider)


@router.post("/refresh", response_model=RefreshResponse)
def refresh_session_endpoint(request: RefreshRequest):
    """刷新访问令牌"""
    return AuthService.refresh_session(request)


@router.post("/logout")
def logout_endpoint(request: LogoutRequest):
    """用户登出"""
    return AuthService.logout(request)
