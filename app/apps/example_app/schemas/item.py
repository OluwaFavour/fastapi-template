"""Pydantic schemas for the example app Items domain."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ItemCreate(BaseModel):
    """Request schema for creating an item."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "My first item",
                "description": "A detailed description of the item.",
            }
        }
    )

    title: str = Field(..., min_length=1, max_length=255, description="Item title")
    description: str | None = Field(
        default=None, max_length=5000, description="Optional item description"
    )


class ItemUpdate(BaseModel):
    """Request schema for updating an item."""

    title: str | None = Field(
        default=None, min_length=1, max_length=255, description="New title"
    )
    description: str | None = Field(
        default=None, max_length=5000, description="New description"
    )


class ItemResponse(BaseModel):
    """Response schema for a single item."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None = None
    owner_id: UUID


class ItemListResponse(BaseModel):
    """Response schema for a list of items."""

    items: list[ItemResponse]
    count: int


__all__ = [
    "ItemCreate",
    "ItemUpdate",
    "ItemResponse",
    "ItemListResponse",
]
