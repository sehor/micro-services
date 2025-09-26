# -*- coding: utf-8 -*-
"""
FastAPI 应用入口。
"""
import logging
import time  # 新增：请求耗时统计
from fastapi import FastAPI
from .config import get_settings
from .routers.chat import router as chat_router
from .routers.providers import router as providers_router
# from .routers.voice import router as voice_router
from .db import create_all, get_engine, AsyncSessionLocal
from .models import ProviderCredential, AliVoice

# SQLAdmin 集成
from sqladmin import Admin, ModelView, action
from wtforms.fields import PasswordField
from starlette.responses import JSONResponse
from starlette.requests import Request  # 新增：用于日志中间件
# 新增：导入 AliVoice 路由
# from .routers.ali_voices import router as ali_voices_router
# 新增：导入 Embeddings 路由
from .routers.embeddings import router as embeddings_router
# 新增：导入 Rerank 路由
from .routers.rerank import router as rerank_router
# 新增：导入 llms-gateway 兼容路由
from .routers.gateway import router as gateway_router
# 新增：导入 services 以统一业务逻辑
from .services.providers_service import (
    delete_provider_credential as svc_delete_provider_credential,
)
# from .services.ali_voice.ali_voice_service import (
#     delete_ali_voice as svc_delete_ali_voice,
# )

# 新增：CORS 支持，允许从本地静态页面(5500端口)访问后端
from fastapi.middleware.cors import CORSMiddleware

 
# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
 
app = FastAPI(title=get_settings().app_name)
 
# CORS 中间件配置（放开整站 CORS）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许任意来源
    allow_credentials=False,  # 为使用 *，需禁用凭证
    allow_methods=["*"],
    allow_headers=["*"],
)

# 兼容性导入：语音相关路由可能依赖第三方 SDK（例如 dashscope），缺失时跳过
try:
    # 函数级注释：尝试导入语音路由，失败时仅记录警告以确保 /health 可用
    from .routers.voice import router as voice_router
except Exception as e:
    voice_router = None
    logger.warning("跳过语音路由加载: %s", e)

try:
    # 函数级注释：尝试导入 AliVoice 路由，失败时仅记录警告以确保基础路由正常
    from .routers.ali_voices import router as ali_voices_router
except Exception as e:
    ali_voices_router = None
    logger.warning("跳过 AliVoice 路由加载: %s", e)

@app.middleware("http")
async def log_request_middleware(request: Request, call_next):
    """请求级日志中间件：记录方法、路径、查询、来源、内容长度、状态码与耗时。
    有助于定位请求是否进入后端、是否卡在路由/下游/响应等阶段。
    """
    start = time.perf_counter()
    method = request.method
    path = request.url.path
    query = request.url.query
    origin = request.headers.get("origin")
    cl = request.headers.get("content-length")

    logger.info(
        "[HTTP] %s %s q=%s origin=%s content-length=%s",
        method, path, query, origin, cl,
    )
    try:
        response = await call_next(request)
    except Exception:
        elapsed = time.perf_counter() - start
        logger.exception("[HTTP] error %s %s elapsed=%.3fs", method, path, elapsed)
        raise
    elapsed = time.perf_counter() - start
    logger.info(
        "[HTTP] done %s %s status=%s elapsed=%.3fs",
        method, path, getattr(response, "status_code", "?"), elapsed,
    )
    return response
 
# 注册路由
app.include_router(chat_router)
app.include_router(providers_router)
if voice_router:
    # 函数级注释：仅当语音路由成功导入时才注册
    app.include_router(voice_router)
if ali_voices_router:
    # 函数级注释：仅当 AliVoice 路由成功导入时才注册
    app.include_router(ali_voices_router)
app.include_router(embeddings_router)
app.include_router(rerank_router)
# 新增：注册 llms-gateway 兼容路由
app.include_router(gateway_router)

# 初始化 SQLAdmin（挂载到 /admin）
settings = get_settings()
if settings.admin_enabled:
    admin = Admin(app, engine=get_engine(), session_maker=AsyncSessionLocal)
else:
    admin = None
 
