"""Example items router — demonstrates the standard routing pattern."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.apps.example_app.db.crud import item_db
from app.apps.example_app.schemas import (
    ItemCreate,
    ItemListResponse,
    ItemResponse,
    ItemUpdate,
)
from app.core.config import request_logger
from app.core.dependencies import CurrentActiveUser, get_async_session
from app.core.exceptions.handlers import exception_schema
from app.core.exceptions.types import ForbiddenException, NotFoundException

router = APIRouter(prefix="/items", tags=["Items"])


@router.post(
    "",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
    responses=exception_schema,
    summary="Create a new item",
)
async def create_item(
    data: ItemCreate,
    user: CurrentActiveUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ItemResponse:
    """Create a new item owned by the authenticated user."""
    request_logger.info(f"POST /items - user={user.email}")
    async with session.begin():
        item = await item_db.create(
            session,
            data={
                "title": data.title,
                "description": data.description,
                "owner_id": user.id,
            },
            commit_self=False,
        )
    return ItemResponse.model_validate(item)


@router.get(
    "",
    response_model=ItemListResponse,
    responses=exception_schema,
    summary="List items for the current user",
)
async def list_items(
    user: CurrentActiveUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ItemListResponse:
    """Return all items owned by the authenticated user."""
    request_logger.info(f"GET /items - user={user.email}")
    async with session.begin():
        items = await item_db.get_by_filters(
            session, filters={"owner_id": user.id, "is_deleted": False}
        )
    return ItemListResponse(
        items=[ItemResponse.model_validate(i) for i in items],
        count=len(items),
    )


@router.get(
    "/{item_id}",
    response_model=ItemResponse,
    responses=exception_schema,
    summary="Get item by ID",
)
async def get_item(
    item_id: UUID,
    user: CurrentActiveUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ItemResponse:
    """Retrieve a single item by its ID."""
    request_logger.info(f"GET /items/{item_id} - user={user.email}")
    async with session.begin():
        item = await item_db.get_by_id(session, id=item_id)

    if item is None or item.is_deleted:
        raise NotFoundException("Item not found.")
    if item.owner_id != user.id:
        raise ForbiddenException("You do not own this item.")

    return ItemResponse.model_validate(item)


@router.patch(
    "/{item_id}",
    response_model=ItemResponse,
    responses=exception_schema,
    summary="Update an item",
)
async def update_item(
    item_id: UUID,
    data: ItemUpdate,
    user: CurrentActiveUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ItemResponse:
    """Update an item's fields."""
    request_logger.info(f"PATCH /items/{item_id} - user={user.email}")

    async with session.begin():
        existing = await item_db.get_by_id(session, id=item_id)
        if existing is None or existing.is_deleted:
            raise NotFoundException("Item not found.")
        if existing.owner_id != user.id:
            raise ForbiddenException("You do not own this item.")

        updates = data.model_dump(exclude_unset=True)
        if not updates:
            return ItemResponse.model_validate(existing)

        updated = await item_db.update(
            session, id=item_id, updates=updates, commit_self=False
        )

    if updated is None:
        raise NotFoundException("Item not found.")
    return ItemResponse.model_validate(updated)


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=exception_schema,
    summary="Delete an item (soft-delete)",
)
async def delete_item(
    item_id: UUID,
    user: CurrentActiveUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> None:
    """Soft-delete an item."""
    request_logger.info(f"DELETE /items/{item_id} - user={user.email}")

    async with session.begin():
        existing = await item_db.get_by_id(session, id=item_id)
        if existing is None or existing.is_deleted:
            raise NotFoundException("Item not found.")
        if existing.owner_id != user.id:
            raise ForbiddenException("You do not own this item.")

        await item_db.soft_delete(session, id=item_id, commit_self=False)
