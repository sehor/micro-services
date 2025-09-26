# -*- coding: utf-8 -*-
"""
ProviderCredential 业务服务：封装增删改查逻辑，供路由调用。
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models import ProviderCredential
from app.crud_schemas import ProviderCredentialCreate


async def create_provider_credential(payload: ProviderCredentialCreate, db: AsyncSession) -> ProviderCredential:
    """创建供应商凭证并提交事务。"""
    cred = ProviderCredential(
        provider=payload.provider,
        base_url=payload.base_url,
        api_key=payload.api_key,
        description=payload.description,
    )
    db.add(cred)
    await db.commit()
    await db.refresh(cred)
    return cred


async def list_provider_credentials(db: AsyncSession) -> list[ProviderCredential]:
    """列出所有供应商凭证。"""
    res = await db.execute(select(ProviderCredential))
    return res.scalars().all()


async def get_provider_credential(cred_id: int, db: AsyncSession) -> ProviderCredential | None:
    """按 ID 获取供应商凭证，未找到返回 None。"""
    res = await db.execute(select(ProviderCredential).where(ProviderCredential.id == cred_id))
    return res.scalar_one_or_none()


async def delete_provider_credential(cred_id: int, db: AsyncSession) -> dict | None:
    """删除指定 ID 的供应商凭证，返回删除结果；未找到返回 None。"""
    res = await db.execute(select(ProviderCredential).where(ProviderCredential.id == cred_id))
    obj = res.scalar_one_or_none()
    if not obj:
        return None
    await db.execute(delete(ProviderCredential).where(ProviderCredential.id == cred_id))
    await db.commit()
    return {"status": "deleted"}