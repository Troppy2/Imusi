"""
Authentication business logic:
- local signup/login
- Google OAuth code exchange login
- token issuance, rotation, and revocation
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import BadRequestError, ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    ensure_google_oauth_configured,
    hash_password,
    hash_token_sha256,
    validate_password_complexity,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User


GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@dataclass
class AuthTokens:
    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_expires_in: int


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized:
        raise BadRequestError("Email is required", details={"field": "email"})
    return normalized


def _coerce_exp_to_datetime(exp_value: object) -> datetime:
    if isinstance(exp_value, (int, float)):
        return datetime.fromtimestamp(exp_value, tz=UTC)
    if isinstance(exp_value, datetime):
        return exp_value.astimezone(UTC)
    raise UnauthorizedError("Invalid token expiry claim")


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _issue_tokens(db: Session, user: User) -> AuthTokens:
    settings = get_settings()
    access_token = create_access_token(user_id=user.id, email=user.email)
    refresh_token = create_refresh_token(user_id=user.id)
    refresh_payload = decode_token(refresh_token, expected_type="refresh")
    refresh_expires_at = _coerce_exp_to_datetime(refresh_payload.get("exp"))

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token_sha256(refresh_token),
            expires_at=refresh_expires_at,
            revoked=False,
        )
    )

    return AuthTokens(
        access_token=access_token,
        refresh_token=refresh_token,
        access_expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_expires_in=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )


def _get_user_by_email(db: Session, email: str) -> User | None:
    stmt = select(User).where(User.email == _normalize_email(email))
    return db.execute(stmt).scalar_one_or_none()


def create_local_user(db: Session, *, email: str, password: str, name: str | None = None) -> User:
    normalized_email = _normalize_email(email)
    if _get_user_by_email(db, normalized_email):
        raise ConflictError("An account with this email already exists", details={"field": "email"})

    validate_password_complexity(password)
    user = User(
        email=normalized_email,
        password_hash=hash_password(password),
        name=name.strip() if isinstance(name, str) and name.strip() else None,
    )
    db.add(user)
    db.flush()
    return user


def authenticate_local_user(db: Session, *, email: str, password: str) -> User:
    user = _get_user_by_email(db, email)
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        raise UnauthorizedError("Invalid email or password", code="INVALID_CREDENTIALS")
    return user


def issue_tokens_for_user(db: Session, user: User) -> AuthTokens:
    tokens = _issue_tokens(db, user)
    db.commit()
    db.refresh(user)
    return tokens


def rotate_refresh_token(db: Session, *, refresh_token: str) -> AuthTokens:
    payload = decode_token(refresh_token, expected_type="refresh")
    user_id = int(payload.get("sub"))
    token_hash = hash_token_sha256(refresh_token)

    stmt = select(RefreshToken).where(
        RefreshToken.user_id == user_id,
        RefreshToken.token_hash == token_hash,
    )
    stored_token = db.execute(stmt).scalar_one_or_none()
    if not stored_token:
        raise UnauthorizedError("Refresh token not recognized")

    now = datetime.now(UTC)
    if stored_token.revoked or _as_utc(stored_token.expires_at) <= now:
        stored_token.revoked = True
        db.commit()
        raise UnauthorizedError("Refresh token is revoked or expired")

    user = db.get(User, user_id)
    if not user:
        raise UnauthorizedError("User for token no longer exists")

    stored_token.revoked = True
    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


def revoke_refresh_token(db: Session, *, refresh_token: str) -> None:
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except UnauthorizedError:
        return

    user_id = int(payload.get("sub"))
    token_hash = hash_token_sha256(refresh_token)
    stmt = select(RefreshToken).where(
        RefreshToken.user_id == user_id,
        RefreshToken.token_hash == token_hash,
    )
    stored_token = db.execute(stmt).scalar_one_or_none()
    if not stored_token:
        return
    stored_token.revoked = True
    db.commit()


def _exchange_google_code_for_userinfo(*, code: str, redirect_uri: str) -> dict:
    settings = get_settings()
    ensure_google_oauth_configured()

    token_response = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=10.0,
    )
    if token_response.status_code != 200:
        raise UnauthorizedError("Google authorization code exchange failed", code="GOOGLE_AUTH_FAILED")

    access_token = token_response.json().get("access_token")
    if not access_token:
        raise UnauthorizedError("Google access token not returned", code="GOOGLE_AUTH_FAILED")

    profile_response = httpx.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10.0,
    )
    if profile_response.status_code != 200:
        raise UnauthorizedError("Google user profile lookup failed", code="GOOGLE_AUTH_FAILED")
    return profile_response.json()


def authenticate_google_user(db: Session, *, code: str, redirect_uri: str) -> User:
    profile = _exchange_google_code_for_userinfo(code=code, redirect_uri=redirect_uri)
    google_id = profile.get("sub")
    email = profile.get("email")
    if not google_id or not email:
        raise UnauthorizedError("Google response missing required identity fields", code="GOOGLE_AUTH_FAILED")

    normalized_email = _normalize_email(email)
    name = profile.get("name")
    picture = profile.get("picture")

    by_google_stmt = select(User).where(User.google_id == google_id)
    user = db.execute(by_google_stmt).scalar_one_or_none()
    if not user:
        user = _get_user_by_email(db, normalized_email)

    if user:
        user.google_id = google_id
        user.email = normalized_email
        user.name = name or user.name
        user.avatar_url = picture or user.avatar_url
    else:
        user = User(
            email=normalized_email,
            google_id=google_id,
            name=name,
            avatar_url=picture,
            password_hash=None,
        )
        db.add(user)
        db.flush()

    return user
