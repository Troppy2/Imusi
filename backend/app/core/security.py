"""
Authentication and token security helpers.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
import secrets
import re

import jwt
from jwt import InvalidTokenError
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.exceptions import BadRequestError, ServerConfigError, UnauthorizedError


pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")
PASSWORD_COMPLEXITY_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{8,}$")


def ensure_auth_secrets_configured() -> None:
    settings = get_settings()
    if not settings.JWT_SECRET or not settings.JWT_REFRESH_SECRET:
        raise ServerConfigError(
            "JWT secrets are not configured. Set JWT_SECRET and JWT_REFRESH_SECRET in environment variables."
        )
    if len(settings.JWT_SECRET) < 32 or len(settings.JWT_REFRESH_SECRET) < 32:
        raise ServerConfigError(
            "JWT secrets must each be at least 32 characters long.",
            details={"min_length": 32},
        )


def ensure_google_oauth_configured() -> None:
    settings = get_settings()
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise ServerConfigError(
            "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in environment variables."
        )


def validate_password_complexity(password: str) -> None:
    if not PASSWORD_COMPLEXITY_RE.match(password):
        raise BadRequestError(
            "Password must be at least 8 characters and include upper/lowercase letters, a number, and a symbol.",
            code="WEAK_PASSWORD",
        )


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(password, password_hash)
    except Exception:
        return False


def hash_token_sha256(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _build_claims(*, subject: str, token_type: str, expires_delta: timedelta, email: str | None = None) -> dict:
    settings = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    if email:
        claims["email"] = email
    if token_type == "refresh":
        claims["jti"] = secrets.token_urlsafe(24)
    return claims


def create_access_token(*, user_id: int, email: str) -> str:
    settings = get_settings()
    ensure_auth_secrets_configured()
    claims = _build_claims(
        subject=str(user_id),
        token_type="access",
        email=email,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return jwt.encode(claims, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(*, user_id: int) -> str:
    settings = get_settings()
    ensure_auth_secrets_configured()
    claims = _build_claims(
        subject=str(user_id),
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return jwt.encode(claims, settings.JWT_REFRESH_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, *, expected_type: str) -> dict:
    settings = get_settings()
    ensure_auth_secrets_configured()
    secret = settings.JWT_SECRET if expected_type == "access" else settings.JWT_REFRESH_SECRET
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )
    except InvalidTokenError as exc:
        raise UnauthorizedError("Invalid or expired token", details={"reason": str(exc)}) from exc

    token_type = payload.get("type")
    if token_type != expected_type:
        raise UnauthorizedError("Invalid token type", details={"expected": expected_type, "received": token_type})
    return payload
