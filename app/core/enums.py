"""Enums shared across the application.

Add your domain-specific enums here. Values should use UPPER_SNAKE_CASE.

Example::

    class PlanType(str, Enum):
        FREE = "free"
        BASIC = "basic"
        PROFESSIONAL = "professional"
"""

from enum import Enum


class UserRole(str, Enum):
    """User roles for access control."""

    USER = "user"
    ADMIN = "admin"


# TODO: Add your domain enums below
