# -*- coding: utf-8 -*-
"""
AliVoice 业务服务：封装 CRUD 与远端注销+回滚逻辑，供路由调用。
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from app.models import AliVoice
from app.crud_schemas import AliVoiceCreate, AliVoiceUpdate
from app.services.ali_voice.voice_clone.voice_clone import CosyVoiceClone

logger = logging.getLogger(__name__)


async def create_ali_voice(payload: AliVoiceCreate, db: AsyncSession) -> AliVoice:
    """创建阿里发音人记录并提交事务。"""
    # 唯一性校验：voice 必须唯一
    res = await db.execute(select(AliVoice).where(AliVoice.voice == payload.voice))
    exists = res.scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="voice 已存在且必须唯一")
    obj = AliVoice(
        scenario=payload.scenario,
        timbre=payload.timbre,
        timbre_traits=payload.timbre_traits,
        voice=payload.voice,
        languages=payload.languages,
        is_cloned=payload.is_cloned,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def list_ali_voices(db: AsyncSession) -> list[AliVoice]:
    """列出所有阿里发音人。"""
    res = await db.execute(select(AliVoice))
    return res.scalars().all()


async def get_ali_voice(voice_id: int, db: AsyncSession) -> AliVoice | None:
    """获取阿里发音人，未找到返回 None。"""
    res = await db.execute(select(AliVoice).where(AliVoice.id == voice_id))
    return res.scalar_one_or_none()


async def update_ali_voice(voice_id: int, payload: AliVoiceUpdate, db: AsyncSession) -> AliVoice | None:
    """更新阿里发音人部分字段，未找到返回 None。"""
    res = await db.execute(select(AliVoice).where(AliVoice.id == voice_id))
    obj = res.scalar_one_or_none()
    if not obj:
        return None

    # 逐字段更新（仅当提供时）
    if payload.scenario is not None:
        obj.scenario = payload.scenario
    if payload.timbre is not None:
        obj.timbre = payload.timbre
    if payload.timbre_traits is not None:
        obj.timbre_traits = payload.timbre_traits
    if payload.voice is not None:
        obj.voice = payload.voice
    if payload.languages is not None:
        obj.languages = payload.languages
    if payload.is_cloned is not None:
        obj.is_cloned = payload.is_cloned

    await db.commit()
    await db.refresh(obj)
    return obj


async def delete_ali_voice(voice_id: int, db: AsyncSession) -> dict:
    """删除阿里发音人；复刻声音先尝试远端注销，若因不存在导致注销失败，仍继续本地删除，其余错误回滚并抛错。"""
    res = await db.execute(select(AliVoice).where(AliVoice.id == voice_id))
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="AliVoice not found")

    try:
        # 复刻声音需先远端注销
        if obj.is_cloned:
            try:
                client = CosyVoiceClone()
                result = client.delete_voice(obj.voice)
            except Exception as e:
                # 远端异常：若判断为“资源不存在”，允许继续本地删除；否则回滚并抛错
                msg = str(e)
                msg_lower = msg.lower()
                not_exist = (
                    ("not found" in msg_lower)
                    or ("does not exist" in msg_lower)
                    or ("not exist" in msg_lower)
                    or ("404" in msg_lower)
                    or ("resource not exist" in msg_lower)
                    or ("resourcenotexist" in msg_lower)
                    or ("badrequest.resourcenotexist" in msg_lower)
                    or ("resource-not-exist" in msg_lower)
                    or ("不存在" in msg)
                    or ("未找到" in msg)
                )
                if not_exist:
                    logger.warning(f"远端注销失败但判定为资源不存在，继续本地删除: {msg}")
                else:
                    logger.error(f"远端注销调用异常: {msg}")
                    await db.rollback()
                    raise HTTPException(status_code=502, detail=f"远端注销调用异常: {msg}")
            else:
                # 返回失败：若为“资源不存在”，允许继续；否则回滚并抛错
                if not result.get("success"):
                    message = result.get("message") or ""
                    error = result.get("error") or ""
                    combined = f"{message} {error}".strip()
                    msg_lower = combined.lower()
                    not_exist = (
                        ("not found" in msg_lower)
                        or ("does not exist" in msg_lower)
                        or ("not exist" in msg_lower)
                        or ("404" in msg_lower)
                        or ("resource not exist" in msg_lower)
                        or ("resourcenotexist" in msg_lower)
                        or ("badrequest.resourcenotexist" in msg_lower)
                        or ("resource-not-exist" in msg_lower)
                        or ("不存在" in combined)
                        or ("未找到" in combined)
                    )
                    if not_exist:
                        logger.warning(f"远端注销失败但判定为资源不存在，继续本地删除: {combined or '未提供错误信息'}")
                    else:
                        logger.error(f"远端注销失败: {combined or '未知错误'}")
                        await db.rollback()
                        raise HTTPException(status_code=502, detail=f"远端注销失败: {message or error or '未知错误'}")

        # 本地删除
        await db.delete(obj)
        await db.commit()
        return {"success": True}

    except HTTPException:
        # 上面已处理并回滚
        raise
    except Exception as e:
        logger.error(f"删除 AliVoice 失败: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")