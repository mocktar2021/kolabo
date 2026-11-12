"""Shared auth dependencies to identify the current user from a bearer token."""
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


def get_optional_user_id(authorization: str | None = Header(default=None)) -> str | None:
    """Who is asking, if anyone. For public endpoints that answer differently
    to a signed-in reader.

    THIS NEVER RAISES, AND THAT IS THE ENTIRE DIFFERENCE from the dependency
    above. The endpoints that need it are public by design:
    /discovery/search, /discovery/featured and the creator storefront are
    reachable with no token because a brand has to be able to see whether
    anybody is on the platform before it signs up. Those pages must keep
    rendering for a visitor. What a caller's identity buys is a better
    answer, never the right to an answer at all.

    A MALFORMED OR EXPIRED TOKEN THEREFORE READS AS ANONYMOUS rather than as
    an error, which is worth being deliberate about because it is the
    surprising half. The alternative is a landing page that 401s at somebody
    whose session quietly expired in another tab, which is a blank screen in
    exchange for nothing: there is no protected data behind these routes to
    defend. Every endpoint that does hold something still uses
    get_current_user_id, and this must never be substituted for it as a
    convenience. A route that reads `user_id or ...` and carries on is a
    route where an invalid token became an anonymous success.

    So: a present, valid token identifies the caller. Everything else is a
    visitor.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token)
    except JWTError:
        return None
    return payload.get("sub") or None
