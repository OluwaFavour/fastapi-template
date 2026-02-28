"""Example admin views — register your model views here."""

from sqladmin import ModelView

from app.core.db.models.user import User
from app.apps.example_app.db.models.item import Item


class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.email, User.full_name, User.role, User.is_active, User.is_verified, User.created_at]
    column_searchable_list = [User.email, User.full_name]
    column_sortable_list = [User.email, User.created_at]
    can_create = False
    can_delete = False
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"


class ItemAdmin(ModelView, model=Item):
    column_list = [Item.id, Item.title, Item.owner_id, Item.is_deleted, Item.created_at]
    column_searchable_list = [Item.title]
    column_sortable_list = [Item.title, Item.created_at]
    name = "Item"
    name_plural = "Items"
    icon = "fa-solid fa-box"


__all__ = ["UserAdmin", "ItemAdmin"]
