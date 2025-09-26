# -*- coding: utf-8 -*-
"""
阿里发音人 CRUD 路由。
- POST   /api/v1/ali-voices/      创建
- GET    /api/v1/ali-voices/      列表
- GET    /api/v1/ali-voices/{id}  详情
- PATCH  /api/v1/ali-voices/{id}  更新（部分字段）
- DELETE /api/v1/ali-voices/{id}  删除（若 is_cloned 则远端注销）
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..db import get_db
from ..models import AliVoice
from ..crud_schemas import AliVoiceCreate, AliVoiceUpdate, AliVoiceOut
from app.services.ali_voice.voice_clone.voice_clone import CosyVoiceClone
from app.services.ali_voice.ali_voice_service import (
    create_ali_voice as svc_create_ali_voice,
    list_ali_voices as svc_list_ali_voices,
    get_ali_voice as svc_get_ali_voice,
    update_ali_voice as svc_update_ali_voice,
    delete_ali_voice as svc_delete_ali_voice,
)
import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ali-voices", tags=["ali-voices"])


@router.post("/", response_model=AliVoiceOut)
async def create_ali_voice(payload: AliVoiceCreate, db: AsyncSession = Depends(get_db)):
    """创建阿里发音人；业务逻辑下沉到 services。"""
    return await svc_create_ali_voice(payload, db)


@router.get("/", response_model=list[AliVoiceOut])
async def list_ali_voices(db: AsyncSession = Depends(get_db)):
    """列出所有阿里发音人。"""
    return await svc_list_ali_voices(db)


@router.get("/{voice_id}", response_model=AliVoiceOut)
async def get_ali_voice(voice_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个阿里发音人详情。"""
    obj = await svc_get_ali_voice(voice_id, db)
    if not obj:
        raise HTTPException(status_code=404, detail="AliVoice not found")
    return obj


@router.patch("/{voice_id}", response_model=AliVoiceOut)
async def update_ali_voice(voice_id: int, payload: AliVoiceUpdate, db: AsyncSession = Depends(get_db)):
    """更新阿里发音人（部分字段）；业务逻辑下沉到 services。"""
    obj = await svc_update_ali_voice(voice_id, payload, db)
    if not obj:
        raise HTTPException(status_code=404, detail="AliVoice not found")
    return obj


@router.delete("/{voice_id}")
async def delete_ali_voice(voice_id: int, db: AsyncSession = Depends(get_db)):
    """删除阿里发音人；如果 is_cloned=True 则调用远端注销，若注销失败则回滚本次删除操作。"""
    return await svc_delete_ali_voice(voice_id, db)