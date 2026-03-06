"""
User schemas.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str | None = None
    avatar_url: str | None = None
    google_id: str | None = None
    created_at: datetime
    updated_at: datetime


class UserUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
