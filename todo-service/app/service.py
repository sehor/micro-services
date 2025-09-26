from typing import List, Optional
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import (
    Todo,
    TodoAttribute,
    TodoCreateWithAttr,
    TodoUpdate,
    AttributeCreate,
    AttributeUpdate,
    TodoRead,
    AttributeRead,
    TodoRemainingTimeRead,
)

# -------------------------------
# Service 层：封装业务逻辑
# -------------------------------

async def fetch_todo_by_id(todo_id: int, session: AsyncSession) -> Todo:
    """按 ID 获取 Todo（不存在则抛 404）。"""
    result = await session.execute(select(Todo).where(Todo.id == todo_id))
    todo = result.scalar_one_or_none()
    if not todo:
        raise HTTPException(status_code=404, detail="代办事项不存在")
    return todo


async def fetch_attribute_by_id(attribute_id: int, session: AsyncSession) -> TodoAttribute:
    """按 ID 获取属性（不存在则抛 404）。"""
    result = await session.execute(select(TodoAttribute).where(TodoAttribute.id == attribute_id))
    attr = result.scalar_one_or_none()
    if not attr:
        raise HTTPException(status_code=404, detail="属性不存在")
    return attr


async def create_attribute_entity(payload: AttributeCreate, session: AsyncSession) -> TodoAttribute:
    """创建属性实体并返回，不提交。"""
    attr = TodoAttribute(
        mergency=payload.mergency,
        corlor=payload.corlor,
        category=payload.category,
    )
    session.add(attr)
    await session.flush()
    return attr


async def update_attribute_entity_fields(attr: TodoAttribute, payload: AttributeUpdate, session: AsyncSession) -> TodoAttribute:
    """按提供的字段更新属性实体（部分更新）。"""
    if payload.mergency is not None:
        attr.mergency = payload.mergency
    if payload.corlor is not None:
        attr.corlor = payload.corlor
    if payload.category is not None:
        attr.category = payload.category
    return attr


async def delete_attribute_entity(attr: TodoAttribute, session: AsyncSession) -> None:
    """删除属性实体，不提交。"""
    await session.delete(attr)


async def attach_attribute_to_todo(todo: Todo, attr: TodoAttribute, session: AsyncSession) -> None:
    """将属性绑定到 Todo。"""
    todo.attribute_id = attr.id


async def detach_attribute_from_todo(todo: Todo, session: AsyncSession) -> None:
    """解除 Todo 与属性的绑定。"""
    todo.attribute_id = None


async def create_todo_service(payload: TodoCreateWithAttr, session: AsyncSession) -> TodoRead:
    """创建代办事项（可带属性）。"""
    try:
        todo = Todo(
            title=payload.title,
            description=payload.description,
            is_completed=payload.is_completed,
            start_at=payload.start_at,
            due_at=payload.due_at,
        )
        session.add(todo)
        await session.flush()

        if payload.attributes is not None:
            attr = await create_attribute_entity(payload.attributes, session)
            await attach_attribute_to_todo(todo, attr, session)

        await session.commit()
        result = await session.execute(select(Todo).where(Todo.id == todo.id))
        todo = result.scalar_one()
        return TodoRead.model_validate(todo)
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="创建代办事项失败")


async def list_todos_service(session: AsyncSession) -> List[TodoRead]:
    """返回全部代办事项（演示用）。"""
    try:
        result = await session.execute(select(Todo).order_by(Todo.id.desc()))
        items = result.scalars().all()
        return [TodoRead.model_validate(item) for item in items]
    except Exception:
        raise HTTPException(status_code=500, detail="查询代办事项列表失败")


async def get_todo_service(todo_id: int, session: AsyncSession) -> TodoRead:
    """获取单个代办事项。"""
    try:
        todo = await fetch_todo_by_id(todo_id, session)
        return TodoRead.model_validate(todo)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="获取代办事项失败")


