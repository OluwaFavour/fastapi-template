"""Example domain model — replace with your own."""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from uuid import UUID

from app.core.db.models.base import BaseModel


class Item(BaseModel):
    __tablename__ = "items"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<Item {self.title}>"
