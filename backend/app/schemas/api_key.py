import datetime
from pydantic import BaseModel, Field

class APIKeyCreate(BaseModel):
    owner: str = Field(..., min_length=1, max_length=255)
    quota_limit: int = Field(100, ge=1, le=1_000_000)
    expiry: datetime.datetime | None = None

class APIKeyResponse(BaseModel):
    id: int
    key_hash: str
    owner: str
    quota_limit: int
    quota_used: int
    expiry: datetime.datetime | None = None
    is_active: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}

class APIKeyGeneratedResponse(BaseModel):
    plain_key: str
    api_key: APIKeyResponse
