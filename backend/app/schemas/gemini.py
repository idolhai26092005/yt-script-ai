from pydantic import BaseModel, Field

class GeminiTestRequest(BaseModel):
    prompt: str = Field("Hello Gemini, this is a test connection.", min_length=1, max_length=4000)
    model_name: str | None = Field(None, max_length=80, pattern=r"^[A-Za-z0-9._:-]+$")

class GeminiTestResponse(BaseModel):
    success: bool
    response: str
    error: str | None = None
