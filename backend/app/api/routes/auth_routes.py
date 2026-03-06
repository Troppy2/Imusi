"""
Authentication routes:
- signup/login
- Google OAuth
- refresh/logout
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.core.exceptions import BadRequestError
from app.schemas.auth import (
    AccessTokenResponse,
    AuthTokensResponse,
    GoogleAuthRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    SignupRequest,
)
from app.schemas.user import UserResponse, UserUpdateRequest
from app.services.auth_service import (
    AuthTokens,
    authenticate_google_user,
    authenticate_local_user,
    create_local_user,
    issue_tokens_for_user,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter()


def _tokens_response(tokens: AuthTokens, user: User) -> AuthTokensResponse:
    return AuthTokensResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type="bearer",
        expires_in=tokens.access_expires_in,
        refresh_expires_in=tokens.refresh_expires_in,
        user=UserResponse.model_validate(user),
    )


@router.post("/signup", response_model=AuthTokensResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    user = create_local_user(db, email=body.email, password=body.password, name=body.name)
    tokens = issue_tokens_for_user(db, user)
    return _tokens_response(tokens, user)


@router.post("/login", response_model=AuthTokensResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_local_user(db, email=body.email, password=body.password)
    tokens = issue_tokens_for_user(db, user)
    return _tokens_response(tokens, user)


@router.post("/google", response_model=AuthTokensResponse)
def google_oauth_login(body: GoogleAuthRequest, db: Session = Depends(get_db)):
    user = authenticate_google_user(db, code=body.code, redirect_uri=body.redirect_uri)
    tokens = issue_tokens_for_user(db, user)
    return _tokens_response(tokens, user)


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh_access_token(body: RefreshRequest, db: Session = Depends(get_db)):
    tokens = rotate_refresh_token(db, refresh_token=body.refresh_token)
    return AccessTokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type="bearer",
        expires_in=tokens.access_expires_in,
        refresh_expires_in=tokens.refresh_expires_in,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: LogoutRequest, db: Session = Depends(get_db)):
    revoke_refresh_token(db, refresh_token=body.refresh_token)
    return None


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
def update_me(
    body: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    next_name = body.name.strip()
    if not next_name:
        raise BadRequestError("name must be non-empty", code="VALIDATION_ERROR")

    current_user.name = next_name
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user
