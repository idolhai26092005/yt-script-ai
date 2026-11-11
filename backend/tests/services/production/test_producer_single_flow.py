import pytest
import json
from unittest.mock import AsyncMock, patch
from app.core.database import SessionLocal, Base, engine
from app.models.project import Project
from app.models.api_key import APIKey
from app.crud.project import create_project
from app.crud.api_key import create_api_key
from app.schemas.api_key import APIKeyCreate
from app.services.production import ProductionService
from app.core.utils import to_legacy_v2

@pytest.mark.asyncio
async def test_producer_single_flow():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        # Clean tables
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()
        
        key_in = APIKeyCreate(owner="Test Bilingual", quota_limit=5)
        _, api_key = create_api_key(db, key_in)
        
        project = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Single flow test",
            input_type="manual",
            input_content="Sample topic",
            style="anime",
            num_scenes=2
        )
        
        service = ProductionService(api_key="test_key", groq_api_key=None, db=db, api_key_id=api_key.id)
        service.enable_post_suggestions_test = True
        
        mock_meta_json = json.dumps({
            "overview_analysis_vi": "Phân tích tổng quan tiếng Việt",
            "storyline_vi": "mạch câu chuyện...",
            "stages_vi": "phân chia giai đoạn...",
            "progression_vi": "tiến trình...",
            "camera_strategy_vi": "chiến lược...",
            "continuity_locks_vi": "locks...",
            "form_locks_vi": "form...",
            "age_stage_locks_vi": "age...",
            "geometry_locks_vi": "geometry...",
            "risk_logic_vi": "risk...",
            "characters": [
                {
                    "character_name": "Nhân vật chính",
                    "description_en": "Main hero description en",
                    "description_vi": "Mô tả tiếng Việt nhân vật chính",
                    "key_identifiers_en": "red hair",
                    "key_identifiers_vi": "tóc đỏ"
                }
            ],
            "environment_master_prompt_en": "Background master prompt en",
            "environment_master_prompt_vi": "Mô tả bối cảnh tiếng Việt",
            "prompt_0": {
                "primary_subject_en": "Named hero with red hair",
                "hard_visual_lock_en": "Anime survival visual lock",
                "setting_lock_en": "Consistent test world",
                "character_lock": [{"name": "Nhân vật chính", "description_en": "Main hero description en, red hair"}],
                "camera_lock_en": "Camera lock",
                "voice_sound_lock_en": "English narration",
                "action_story_logic_en": "1. Start 2. Escalate 3. Resolve",
                "scene_function_rules_en": "One function per scene",
                "continuity_lock_en": "Continuity prompt en",
                "internal_logic_en": "No teleportation",
                "negative_constraints_en": "No modern objects"
            },
            "voice_sound_strategy_vi": "chiến lược âm thanh..."
        })
        
        mock_arc_json = json.dumps({
            "emotion_arc": [
                {
                    "scene_number": 1,
                    "emotion_label": "bi tráng",
                    "beat_summary": "Khởi đầu câu chuyện",
                    "physical_state_end": "Sẵn sàng",
                    "camera_complexity": "low",
                    "scene_lead_character": "Nhân vật chính"
                },
                {
                    "scene_number": 2,
                    "emotion_label": "Kịch tính",
                    "beat_summary": "Cao trào",
                    "physical_state_end": "Thắng lợi",
                    "camera_complexity": "medium",
                    "scene_lead_character": "Nhân vật chính"
                }
            ]
        })
        
        mock_batch_scenes_json = json.dumps({
            "scenes": [
                {
                    "scene_number": 1,
                    "title": "Scene 1",
                    "action_detail_vi": "Hành động scene 1",
                    "emotion_gesture_vi": "Cảm xúc scene 1",
                    "camera_movement_vi": "Camera scene 1",
                    "transition_to_next_vi": "Chuyển cảnh scene 1",
                    "veo3_prompt_en": "Reference the approved Prompt 0 continuity board, red-haired hero enters the test world, anime style, voice: \"The first test begins.\"",
                    "voice_over_en": "The first test begins.",
                    "veo3_prompt_vi": "Prompt vi scene 1",
                    "scene_specific_negative_en": "low quality"
                },
                {
                    "scene_number": 2,
                    "title": "Scene 2",
                    "action_detail_vi": "Hành động scene 2",
                    "emotion_gesture_vi": "Cảm xúc scene 2",
                    "camera_movement_vi": "Camera scene 2",
                    "transition_to_next_vi": "Chuyển cảnh scene 2",
                    "veo3_prompt_en": "Reference the approved Prompt 0 continuity board, red-haired hero resolves the test scene, anime style, voice: \"The trial reaches its end.\"",
                    "voice_over_en": "The trial reaches its end.",
                    "veo3_prompt_vi": "Prompt vi scene 2",
                    "scene_specific_negative_en": "low quality"
                }
            ]
        })
        
        mock_global_json = json.dumps({
            "continuity_prompt_en": "Continuity prompt en",
            "continuity_prompt_vi": "Hướng dẫn liên kết tiếng Việt",
            "global_negative_prompt_en": "worst quality",
            "reference_images": {
                "character_ref_prompt_en": "Ref character en",
                "background_ref_prompt_en": "Ref background en",
                "thumbnail_ref_prompt_en": "Ref thumbnail en"
            }
        })
        
        mock_post_json = json.dumps({
            "suggestions": [
                {
                    "index": 0,
                    "title": "Gợi ý tập tiếp",
                    "synopsis": "Tóm tắt gợi ý",
                    "mood": "kịch tính",
                    "topic_type": "fictional_original"
                }
            ]
        })
        
        with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = [
                mock_meta_json,          # Phase 0 Blueprint
                mock_arc_json,           # Phase 1 Emotion Arc
                mock_batch_scenes_json,  # Phase 2 Batch Scenes
                mock_global_json,        # Phase 3 Packaging
                mock_post_json           # Post suggestions
            ]
            
            events = []
            async for event in service.generate_full_script_stream(
                suggestion={"index": 0, "title": "Main topic", "synopsis": "Desc", "topic_type": "fictional_original"},
                style="anime",
                num_scenes=2,
                project_id=project.id,
                db=db
            ):
                events.append(event)
                
            assert len(events) > 0
            
            db.refresh(project)
            assert project.status == "script_generated"
            assert project.post_suggestions is not None
            assert len(project.post_suggestions) == 1
            assert project.post_suggestions[0]["title"] == "Gợi ý tập tiếp"
            
            script_out = to_legacy_v2(json.loads(project.script_output))
            
            # Verify bilingual fields exist in output
            assert script_out["overview_analysis_vi"] == "Phân tích tổng quan tiếng Việt"
            assert script_out["characters"][0]["description_vi"] == "Mô tả tiếng Việt nhân vật chính"
            assert script_out["characters"][0]["key_identifiers_vi"] == "tóc đỏ"
            assert script_out["environment_master_prompt_vi"] == "Mô tả bối cảnh tiếng Việt"
            assert script_out["scenes"][0]["veo3_prompt_vi"] == "Prompt vi scene 1"
            assert script_out["continuity_board"]["continuity_prompt_en"] == "Continuity prompt en"
            
    finally:
        db.close()
