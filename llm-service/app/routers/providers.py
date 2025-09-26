# -*- coding: utf-8 -*-
"""
ProviderCredential 的 CRUD 路由。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from ..db import get_db
from ..models import ProviderCredential
from ..crud_schemas import ProviderCredentialCreate, ProviderCredentialOut
from app.services.providers_service import (
    create_provider_credential as svc_create_provider_credential,
    list_provider_credentials as svc_list_provider_credentials,
    get_provider_credential as svc_get_provider_credential,
    delete_provider_credential as svc_delete_provider_credential,
)

router = APIRouter(prefix="/api/v1/providers", tags=["providers"])


@router.post("/", response_model=ProviderCredentialOut)
async def create_provider_credential(payload: ProviderCredentialCreate, db: AsyncSession = Depends(get_db)):
    """创建供应商凭证"""
    return await svc_create_provider_credential(payload, db)


@router.get("/", response_model=list[ProviderCredentialOut])
async def list_provider_credentials(db: AsyncSession = Depends(get_db)):
    """列出所有凭证（不返回 api_key）"""
    return await svc_list_provider_credentials(db)


@router.get("/{cred_id}", response_model=ProviderCredentialOut)
async def get_provider_credential(cred_id: int, db: AsyncSession = Depends(get_db)):
    """按 ID 获取凭证"""
    obj = await svc_get_provider_credential(cred_id, db)
    if not obj:
        raise HTTPException(status_code=404, detail="Credential not found")
    return obj


@router.delete("/{cred_id}")
async def delete_provider_credential(cred_id: int, db: AsyncSession = Depends(get_db)):
    """删除凭证"""
    result = await svc_delete_provider_credential(cred_id, db)
    if result is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    return result