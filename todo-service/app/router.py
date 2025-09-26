from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session, TodoRead, TodoCreateWithAttr, TodoUpdate, AttributeCreate, AttributeUpdate, AttributeRead, TodoRemainingTimeRead
from .service import (
    create_todo_service,
    list_todos_service,
    get_todo_service,
    update_todo_service,
    delete_todo_service,
    get_attributes_service,
    create_attributes_service,
    update_attributes_service,
    delete_attributes_service,
    get_remaining_time_service,
)

# -------------------------------
# API 路由
# -------------------------------
router = APIRouter(prefix="/api", tags=["todos"])

@router.post("/todos", response_model=TodoRead, status_code=status.HTTP_201_CREATED)
async def create_todo(payload: TodoCreateWithAttr, session: AsyncSession = Depends(get_session)) -> TodoRead:
    """创建代办事项（可带属性）。"""
    return await create_todo_service(payload, session)

@router.get("/todos", response_model=List[TodoRead])
async def list_todos(session: AsyncSession = Depends(get_session)) -> List[TodoRead]:
    """返回全部代办事项。"""
    return await list_todos_service(session)

@router.get("/todos/{todo_id}", response_model=TodoRead)
async def get_todo(todo_id: int, session: AsyncSession = Depends(get_session)) -> TodoRead:
    """获取单个代办事项。"""
    return await get_todo_service(todo_id, session)

@router.put("/todos/{todo_id}", response_model=TodoRead)
async def update_todo(todo_id: int, payload: TodoUpdate, session: AsyncSession = Depends(get_session)) -> TodoRead:
    """更新代办事项。"""
    return await update_todo_service(todo_id, payload, session)

@router.delete("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(todo_id: int, session: AsyncSession = Depends(get_session)) -> None:
    """删除代办事项。"""
    return await delete_todo_service(todo_id, session)

# ---- 属性路由 ----
attr_router = APIRouter(prefix="/api", tags=["attributes"])

@attr_router.get("/todos/{todo_id}/attributes", response_model=AttributeRead)
async def get_attributes(todo_id: int, session: AsyncSession = Depends(get_session)) -> AttributeRead:
    """获取指定代办事项的属性。"""
    return await get_attributes_service(todo_id, session)

@attr_router.post("/todos/{todo_id}/attributes", response_model=AttributeRead, status_code=status.HTTP_201_CREATED)
async def create_attributes(todo_id: int, payload: AttributeCreate, session: AsyncSession = Depends(get_session)) -> AttributeRead:
    """为指定代办事项创建属性。"""
    return await create_attributes_service(todo_id, payload, session)

@attr_router.put("/todos/{todo_id}/attributes", response_model=AttributeRead)
async def update_attributes(todo_id: int, payload: AttributeUpdate, session: AsyncSession = Depends(get_session)) -> AttributeRead:
    """更新指定代办事项的属性。"""
    return await update_attributes_service(todo_id, payload, session)

@attr_router.delete("/todos/{todo_id}/attributes", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attributes(todo_id: int, session: AsyncSession = Depends(get_session)) -> None:
    """删除指定代办事项的属性。"""
    return await delete_attributes_service(todo_id, session)

# ---- 剩余时间路由 ----
@router.get("/todos/{todo_id}/remaining-time", response_model=TodoRemainingTimeRead)
async def get_remaining_time(todo_id: int, session: AsyncSession = Depends(get_session)) -> TodoRemainingTimeRead:
    """查询指定代办事项剩余时间（单位秒）。"""
    return await get_remaining_time_service(todo_id, session)