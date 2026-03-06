"""
Authentication request/response schemas.
"""
from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserResponse


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class GoogleAuthRequest(BaseModel):
    code: str = Field(min_length=1)
    redirect_uri: str = Field(min_length=1, max_length=2048)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=4096)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=4096)


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str | None = None
    refresh_expires_in: int | None = None


class AuthTokensResponse(AccessTokenResponse):
    refresh_token: str
    refresh_expires_in: int
    user: UserResponse
