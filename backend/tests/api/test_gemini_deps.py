import pytest
from fastapi import HTTPException
from unittest.mock import patch
from app.deps import get_gemini_api_key

@pytest.mark.asyncio
async def test_get_gemini_api_key_from_header():
    # Case 1: Key is provided in the header
    key = get_gemini_api_key(x_gemini_api_key="header_key")
    assert key == "header_key"

@pytest.mark.asyncio
async def test_get_gemini_api_key_from_settings():
    # Case 2: Key not in header, but available in settings
    with patch('app.core.config.settings') as settings_mock:
        settings_mock.GEMINI_API_KEY = "settings_key"
        key = get_gemini_api_key(x_gemini_api_key=None)
        assert key == "settings_key"

@pytest.mark.asyncio
async def test_get_gemini_api_key_not_found():
    # Case 3: Key not found or matches placeholder raises 401
    with patch('app.core.config.settings') as settings_mock:
        settings_mock.GEMINI_API_KEY = "your_gemini_api_key_here"
        with pytest.raises(HTTPException) as excinfo:
            get_gemini_api_key(x_gemini_api_key=None)
        assert excinfo.value.status_code == 401
        assert "Gemini API Key is missing" in excinfo.value.detail

    with patch('app.core.config.settings') as settings_mock:
        settings_mock.GEMINI_API_KEY = None
        with pytest.raises(HTTPException) as excinfo:
            get_gemini_api_key(x_gemini_api_key=None)
        assert excinfo.value.status_code == 401
        assert "Gemini API Key is missing" in excinfo.value.detail