async def update_todo_service(todo_id: int, payload: TodoUpdate, session: AsyncSession) -> TodoRead:
    """更新代办事项。"""
    try:
        todo = await fetch_todo_by_id(todo_id, session)

        if payload.title is not None:
            todo.title = payload.title
        if payload.description is not None:
            todo.description = payload.description
        if payload.is_completed is not None:
            todo.is_completed = payload.is_completed
        if payload.start_at is not None:
            todo.start_at = payload.start_at
        if payload.due_at is not None:
            todo.due_at = payload.due_at

        await session.commit()
        result = await session.execute(select(Todo).where(Todo.id == todo_id))
        todo = result.scalar_one()
        return TodoRead.model_validate(todo)
    except HTTPException:
        raise
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="更新代办事项失败")


async def delete_todo_service(todo_id: int, session: AsyncSession) -> None:
    """删除代办事项。若存在属性，则一并删除，并清空引用。"""
    try:
        todo = await fetch_todo_by_id(todo_id, session)
        if todo.attribute_id:
            attr = await fetch_attribute_by_id(todo.attribute_id, session)
            await delete_attribute_entity(attr, session)
            await detach_attribute_from_todo(todo, session)
        await session.delete(todo)
        await session.commit()
        return None
    except HTTPException:
        raise
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="删除代办事项失败")


# ---- 属性逻辑 ----
async def get_attributes_service(todo_id: int, session: AsyncSession) -> AttributeRead:
    """获取指定代办事项的属性。"""
    try:
        todo = await fetch_todo_by_id(todo_id, session)
        if not todo.attribute_id:
            raise HTTPException(status_code=404, detail="属性不存在")
        attr = await fetch_attribute_by_id(todo.attribute_id, session)
        return AttributeRead.model_validate(attr)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="获取属性失败")


async def create_attributes_service(todo_id: int, payload: AttributeCreate, session: AsyncSession) -> AttributeRead:
    """为指定代办事项创建属性（若已存在将报错）。"""
    try:
        todo = await fetch_todo_by_id(todo_id, session)
        if todo.attribute_id:
            raise HTTPException(status_code=400, detail="属性已存在")
        attr = await create_attribute_entity(payload, session)
        await attach_attribute_to_todo(todo, attr, session)
        await session.commit()
        await session.refresh(attr)
        return AttributeRead.model_validate(attr)
    except HTTPException:
        raise
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="创建属性失败")


async def update_attributes_service(todo_id: int, payload: AttributeUpdate, session: AsyncSession) -> AttributeRead:
    """更新指定代办事项的属性。"""
    try:
        todo = await fetch_todo_by_id(todo_id, session)
        if not todo.attribute_id:
            raise HTTPException(status_code=404, detail="属性不存在")
        attr = await fetch_attribute_by_id(todo.attribute_id, session)
        await update_attribute_entity_fields(attr, payload, session)
        await session.commit()
        await session.refresh(attr)
        return AttributeRead.model_validate(attr)
    except HTTPException:
        raise
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="更新属性失败")


async def delete_attributes_service(todo_id: int, session: AsyncSession) -> None:
    """删除指定代办事项的属性。"""
    try:
        todo = await fetch_todo_by_id(todo_id, session)
        if not todo.attribute_id:
            raise HTTPException(status_code=404, detail="属性不存在")
        attr = await fetch_attribute_by_id(todo.attribute_id, session)
        await detach_attribute_from_todo(todo, session)
        await delete_attribute_entity(attr, session)
        await session.commit()
        return None
    except HTTPException:
        raise
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="删除属性失败")


async def get_remaining_time_service(todo_id: int, session: AsyncSession) -> TodoRemainingTimeRead:
    """查询指定代办事项剩余时间（单位：秒，可为负代表已逾期）。"""
    try:
        todo = await fetch_todo_by_id(todo_id, session)
        if not todo.due_at:
            raise HTTPException(status_code=404, detail="该事项未设置结束期限")
        now = datetime.now(timezone.utc)
        due = todo.due_at
        # 兼容旧数据可能无 tz 信息
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        remaining_seconds = (due - now).total_seconds()
        return TodoRemainingTimeRead(
            todo_id=todo.id,
            due_at=todo.due_at,
            remaining_seconds=remaining_seconds,
            is_overdue=remaining_seconds < 0,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="查询剩余时间失败")