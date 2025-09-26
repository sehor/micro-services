"""
健康检查路由
"""
from fastapi import APIRouter

router = APIRouter(tags=["健康检查"])


@router.get("/health")
def health():
    """健康检查端点"""
    return {"status": "ok"}
