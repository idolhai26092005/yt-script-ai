import json
import asyncio
import time
import re
import threading
import cachetools
import hashlib
import logging
from google import genai


from app.core.utils import clean_json_response

logger = logging.getLogger("uvicorn.error")

class ModelFallbackChain:
    FALLBACK_MODELS = [
        "gemini-3.1-pro",
        "gemini-2.5-pro",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-3-flash",
        "gemini-2.5-flash",
        "gemma-4-31b",
        "gemma-4-26b",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "llama-3.3-70b-versatile"
    ]

MODEL_CONFIG = {
    "gemini-3.1-flash-lite": {
        "rpm": 15, "rpd": 500, "supports_schema": True,
        "display_name": "Gemini 3.1 Flash Lite",
        "description": "Nhanh, ổn định, tiết kiệm quota",
        "group": "fast",
        "icon": "⚡",
        "badge": "Khuyên dùng",
        "popular": True,
    },
    "gemini-2.5-flash-lite": {
        "rpm": 10, "rpd": 20, "supports_schema": True,
        "display_name": "Gemini 2.5 Flash Lite",
        "description": "Cân bằng tốc độ và chất lượng",
        "group": "fast",
        "icon": "⚡",
        "badge": None,
        "popular": False,
    },
    "gemini-3.5-flash": {
        "rpm": 5, "rpd": 20, "supports_schema": True,
        "display_name": "Gemini 3.5 Flash",
        "description": "Chất lượng tốt hơn, chậm hơn một chút",
        "group": "quality",
        "icon": "✨",
        "badge": None,
        "popular": True,
    },
    "gemini-3-flash": {
        "rpm": 5, "rpd": 20, "supports_schema": True,
        "display_name": "Gemini 3-Flash",
        "description": "Phiên bản cân bằng tốt",
        "group": "quality",
        "icon": "✨",
        "badge": None,
        "popular": False,
    },
    "gemini-2.5-flash": {
        "rpm": 5, "rpd": 20, "supports_schema": True,
        "display_name": "Gemini 2.5 Flash",
        "description": "Ổn định, được thử nghiệm nhiều",
        "group": "quality",
        "icon": "✨",
        "badge": None,
        "popular": False,
    },
    "gemini-3.1-pro": {
        "rpm": 5, "rpd": 50, "supports_schema": True,
        "display_name": "Gemini 3.1 Pro",
        "description": "Tốt nhất cho nội dung phức tạp",
        "group": "quality",
        "icon": "💎",
        "badge": "Chất lượng cao",
        "popular": True,
    },
    "gemini-2.5-pro": {
        "rpm": 5, "rpd": 50, "supports_schema": True,
        "display_name": "Gemini 2.5 Pro",
        "description": "Phiên bản Pro ổn định",
        "group": "quality",
        "icon": "💎",
        "badge": "Chất lượng cao",
        "popular": False,
    },
    "gemma-4-31b": {
        "rpm": 15, "rpd": 1500, "supports_schema": False,
        "display_name": "Gemma 4 31B",
        "description": "Open-source, nhiều lượt gọi",
        "group": "fallback",
        "icon": "🧩",
        "badge": None,
        "popular": False,
    },
    "gemma-4-26b": {
        "rpm": 15, "rpd": 1500, "supports_schema": False,
        "display_name": "Gemma 4 26B",
        "description": "Nhẹ hơn, tốc độ nhanh",
        "group": "fallback",
        "icon": "🧩",
        "badge": None,
        "popular": False,
    },
    "gemini-2.0-flash": {
        "rpm": 15, "rpd": 500, "supports_schema": True,
        "display_name": "Gemini 2.0 Flash",
        "description": "Phiên bản Flash ổn định cũ",
        "group": "fast",
        "icon": "⚡",
        "badge": None,
        "popular": False,
    },
    "gemini-1.5-flash": {
        "rpm": 15, "rpd": 500, "supports_schema": True,
        "display_name": "Gemini 1.5 Flash",
        "description": "Phiên bản Flash cũ, tương thích tốt",
        "group": "fast",
        "icon": "⚡",
        "badge": None,
        "popular": False,
    },
    "gemini-1.5-pro": {
        "rpm": 5, "rpd": 50, "supports_schema": True,
        "display_name": "Gemini 1.5 Pro",
        "description": "Phiên bản Pro cũ",
        "group": "quality",
        "icon": "💎",
        "badge": None,
        "popular": False,
    },
    "llama-3.3-70b-versatile": {
        "rpm": 30, "rpd": 14400, "supports_schema": True,
        "display_name": "Llama 3.3 70B (Groq)",
        "description": "Dự phòng khi Gemini hết quota",
        "group": "fallback",
        "icon": "🦙",
        "badge": "Nhiều lượt",
        "popular": True,
    },
}

