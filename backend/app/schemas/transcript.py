from pydantic import BaseModel, Field

class TranscriptRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)

class TranscriptResponse(BaseModel):
    success: bool
    video_id: str | None = None
    transcript: str | None = None
    segments: list[dict] | None = None
    error: str | None = None
