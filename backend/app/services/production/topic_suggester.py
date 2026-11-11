from app.services.production.base import BaseGeminiService
from app.services.production.prompts.suggestions import SYSTEM_PROMPT_TOPIC_SUGGESTIONS

class TopicSuggester(BaseGeminiService):
    """Dịch vụ sinh ý tưởng cốt lõi từ chủ đề nóng."""

    async def suggest_from_topic(
        self,
        topic_name: str,
        topic_description: str,
        style: str,
        model_name: str = "gemini-3.1-flash-lite"
    ) -> str:
        """Sinh ra cốt truyện gợi ý sơ khởi từ chủ đề nóng."""
        prompt = SYSTEM_PROMPT_TOPIC_SUGGESTIONS.format(
            topic_name=topic_name,
            topic_description=topic_description,
            style=style
        )
        return await self._call_gemini_with_retry(prompt, model_name=model_name)