# Durable performance guard: fallback order must start from the user-requested
# model so one slow fallback does not poison later calls for an hour.
def get_fallback_chain_starting_from(model_name: str) -> list[str]:
    chain = ModelFallbackChain.FALLBACK_MODELS.copy()
    normalized_model_name = model_name.lower().strip()
    if normalized_model_name in chain:
        idx = chain.index(normalized_model_name)
        return chain[idx:] + chain[:idx]
    else:
        return [model_name] + chain

def is_rate_limit_error(e: Exception) -> bool:
    err_str = str(e).lower()
    return "429" in err_str or "resource_exhausted" in err_str or "resource has been exhausted" in err_str or "quota" in err_str or "exhausted" in err_str

def should_fallback_to_next_model(e: Exception) -> bool:
    err_str = str(e).lower()
    if is_rate_limit_error(e):
        return True
    if "404" in err_str or "not found" in err_str or "not supported" in err_str:
        return True
    if "400" in err_str and ("not supported" in err_str or "not available" in err_str or "schema" in err_str or "mode" in err_str):
        return True
    if "503" in err_str or "service unavailable" in err_str or "high demand" in err_str or "overloaded" in err_str:
        return True
    return False

def get_models_status(api_key_id: int, db) -> list[dict]:
    """Trả về danh sách model kèm trạng thái, lượt gọi còn lại."""
    from app.crud.model_usage import get_all_today_usage
    today_usage = {r.model_name: r for r in get_all_today_usage(db, api_key_id)}

    selectable_models = [
        "gemini-3.1-flash-lite", "gemini-2.5-flash-lite",
        "gemini-3.5-flash", "gemini-3-flash", "gemini-2.5-flash",
        "gemini-3.1-pro", "gemini-2.5-pro",
        "gemma-4-31b", "gemma-4-26b",
        "llama-3.3-70b-versatile",
    ]

    result = []
    for model_id in selectable_models:
        config = MODEL_CONFIG.get(model_id)
        if not config:
            continue

        usage = today_usage.get(model_id)
        used_today = usage.request_count if usage else 0
        rpd = config["rpd"]
        remaining = max(0, rpd - used_today)

        if remaining == 0:
            status = "exhausted"
        elif model_id in _model_backoffs:
            _, until = _model_backoffs[model_id]
            if time.time() < until:
                status = "cooldown"
            else:
                status = "active"
        else:
            status = "active"

        result.append({
            "id": model_id,
            "display_name": config.get("display_name", model_id),
            "description": config.get("description", ""),
            "group": config.get("group", "quality"),
            "icon": config.get("icon", "🤖"),
            "badge": config.get("badge"),
            "popular": config.get("popular", False),
            "rpd": rpd,
            "remaining_rpd": remaining,
            "used_today": used_today,
            "status": status,
        })
    return result



_genai_configure_lock = threading.Lock()
_current_active_models = cachetools.TTLCache(maxsize=1000, ttl=3600)
_user_semaphores = cachetools.TTLCache(maxsize=1000, ttl=3600)
_last_request_times = cachetools.TTLCache(maxsize=1000, ttl=3600)
_model_backoffs = cachetools.TTLCache(maxsize=100, ttl=3600)

