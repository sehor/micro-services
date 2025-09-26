"""
Supabase 数据访问层
"""

from supabase import Client, create_client

from app.config import settings
from app.logging.config import get_structured_logger
from app.models.auth import CheckAccessResponse

logger = get_structured_logger(__name__)

# 全局 Supabase 客户端实例
_supabase_client: Client | None = None


class SupabaseRepository:
    """Supabase 数据访问层"""

    @staticmethod
    def get_client() -> Client:
        """获取 Supabase 客户端实例（单例模式）"""
        global _supabase_client
        if _supabase_client is None:
            _supabase_client = create_client(
                settings.supabase_url,
                settings.supabase_service_role_key
            )
        return _supabase_client

    @staticmethod
    def query_user_app_access(user_id: str, app_identifier: str) -> CheckAccessResponse:
        """查询 user_app_access 表，返回访问状态"""
        client = SupabaseRepository.get_client()
        try:
            resp = client.table("user_app_access").select("status").eq("user_id", user_id).eq("app_identifier", app_identifier).execute()

            if resp.data and len(resp.data) > 0:
                status = resp.data[0].get("status", "unknown")
                has_access = status == "active"
                return CheckAccessResponse(has_access=has_access, status=status)
            else:
                # 如果没有记录，默认拒绝访问
                return CheckAccessResponse(has_access=False, status="no_record")
        except Exception as e:
            logger.error("查询用户应用访问权限失败 user_id=%s app_identifier=%s err=%s", user_id, app_identifier, str(e))
            return CheckAccessResponse(has_access=False, status="error")

    @staticmethod
    def sign_up(email: str, password: str):
        """用户注册"""
        client = SupabaseRepository.get_client()
        return client.auth.sign_up({"email": email, "password": password})

    @staticmethod
    def sign_in(email: str, password: str):
        """用户登录"""
        client = SupabaseRepository.get_client()
        return client.auth.sign_in_with_password({"email": email, "password": password})

    @staticmethod
    def get_oauth_url(provider: str) -> str:
        """获取第三方登录授权 URL"""
        client = SupabaseRepository.get_client()
        resp = client.auth.sign_in_with_oauth({
            "provider": provider,
            "options": {
                "redirect_to": f"{settings.base_url}/auth/callback"
            }
        })
        return resp.url

    @staticmethod
    def refresh_session(refresh_token: str):
        """刷新会话"""
        client = SupabaseRepository.get_client()
        return client.auth.refresh_session(refresh_token)

    @staticmethod
    def sign_out(refresh_token: str = None):
        """用户登出"""
        client = SupabaseRepository.get_client()
        # Supabase Python SDK的sign_out方法不需要refresh_token参数
        # 它会自动使用当前会话进行登出
        return client.auth.sign_out()
