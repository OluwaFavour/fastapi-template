"""
Authentication dependencies for FastAPI endpoints.

Provides:
- get_current_user: Extract + validate JWT, return User
- get_current_active_user: Ensures user is active
- get_current_verified_user: Ensures user is email-verified
- get_optional_user: Returns user or None (public endpoints)
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies.db import get_async_session
from app.core.config import auth_logger
from app.core.db.crud import user_db
from app.core.db.models import User
from app.core.exceptions.types import AuthenticationException, ForbiddenException
from app.core.utils import decode_jwt_token

# Security scheme for Bearer token authentication
bearer_scheme = HTTPBearer(auto_error=True)
optional_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> User:
    """Extract and validate the JWT access token, returning the authenticated User."""
    token = credentials.credentials

    payload = decode_jwt_token(token)
    if payload is None:
        auth_logger.warning("Authentication failed: invalid or expired token")
        raise AuthenticationException("Invalid or expired access token")

    user_id_str = payload.get("sub")
    if not user_id_str:
        auth_logger.warning("Authentication failed: token missing 'sub' claim")
        raise AuthenticationException("Invalid access token")

    token_type = payload.get("type")
    if token_type != "access":
        auth_logger.warning(f"Authentication failed: wrong token type '{token_type}'")
        raise AuthenticationException("Invalid access token")

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        auth_logger.warning(
            f"Authentication failed: invalid user ID format '{user_id_str}'"
        )
        raise AuthenticationException("Invalid access token")

    async with session.begin():
        user = await user_db.get_by_id(session=session, id=user_id)

    if user is None:
        auth_logger.warning(f"Authentication failed: user not found {user_id}")
        raise AuthenticationException("User not found")

    if user.is_deleted:
        auth_logger.warning(f"Authentication failed: user deleted {user_id}")
        raise AuthenticationException("User account has been deleted")

    auth_logger.debug(f"User authenticated: {user.email}")
    return user


async def get_current_active_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Ensure the current user is active."""
    if not user.is_active:
        auth_logger.warning(f"Access denied: user deactivated {user.email}")
        raise ForbiddenException("User account is deactivated")
    return user


async def get_current_verified_user(
    user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Ensure the current user has verified their email."""
    if not user.is_verified:
        auth_logger.warning(f"Access denied: email not verified {user.email}")
        raise ForbiddenException("Email verification required")
    return user


async def get_optional_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(optional_bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> User | None:
    """Optionally get the current user if a valid access token is provided."""
    if credentials is None:
        return None

    token = credentials.credentials
    payload = decode_jwt_token(token)
    if payload is None:
        return None

    user_id_str = payload.get("sub")
    if not user_id_str:
        return None

    token_type = payload.get("type")
    if token_type != "access":
        return None

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        return None

    async with session.begin():
        user = await user_db.get_by_id(session=session, id=user_id)

    if user is None or user.is_deleted or not user.is_active:
        return None

    return user


# Type aliases for cleaner dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]
CurrentVerifiedUser = Annotated[User, Depends(get_current_verified_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]

__all__ = [
    "get_current_user",
    "get_current_active_user",
    "get_current_verified_user",
    "get_optional_user",
    "CurrentUser",
    "CurrentActiveUser",
    "CurrentVerifiedUser",
    "OptionalUser",
    "bearer_scheme",
    "optional_bearer_scheme",
]