class BaseGeminiService:
    def __init__(self, api_key: str, groq_api_key: str | None = None, db = None, api_key_id: int | None = None):
        if not api_key:
            raise ValueError("Gemini API Key is required")
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)
        from app.core.config import settings
        self.groq_api_key = groq_api_key or settings.GROQ_API_KEY
        self.db = db
        self.api_key_id = api_key_id



    async def generate_text(self, prompt: str, model_name: str = "gemini-2.5-flash") -> str:
        try:
            return await self._call_gemini_with_retry(prompt, model_name)
        except Exception as e:
            raise RuntimeError(f"Gemini API Error: {str(e)}")

    async def _call_gemini_with_retry(
        self, 
        prompt: str | list, 
        model_name: str, 
        generation_config: dict = None, 
        max_retries: int = 3
    ) -> str:
        from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception
        key_hash = hashlib.sha256(self.api_key.encode()).hexdigest()
        
        # Durable fallback-speed guard: use remembered fallbacks only after the
        # requested model has had a fresh chance in this call.
        requested_model = model_name.lower().strip()
        fallback_cache_key = (key_hash, requested_model)
        remembered_model = _current_active_models.get(fallback_cache_key)
        fallback_models = get_fallback_chain_starting_from(model_name)
        if remembered_model and remembered_model in fallback_models and remembered_model != fallback_models[0]:
            fallback_models = [
                fallback_models[0],
                remembered_model,
                *[m for m in fallback_models[1:] if m != remembered_model],
            ]
        logger.info(
            "Gemini request routing: requested=%s remembered=%s first=%s chain=%s",
            model_name,
            remembered_model,
            fallback_models[0] if fallback_models else None,
            fallback_models,
        )
        
        last_error = None
        for current_model in fallback_models:
            config = MODEL_CONFIG.get(current_model, {"rpm": 5, "supports_schema": True})
            rpm = config.get("rpm", 5)
            supports_schema = config.get("supports_schema", True)
            
            interval = 60.0 / rpm
            now = time.time()
            if current_model in _model_backoffs:
                backoff_time, until = _model_backoffs[current_model]
                if now < until:
                    interval *= backoff_time
                    
            interval += 0.5
            
            if key_hash not in _user_semaphores:
                _user_semaphores[key_hash] = asyncio.Semaphore(1)
            sem = _user_semaphores[key_hash]
            
            try:
                async with sem:
                    last_time = _last_request_times.get((key_hash, current_model), 0.0)
                    elapsed = time.time() - last_time
                    if elapsed < interval:
                        await asyncio.sleep(interval - elapsed)
                        
                    attempt_count = [0]
                    
                    async def do_call():
                        attempt_count[0] += 1
                        current_config = generation_config.copy() if generation_config else {}
                        
                        if isinstance(prompt, list):
                            current_prompt = prompt.copy()
                            if not supports_schema:
                                current_config.pop("response_mime_type", None)
                                current_config.pop("response_schema", None)
                                for i, item in enumerate(current_prompt):
                                    if isinstance(item, str):
                                        if "json" not in item.lower():
                                            current_prompt[i] = item + "\n\nRespond ONLY with valid JSON. Do not include markdown formatting or extra text outside the JSON."
                        else:
                            current_prompt = prompt
                            if not supports_schema:
                                current_config.pop("response_mime_type", None)
                                current_config.pop("response_schema", None)
                                if "json" not in current_prompt.lower():
                                    current_prompt = current_prompt + "\n\nRespond ONLY with valid JSON. Do not include markdown formatting or extra text outside the JSON."
                        
                        if "llama" in current_model.lower():
                            if not self.groq_api_key:
                                raise ValueError("Groq API Key is missing. Cấu hình Groq API Key để sử dụng Llama.")
                            from app.services.groq import GroqService
                            groq_service = GroqService(api_key=self.groq_api_key)
                            
                            final_prompt = current_prompt
                            if isinstance(current_prompt, list):
                                text_parts = []
                                for part in current_prompt:
                                    if isinstance(part, str):
                                        text_parts.append(part)
                                final_prompt = "\n".join(text_parts)
                                
                            res_text = await groq_service.generate_content_async(
                                prompt=final_prompt,
                                model_name=current_model,
                                generation_config=current_config
                            )
                            return res_text

                        api_model_name = current_model
                        if current_model == "gemma-4-31b":
                            api_model_name = "gemma-4-31b-it"
                        elif current_model == "gemma-4-26b":
                            api_model_name = "gemma-4-26b-a4b-it"
                        
                        response = await self.client.aio.models.generate_content(
                            model=api_model_name,
                            contents=current_prompt,
                            config=current_config
                        )
                        
                        if attempt_count[0] > 1:
                            _model_backoffs[current_model] = (1.5, time.time() + 60)
                            
                        res_text = response.text
                        if current_config.get("response_mime_type") == "application/json" or not supports_schema:
                            res_text = clean_json_response(res_text)
                            if not supports_schema:
                                try:
                                    json.loads(res_text)
                                except json.JSONDecodeError:
                                    match_brace = re.search(r'(\{.*\}|\[.*\])', res_text, re.DOTALL)
                                    if match_brace:
                                        try:
                                            json.loads(match_brace.group(1))
                                            res_text = match_brace.group(1)
                                        except json.JSONDecodeError:
                                            pass
                        return res_text

                    call_started_at = time.time()
                    res_text = None
                    async for attempt in AsyncRetrying(
                        stop=stop_after_attempt(max_retries),
                        wait=wait_exponential(multiplier=2, min=2, max=10),
                        retry=retry_if_exception(is_rate_limit_error),
                        reraise=True
                    ):
                        with attempt:
                            res_text = await do_call()
                    
                    _last_request_times[(key_hash, current_model)] = time.time()
                    _current_active_models[fallback_cache_key] = current_model
                    logger.info(
                        "Gemini request completed: requested=%s actual=%s attempts=%s latency_ms=%.1f",
                        model_name,
                        current_model,
                        attempt_count[0],
                        (time.time() - call_started_at) * 1000.0,
                    )
                    
                    if self.db and self.api_key_id:
                        try:
                            from app.crud.model_usage import increment_model_usage
                            increment_model_usage(self.db, self.api_key_id, current_model)
                        except Exception as mu_err:
                            logger.error(f"Failed to record model usage for {current_model}: {mu_err}")
                            
                    return res_text
                    
            except Exception as e:
                if should_fallback_to_next_model(e):
                    logger.warning(
                        "Gemini fallback: requested=%s actual=%s reason=%s next_available=True",
                        model_name,
                        current_model,
                        str(e),
                    )
                    last_error = e
                    continue
                else:
                    raise e
        
        if last_error:
            raise last_error
        raise RuntimeError("No model was able to service the request.")
