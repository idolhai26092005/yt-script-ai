import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.production import ProductionService
from app.models.project import Project

@pytest.mark.asyncio
async def test_producer_longform_flow():
    # Setup mock project and DB
    mock_db = MagicMock()
    mock_project = Project(id=1, title="Test Longform Flow", status="generating")
    mock_db.query.return_value.filter.return_value.first.return_value = mock_project
    
    service = ProductionService(api_key="test_longform_key", groq_api_key=None, db=mock_db, api_key_id=None)
    service.enable_post_suggestions_test = True
    
    suggestion = {"index": 0, "title": "Epic Battle", "synopsis": "Long story overview", "topic_type": "fictional_original"}
    
    # Mock phases and compressor calls
    mock_meta_json = json.dumps({
        "overview_analysis_vi": "Phân tích dài",
        "storyline_vi": "Hero bước vào trận chiến dài.",
        "stages_vi": "Giai đoạn 1-3.",
        "progression_vi": "Cảnh 1-30 leo thang.",
        "camera_strategy_vi": "Anime camera.",
        "continuity_locks_vi": "Khóa Hero.",
        "form_locks_vi": "Hero giữ ngoại hình.",
        "age_stage_locks_vi": "Hero trưởng thành.",
        "geometry_locks_vi": "Rome ổn định.",
        "risk_logic_vi": "Hành động leo thang hợp lý.",
        "voice_sound_strategy_vi": "Giọng kể rõ.",
        "characters": [{"character_name": "Hero", "description_en": "Desc", "key_identifiers_en": "hero"}],
        "environment_master_prompt_en": "Rome",
        "environment_master_prompt_vi": "La Mã",
        "prompt_0": {
            "primary_subject_en": "Hero",
            "hard_visual_lock_en": "Desc",
            "setting_lock_en": "Rome",
            "character_lock": [{"name": "Hero", "description_en": "Desc"}],
            "camera_lock_en": "Anime camera",
            "voice_sound_lock_en": "Clear narration",
            "action_story_logic_en": "Hero advances through a long battle",
            "scene_function_rules_en": "Every scene advances the battle",
            "continuity_lock_en": "Keep Hero and Rome stable",
            "internal_logic_en": "No contradictions",
            "negative_constraints_en": "No generic protagonist"
        }
    })
    
    mock_arc_json = json.dumps({
        "emotion_arc": [
            {
                "scene_number": i,
                "emotion_label": "bi tráng" if i % 2 == 0 else f"hành động {i}",
                "beat_summary": f"Tóm tắt {i}",
                "physical_state_end": "Ok",
                "camera_complexity": "medium",
                "scene_lead_character": "Hero"
            }
            for i in range(1, 31)  # 30 scenes = 2 chunks of size 15
        ]
    })
    
    mock_batch_scenes_chunk1 = json.dumps([
        {
            "scene_number": i,
            "title": f"Scene {i}",
            "action_detail_vi": f"Hành động {i}",
            "emotion_gesture_vi": "ok",
            "camera_movement_vi": "ok",
            "transition_to_next_vi": "ok",
            "veo3_prompt_en": f"Veo prompt {i}",
            "veo3_prompt_vi": f"Veo vi {i}"
        }
        for i in range(1, 16)
    ])
    
    mock_batch_scenes_chunk2 = json.dumps([
        {
            "scene_number": i,
            "title": f"Scene {i}",
            "action_detail_vi": f"Hành động {i}",
            "emotion_gesture_vi": "ok",
            "camera_movement_vi": "ok",
            "transition_to_next_vi": "ok",
            "veo3_prompt_en": f"Veo prompt {i}",
            "veo3_prompt_vi": f"Veo vi {i}"
        }
        for i in range(16, 31)
    ])
    
    mock_negatives_json = json.dumps({
        "scene_negatives": [{"scene_number": i, "specific_negatives_en": ""} for i in range(1, 31)]
    })
    
    mock_global_json = json.dumps({
        "continuity_prompt_en": "Keep style",
        "global_negative_prompt_en": "worst quality",
        "reference_images": {}
    })
    
    mock_critique_json = json.dumps({"has_changes": False, "scenes": []})
    mock_validation_json = json.dumps({"has_changes": False, "scenes": []})
    mock_post_json = json.dumps({"suggestions": []})
    
    # Context compressor mock returns
    mock_compress_chunk_json = json.dumps({
        "plot_summary": "Tóm tắt chunk 1",
        "last_scene_state": "Hero đứng yên"
    })
    
    async def dynamic_mock(prompt, **kwargs):
        import re
        # Phase 2 Batch Scene Generation
        match_batch = re.search(r'This batch: Scenes (\d+) to (\d+)', prompt)
        if match_batch:
            start_num = int(match_batch.group(1))
            end_num = int(match_batch.group(2))
            res = json.dumps({
                "scenes": [
                    {
                        "scene_number": i,
                        "title": f"Scene {i}",
                        "action_detail_vi": f"Hành động {i}",
                        "emotion_gesture_vi": "ok",
                        "camera_movement_vi": "ok",
                        "transition_to_next_vi": "ok",
                        "veo3_prompt_en": f"Reference the approved Hero: Hero in Rome battle scene {i}, anime style, aspect ratio 9:16, voice: \"Hero moves forward.\"",
                        "voice_over_en": "Hero moves forward.",
                        "veo3_prompt_vi": f"Veo vi {i}",
                        "scene_specific_negative_en": ""
                    }
                    for i in range(start_num, end_num + 1)
                ]
            })
            return res + "\n" + json.dumps({"extra": "model note after valid scene JSON"})

        if "environment_master_prompt_en" in prompt:
            return mock_meta_json
        elif "emotion_arc" in prompt and "các Scene" not in prompt and "Scene [" not in prompt and "cho Scene" not in prompt and "critique_notes" not in prompt:
            match_arc = re.search(r'Number of scenes:\s*(\d+)', prompt)
            chunk_num = int(match_arc.group(1)) if match_arc else 30
            return json.dumps({
                "emotion_arc": [
                    {
                        "scene_number": i,
                        "emotion_label": "bi tráng" if i % 2 == 0 else f"hào hứng {i}",
                        "beat_summary": f"Tóm tắt {i}",
                        "physical_state_end": "Ok",
                        "camera_complexity": "medium",
                        "scene_lead_character": "Hero"
                    }
                    for i in range(1, chunk_num + 1)
                ]
            })
        elif "Based on this screenplay, generate reference image prompts" in prompt:
            return json.dumps({
                "background_ref_prompt_en": "Rome background reference",
                "thumbnail_ref_prompt_en": "Hero battle thumbnail",
            })
        elif "scene_negatives" in prompt:
            return mock_negatives_json
        elif "continuity_prompt_en" in prompt:
            return mock_global_json
        elif "critique_notes" in prompt:
            return mock_critique_json
        elif "has_changes" in prompt:
            return mock_validation_json
        elif "suggestions" in prompt:
            return mock_post_json
        elif "Bạn là trợ lý AI chuyên nghiệp về sản xuất video" in prompt or "Bạn là trợ lý AI chuyên nghiệp về biên kịch" in prompt:
            return mock_compress_chunk_json
        return "{}"

    with patch("app.services.gemini.base.BaseGeminiService._call_gemini_with_retry", new_callable=AsyncMock) as mock_call, \
         patch.object(service, "_save_script") as mock_save:
         
        mock_call.side_effect = dynamic_mock
        
        events = []
        async for event in service.generate_full_script_stream(
            suggestion=suggestion,
            style="anime",
            num_scenes=30,  # 30 scenes = 2 chunks
            project_id=1,
            db=mock_db,
            aspect_ratio="9:16"
        ):
            events.append(event)
            
        assert len(events) > 0
        
        # Verify Phase 1 chunk progress and Phase 2 scene batch progress are both yielded.
        assert any("emotion_arc_chunk_1_of_2" in e for e in events)
        assert any("emotion_arc_chunk_2_of_2" in e for e in events)
        progress_events = [e for e in events if '"group": "scenes"' in e and "batch_" in e]
        assert len(progress_events) == 3
        assert "batch_1_of_3" in progress_events[0]
        assert "batch_2_of_3" in progress_events[1]
        assert "batch_3_of_3" in progress_events[2]
        
        # Verify that all 30 scenes are saved
        saved_data = mock_save.call_args[0][2]
        assert len(saved_data["scenes"]) == 30
        assert saved_data["scenes"][0]["scene_number"] == 1
        assert saved_data["scenes"][29]["scene_number"] == 30
