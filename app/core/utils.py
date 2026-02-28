"""
Utility functions for the application.

- Secure password hashing using bcrypt
- Password verification against hashed values
- JWT token creation and decoding
- HMAC-based OTP hashing for queryable secure storage
"""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from typing import Any
import uuid

import bcrypt
import jwt

from app.core.config import settings, utils_logger


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(password: str | None) -> str:
    """Hash a password using bcrypt with a secure salt.

    Args:
        password: The plain text password to hash. Cannot be None.

    Returns:
        The bcrypt hashed password (60 characters).

    Raises:
        ValueError: If password is None.
    """
    if password is None:
        utils_logger.error("Attempted to hash None password")
        raise ValueError("Password cannot be None")

    try:
        password_bytes = password.encode("utf-8")

        # Bcrypt has a 72-byte limit
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]

        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)

        utils_logger.info("Password hashed successfully")
        return hashed.decode("utf-8")

    except Exception as e:
        utils_logger.error(f"Failed to hash password: {type(e).__name__} - {str(e)}")
        raise


def verify_password(password: str | None, hashed_password: str | None) -> bool:
    """Verify a password against a bcrypt hash (constant-time comparison).

    Returns False for any invalid inputs.
    """
    if password is None or hashed_password is None:
        return False

    try:
        password_bytes = password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")

        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]

        return bcrypt.checkpw(password_bytes, hashed_bytes)

    except (ValueError, AttributeError):
        return False
    except Exception as e:
        utils_logger.error(
            f"Unexpected error during password verification: {type(e).__name__} - {str(e)}"
        )
        return False


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------


def create_jwt_token(
    data: dict[str, Any] | None, expires_delta: timedelta | None = None
) -> str:
    """Create a JWT token with the given data and expiration time.

    Args:
        data: Dictionary containing claims to encode. Cannot be None.
        expires_delta: Optional expiration timedelta. Defaults to 15 minutes.

    Returns:
        Encoded JWT token string.

    Raises:
        ValueError: If data is None.
    """
    if data is None:
        utils_logger.error("Attempted to create JWT token with None data")
        raise ValueError("Data cannot be None")

    try:
        to_encode = data.copy()

        if expires_delta is None:
            expires_delta = timedelta(minutes=15)

        expire = datetime.now(timezone.utc) + expires_delta
        to_encode["exp"] = expire
        to_encode["iat"] = datetime.now(timezone.utc)
        to_encode["jti"] = str(uuid.uuid4())

        encoded_jwt = jwt.encode(
            to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )

        utils_logger.info(
            f"JWT token created successfully with expiration: {expire.isoformat()}"
        )
        return encoded_jwt

    except Exception as e:
        utils_logger.error(f"Failed to create JWT token: {type(e).__name__} - {str(e)}")
        raise


def decode_jwt_token(token: str | None) -> dict[str, Any] | None:
    """Decode and validate a JWT token.

    Returns None for any invalid, expired, or tampered tokens.
    """
    if not token:
        return None

    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        utils_logger.info("JWT token decoded and validated successfully")
        return payload

    except jwt.ExpiredSignatureError:
        utils_logger.warning("JWT token decoding failed: token has expired")
        return None
    except jwt.InvalidTokenError as e:
        utils_logger.warning(
            f"JWT token decoding failed: invalid token - {type(e).__name__}"
        )
        return None
    except Exception as e:
        utils_logger.error(
            f"Unexpected error during JWT token decoding: {type(e).__name__} - {str(e)}"
        )
        return None


# ---------------------------------------------------------------------------
# OTP helpers
# ---------------------------------------------------------------------------


def generate_otp(length: int = 6) -> str:
    """Generate a cryptographically secure numeric OTP."""
    return "".join(secrets.choice("0123456789") for _ in range(length))


def hash_otp(otp: str) -> str:
    """Hash an OTP using HMAC-SHA256 for queryable secure storage."""
    return hmac.new(
        settings.OTP_SECRET_KEY.encode("utf-8"),
        otp.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_otp(otp: str, hashed_otp: str) -> bool:
    """Verify an OTP against its HMAC hash (constant-time comparison)."""
    return hmac.compare_digest(hash_otp(otp), hashed_otp)


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------


def convert_unix_timestamp_to_datetime(timestamp: int | None) -> datetime | None:
    """Convert a Unix timestamp to a timezone-aware datetime, or None."""
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


__all__ = [
    "hash_password",
    "verify_password",
    "create_jwt_token",
    "decode_jwt_token",
    "generate_otp",
    "hash_otp",
    "verify_otp",
    "convert_unix_timestamp_to_datetime",
]
