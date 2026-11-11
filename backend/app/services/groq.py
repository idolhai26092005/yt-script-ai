import httpx

from app.core.config import settings


def _safe_error_excerpt(text: str, limit: int = 300) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "...[truncated]"


class GroqService:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"

    async def generate_content_async(
        self,
        prompt: str,
        model_name: str = "llama-3.3-70b-versatile",
        generation_config: dict = None
    ) -> str:
        if not self.api_key:
            raise ValueError("Groq API Key is missing.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Format prompt
        messages = [
            {"role": "user", "content": prompt}
        ]

        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.7,
        }

        # If json is requested
        if generation_config and generation_config.get("response_mime_type") == "application/json":
            payload["response_format"] = {"type": "json_object"}
            if "json" not in prompt.lower():
                payload["messages"][0]["content"] += "\n\nRespond ONLY with valid JSON."

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=60.0
                )
                if response.status_code == 429:
                    raise RuntimeError("Groq API rate limit (429) exceeded.")
                elif response.status_code != 200:
                    raise RuntimeError(
                        f"Groq API error: {response.status_code} - {_safe_error_excerpt(response.text)}"
                    )
                
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                return content
            except httpx.HTTPError as e:
                raise RuntimeError(f"Groq connection error: {str(e)}")
