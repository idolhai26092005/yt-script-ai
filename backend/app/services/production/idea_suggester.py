from app.services.production.base import BaseGeminiService, logger
from app.services.production.prompts.suggestions import SYSTEM_PROMPT_GENERATE_SUGGESTIONS
from app.core.utils import parse_llm_json_response


def _log_excerpt(value: str, limit: int = 500) -> str:
    value = " ".join((value or "").split())
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "...[truncated]"


class IdeaSuggester(BaseGeminiService):
    """Dịch vụ sinh các gợi ý kịch bản từ ý tưởng/nội dung/URL đầu vào."""

    async def generate_suggestions(
        self,
        input_content: str,
        style: str,
        num_scenes: int,
        num_suggestions: int = 5,
        model_name: str = "gemini-3.1-flash-lite"
    ) -> list[dict]:
        """
        Sinh 5 gợi ý kịch bản tóm tắt khác nhau.
        Gợi ý số 0 có is_original = True.
        """
        prompt = SYSTEM_PROMPT_GENERATE_SUGGESTIONS.format(
            input_content=input_content,
            style=style,
            num_scenes=num_scenes,
            num_suggestions=num_suggestions,
            last_suggestion_idx=num_suggestions - 1
        )

        raw_output = await self._call_gemini_with_retry(
            prompt=prompt,
            model_name=model_name,
            generation_config={"response_mime_type": "application/json"}
        )

        try:
            suggestions_list = parse_llm_json_response(raw_output)
            if not isinstance(suggestions_list, list):
                raise ValueError("Output is not a JSON list")
            for sugg in suggestions_list:
                if "topic_type" not in sugg:
                    sugg["topic_type"] = "fictional_original"
                if "has_named_historical_figure" not in sugg:
                    sugg["has_named_historical_figure"] = False
                if "narrative_shape" not in sugg:
                    # Default narrative shape mapping based on topic type
                    tt = sugg["topic_type"]
                    if tt == "historical":
                        if sugg.get("has_named_historical_figure", False):
                            sugg["narrative_shape"] = "reflective"
                        else:
                            sugg["narrative_shape"] = "explanatory"
                    elif tt == "scientific":
                        sugg["narrative_shape"] = "explanatory"
                    else:
                        sugg["narrative_shape"] = "adventure"
            return suggestions_list
        except Exception as e:
            logger.error(f"Failed to parse suggestions JSON: {str(e)}. Raw excerpt: {_log_excerpt(raw_output)}")
            return [
                {
                    "index": i,
                    "title": f"Gợi ý kịch bản #{i+1}",
                    "synopsis": f"Tóm tắt hướng kịch bản thứ {i+1} dựa trên: {input_content[:50]}...",
                    "mood": "Cinematic",
                    "hook": "Cảnh quay bắt đầu đầy bất ngờ...",
                    "is_original": (i == 0),
                    "topic_type": "fictional_original",
                    "narrative_shape": "adventure",
                    "has_named_historical_figure": False
                } for i in range(num_suggestions)
            ]
