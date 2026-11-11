import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.production import ProductionService
from app.models.project import Project

@pytest.mark.asyncio
async def test_producer_post_suggestions():
    # Setup service with mock DB
    mock_db = MagicMock()
    mock_project = Project(id=1, title="Test", status="generating")
    mock_db.query.return_value.filter.return_value.first.return_value = mock_project
    
    service = ProductionService(api_key="test", groq_api_key=None, db=mock_db, api_key_id=None)
    service.enable_post_suggestions_test = True
    
    suggestion = {"index": 0, "title": "Tập 1", "synopsis": "Tóm tắt"}
    
    async def mock_phase0(*args, **kwargs):
        script_data = args[6]
        script_data.update({
            "topic_type": "fictional_original",
            "overview_analysis_vi": "Phân tích",
            "storyline_vi": "Hero tiếp tục hành trình.",
            "stages_vi": "Giai đoạn 1.",
            "progression_vi": "Cảnh 1-4.",
            "camera_strategy_vi": "Anime camera.",
            "continuity_locks_vi": "Khóa Hero.",
            "form_locks_vi": "Hero giữ ngoại hình.",
            "age_stage_locks_vi": "Hero trưởng thành.",
            "geometry_locks_vi": "Rome ổn định.",
            "risk_logic_vi": "Logic hành động.",
            "voice_sound_strategy_vi": "Giọng kể rõ.",
            "characters": [{"character_name": "Hero", "description_en": "Desc", "key_identifiers_en": "hero"}],
            "environment_master_prompt_en": "Rome",
            "continuity_prompt_en": "Keep Hero stable.",
            "global_negative_prompt_en": "No generic protagonist",
            "continuity_board": {"continuity_prompt_en": "Keep Hero stable.", "continuity_prompt_vi": ""},
            # Phase 0 gate guard: mocked blueprint must include the current
            # central story contract so this test reaches post-suggestion logic.
            "story_contract": {
                "main_subject_en": "Hero",
                "protagonist_en": "Hero",
                "central_opponent_or_force_en": "Rome trial",
                "core_goal_en": "Hero continues the journey through Rome.",
                "must_remain_visible_terms": ["Hero", "Rome"],
                "forbidden_takeover_rule": "No side thread replaces Hero's Rome journey.",
            },
            "prompt_0": {
                "primary_subject_en": "Hero",
                "hard_visual_lock_en": "Desc",
                "setting_lock_en": "Rome",
                "character_lock": [{"name": "Hero", "description_en": "Desc"}],
                "camera_lock_en": "Anime camera",
                "voice_sound_lock_en": "Clear narration",
                "action_story_logic_en": "Hero advances",
                "scene_function_rules_en": "Every scene advances plot",
                "continuity_lock_en": "Keep Hero stable.",
                "internal_logic_en": "No contradictions",
                "negative_constraints_en": "No generic protagonist"
            }
        })
        if False:
            yield None

    async def mock_phase1(*args, **kwargs):
        script_data = args[4]
        script_data["emotion_arc"] = [
            {
                "scene_number": i,
                "emotion_label": label,
                "beat_summary": f"Hero beat {i}",
                "physical_state_end": "Standing",
                "camera_complexity": "low",
                "scene_lead_character": "Hero",
            }
            for i, label in enumerate(["sửng sốt", "lo âu", "bi tráng", "bình yên"], start=1)
        ]
        if False:
            yield None

    async def mock_phase2(*args, **kwargs):
        script_data = args[4]
        script_data["scenes"] = [
            {
                "scene_number": i,
                "title": f"Scene {i} [00:00 - 00:08]",
                "action_detail_vi": f"Hero action {i}",
                "emotion_gesture_vi": "Hero focused",
                "camera_movement_vi": "Slow push",
                "transition_to_next_vi": "Cut",
                "veo3_prompt_en": f"Reference the approved Hero: Hero in Rome scene {i}, anime style, voice: \"Hero moves forward.\"",
                "voice_over_en": "Hero moves forward.",
                "negative_prompt_en": "low quality",
                "scene_specific_negative_en": "watermark",
            }
            for i in range(1, 5)
        ]
        if False:
            yield None

    async def mock_phase3(*args, **kwargs):
        script_data = args[3]
        script_data["global_negative_prompt_en"] = "low quality"
        script_data["reference_images"] = {
            "character_ref_prompt_en": "Hero ref",
            "background_ref_prompt_en": "Rome ref",
            "thumbnail_ref_prompt_en": "Thumb ref",
        }
        if False:
            yield None

    service._phase0_prompt0_and_blueprint = mock_phase0
    service._phase1_generate_emotion_arc = mock_phase1
    service._phase2_batch_generate_scenes = mock_phase2
    service._phase3_packaging = mock_phase3

    
    # Mock call_gemini for Phase 8 suggestions
    mock_post_json = json.dumps({
        "suggestions": [
            {
                "index": 0,
                "title": "Gợi ý tiếp 1",
                "synopsis": "Tóm tắt tiếp 1",
                "mood": "kịch tính",
                "topic_type": "fictional_original"
            }
        ]
    })
    
    with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call, \
         patch.object(service, "_save_script") as mock_save:
        mock_call.return_value = mock_post_json
        
        events = []
        async for event in service.generate_full_script_stream(
            suggestion=suggestion,
            style="anime",
            num_scenes=4,
            project_id=1,
            db=mock_db,
            aspect_ratio="9:16"
        ):
            events.append(event)
            
        # Check that gemini was called for post suggestions
        # We can find it in one of the call arguments
        suggestions_call_found = False
        for call in mock_call.call_args_list:
            if "POST_GENERATION_SUGGESTION_PROMPT" in str(call):
                suggestions_call_found = True
            # Or inspect the prompt string
            prompt = call[1].get("prompt", "")
            if "Dựa trên kịch bản video đã hoàn thành:" in prompt:
                suggestions_call_found = True
                
        assert suggestions_call_found, "Post suggestions prompt was not called"
        
        # Check that save_script was called with post_suggestions
        from unittest.mock import ANY
        mock_save.assert_called_with(
            1, 0, ANY, "script_generated", topic_type="fictional_original"
        )
        saved_data = mock_save.call_args[0][2]
        assert "post_suggestions" in saved_data
        assert len(saved_data["post_suggestions"]) == 1
        assert saved_data["post_suggestions"][0]["title"] == "Gợi ý tiếp 1"
