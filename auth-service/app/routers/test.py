"""
测试页面路由（仅开发环境）
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.config import settings

router = APIRouter(tags=["测试"])


@router.get("/test", response_class=HTMLResponse)
def test_page():
    """认证系统测试页面（仅开发环境可用）"""
    if not settings.enable_test_page:
        raise HTTPException(status_code=404, detail="测试页面在当前环境不可用")
    try:
        with open("app/templates/auth_test.html", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="测试页面未找到")