class ProviderCredentialAdmin(ModelView, model=ProviderCredential):
     """ProviderCredential 模型的后台管理视图"""
     # 列表页展示字段（不展示敏感的 api_key）
     column_list = [
         ProviderCredential.id,
         ProviderCredential.provider,
         ProviderCredential.base_url,
         ProviderCredential.description,
     ]
     # 表单中显示的字段
     form_columns = [
         ProviderCredential.provider,
         ProviderCredential.base_url,
         ProviderCredential.api_key,
         ProviderCredential.description,
     ]
     # 表单中将 api_key 以密码输入框呈现
     form_overrides = {"api_key": PasswordField}
     # 为保持与 API 逻辑一致，禁用默认删除，改用自定义 Action
     can_delete = False
 
     @action(
         name="delete_provider_credentials",
         label="删除（调用服务）",
         confirmation_message="确认删除选中凭证？此操作不可撤销。",
     )
     async def delete_provider_credentials_action(self, request):
         """删除所选 ProviderCredential（统一走 services）"""
         pks = (request.query_params.get("pks") or "").strip()
         if not pks:
             logger.error("ProviderCredential 删除操作缺少 pks 参数")
             return JSONResponse({"detail": "No items selected"}, status_code=400)
         ids = []
         try:
             ids = [int(x) for x in pks.split(",") if x]
         except Exception as e:
             logger.exception("ProviderCredential 删除解析 pks 失败: %s", pks)
             return JSONResponse({"detail": "Invalid pks"}, status_code=400)
 
         success, failed = [], []
         # 通过 SQLAdmin 注入的 session_maker 获取异步会话
         async with self.session_maker() as db:
             for _id in ids:
                 try:
                     result = await svc_delete_provider_credential(_id, db)
                     if result is None:
                         failed.append({"id": _id, "reason": "not found"})
                     else:
                         success.append(_id)
                 except Exception as e:
                     logger.exception("删除 ProviderCredential 失败 id=%s", _id)
                     failed.append({"id": _id, "reason": str(e)})
         status = 200 if success else 400
         return JSONResponse({"deleted": success, "failed": failed}, status_code=status)
 
 
class AliVoiceAdmin(ModelView, model=AliVoice):
     """AliVoice 模型的后台管理视图"""
     # 列表页展示字段
     column_list = [
         AliVoice.id,
         AliVoice.voice,
         AliVoice.timbre,
         AliVoice.scenario,
         AliVoice.timbre_traits,
         AliVoice.languages,
         AliVoice.is_cloned,
     ]
     # 表单中显示的字段
     form_columns = [
         AliVoice.voice,
         AliVoice.timbre,
         AliVoice.scenario,
         AliVoice.timbre_traits,
         AliVoice.languages,
         AliVoice.is_cloned,
     ]
     # 为保持与 API 逻辑一致（含远端注销与失败回滚），禁用默认删除
     can_delete = False
 
     @action(
         name="delete_ali_voices",
         label="删除（含远端注销）",
         confirmation_message="确认删除选中发音人？若为复刻音色将尝试远端注销，失败将回滚。",
     )
     async def delete_ali_voices_action(self, request):
         """删除所选 AliVoice（统一走 services，包含远端注销与回滚）"""
         pks = (request.query_params.get("pks") or "").strip()
         if not pks:
             logger.error("AliVoice 删除操作缺少 pks 参数")
             return JSONResponse({"detail": "No items selected"}, status_code=400)
         ids = []
         try:
             ids = [int(x) for x in pks.split(",") if x]
         except Exception:
             logger.exception("AliVoice 删除解析 pks 失败: %s", pks)
             return JSONResponse({"detail": "Invalid pks"}, status_code=400)
 
         success, failed = [], []
         async with self.session_maker() as db:
             for _id in ids:
                 try:
                     # 函数级注释：惰性导入依赖第三方 SDK 的服务，避免模块级导入导致应用无法启动
                     from .services.ali_voice.ali_voice_service import (
                         delete_ali_voice as svc_delete_ali_voice,
                     )
                     result = await svc_delete_ali_voice(_id, db)
                     # 服务返回 {"success": True} 表示删除成功
                     if isinstance(result, dict) and result.get("success") is True:
                         success.append(_id)
                     else:
                         failed.append({"id": _id, "reason": "not found or failed"})
                 except Exception as e:
                     logger.exception("删除 AliVoice 失败 id=%s", _id)
                     failed.append({"id": _id, "reason": str(e)})
         status = 200 if success else 400
         return JSONResponse({"deleted": success, "failed": failed}, status_code=status)
 
# 仅当 admin 启用时才注册视图，避免初始化过程影响普通请求
if admin is not None:
    admin.add_view(ProviderCredentialAdmin)
    admin.add_view(AliVoiceAdmin)

@app.get("/health")
async def health() -> dict:
    """存活探针"""
    return {"status": "ok"}

@app.on_event("startup")
async def on_startup() -> None:
    """应用启动时的初始化逻辑（可选自动建表）"""
    settings = get_settings()
    if settings.db_auto_create:
        await create_all()