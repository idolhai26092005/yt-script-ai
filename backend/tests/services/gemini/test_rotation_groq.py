import pytest
import asyncio
import hashlib
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.gemini import GeminiService

@pytest.fixture(autouse=True)
def reset_active_model():
    from app.services import gemini
    gemini._current_active_models.clear()
    gemini._last_request_times.clear()
    gemini._model_backoffs.clear()

@pytest.mark.asyncio
async def test_gemini_rotation_and_groq_fallback():
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=Exception("429 Resource exhausted"))

    with patch("google.genai.Client", return_value=mock_client):
        with patch("app.services.groq.GroqService.generate_content_async", new_callable=AsyncMock) as mock_groq:
            mock_groq.return_value = '{"status": "ok"}'
            
            service = GeminiService(api_key="dummy_gemini_key", groq_api_key="dummy_groq_key")
            res = await service._call_gemini_with_retry(
                prompt="test prompt",
                model_name="gemini-3.1-flash-lite",
                generation_config={"response_mime_type": "application/json"},
                max_retries=1
            )
            
            mock_groq.assert_called_once()
            assert res == '{"status": "ok"}'

@pytest.mark.asyncio
async def test_gemini_rotation_to_working_model():
    mock_response = MagicMock()
    mock_response.text = '{"success": true}'

    async def side_effect(*args, **kwargs):
        model_name = kwargs.get("model", "")
        if "3.1" in model_name:
            raise Exception("429 Rate limit")
        return mock_response

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=side_effect)

    with patch("google.genai.Client", return_value=mock_client):
        service = GeminiService(api_key="dummy_gemini_key")
        res = await service._call_gemini_with_retry(
            prompt="test prompt",
            model_name="gemini-3.1-flash-lite",
            generation_config={"response_mime_type": "application/json"},
            max_retries=1
        )
        assert res == '{"success": true}'

@pytest.mark.asyncio
async def test_direct_llama_selection():
    mock_client = MagicMock()
    with patch("google.genai.Client", return_value=mock_client):
        with patch("app.services.groq.GroqService.generate_content_async", new_callable=AsyncMock) as mock_groq:
            mock_groq.return_value = '{"status": "llama_ok"}'
            
            service = GeminiService(api_key="dummy_gemini_key", groq_api_key="dummy_groq_key")
            res = await service._call_gemini_with_retry(
                prompt="test prompt",
                model_name="llama-3.3-70b-versatile",
                generation_config={"response_mime_type": "application/json"},
                max_retries=1
            )
            
            mock_groq.assert_called_once()
            assert res == '{"status": "llama_ok"}'

@pytest.mark.asyncio
async def test_gemini_503_fallback_to_working_model():
    mock_response = MagicMock()
    mock_response.text = '{"success": true}'

    async def side_effect(*args, **kwargs):
        model_name = kwargs.get("model", "")
        if "3.1" in model_name:
            raise Exception("503 Service Unavailable: This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.")
        return mock_response

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=side_effect)

    with patch("google.genai.Client", return_value=mock_client):
        service = GeminiService(api_key="dummy_gemini_key")
        res = await service._call_gemini_with_retry(
            prompt="test prompt",
            model_name="gemini-3.1-flash-lite",
            generation_config={"response_mime_type": "application/json"},
            max_retries=1
        )
        assert res == '{"success": true}'


@pytest.mark.asyncio
async def test_requested_model_runs_first_even_when_fallback_cache_remembers_slower_model():
    # Durable fallback-speed regression: a remembered slower fallback must not
    # become the first model for later requests that explicitly select a fast model.
    from app.services import gemini

    mock_response = MagicMock()
    mock_response.text = '{"fast": true}'
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    key_hash = hashlib.sha256("dummy_gemini_key".encode()).hexdigest()
    gemini._current_active_models[(key_hash, "gemini-3.1-flash-lite")] = "gemini-2.5-flash"

    with patch("google.genai.Client", return_value=mock_client):
        service = GeminiService(api_key="dummy_gemini_key")
        res = await service._call_gemini_with_retry(
            prompt="test prompt",
            model_name="gemini-3.1-flash-lite",
            generation_config={"response_mime_type": "application/json"},
            max_retries=1,
        )

    assert res == '{"fast": true}'
    assert mock_client.aio.models.generate_content.call_args_list[0].kwargs["model"] == "gemini-3.1-flash-lite"
