import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .db import init_db
from .router import router, attr_router

logger = logging.getLogger("todo-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：
    - startup: 调用 init_db()（其内部会根据 DB_AUTO_CREATE 判定是否建表/迁移）
    - shutdown: 当前无需特殊处理
    """
    try:
        await init_db()
        yield
    except Exception:
        logger.exception("应用启动失败（lifespan）")
        raise


# 应用入口，使用 lifespan 替代 on_event（避免弃用用法）
app = FastAPI(title="Todo Service", version="0.1.0", lifespan=lifespan)

# 模板目录
templates = Jinja2Templates(directory="app/templates")

# 挂载路由
app.include_router(router)
app.include_router(attr_router)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """渲染首页测试页模板。"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health() -> dict:
    """存活探针：用于容器与网关健康检查"""
    return {"status": "ok"}


# 便于本地调试：python -m uvicorn app.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)