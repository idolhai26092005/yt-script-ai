import json
import pytest
from unittest.mock import AsyncMock, patch
from app.services.production import ProductionService

def make_phase0_response() -> str:
    return json.dumps({
        "overview_analysis_vi": "test analysis",
        "storyline_vi": "Storyline",
        "stages_vi": "Stages",
        "progression_vi": "Progression",
        "camera_strategy_vi": "Camera",
        "continuity_locks_vi": "Locks",
        "form_locks_vi": "Form locks",
        "age_stage_locks_vi": "Adult hero",
        "geometry_locks_vi": "Green fields",
        "risk_logic_vi": "Risk logic",
        "voice_sound_strategy_vi": "Voice strategy",
        "characters": [{"character_name": "Hero", "description_en": "A brave hero", "key_identifiers_en": "hero"}],
        "environment_master_prompt_en": "env en",
        "environment_master_prompt_vi": "env vi",
        "prompt_0": {
            "primary_subject_en": "Hero",
            "hard_visual_lock_en": "A brave hero",
            "setting_lock_en": "env en",
            "character_lock": [{"name": "Hero", "description_en": "A brave hero"}],
            "camera_lock_en": "Camera",
            "voice_sound_lock_en": "Voice",
            "action_story_logic_en": "Hero continues the episode",
            "scene_function_rules_en": "Each scene advances the plot",
            "continuity_lock_en": "Keep Hero stable",
            "internal_logic_en": "No contradictions",
            "negative_constraints_en": "No generic protagonist"
        }
    })

@pytest.mark.asyncio
async def test_producer_context_injection():
    service = ProductionService(api_key="test", groq_api_key=None, db=None, api_key_id=None)
    
    suggestion = {"index": 0, "title": "Tập 2", "synopsis": "Diễn tiến tập 2"}
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
    
    mock_meta_json = make_phase0_response()
    
    # Case 1: context_from_previous is None
    with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = mock_meta_json
        
        events = []
        async for event in service._phase0_prompt0_and_blueprint(
            suggestion, "anime", 4, 8, False, "gemini-3.1-flash-lite", script_data, 1, "fictional_original",
            context_from_previous=None
        ):
            events.append(event)
            
        mock_call.assert_called_once()
        prompt_arg = mock_call.call_args[1]["prompt"]
        assert "ROLLING CONTEXT" not in prompt_arg
        assert "VISUAL LOCKS" not in prompt_arg
        
    # Case 2: context_from_previous is provided
    context = {
        "master_summary": "Tóm tắt tổng hợp các tập trước.",
        "recent_episodes": [
            {
                "episode_number": 1,
                "title": "Tập 1",
                "summary": {
                    "plot_summary": "Cốt truyện tập 1",
                    "character_states": "Nhân vật vui vẻ",
                    "cliffhanger": "Một vụ nổ xảy ra"
                }
            }
        ],
        "visual_locks": {
            "characters": [{"character_name": "Hero", "description_en": "A brave hero"}],
            "environment_master_prompt_en": "Green fields",
            "environment_master_prompt_vi": "Cánh đồng xanh"
        }
    }
    
    with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = mock_meta_json
        
        events = []
        async for event in service._phase0_prompt0_and_blueprint(
            suggestion, "anime", 4, 8, False, "gemini-3.1-flash-lite", script_data, 1, "fictional_original",
            context_from_previous=context
        ):
            events.append(event)
            
        mock_call.assert_called_once()
        prompt_arg = mock_call.call_args[1]["prompt"]
        assert "SERIES CONTEXT" in prompt_arg
        assert "LOCKED VISUAL IDENTITY" in prompt_arg
        assert "Tóm tắt tổng hợp các tập trước." in prompt_arg
        assert "Cốt truyện tập 1" in prompt_arg
        assert "Nhân vật vui vẻ" in prompt_arg
        assert "Một vụ nổ xảy ra" in prompt_arg
        assert "Green fields" in prompt_arg

@pytest.mark.asyncio
async def test_producer_series_bridge_injection():
    import json
    service = ProductionService(api_key="test", groq_api_key=None, db=None, api_key_id=None)
    
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
        "reference_images": {},
        "series_bridge_vi": None
    }
    
    mock_global_json = '{"global_negative_prompt_en": "test neg", "reference_images": {"character_ref_prompt_en": "char", "background_ref_prompt_en": "bg", "thumbnail_ref_prompt_en": "thumb"}}'
    
    # Case 1: no context
    with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = mock_global_json
        
        events = []
        suggestion = {"title": "Title"}
        async for event in service._phase3_packaging(
            suggestion, "anime", "gemini-3.1-flash-lite", script_data, 1, "fictional_original", "9:16",
            context_from_previous=None
        ):
            events.append(event)
            
        assert script_data["series_bridge_vi"] is None

    # Case 2: context provided with cliffhanger
    context = {
        "recent_episodes": [
            {
                "episode_number": 2,
                "summary": {
                    "character_states": "Nhân vật vui vẻ",
                    "cliffhanger": "Vụ nổ xảy ra"
                }
            }
        ]
    }
    with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = mock_global_json
        
        events = []
        suggestion = {"title": "Title"}
        async for event in service._phase3_packaging(
            suggestion, "anime", "gemini-3.1-flash-lite", script_data, 1, "fictional_original", "9:16",
            context_from_previous=context
        ):
            events.append(event)
            
        assert script_data["series_bridge_vi"] is not None
        assert "Tập 2" in script_data["series_bridge_vi"]
        assert "Nhân vật vui vẻ" in script_data["series_bridge_vi"]
        assert "Vụ nổ xảy ra" in script_data["series_bridge_vi"]

    # Case 3: context provided but missing cliffhanger
    context_missing = {
        "recent_episodes": [
            {
                "episode_number": 2,
                "summary": {
                    "character_states": "Nhân vật vui vẻ"
                }
            }
        ]
    }
    script_data["series_bridge_vi"] = None
    with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = mock_global_json
        
        events = []
        suggestion = {"title": "Title"}
        async for event in service._phase3_packaging(
            suggestion, "anime", "gemini-3.1-flash-lite", script_data, 1, "fictional_original", "9:16",
            context_from_previous=context_missing
        ):
            events.append(event)
            
        assert script_data["series_bridge_vi"] is None
