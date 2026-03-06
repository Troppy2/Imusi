"""
Artist-related Pydantic schemas.
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ArtistBase(BaseModel):
    name: str


class ArtistCreate(ArtistBase):
    pass


class ArtistResponse(ArtistBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
