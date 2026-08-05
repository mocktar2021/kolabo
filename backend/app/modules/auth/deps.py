"""Shared auth dependency to identify the current user from a bearer token."""
from fastapi import Header, status
from jose import JWTError

from app.core.errors import AppError
from app.core.security import decode_token


def get_current_user_id(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError(
            status.HTTP_401_UNAUTHORIZED,
            code="auth_token_missing",
            detail="Missing bearer token",
        )
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token)
    except JWTError:
        raise AppError(
            status.HTTP_401_UNAUTHORIZED,
            code="auth_token_invalid",
            detail="Invalid token",
        )
    sub = payload.get("sub")
    if not sub:
        raise AppError(
            status.HTTP_401_UNAUTHORIZED,
            code="auth_token_invalid",
            detail="Invalid token",
        )
    return sub
