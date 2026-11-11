import pytest
import json
from unittest.mock import AsyncMock, patch
from app.services.production import ProductionService

def make_phase0_response(include_bilingual: bool = True) -> str:
    character = {
        "character_name": "Hero",
        "description_en": "desc en",
        "key_identifiers_en": "key en",
    }
    if include_bilingual:
        character.update({"description_vi": "mô tả vi", "key_identifiers_vi": "key vi"})
    return json.dumps({
        "overview_analysis_vi": "phân tích tổng quan",
        "storyline_vi": "Mạch truyện",
        "stages_vi": "Giai đoạn 1",
        "progression_vi": "Cảnh 1-4",
        "camera_strategy_vi": "Camera anime",
        "continuity_locks_vi": "Khóa Hero",
        "form_locks_vi": "Hero không đổi",
        "age_stage_locks_vi": "Hero trưởng thành",
        "geometry_locks_vi": "Không gian env",
        "risk_logic_vi": "Logic hành động",
        "voice_sound_strategy_vi": "Giọng kể rõ",
        "characters": [character],
        "environment_master_prompt_en": "env en",
        "environment_master_prompt_vi": "env vi" if include_bilingual else "",
        "prompt_0": {
            "primary_subject_en": "Hero",
            "hard_visual_lock_en": "desc en",
            "setting_lock_en": "env en",
            "character_lock": [{"name": "Hero", "description_en": "desc en"}],
            "camera_lock_en": "Camera anime",
            "voice_sound_lock_en": "Clean voice",
            "action_story_logic_en": "Hero follows the story",
            "scene_function_rules_en": "Each scene advances the plot",
            "continuity_lock_en": "cont en",
            "internal_logic_en": "No contradictions",
            "negative_constraints_en": "No generic protagonist"
        }
    })

@pytest.mark.asyncio
async def test_producer_bilingual_parse():
    service = ProductionService(api_key="test", groq_api_key=None, db=None, api_key_id=None)
    
    suggestion = {"index": 0, "title": "Tập 1", "synopsis": "Tóm tắt"}
    script_data = {
        "topic_type": "fictional_original",
        "overview_analysis_vi": "",
        "characters": [],
        "environment_master_prompt_en": "",
        "environment_master_prompt_vi": "",
        "emotion_arc": [],
        "scenes": [],
        "continuity_board": {
            "continuity_prompt_en": "",
            "continuity_prompt_vi": ""
        },
        "global_negative_prompt_en": "",
        "reference_images": {}
    }
    
    # 1. Parse success with bilingual fields
    mock_meta_json = make_phase0_response(include_bilingual=True)
    
    with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = mock_meta_json
        
        async for _ in service._phase0_prompt0_and_blueprint(
            suggestion, "anime", 4, 8, False, "gemini-3.1-flash-lite", script_data, 1, "fictional_original"
        ):
            pass
            
        assert script_data["overview_analysis_vi"] == "phân tích tổng quan"
        assert len(script_data["characters"]) == 1
        assert script_data["characters"][0]["description_vi"] == "mô tả vi"
        assert script_data["characters"][0]["key_identifiers_vi"] == "key vi"
        assert script_data["environment_master_prompt_vi"] == "env vi"
        assert script_data["continuity_board"]["continuity_prompt_en"] == "cont en"

    # 2. Parsing fallback when bilingual fields are missing
    mock_meta_missing_json = make_phase0_response(include_bilingual=False)
    
    script_data_missing = script_data.copy()
    with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = mock_meta_missing_json
        
        async for _ in service._phase0_prompt0_and_blueprint(
            suggestion, "anime", 4, 8, False, "gemini-3.1-flash-lite", script_data_missing, 1, "fictional_original"
        ):
            pass
            
        assert len(script_data_missing["characters"]) == 1
        # Fallback value is not overwritten if the parsed json doesn't have it, but standard parsing returns whatever is present
        # In Pydantic validation later, missing values default to ""
