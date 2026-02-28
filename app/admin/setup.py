"""
SQLAdmin setup and initialization.

Creates the Admin instance and mounts it on the FastAPI application.
"""

from fastapi import FastAPI
from sqladmin import Admin

from app.admin.auth import admin_auth
from app.admin.views import UserAdmin, ItemAdmin
from app.core.db import async_engine

admin: Admin | None = None


def init_admin(app: FastAPI) -> None:
    """Initialize and mount the admin interface on the FastAPI app."""
    global admin

    admin = Admin(
        app=app,
        engine=async_engine,
        title="Admin",  # TODO: Replace with your project name
        base_url="/admin",
        authentication_backend=admin_auth,
    )

    admin.add_view(UserAdmin)
    admin.add_view(ItemAdmin)


__all__ = ["admin", "init_admin"]
