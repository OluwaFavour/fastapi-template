from typing import Any, cast

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.config import request_logger
from app.core.exceptions.types import (
    AppException,
    AuthenticationException,
    BadRequestException,
    ConflictException,
    DatabaseException,
    ForbiddenException,
    NotFoundException,
    NotImplementedException,
    OAuthException,
    OTPExpiredException,
    OTPInvalidException,
    PaymentRequiredException,
    RateLimitExceededException,
    TooManyAttemptsException,
)


async def general_exception_handler(request: Request, exc: Exception):
    """Handles general/unhandled exceptions."""
    app_exc = cast(AppException, exc)
    request_logger.error(f"GeneralException: {exc}")
    return JSONResponse(
        status_code=app_exc.status_code,
        content={"detail": f"An unexpected error occurred.\n{str(exc)}"},
    )


async def database_exception_handler(request: Request, exc: Exception):
    """Handles database exceptions."""
    db_exc = cast(DatabaseException, exc)
    request_logger.error(f"DatabaseException: {exc}")
    return JSONResponse(
        status_code=db_exc.status_code,
        content={"detail": f"A database error occurred.\n{str(exc)}"},
    )


async def authentication_exception_handler(request: Request, exc: Exception):
    """Handles authentication exceptions."""
    auth_exc = cast(AuthenticationException, exc)
    request_logger.warning(f"AuthenticationException: {exc}")
    return JSONResponse(
        status_code=auth_exc.status_code,
        content={"detail": str(exc)},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def oauth_exception_handler(request: Request, exc: Exception):
    """Handles OAuth exceptions."""
    oauth_exc = cast(OAuthException, exc)
    request_logger.warning(f"OAuthException: {exc}")
    return JSONResponse(
        status_code=oauth_exc.status_code,
        content={"detail": str(exc)},
    )


async def otp_expired_exception_handler(request: Request, exc: Exception):
    """Handles OTP expired exceptions."""
    otp_exc = cast(OTPExpiredException, exc)
    request_logger.warning(f"OTPExpiredException: {exc}")
    return JSONResponse(
        status_code=otp_exc.status_code,
        content={"detail": str(exc)},
    )


async def otp_invalid_exception_handler(request: Request, exc: Exception):
    """Handles OTP invalid exceptions."""
    otp_exc = cast(OTPInvalidException, exc)
    request_logger.warning(f"OTPInvalidException: {exc}")
    return JSONResponse(
        status_code=otp_exc.status_code,
        content={"detail": str(exc)},
    )


async def too_many_attempts_exception_handler(request: Request, exc: Exception):
    """Handles too many attempts exceptions."""
    tma_exc = cast(TooManyAttemptsException, exc)
    request_logger.warning(f"TooManyAttemptsException: {exc}")
    return JSONResponse(
        status_code=tma_exc.status_code,
        content={"detail": str(exc)},
    )


async def rate_limit_exception_handler(request: Request, exc: Exception):
    """Handles rate limit exceeded exceptions."""
    rate_exc = cast(RateLimitExceededException, exc)
    request_logger.warning(f"RateLimitExceededException: {exc}")
    headers = {}
    if rate_exc.retry_after:
        headers["Retry-After"] = str(rate_exc.retry_after)
    return JSONResponse(
        status_code=rate_exc.status_code,
        content={"detail": str(exc)},
        headers=headers,
    )


async def not_found_exception_handler(request: Request, exc: Exception):
    """Handles not found exceptions."""
    nf_exc = cast(NotFoundException, exc)
    request_logger.warning(f"NotFoundException: {exc}")
    return JSONResponse(
        status_code=nf_exc.status_code,
        content={"detail": str(exc)},
    )


async def conflict_exception_handler(request: Request, exc: Exception):
    """Handles conflict exceptions."""
    conf_exc = cast(ConflictException, exc)
    request_logger.warning(f"ConflictException: {exc}")
    return JSONResponse(
        status_code=conf_exc.status_code,
        content={"detail": str(exc)},
    )


async def bad_request_exception_handler(request: Request, exc: Exception):
    """Handles bad request exceptions."""
    br_exc = cast(BadRequestException, exc)
    request_logger.warning(f"BadRequestException: {exc}")
    return JSONResponse(
        status_code=br_exc.status_code,
        content={"detail": str(exc)},
    )


async def forbidden_exception_handler(request: Request, exc: Exception):
    """Handles forbidden exceptions."""
    forb_exc = cast(ForbiddenException, exc)
    request_logger.warning(f"ForbiddenException: {exc}")
    return JSONResponse(
        status_code=forb_exc.status_code,
        content={"detail": str(exc)},
    )


async def payment_required_exception_handler(request: Request, exc: Exception):
    """Handles payment required exceptions."""
    pay_exc = cast(PaymentRequiredException, exc)
    request_logger.warning(f"PaymentRequiredException: {exc}")
    return JSONResponse(
        status_code=pay_exc.status_code,
        content={"detail": str(exc)},
    )


async def not_implemented_exception_handler(request: Request, exc: Exception):
    """Handles not implemented exceptions."""
    not_impl_exc = cast(NotImplementedException, exc)
    request_logger.info(f"NotImplementedException: {exc}")
    return JSONResponse(
        status_code=not_impl_exc.status_code,
        content={"detail": str(exc)},
    )


async def value_error_exception_handler(request: Request, exc: Exception):
    """Handles value errors."""
    value_exc = cast(ValueError, exc)
    request_logger.warning(f"ValueError: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(value_exc)},
    )


exception_schema: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {
        "description": "Bad Request",
        "content": {
            "application/json": {
                "example": {"detail": "Bad request error message"},
            }
        },
    },
    status.HTTP_404_NOT_FOUND: {
        "description": "Not Found",
        "content": {
            "application/json": {
                "example": {"detail": "Resource not found."},
            }
        },
    },
    status.HTTP_409_CONFLICT: {
        "description": "Conflict",
        "content": {
            "application/json": {
                "example": {"detail": "Resource conflict."},
            }
        },
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "example": {"detail": "Some internal server error message"},
            }
        },
    },
    status.HTTP_401_UNAUTHORIZED: {
        "description": "Authentication Error",
        "content": {
            "application/json": {
                "example": {"detail": "Authentication failed."},
            }
        },
    },
    status.HTTP_429_TOO_MANY_REQUESTS: {
        "description": "Rate Limit Exceeded",
        "content": {
            "application/json": {
                "example": {"detail": "Rate limit exceeded. Please try again later."},
            }
        },
    },
    status.HTTP_501_NOT_IMPLEMENTED: {
        "description": "Not Implemented",
        "content": {
            "application/json": {
                "example": {"detail": "This feature is not yet implemented."},
            }
        },
    },
}


__all__ = [
    "general_exception_handler",
    "database_exception_handler",
    "authentication_exception_handler",
    "oauth_exception_handler",
    "otp_expired_exception_handler",
    "otp_invalid_exception_handler",
    "too_many_attempts_exception_handler",
    "rate_limit_exception_handler",
    "not_found_exception_handler",
    "conflict_exception_handler",
    "bad_request_exception_handler",
    "forbidden_exception_handler",
    "payment_required_exception_handler",
    "not_implemented_exception_handler",
    "value_error_exception_handler",
    "exception_schema",
]
