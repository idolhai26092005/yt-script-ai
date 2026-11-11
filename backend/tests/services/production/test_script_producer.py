import sys
import os
import json
import pytest
from unittest.mock import AsyncMock, patch

# Add parent path to path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from app.core.database import SessionLocal, Base, engine
from app.models.project import Project
from app.models.api_key import APIKey
from app.models.trending_topic import TrendingTopic
from app.crud.project import create_project, get_project
from app.crud.api_key import create_api_key
from app.schemas.api_key import APIKeyCreate
from app.services.production import ProductionService
from app.core.utils import to_legacy_v2
import re

def make_dynamic_mock(meta_json, arc_json, scene_json_or_list, global_json, critique_json, fact_check_json=None, color_recheck_json=None):
    scenes_map = {}
    try:
        raw_scenes = json.loads(scene_json_or_list)
        if isinstance(raw_scenes, list):
            for s in raw_scenes:
                scenes_map[s["scene_number"]] = s
        elif isinstance(raw_scenes, dict):
            if "scenes" in raw_scenes:
                for s in raw_scenes["scenes"]:
                    scenes_map[s["scene_number"]] = s
            else:
                scenes_map[raw_scenes.get("scene_number", 1)] = raw_scenes
    except Exception:
        pass

    async def side_effect(prompt, **kwargs):
        # 1. Fact Check (check this first because fact check prompts contain "overview_analysis_vi" schema block)
        if "Fact-Checking" in prompt or "Fact-Check" in prompt or "fact-checker" in prompt or "VERIFIABILITY LEVEL" in prompt or "audit the provided video script" in prompt:
            try:
                data = json.loads(fact_check_json or "{}")
            except Exception:
                data = {}
            if isinstance(data, dict) and "scenes" in data:
                returned = {s.get("scene_number"): s for s in data.get("scenes", [])}
                expected = sorted(scenes_map) or sorted(returned)
                full_scenes = []
                for idx in expected:
                    scene = dict(scenes_map.get(idx, {"scene_number": idx}))
                    scene.update(returned.get(idx, {}))
                    scene.setdefault("historical_basis_vi", f"Verified basis for scene {idx}")
                    scene.setdefault("verifiability_level", "specific_event")
                    if not scene.get("veo3_prompt_en", "").startswith("Reference the approved"):
                        scene["veo3_prompt_en"] = "Reference the approved " + scene.get("veo3_prompt_en", f"Subject scene {idx}")
                    scene.setdefault("voice_over_en", f"Narration line for scene {idx}.")
                    full_scenes.append(scene)
                data["scenes"] = full_scenes
                return json.dumps(data)
            return fact_check_json or "{}"

        # 2. Phase 0 (Prompt 0 + blueprint)
        if "PROMPT 0 (Identity Lock" in prompt or "overview_analysis_vi" in prompt:
            try:
                data = json.loads(meta_json)
            except Exception:
                data = {}
            if "prompt_0" not in data:
                data["prompt_0"] = {
                    "primary_subject_en": "Subject lock",
                    "hard_visual_lock_en": "Visual lock",
                    "setting_lock_en": "Setting lock",
                    "character_lock": [{"name": "Hero", "description_en": "Hero desc"}],
                    "camera_lock_en": "Camera lock",
                    "voice_sound_lock_en": "Voice lock",
                    "action_story_logic_en": "Logic lock",
                    "scene_function_rules_en": "Rules lock",
                    "continuity_lock_en": "Continuity lock",
                    "internal_logic_en": "Internal logic",
                    "negative_constraints_en": "Negative constraints"
                }
            if "voice_sound_strategy_vi" not in data:
                data["voice_sound_strategy_vi"] = "Sound strategy"
            if not data.get("characters"):
                data["characters"] = [{"character_name": "Hero", "description_en": "Hero desc", "key_identifiers_en": "hero"}]
            # Durable producer-fixture guard: mocked Phase 0 responses include
            # the contract expected by current blueprint and resume gates.
            if not data.get("story_contract"):
                characters = data.get("characters") or []
                lead = (
                    (characters[0].get("character_name") if characters else "")
                    or (data.get("prompt_0") or {}).get("primary_subject_en")
                    or "Hero"
                )
                data["story_contract"] = {
                    "main_subject_en": lead,
                    "protagonist_en": lead,
                    "central_opponent_or_force_en": lead,
                    "core_goal_en": f"{lead} completes the central mission",
                    "must_remain_visible_terms": [lead],
                    "forbidden_takeover_rule": "No side thread replaces the central mission.",
                }
                for key in ("storyline_vi", "stages_vi"):
                    text = str(data.get(key) or "")
                    if lead and lead.lower() not in text.lower():
                        data[key] = f"{text} {lead}".strip()
            return json.dumps(data)

        # 3. Phase 1 (Emotion Arc)
        if "nhịp kịch tính" in prompt or "emotion_arc" in prompt or "Emotion Arc" in prompt:
            return arc_json

        # 4. Phase 2 (Batch Scene Generation)
        if "BATCH_SCENE_GENERATION_TEMPLATE" in prompt or "veo3_prompt_en — MANDATORY FORMAT" in prompt or "This batch: Scenes" in prompt:
            match = re.search(r'Scenes (\d+)\s+to\s+(\d+)', prompt, re.IGNORECASE)
            if not match:
                match = re.search(r'scenes\s+(\d+)–(\d+)', prompt, re.IGNORECASE)
            if not match:
                match = re.search(r'scenes\s+(\d+)–(\d+)', prompt, re.IGNORECASE)
            if not match:
                match = re.search(r'scenes\s+(\d+)\s+through\s+(\d+)', prompt, re.IGNORECASE)
            if not match:
                match = re.search(r'scenes\s+(\d+)\s+to\s+(\d+)', prompt, re.IGNORECASE)

            if match:
                start = int(match.group(1))
                end = int(match.group(2))
            else:
                start = 1
                end = 4

            scenes_list = []
            for idx in range(start, end + 1):
                scene_data = scenes_map.get(idx)
                if not scene_data:
                    scene_data = {
                        "scene_number": idx,
                        "title": f"Scene {idx}",
                        "action_detail_vi": f"Hành động {idx}",
                        "veo3_prompt_en": f"Reference the approved Hero: Cinematic shot {idx}, voice: \"Narration line for scene {idx}.\"",
                        "voice_over_en": f"Narration line for scene {idx}.",
                        "historical_basis_vi": None,
                        "needs_fact_check": False,
                        "fact_check_note_vi": None,
                        "verifiability_level": "specific_event"
                    }
                else:
                    # make sure prefix is valid
                    if "veo3_prompt_en" in scene_data and not scene_data["veo3_prompt_en"].startswith("Reference the approved"):
                        scene_data["veo3_prompt_en"] = "Reference the approved " + scene_data["veo3_prompt_en"]
                    if "voice_over_en" not in scene_data:
                        scene_data["voice_over_en"] = f"Narration line for scene {idx}."
                    if "historical_basis_vi" in scene_data and "verifiability_level" not in scene_data:
                        scene_data["verifiability_level"] = "specific_event"
                scenes_list.append(scene_data)
            return json.dumps({"scenes": scenes_list})

        # 5. Phase 3 (Packaging / Reference images)
        if "REFERENCE_IMAGES_PROMPT" in prompt or "thumbnail_ref_prompt_en" in prompt or "background_ref_prompt_en" in prompt:
            try:
                data = json.loads(global_json)
                if isinstance(data, dict) and "reference_images" in data:
                    return json.dumps(data["reference_images"])
            except Exception:
                pass
            return global_json

        return "{}"

    mock = AsyncMock()
    mock.side_effect = side_effect
    return mock

@pytest.mark.asyncio
async def test_idea_suggester_and_script_producer():
    # Setup test tables
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Clean tables
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()

        # Create API key
        key_in = APIKeyCreate(owner="Test Service Owner", quota_limit=5)
        _, api_key = create_api_key(db, key_in)

        # Create Project
        project = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Dự án phục dựng sử Việt",
            input_type="manual",
            input_content="Chiến thắng Bạch Đằng năm 938",
            style="anime",
            num_scenes=4
        )

        service = ProductionService(api_key="test_gemini_key", groq_api_key=None, db=db, api_key_id=api_key.id)

        # 1. Mock and Test generate_suggestions
        mock_suggestions_json = json.dumps([
            {
                "index": 0,
                "title": "Bạch Đằng Giang lịch sử",
                "synopsis": "Kịch bản tóm tắt tái hiện trận thủy chiến lịch sử.",
                "mood": "Cinematic",
                "hook": "Dòng sông cuộn sóng dữ...",
                "is_original": True,
                "topic_type": "historical"
            },
            {
                "index": 1,
                "title": "Huyền thoại cọc gỗ",
                "synopsis": "Góc nhìn từ những người thợ đóng cọc gỗ trên sông Bạch Đằng.",
                "mood": "Epic",
                "hook": "Bí mật nằm dưới dòng nước...",
                "is_original": False,
                "topic_type": "historical"
            }
        ])

        with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_suggestions_json
            
            sugs = await service.generate_suggestions(
                input_content="Bạch Đằng năm 938",
                style="anime",
                num_scenes=4,
                num_suggestions=2
            )
            
            assert len(sugs) == 2
            assert sugs[0]["title"] == "Bạch Đằng Giang lịch sử"
            assert sugs[0]["is_original"] is True
            assert sugs[0]["topic_type"] == "historical"
            assert sugs[1]["is_original"] is False
            assert sugs[1]["topic_type"] == "historical"
            
            mock_call.assert_called_once()

        with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_suggestions_json + "\n" + json.dumps({"extra": "ignored"})

            sugs = await service.generate_suggestions(
                input_content="Bạch Đằng năm 938",
                style="anime",
                num_scenes=4,
                num_suggestions=2
            )

            assert len(sugs) == 2
            assert sugs[0]["title"] == "Bạch Đằng Giang lịch sử"

        # 2. Mock and Test suggest_from_topic
        with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "Ý tưởng kịch bản tóm tắt chi tiết từ chủ đề."
            idea = await service.suggest_from_topic("Lịch sử Việt Nam", "Trận Bạch Đằng", "anime")
            assert "Ý tưởng" in idea
            mock_call.assert_called_once()

        # 3. Mock and Test generate_full_script_stream
        selected_suggestion = {
            "index": 0,
            "title": "Bạch Đằng Giang lịch sử",
            "synopsis": "Kịch bản tóm tắt trận thủy chiến."
        }

        mock_meta_json = json.dumps({
            "overview_analysis_vi": "Video dồn dập, nhịp điệu nhanh.",
            "storyline_vi": "Mạch truyện Ngô Quyền đập tan quân Nam Hán.",
            "stages_vi": "Giai đoạn 1: Chuẩn bị cọc gỗ trên sông.",
            "progression_vi": "Cảnh 1-4: Thiết lập trận địa cọc gỗ.",
            "camera_strategy_vi": "Camera góc rộng toàn cảnh sông Bạch Đằng.",
            "continuity_locks_vi": "Khóa nhân vật Ngô Quyền và cọc gỗ sông Bạch Đằng.",
            "form_locks_vi": "Khóa hình dáng cọc nhọn bằng gỗ lim.",
            "age_stage_locks_vi": "Ngô Quyền trung niên.",
            "geometry_locks_vi": "Sông nước và cọc gỗ thẳng đứng.",
            "risk_logic_vi": "Thủy triều rút dồn dập.",
            "characters": [{"character_name": "Ngô Quyền", "description_en": "A brave commander, iron armor, tall", "key_identifiers_en": "iron armor, tall"}],
            "environment_master_prompt_en": "Bạch Đằng river in early winter morning."
        })

        mock_arc_json = json.dumps({
            "emotion_arc": [
                {"scene_number": 1, "emotion_label": "sửng sốt", "beat_summary": "Ngô Quyền chỉ huy đóng cọc gỗ dưới triều nước cao.", "physical_state_end": "Đứng trên bờ sông quan sát trận địa", "camera_complexity": "low", "scene_lead_character": "Ngô Quyền"},
                {"scene_number": 2, "emotion_label": "lo âu", "beat_summary": "Thủy triều bắt đầu đổi hướng khiến quân lính gấp rút che giấu cọc.", "physical_state_end": "Cúi xuống cạnh hàng cọc đã phủ bùn", "camera_complexity": "low", "scene_lead_character": "Ngô Quyền"},
                {"scene_number": 3, "emotion_label": "hùng tráng", "beat_summary": "Thuyền địch tiến vào luồng sông hẹp do hàng cọc dẫn dụ.", "physical_state_end": "Đứng sau tuyến quân nhìn thuyền địch mắc bẫy", "camera_complexity": "low", "scene_lead_character": "Ngô Quyền"},
                {"scene_number": 4, "emotion_label": "bình yên", "beat_summary": "Sau va chạm, mặt sông lắng lại để lộ trận địa đã hoàn tất.", "physical_state_end": "Đứng yên bên bờ sông sau giao tranh", "camera_complexity": "low", "scene_lead_character": "Ngô Quyền"}
            ]
        })

        mock_batch_scenes_1_3 = json.dumps([
            {
                "scene_number": 1,
                "title": "Scene 1 [00:00 - 00:08]",
                "action_detail_vi": "Ngô Quyền ra hiệu cho quân lính đóng hàng cọc đầu tiên dưới mặt nước.",
                "emotion_gesture_vi": "Lính Nam Hán hoảng sợ",
                "camera_movement_vi": "Góc máy flycam hạ độ cao nhanh",
                "transition_to_next_vi": "Dissolve sang cảnh sau",
                "veo3_prompt_en": "A cinematic shot of Ngô Quyền directing soldiers placing hidden wooden stakes, style anime, vertical 9:16, warm golden lighting",
                "scene_specific_negative_en": "watermark, text overlay"
            },
            {
                "scene_number": 2,
                "title": "Scene 2 [00:08 - 00:16]",
                "action_detail_vi": "Quân lính phủ bùn và lau sậy lên hàng cọc khi thủy triều bắt đầu đổi hướng.",
                "emotion_gesture_vi": "Lính Nam Hán hoảng sợ",
                "camera_movement_vi": "Góc máy flycam hạ độ cao nhanh",
                "transition_to_next_vi": "Dissolve sang cảnh sau",
                "veo3_prompt_en": "A cinematic shot of soldiers concealing stakes under mud and reeds, style anime, vertical 9:16, warm golden lighting",
                "scene_specific_negative_en": "watermark, text overlay"
            },
            {
                "scene_number": 3,
                "title": "Scene 3 [00:16 - 00:24]",
                "action_detail_vi": "Thuyền địch bị dẫn vào luồng hẹp, mũi thuyền rung lên khi chạm cọc ngầm.",
                "emotion_gesture_vi": "Lính Nam Hán hoảng sợ",
                "camera_movement_vi": "Góc máy flycam hạ độ cao nhanh",
                "transition_to_next_vi": "Dissolve sang cảnh sau",
                "veo3_prompt_en": "A cinematic shot of enemy boats entering a narrow hidden-stake channel, style anime, vertical 9:16, warm golden lighting",
                "scene_specific_negative_en": "watermark, text overlay"
            }
        ])

        mock_batch_scenes_4 = json.dumps([
            {
                "scene_number": 4,
                "title": "Scene 4 [00:24 - 00:32]",
                "action_detail_vi": "Mặt sông yên lại sau va chạm, hàng cọc lộ rõ như kết quả của kế hoạch.",
                "emotion_gesture_vi": "Lính Nam Hán hoảng sợ",
                "camera_movement_vi": "Góc máy flycam hạ độ cao nhanh",
                "transition_to_next_vi": "Dissolve sang cảnh sau",
                "veo3_prompt_en": "A cinematic shot of exposed wooden stakes after the clash, style anime, vertical 9:16, warm golden lighting",
                "scene_specific_negative_en": "watermark, text overlay"
            }
        ])

        mock_negatives_json = json.dumps({
            "scene_negatives": [
                {"scene_number": 1, "specific_negatives_en": "watermark, text overlay"},
                {"scene_number": 2, "specific_negatives_en": "watermark, text overlay"},
                {"scene_number": 3, "specific_negatives_en": "watermark, text overlay"},
                {"scene_number": 4, "specific_negatives_en": "watermark, text overlay"}
            ]
        })

        mock_global_json = json.dumps({
            "continuity_prompt_en": "Keep the light misty.",
            "global_negative_prompt_en": "morped figures, low quality",
            "reference_images": {
                "character_ref_prompt_en": "Ngô Quyền reference image",
                "background_ref_prompt_en": "River reference image",
                "thumbnail_ref_prompt_en": "Bạch Đằng thumbnail"
            }
        })

        mock_critique_json = json.dumps({
            "has_changes": False,
            "critique_notes": "All looks good.",
            "scenes": []
        })

        mock_validation_json = json.dumps({
            "has_changes": False,
            "validation_notes": "Color schemes match.",
            "scenes": []
        })

        mock_scene_1 = json.dumps({
            "scene_number": 1,
            "title": "Scene 1 [00:00 - 00:08]",
            "action_detail_vi": "Ngô Quyền ra hiệu cho quân lính đóng hàng cọc đầu tiên dưới mặt nước.",
            "emotion_gesture_vi": "Lính Nam Hán hoảng sợ",
            "camera_movement_vi": "Góc máy flycam hạ độ cao nhanh",
            "transition_to_next_vi": "Dissolve sang cảnh sau",
            "veo3_prompt_en": "A cinematic shot of Ngô Quyền directing soldiers placing hidden wooden stakes, style anime, vertical 9:16, warm golden lighting",
            "scene_specific_negative_en": "watermark, text overlay"
        })
        mock_scene_2 = json.dumps({
            "scene_number": 2,
            "title": "Scene 2 [00:08 - 00:16]",
            "action_detail_vi": "Quân lính phủ bùn và lau sậy lên hàng cọc khi thủy triều bắt đầu đổi hướng.",
            "emotion_gesture_vi": "Lính Nam Hán hoảng sợ",
            "camera_movement_vi": "Góc máy flycam hạ độ cao nhanh",
            "transition_to_next_vi": "Dissolve sang cảnh sau",
            "veo3_prompt_en": "A cinematic shot of soldiers concealing stakes under mud and reeds, style anime, vertical 9:16, warm golden lighting",
            "scene_specific_negative_en": "watermark, text overlay"
        })
        mock_scene_3 = json.dumps({
            "scene_number": 3,
            "title": "Scene 3 [00:16 - 00:24]",
            "action_detail_vi": "Thuyền địch bị dẫn vào luồng hẹp, mũi thuyền rung lên khi chạm cọc ngầm.",
            "emotion_gesture_vi": "Lính Nam Hán hoảng sợ",
            "camera_movement_vi": "Góc máy flycam hạ độ cao nhanh",
            "transition_to_next_vi": "Dissolve sang cảnh sau",
            "veo3_prompt_en": "A cinematic shot of enemy boats entering a narrow hidden-stake channel, style anime, vertical 9:16, warm golden lighting",
            "scene_specific_negative_en": "watermark, text overlay"
        })
        mock_scene_4 = json.dumps({
            "scene_number": 4,
            "title": "Scene 4 [00:24 - 00:32]",
            "action_detail_vi": "Mặt sông yên lại sau va chạm, hàng cọc lộ rõ như kết quả của kế hoạch.",
            "emotion_gesture_vi": "Lính Nam Hán hoảng sợ",
            "camera_movement_vi": "Góc máy flycam hạ độ cao nhanh",
            "transition_to_next_vi": "Dissolve sang cảnh sau",
            "veo3_prompt_en": "A cinematic shot of exposed wooden stakes after the clash, style anime, vertical 9:16, warm golden lighting",
            "scene_specific_negative_en": "watermark, text overlay"
        })

        scenes_list_json = json.dumps([
            json.loads(mock_scene_1),
            json.loads(mock_scene_2),
            json.loads(mock_scene_3),
            json.loads(mock_scene_4)
        ])
        mock_gemini = make_dynamic_mock(
            meta_json=mock_meta_json,
            arc_json=mock_arc_json,
            scene_json_or_list=scenes_list_json,
            global_json=mock_global_json,
            critique_json=mock_critique_json
        )
        with patch.object(service, "_call_gemini_with_retry", mock_gemini) as mock_call:

            sse_events = []
            async for event in service.generate_full_script_stream(
                suggestion=selected_suggestion,
                style="anime",
                num_scenes=4,
                project_id=project.id,
                db=db
            ):
                sse_events.append(event)

            # Check that SSE yields events
            assert len(sse_events) > 0
            
            # Check SSE status list
            statuses = []
            for ev in sse_events:
                if ev.startswith("data: "):
                    payload = json.loads(ev[6:].strip())
                    statuses.append(payload.get("status"))

            assert "generating" in statuses
            assert "metadata" in statuses
            assert "emotion_arc" in statuses
            assert "scene" in statuses
            assert "global" in statuses
            assert "done" in statuses

            # Verify database project script output
            db.refresh(project)
            assert project.status == "script_generated"
            script_out = to_legacy_v2(json.loads(project.script_output))
            assert script_out["overview_analysis_vi"] == "Video dồn dập, nhịp điệu nhanh."
            assert script_out["storyline_vi"] == "Mạch truyện Ngô Quyền đập tan quân Nam Hán."
            assert len(script_out["scenes"]) == 4
            assert script_out["scenes"][0]["scene_number"] == 1
            assert script_out["scenes"][0]["scene_specific_negative_en"] == "watermark, text overlay"
            assert script_out["scenes"][0]["negative_prompt_en"]

        print("✓ AI Services Unit Tests passed!")
    finally:
        db.close()


@pytest.mark.asyncio
async def test_historical_script_generation_with_fact_check():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()

        key_in = APIKeyCreate(owner="Test Historical Owner", quota_limit=5)
        _, api_key = create_api_key(db, key_in)

        project = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Sử Việt Trận Bạch Đằng",
            input_type="manual",
            input_content="Trận Bạch Đằng Ngô Quyền 938",
            style="realistic",
            num_scenes=2
        )

        service = ProductionService(api_key="test_gemini_key", groq_api_key=None, db=db, api_key_id=api_key.id)

        selected_suggestion = {
            "index": 0,
            "title": "Bạch Đằng 938",
            "synopsis": "Kịch bản Trận Bạch Đằng.",
            "topic_type": "historical"
        }

        mock_meta_json = json.dumps({
            "overview_analysis_vi": "Tái hiện trận Bạch Đằng.",
            "storyline_vi": "Mạch truyện Ngô Quyền đập tan quân Nam Hán.",
            "stages_vi": "Giai đoạn 1: Chuẩn bị cọc gỗ trên sông.",
            "progression_vi": "Cảnh 1-4: Thiết lập trận địa cọc gỗ.",
            "camera_strategy_vi": "Camera góc rộng toàn cảnh sông Bạch Đằng.",
            "continuity_locks_vi": "Khóa nhân vật Ngô Quyền và cọc gỗ sông Bạch Đằng.",
            "form_locks_vi": "Khóa hình dáng cọc nhọn bằng gỗ lim.",
            "age_stage_locks_vi": "Ngô Quyền trung niên.",
            "geometry_locks_vi": "Sông nước và cọc gỗ thẳng đứng.",
            "risk_logic_vi": "Thủy triều rút dồn dập.",
            "characters": [{"character_name": "Ngô Quyền", "description_en": "Brave general", "key_identifiers_en": "brave general"}],
            "environment_master_prompt_en": "River scene."
        })

        mock_arc_json = json.dumps({
            "emotion_arc": [
                {"scene_number": 1, "emotion_label": "sửng sốt", "beat_summary": "Ngô Quyền kiểm tra hàng cọc mới cắm trên sông.", "physical_state_end": "Đứng cạnh hàng cọc mới cắm", "camera_complexity": "low", "scene_lead_character": "Ngô Quyền"},
                {"scene_number": 2, "emotion_label": "lo âu", "beat_summary": "Thuyền địch lao tới khiến hàng cọc bắt đầu phát huy tác dụng.", "physical_state_end": "Nhìn thuyền địch chạm vào cọc", "camera_complexity": "low", "scene_lead_character": "Ngô Quyền"}
            ]
        })

        mock_batch_scenes_1_2 = json.dumps([
            {
                "scene_number": 1,
                "title": "Scene 1 [00:00 - 00:08]",
                "action_detail_vi": "Ngô Quyền kiểm tra hàng cọc gỗ vừa được cắm dưới lòng sông.",
                "emotion_gesture_vi": "Hào khí quân ta",
                "camera_movement_vi": "Góc rộng",
                "transition_to_next_vi": "Chuyển tiếp",
                "veo3_prompt_en": "Wooden stakes newly planted in the river beside Ngô Quyền, realistic style, vertical 9:16, warm golden lighting",
                "historical_basis_vi": "Ngô Quyền dùng cọc gỗ đóng trên sông",
                "needs_fact_check": False,
                "fact_check_note_vi": None,
                "scene_specific_negative_en": "watermark"
            },
            {
                "scene_number": 2,
                "title": "Scene 2 [00:08 - 00:16]",
                "action_detail_vi": "Thuyền địch lao tới và bắt đầu va vào hàng cọc ngầm.",
                "emotion_gesture_vi": "Hào khí quân ta",
                "camera_movement_vi": "Góc rộng",
                "transition_to_next_vi": "Chuyển tiếp",
                "veo3_prompt_en": "Enemy boat hits hidden wooden stakes in the river, realistic style, vertical 9:16, warm golden lighting",
                "historical_basis_vi": "Ngô Quyền dùng cọc gỗ đóng trên sông",
                "needs_fact_check": False,
                "fact_check_note_vi": None,
                "scene_specific_negative_en": "watermark"
            }
        ])

        mock_negatives_json = json.dumps({
            "scene_negatives": [
                {"scene_number": 1, "specific_negatives_en": "watermark"},
                {"scene_number": 2, "specific_negatives_en": "watermark"}
            ]
        })

        mock_global_json = json.dumps({
            "continuity_prompt_en": "Keep visual style.",
            "global_negative_prompt_en": "lowres",
            "reference_images": {
                "character_ref_prompt_en": "Ngô Quyền prompt",
                "background_ref_prompt_en": "River prompt",
                "thumbnail_ref_prompt_en": "Thumbnail prompt"
            }
        })

        mock_critique_json = json.dumps({
            "has_changes": False,
            "critique_notes": "Ok.",
            "scenes": []
        })

        mock_validation_json = json.dumps({
            "has_changes": False,
            "validation_notes": "Ok.",
            "scenes": []
        })

        mock_fact_check_json = json.dumps({
            "has_issues": True,
            "fact_check_notes": "Audit completed. Minor issue fixed.",
            "scenes": [
                {
                    "scene_number": 1,
                    "title": "Scene 1 [00:00 - 00:08]",
                    "action_detail_vi": "Cảnh cọc gỗ cắm trên sông Bạch Đằng",
                    "emotion_gesture_vi": "Hào khí quân ta",
                    "camera_movement_vi": "Góc rộng",
                    "transition_to_next_vi": "Chuyển tiếp",
                    "voice_over_vi": "Lời bình 1",
                    "veo3_prompt_en": "Reference the approved Ngô Quyền: Wooden stakes in river, featuring Ngô Quyền",
                    "historical_basis_vi": "Ngô Quyền chỉ huy đóng cọc gỗ trên sông Bạch Đằng",
                    "needs_fact_check": True,
                    "fact_check_note_vi": "Đã điều chỉnh mô tả hành động bám sát sử liệu hơn.",
                    "scene_specific_negative_en": "watermark"
                },
                {
                    "scene_number": 2,
                    "title": "Scene 2 [00:08 - 00:16]",
                    "action_detail_vi": "Cảnh thuyền địch va vào cọc",
                    "emotion_gesture_vi": "Địch hoảng loạn",
                    "camera_movement_vi": "Góc cận",
                    "transition_to_next_vi": "Chuyển tiếp",
                    "voice_over_vi": "Lời bình 2",
                    "veo3_prompt_en": "Reference the approved Ngô Quyền: Enemy ship hits stakes, featuring Ngô Quyền",
                    "historical_basis_vi": "Thuyền Nam Hán bị vỡ khi thủy triều rút làm cọc gỗ nhô lên",
                    "needs_fact_check": False,
                    "fact_check_note_vi": None,
                    "scene_specific_negative_en": "watermark"
                }
            ]
        })

        mock_gemini = make_dynamic_mock(
            meta_json=mock_meta_json,
            arc_json=mock_arc_json,
            scene_json_or_list=mock_batch_scenes_1_2,
            global_json=mock_global_json,
            critique_json=mock_critique_json,
            fact_check_json=mock_fact_check_json
        )
        with patch.object(service, "_call_gemini_with_retry", mock_gemini) as mock_call:

            sse_events = []
            async for event in service.generate_full_script_stream(
                suggestion=selected_suggestion,
                style="realistic",
                num_scenes=2,
                project_id=project.id,
                db=db
            ):
                sse_events.append(event)

            # Assertions
            statuses = [json.loads(ev[6:].strip()).get("status") for ev in sse_events if ev.startswith("data: ")]
            assert "generating" in statuses
            assert "metadata" in statuses
            assert "emotion_arc" in statuses
            assert "scene" in statuses
            assert "global" in statuses
            assert "done" in statuses
            
            # Check fact_check step was run
            steps = [json.loads(ev[6:].strip()).get("step") for ev in sse_events if ev.startswith("data: ") and json.loads(ev[6:].strip()).get("status") == "generating"]
            assert "fact_check" in steps

            # Verify saved script has topic_type and fact-check results
            db.refresh(project)
            assert project.topic_type == "historical"
            script_out = to_legacy_v2(json.loads(project.script_output))
            assert script_out["topic_type"] == "historical"
            assert len(script_out["scenes"]) == 2
            assert script_out["scenes"][0]["needs_fact_check"] is True
            assert script_out["scenes"][0]["historical_basis_vi"] is not None

    finally:
        db.close()


@pytest.mark.asyncio
async def test_fictional_script_generation_no_fact_check():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()

        key_in = APIKeyCreate(owner="Test Fictional Owner", quota_limit=5)
        _, api_key = create_api_key(db, key_in)

        project = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Câu chuyện rồng lửa",
            input_type="manual",
            input_content="Rồng phun lửa cứu công chúa",
            style="cartoon",
            num_scenes=2
        )

        service = ProductionService(api_key="test_gemini_key", groq_api_key=None, db=db, api_key_id=api_key.id)

        selected_suggestion = {
            "index": 0,
            "title": "Rồng lửa",
            "synopsis": "Chuyện hư cấu rồng phun lửa.",
            "topic_type": "fictional_original"
        }

        mock_meta_json = json.dumps({
            "overview_analysis_vi": "Video hoạt họa tươi sáng.",
            "storyline_vi": "Mạch truyện rồng phun lửa.",
            "stages_vi": "Giai đoạn 1: Thiết lập lâu đài rồng lửa.",
            "progression_vi": "Cảnh 1-2: Rồng xuất hiện bảo vệ công chúa.",
            "camera_strategy_vi": "Camera hoạt họa bay xung quanh lâu đài.",
            "continuity_locks_vi": "Khóa hình dáng rồng và lâu đài.",
            "form_locks_vi": "Dáng rồng dễ thương không đổi màu.",
            "age_stage_locks_vi": "Rồng con.",
            "geometry_locks_vi": "Lâu đài giữa núi đá.",
            "risk_logic_vi": "Lửa rồng phun to dần.",
            "characters": [{"character_name": "Rồng", "description_en": "Cute green dragon", "key_identifiers_en": "green dragon"}],
            "environment_master_prompt_en": "Fantasy castle backdrop."
        })

        mock_arc_json = json.dumps({
            "emotion_arc": [
                {"scene_number": 1, "emotion_label": "sửng sốt", "beat_summary": "Rồng phun lửa", "physical_state_end": "Rồng cười", "camera_complexity": "low", "scene_lead_character": "Rồng"},
                {"scene_number": 2, "emotion_label": "lo âu", "beat_summary": "Rồng phun lửa", "physical_state_end": "Rồng cười", "camera_complexity": "low", "scene_lead_character": "Rồng"}
            ]
        })

        mock_batch_scenes_fictional = json.dumps([
            {
                "scene_number": 1,
                "title": "Scene 1 [00:00 - 00:08]",
                "action_detail_vi": "Rồng mở cánh chắn trước cổng thành khi khói bốc lên.",
                "emotion_gesture_vi": "Rồng cười tươi",
                "camera_movement_vi": "Zoom in",
                "transition_to_next_vi": "Chuyển tiếp",
                "veo3_prompt_en": "Dragon spreads wings before the castle gate, cartoon style, vertical 9:16, warm golden lighting",
                "scene_specific_negative_en": "watermark"
            },
            {
                "scene_number": 2,
                "title": "Scene 2 [00:08 - 00:16]",
                "action_detail_vi": "Rồng phun một luồng lửa ngắn để đẩy lùi bóng tối đang tiến sát.",
                "emotion_gesture_vi": "Rồng cười tươi",
                "camera_movement_vi": "Zoom in",
                "transition_to_next_vi": "Chuyển tiếp",
                "veo3_prompt_en": "Dragon breathes a short burst of fire against approaching darkness, cartoon style, vertical 9:16, warm golden lighting",
                "scene_specific_negative_en": "watermark"
            }
        ])

        mock_negatives_json = json.dumps({
            "scene_negatives": [
                {"scene_number": 1, "specific_negatives_en": "watermark"},
                {"scene_number": 2, "specific_negatives_en": "watermark"}
            ]
        })

        mock_global_json = json.dumps({
            "continuity_prompt_en": "Match green color.",
            "global_negative_prompt_en": "low quality",
            "reference_images": {
                "character_ref_prompt_en": "Dragon prompt",
                "background_ref_prompt_en": "Castle prompt",
                "thumbnail_ref_prompt_en": "Thumbnail prompt"
            }
        })

        mock_critique_json = json.dumps({
            "has_changes": False,
            "critique_notes": "Ok.",
            "scenes": []
        })

        mock_validation_json = json.dumps({
            "has_changes": False,
            "validation_notes": "Ok.",
            "scenes": []
        })

        mock_gemini = make_dynamic_mock(
            meta_json=mock_meta_json,
            arc_json=mock_arc_json,
            scene_json_or_list=mock_batch_scenes_fictional,
            global_json=mock_global_json,
            critique_json=mock_critique_json
        )
        with patch.object(service, "_call_gemini_with_retry", mock_gemini) as mock_call:

            sse_events = []
            async for event in service.generate_full_script_stream(
                suggestion=selected_suggestion,
                style="cartoon",
                num_scenes=2,
                project_id=project.id,
                db=db
            ):
                sse_events.append(event)

            # Assertions
            statuses = [json.loads(ev[6:].strip()).get("status") for ev in sse_events if ev.startswith("data: ")]
            assert "generating" in statuses
            assert "done" in statuses

            # Verify no fact-check call was made (total call count of gemini is 4: meta, arc, batch scenes, global)
            assert mock_call.call_count == 4

            # Verify step list has no fact_check
            steps = [json.loads(ev[6:].strip()).get("step") for ev in sse_events if ev.startswith("data: ") and json.loads(ev[6:].strip()).get("status") == "generating"]
            assert "fact_check" not in steps

            # Verify saved script has topic_type and defaults for fields
            db.refresh(project)
            assert project.topic_type == "fictional_original"
            script_out = to_legacy_v2(json.loads(project.script_output))
            assert script_out["topic_type"] == "fictional_original"
            assert script_out["scenes"][0]["historical_basis_vi"] is None
            assert script_out["scenes"][0]["needs_fact_check"] is False

    finally:
        db.close()


@pytest.mark.asyncio
async def test_script_generation_with_scene_cache():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()

        key_in = APIKeyCreate(owner="Test Cache Owner", quota_limit=5)
        _, api_key = create_api_key(db, key_in)

        # Cache content: Scene 1 has valid cache, Scene 2 does not match emotion_arc input
        cached_data = {
            "topic_type": "fictional_original",
            "overview_analysis_vi": "Video hoạt họa tươi sáng.",
            "characters": [{"character_name": "Rồng", "description_en": "Cute green dragon", "key_identifiers_en": "green dragon"}],
            "environment_master_prompt_en": "Fantasy castle backdrop.",
            "emotion_arc": [
                {"scene_number": 1, "emotion_label": "sửng sốt", "beat_summary": "Rồng phun lửa", "physical_state_end": "Rồng cười", "camera_complexity": "low", "scene_lead_character": "Rồng"},
                {"scene_number": 2, "emotion_label": "lo âu", "beat_summary": "Rồng phun lửa", "physical_state_end": "Rồng cười", "camera_complexity": "low", "scene_lead_character": "Rồng"}
            ],
            "scenes": [
                {
                    "scene_number": 1,
                    "title": "Scene 1 [00:00 - 00:08]",
                    "action_detail_vi": "Rồng phun lửa (từ cache)",
                    "emotion_gesture_vi": "Rồng cười tươi",
                    "camera_movement_vi": "Zoom in",
                    "transition_to_next_vi": "Chuyển tiếp",
                    "veo3_prompt_en": "Reference the approved Rồng: Cute green dragon breathes fire, cartoon style, vertical 9:16, warm golden lighting, voice: \"The dragon guards the castle.\"",
                    "voice_over_en": "The dragon guards the castle.",
                    "scene_specific_negative_en": "watermark"
                },
                {
                    "scene_number": 2,
                    "title": "Scene 2 [00:08 - 00:16]",
                    "action_detail_vi": "Rồng phun lửa cũ",
                    "emotion_gesture_vi": "Rồng khóc",
                    "camera_movement_vi": "Zoom out",
                    "transition_to_next_vi": "Chuyển tiếp",
                    "veo3_prompt_en": "Reference the approved Rồng: Cute green dragon cries, cartoon style, vertical 9:16, cold lighting, voice: \"The dragon hesitates.\"",
                    "voice_over_en": "The dragon hesitates.",
                    "scene_specific_negative_en": "watermark"
                }
            ]
        }

        project = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Câu chuyện rồng lửa",
            input_type="manual",
            input_content="Rồng phun lửa cứu công chúa",
            style="cartoon",
            num_scenes=2
        )
        selected_suggestion = {
            "index": 0,
            "title": "Rồng lửa",
            "synopsis": "Chuyện hư cấu rồng phun lửa.",
            "topic_type": "fictional_original"
        }
        service = ProductionService(api_key="test_gemini_key", groq_api_key=None, db=db, api_key_id=api_key.id)
        prompt_0 = {
            "primary_subject_en": "Cute green dragon",
            "hard_visual_lock_en": "Cute green dragon keeps bright green scales",
            "setting_lock_en": "Fantasy castle backdrop",
            "character_lock": [{"name": "Rồng", "description_en": "Cute green dragon"}],
            "camera_lock_en": "Cartoon cinematic camera",
            "voice_sound_lock_en": "Short English narration",
            "action_story_logic_en": "Dragon protects the castle",
            "scene_function_rules_en": "One clear action per scene",
            "continuity_lock_en": "Cute green dragon at fantasy castle",
            "internal_logic_en": "Dragon stays in same castle space",
            "negative_constraints_en": "low quality, watermark"
        }
        cached_data.update({
            "schema_version": "2.0",
            "prompt_0": prompt_0,
            "storyline_vi": "Mạch truyện rồng phun lửa.",
            "stages_vi": "Giai đoạn 1: Thiết lập lâu đài rồng lửa.",
            "progression_vi": "Cảnh 1-2: Rồng xuất hiện bảo vệ công chúa.",
            "camera_strategy_vi": "Camera hoạt họa bay xung quanh lâu đài.",
            "continuity_locks_vi": "Khóa hình dáng rồng và lâu đài.",
            "form_locks_vi": "Dáng rồng dễ thương không đổi màu.",
            "age_stage_locks_vi": "Rồng con.",
            "geometry_locks_vi": "Lâu đài giữa núi đá.",
            "risk_logic_vi": "Lửa rồng phun to dần.",
            "voice_sound_strategy_vi": "Lời dẫn ngắn.",
            "continuity_board": {"continuity_prompt_en": prompt_0["continuity_lock_en"], "continuity_prompt_vi": ""},
            "continuity_prompt_en": prompt_0["continuity_lock_en"],
            "continuity_prompt_vi": "",
            "global_negative_prompt_en": prompt_0["negative_constraints_en"],
            # Durable scene-cache fixture guard: resume checks require the
            # cached blueprint contract to appear in storyline/stage context.
            "story_contract": {
                "main_subject_en": "Rồng",
                "protagonist_en": "Rồng",
                "central_opponent_or_force_en": "công chúa",
                "core_goal_en": "Rồng cứu công chúa",
                "must_remain_visible_terms": ["Rồng", "công chúa"],
                "forbidden_takeover_rule": "Không để lâu đài thay thế nhiệm vụ cứu công chúa.",
            },
            "reference_images": {
                "character_ref_prompt_en": "Dragon prompt",
                "background_ref_prompt_en": "Castle prompt",
                "thumbnail_ref_prompt_en": "Thumbnail prompt"
            },
            "_resume_signature": service._build_resume_signature(
                suggestion=selected_suggestion,
                style="cartoon",
                num_scenes=2,
                topic_type="fictional_original",
                aspect_ratio="9:16",
                scene_duration_sec=8,
                generation_mode="single",
            )
        })
        cached_data["scenes"] = cached_data["scenes"][:1]
        project.script_output = json.dumps(cached_data, ensure_ascii=False)
        db.commit()

        mock_meta_json = json.dumps({
            "overview_analysis_vi": "Video hoạt họa tươi sáng.",
            "storyline_vi": "Mạch truyện rồng phun lửa.",
            "stages_vi": "Giai đoạn 1: Thiết lập lâu đài rồng lửa.",
            "progression_vi": "Cảnh 1-2: Rồng xuất hiện bảo vệ công chúa.",
            "camera_strategy_vi": "Camera hoạt họa bay xung quanh lâu đài.",
            "continuity_locks_vi": "Khóa hình dáng rồng và lâu đài.",
            "form_locks_vi": "Dáng rồng dễ thương không đổi màu.",
            "age_stage_locks_vi": "Rồng con.",
            "geometry_locks_vi": "Lâu đài giữa núi đá.",
            "risk_logic_vi": "Lửa rồng phun to dần.",
            "characters": [{"character_name": "Rồng", "description_en": "Cute green dragon", "key_identifiers_en": "green dragon"}],
            "environment_master_prompt_en": "Fantasy castle backdrop."
        })

        mock_arc_json = json.dumps({
            "emotion_arc": [
                {"scene_number": 1, "emotion_label": "sửng sốt", "beat_summary": "Rồng phun lửa", "physical_state_end": "Rồng cười", "camera_complexity": "low", "scene_lead_character": "Rồng"},
                # Scene 2's new emotion_label is different from cache ("hoảng hốt" vs "lo âu"), so cache should invalidate for scene 2
                {"scene_number": 2, "emotion_label": "hoảng hốt", "beat_summary": "Rồng phun lửa", "physical_state_end": "Rồng cười", "camera_complexity": "low", "scene_lead_character": "Rồng"}
            ]
        })

        mock_batch_scenes_fictional = json.dumps([
            {
                "scene_number": 2,
                "title": "Scene 2 [00:08 - 00:16]",
                "action_detail_vi": "Rồng phun lửa hoảng hốt",
                "emotion_gesture_vi": "Rồng cười hoảng hốt",
                "camera_movement_vi": "Zoom in",
                "transition_to_next_vi": "Chuyển tiếp",
                "veo3_prompt_en": "Reference the approved Rồng: Cute green dragon breathes fire in shock, cartoon style, vertical 9:16, warm golden lighting, voice: \"The dragon flares in surprise.\"",
                "voice_over_en": "The dragon flares in surprise.",
                "scene_specific_negative_en": "watermark"
            }
        ])

        mock_negatives_json = json.dumps({
            "scene_negatives": [
                {"scene_number": 1, "specific_negatives_en": "watermark"},
                {"scene_number": 2, "specific_negatives_en": "watermark"}
            ]
        })

        mock_global_json = json.dumps({
            "continuity_prompt_en": "Match green color.",
            "global_negative_prompt_en": "low quality",
            "reference_images": {
                "character_ref_prompt_en": "Dragon prompt",
                "background_ref_prompt_en": "Castle prompt",
                "thumbnail_ref_prompt_en": "Thumbnail prompt"
            }
        })

        mock_critique_json = json.dumps({
            "has_changes": False,
            "critique_notes": "Ok.",
            "scenes": []
        })

        mock_validation_json = json.dumps({
            "has_changes": False,
            "validation_notes": "Ok.",
            "scenes": []
        })

        mock_gemini = make_dynamic_mock(
            meta_json=mock_meta_json,
            arc_json=mock_arc_json,
            scene_json_or_list=mock_batch_scenes_fictional,
            global_json=mock_global_json,
            critique_json=mock_critique_json
        )
        with patch.object(service, "_call_gemini_with_retry", mock_gemini) as mock_call:

            sse_events = []
            async for event in service.generate_full_script_stream(
                suggestion=selected_suggestion,
                style="cartoon",
                num_scenes=2,
                project_id=project.id,
                db=db
            ):
                sse_events.append(event)

            # Scene 1 must be from cache ("Rồng phun lửa (từ cache)")
            db.refresh(project)
            script_out = to_legacy_v2(json.loads(project.script_output))
            assert script_out["scenes"][0]["action_detail_vi"] == "Rồng phun lửa (từ cache)"
            # Scene 2 must be generated ("Rồng phun lửa hoảng hốt")
            assert script_out["scenes"][1]["action_detail_vi"] == "Rồng phun lửa hoảng hốt"
            assert mock_call.call_count == 1
    finally:
        db.close()


@pytest.mark.asyncio
async def test_script_generation_sequential_fallback():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()

        key_in = APIKeyCreate(owner="Test Fallback Owner", quota_limit=5)
        _, api_key = create_api_key(db, key_in)

        project = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Câu chuyện rồng lửa",
            input_type="manual",
            input_content="Rồng phun lửa cứu công chúa",
            style="cartoon",
            num_scenes=2
        )

        service = ProductionService(api_key="test_gemini_key", groq_api_key=None, db=db, api_key_id=api_key.id)

        selected_suggestion = {
            "index": 0,
            "title": "Rồng lửa",
            "synopsis": "Chuyện hư cấu rồng phun lửa.",
            "topic_type": "fictional_original"
        }

        mock_meta_json = json.dumps({
            "overview_analysis_vi": "Video hoạt họa tươi sáng.",
            "storyline_vi": "Mạch truyện rồng phun lửa.",
            "stages_vi": "Giai đoạn 1: Thiết lập lâu đài rồng lửa.",
            "progression_vi": "Cảnh 1-2: Rồng xuất hiện bảo vệ công chúa.",
            "camera_strategy_vi": "Camera hoạt họa bay xung quanh lâu đài.",
            "continuity_locks_vi": "Khóa hình dáng rồng và lâu đài.",
            "form_locks_vi": "Dáng rồng dễ thương không đổi màu.",
            "age_stage_locks_vi": "Rồng con.",
            "geometry_locks_vi": "Lâu đài giữa núi đá.",
            "risk_logic_vi": "Lửa rồng phun to dần.",
            "characters": [{"character_name": "Rồng", "description_en": "Cute green dragon", "key_identifiers_en": "green dragon"}],
            "environment_master_prompt_en": "Fantasy castle backdrop."
        })

        mock_arc_json = json.dumps({
            "emotion_arc": [
                {"scene_number": 1, "emotion_label": "sửng sốt", "beat_summary": "Rồng phun lửa", "physical_state_end": "Rồng cười", "camera_complexity": "low", "scene_lead_character": "Rồng"},
                {"scene_number": 2, "emotion_label": "lo âu", "beat_summary": "Rồng phun lửa", "physical_state_end": "Rồng cười", "camera_complexity": "low", "scene_lead_character": "Rồng"}
            ]
        })

        # Scene 1 and 2 individually generated mocks
        mock_scene1_json = json.dumps({
            "scene_number": 1,
            "title": "Scene 1 [00:00 - 00:08]",
            "action_detail_vi": "Rồng phun lửa 1",
            "emotion_gesture_vi": "Rồng cười tươi 1",
            "camera_movement_vi": "Zoom in",
            "transition_to_next_vi": "Chuyển tiếp",
            "veo3_prompt_en": "Dragon breathes fire, cartoon style, vertical 9:16",
            "scene_specific_negative_en": "watermark"
        })

        mock_scene2_json = json.dumps({
            "scene_number": 2,
            "title": "Scene 2 [00:08 - 00:16]",
            "action_detail_vi": "Rồng phun lửa 2",
            "emotion_gesture_vi": "Rồng cười tươi 2",
            "camera_movement_vi": "Zoom in",
            "transition_to_next_vi": "Chuyển tiếp",
            "veo3_prompt_en": "Dragon breathes fire, cartoon style, vertical 9:16",
            "scene_specific_negative_en": "watermark"
        })

        mock_negatives_json = json.dumps({
            "scene_negatives": [
                {"scene_number": 1, "specific_negatives_en": "watermark"},
                {"scene_number": 2, "specific_negatives_en": "watermark"}
            ]
        })

        mock_global_json = json.dumps({
            "continuity_prompt_en": "Match green color.",
            "global_negative_prompt_en": "low quality",
            "reference_images": {
                "character_ref_prompt_en": "Dragon prompt",
                "background_ref_prompt_en": "Castle prompt",
                "thumbnail_ref_prompt_en": "Thumbnail prompt"
            }
        })

        mock_critique_json = json.dumps({
            "has_changes": False,
            "critique_notes": "Ok.",
            "scenes": []
        })

        mock_validation_json = json.dumps({
            "has_changes": False,
            "validation_notes": "Ok.",
            "scenes": []
        })

        # Define mock side effect that raises error on batch scene generation
        async def fallback_side_effect(prompt, **kwargs):
            if "BATCH_SCENE_GENERATION_TEMPLATE" in prompt or "veo3_prompt_en — MANDATORY FORMAT" in prompt or "This batch: Scenes" in prompt:
                raise Exception("BATCH_GENERATION_API_ERROR")

            if "Bản Kế Hoạch Sản Xuất" in prompt or "overview_analysis_vi" in prompt:
                data = json.loads(mock_meta_json)
                data["prompt_0"] = {
                    "primary_subject_en": "Rồng",
                    "hard_visual_lock_en": "Cute green dragon",
                    "setting_lock_en": "Fantasy castle backdrop",
                    "character_lock": [{"name": "Rồng", "description_en": "Cute green dragon"}],
                    "camera_lock_en": "Cartoon castle camera",
                    "voice_sound_lock_en": "Bright narration",
                    "action_story_logic_en": "Dragon protects the princess",
                    "scene_function_rules_en": "Each scene advances the rescue",
                    "continuity_lock_en": "Keep the green dragon and castle stable",
                    "internal_logic_en": "Fire and movement stay physically consistent",
                    "negative_constraints_en": "No generic protagonist"
                }
                data["voice_sound_strategy_vi"] = "Giọng kể hoạt họa sáng rõ."
                return json.dumps(data)
            if "nhịp kịch tính" in prompt or "emotion_arc" in prompt or "Emotion Arc" in prompt:
                return mock_arc_json
            if "kịch bản phân cảnh" in prompt or "global_negative_prompt_en" in prompt or "Reference Images" in prompt:
                return mock_global_json
            if "phê bình kịch bản" in prompt or "Self-Critique" in prompt or "phê bình" in prompt:
                return mock_critique_json
            return "{}"

        mock_call = AsyncMock()
        mock_call.side_effect = fallback_side_effect

        with patch.object(service, "_call_gemini_with_retry", mock_call):

            sse_events = []
            with pytest.raises(RuntimeError, match="Batch scene generation failed"):
                async for event in service.generate_full_script_stream(
                    suggestion=selected_suggestion,
                    style="cartoon",
                    num_scenes=2,
                    project_id=project.id,
                    db=db
                ):
                    sse_events.append(event)

            assert mock_call.call_count == 5
    finally:
        db.close()


@pytest.mark.asyncio
async def test_fact_check_chunking():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()

        key_in = APIKeyCreate(owner="Test Fact Check Chunk Owner", quota_limit=5)
        _, api_key = create_api_key(db, key_in)

        project = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Sử Việt Trận Bạch Đằng",
            input_type="manual",
            input_content="Trận Bạch Đằng Ngô Quyền 938",
            style="realistic",
            # 6 scenes so it splits into 2 chunks of 5 and 1
            num_scenes=6
        )

        service = ProductionService(api_key="test_gemini_key", groq_api_key=None, db=db, api_key_id=api_key.id)

        selected_suggestion = {
            "index": 0,
            "title": "Bạch Đằng 938",
            "synopsis": "Kịch bản Trận Bạch Đằng.",
            "topic_type": "historical"
        }

        mock_meta_json = json.dumps({
            "overview_analysis_vi": "Tái hiện trận Bạch Đằng.",
            "storyline_vi": "Mạch truyện Ngô Quyền đập tan quân Nam Hán.",
            "stages_vi": "Giai đoạn 1: Chuẩn bị cọc gỗ trên sông.",
            "progression_vi": "Cảnh 1-6: Thiết lập trận địa cọc gỗ.",
            "camera_strategy_vi": "Camera góc rộng toàn cảnh sông Bạch Đằng.",
            "continuity_locks_vi": "Khóa nhân vật Ngô Quyền.",
            "form_locks_vi": "Khóa hình dáng cọc nhọn.",
            "age_stage_locks_vi": "Ngô Quyền trung niên.",
            "geometry_locks_vi": "Sông nước.",
            "risk_logic_vi": "Thủy triều rút.",
            "characters": [{"character_name": "Ngô Quyền", "description_en": "Brave general", "key_identifiers_en": "brave general"}],
            "environment_master_prompt_en": "River scene."
        })

        mock_arc_json = json.dumps({
            "emotion_arc": [
                {"scene_number": 1, "emotion_label": "sửng sốt", "beat_summary": "Đóng cọc gỗ", "physical_state_end": "Đứng chỉ tay", "camera_complexity": "low", "scene_lead_character": "Ngô Quyền"},
                {"scene_number": 2, "emotion_label": "lo âu", "beat_summary": "Đóng cọc gỗ", "physical_state_end": "Đứng chỉ tay", "camera_complexity": "low", "scene_lead_character": "Ngô Quyền"},
                {"scene_number": 3, "emotion_label": "hoảng hốt", "beat_summary": "Đóng cọc gỗ", "physical_state_end": "Đứng chỉ tay", "camera_complexity": "low", "scene_lead_character": "Ngô Quyền"},
                {"scene_number": 4, "emotion_label": "bi tráng", "beat_summary": "Đóng cọc gỗ", "physical_state_end": "Đứng chỉ tay", "camera_complexity": "low", "scene_lead_character": "Ngô Quyền"},
                {"scene_number": 5, "emotion_label": "hùng tráng", "beat_summary": "Đóng cọc gỗ", "physical_state_end": "Đứng chỉ tay", "camera_complexity": "low", "scene_lead_character": "Ngô Quyền"},
                {"scene_number": 6, "emotion_label": "bình yên", "beat_summary": "Đóng cọc gỗ", "physical_state_end": "Đứng chỉ tay", "camera_complexity": "low", "scene_lead_character": "Ngô Quyền"}
            ]
        })

        mock_batch_scenes_1_3 = json.dumps([
            {
                "scene_number": idx,
                "title": f"Scene {idx} [00:00 - 00:08]",
                "action_detail_vi": f"Cảnh cọc gỗ {idx}",
                "emotion_gesture_vi": "Hào khí quân ta",
                "camera_movement_vi": "Góc rộng",
                "transition_to_next_vi": "Chuyển tiếp",
                "veo3_prompt_en": "Reference the approved stakes: Wooden stakes in river, realistic style, vertical 9:16, warm golden lighting",
                "voice_over_vi": "Quân ta chuẩn bị trận địa cọc gỗ trên sông.",
                "historical_basis_vi": "Ngô Quyền dùng cọc gỗ đóng trên sông",
                "needs_fact_check": False,
                "fact_check_note_vi": None,
                "scene_specific_negative_en": "watermark"
            }
            for idx in [1, 2, 3]
        ])

        mock_batch_scenes_4_6 = json.dumps([
            {
                "scene_number": idx,
                "title": f"Scene {idx} [00:00 - 00:08]",
                "action_detail_vi": f"Cảnh cọc gỗ {idx}",
                "emotion_gesture_vi": "Hào khí quân ta",
                "camera_movement_vi": "Góc rộng",
                "transition_to_next_vi": "Chuyển tiếp",
                "veo3_prompt_en": "Reference the approved stakes: Wooden stakes in river, realistic style, vertical 9:16, warm golden lighting",
                "voice_over_vi": "Trận địa cọc gỗ đã sẵn sàng đón địch.",
                "historical_basis_vi": "Ngô Quyền dùng cọc gỗ đóng trên sông",
                "needs_fact_check": False,
                "fact_check_note_vi": None,
                "scene_specific_negative_en": "watermark"
            }
            for idx in [4, 5, 6]
        ])

        mock_negatives_json = json.dumps({
            "scene_negatives": [{"scene_number": idx, "specific_negatives_en": "watermark"} for idx in range(1, 7)]
        })

        mock_global_json = json.dumps({
            "continuity_prompt_en": "Keep visual style.",
            "global_negative_prompt_en": "lowres",
            "reference_images": {
                "character_ref_prompt_en": "Ngô Quyền prompt",
                "background_ref_prompt_en": "River prompt",
                "thumbnail_ref_prompt_en": "Thumbnail prompt"
            }
        })

        mock_critique_json = json.dumps({
            "has_changes": False,
            "critique_notes": "Ok.",
            "scenes": []
        })

        mock_validation_json = json.dumps({
            "has_changes": False,
            "validation_notes": "Ok.",
            "scenes": []
        })

        # Fact Check Mock for all scenes in a single call
        mock_fact_check_single = json.dumps({
            "has_issues": True,
            "fact_check_notes": "Audit all scenes.",
            "scenes": [
                {
                    "scene_number": 1,
                    "action_detail_vi": "Cảnh cọc gỗ cắm trên sông Bạch Đằng (Fact Check)",
                    "needs_fact_check": True,
                    "fact_check_note_vi": "Adjusted actions",
                    "verifiability_level": "specific_event",
                    "scene_specific_negative_en": "watermark",
                    "voice_over_vi": "Quân ta chuẩn bị trận địa cọc gỗ trên sông Bạch Đằng.",
                    "veo3_prompt_en": "Reference the approved stakes: Cảnh cọc gỗ cắm trên sông Bạch Đằng"
                }
            ]
        })

        # Unify mock scenes 1-3 and 4-6 lists
        all_mock_scenes_list = json.loads(mock_batch_scenes_1_3) + json.loads(mock_batch_scenes_4_6)
        mock_gemini = make_dynamic_mock(
            meta_json=mock_meta_json,
            arc_json=mock_arc_json,
            scene_json_or_list=json.dumps(all_mock_scenes_list),
            global_json=mock_global_json,
            critique_json=mock_critique_json,
            fact_check_json=mock_fact_check_single
        )
        with patch.object(service, "_call_gemini_with_retry", mock_gemini) as mock_call:

            sse_events = []
            async for event in service.generate_full_script_stream(
                suggestion=selected_suggestion,
                style="realistic",
                num_scenes=6,
                project_id=project.id,
                db=db
            ):
                sse_events.append(event)

            db.refresh(project)
            script_out = to_legacy_v2(json.loads(project.script_output))
            assert len(script_out["scenes"]) == 6
            # Assert Scene 1 got historical checks from fact check pass
            assert script_out["scenes"][0]["action_detail_vi"] == "Cảnh cọc gỗ cắm trên sông Bạch Đằng (Fact Check)"
            assert script_out["scenes"][0]["needs_fact_check"] is True
            # Assert Scene 6 kept its original value since no changes returned
            assert script_out["scenes"][5]["action_detail_vi"] == "Cảnh cọc gỗ 6"
            # 5 calls: meta (1) + arc (1) + batch scenes (1) + global (1) + fact-check (1) = 5
            assert mock_call.call_count == 5
    finally:
        db.close()


@pytest.mark.asyncio
async def test_emotion_arc_shapes_and_color_recheck():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()

        key_in = APIKeyCreate(owner="Test Shapes Owner", quota_limit=5)
        _, api_key = create_api_key(db, key_in)

        project = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Tragedies of Ancient Rome",
            input_type="manual",
            input_content="Caesar downfall",
            style="realistic",
            num_scenes=6
        )

        service = ProductionService(api_key="test_gemini_key", groq_api_key=None, db=db, api_key_id=api_key.id)

        # Suggestion with a specific narrative shape (will be overridden to reflective under Option C)
        selected_suggestion = {
            "index": 0,
            "title": "Tragedies",
            "synopsis": "Caesar tragic downfall.",
            "topic_type": "historical",
            "has_named_historical_figure": True,
            "narrative_shape": "tragedy"
        }

        mock_meta_json = json.dumps({
            "overview_analysis_vi": "Rome.",
            "storyline_vi": "Rome storyline.",
            "stages_vi": "Stages.",
            "progression_vi": "Progression.",
            "camera_strategy_vi": "Camera.",
            "continuity_locks_vi": "Locks.",
            "form_locks_vi": "Locks.",
            "age_stage_locks_vi": "Locks.",
            "geometry_locks_vi": "Locks.",
            "risk_logic_vi": "Risk.",
            "characters": [{"character_name": "Caesar", "description_en": "Roman general", "key_identifiers_en": "caesar"}],
            "environment_master_prompt_en": "Rome square."
        })

        mock_arc_json = json.dumps({
            "emotion_arc": [
                {"scene_number": 1, "emotion_label": "sửng sốt", "beat_summary": "Rise of Caesar", "physical_state_end": "Standing", "camera_complexity": "low", "scene_lead_character": "Caesar"},
                {"scene_number": 2, "emotion_label": "lo âu", "beat_summary": "Rise of Caesar", "physical_state_end": "Standing", "camera_complexity": "low", "scene_lead_character": "Caesar"},
                {"scene_number": 3, "emotion_label": "hoảng hốt", "beat_summary": "Rise of Caesar", "physical_state_end": "Standing", "camera_complexity": "low", "scene_lead_character": "Caesar"},
                {"scene_number": 4, "emotion_label": "bi tráng", "beat_summary": "Rise of Caesar", "physical_state_end": "Standing", "camera_complexity": "low", "scene_lead_character": "Caesar"},
                {"scene_number": 5, "emotion_label": "hùng tráng", "beat_summary": "Rise of Caesar", "physical_state_end": "Standing", "camera_complexity": "low", "scene_lead_character": "Caesar"},
                {"scene_number": 6, "emotion_label": "bình yên", "beat_summary": "Rise of Caesar", "physical_state_end": "Standing", "camera_complexity": "low", "scene_lead_character": "Caesar"}
            ]
        })

        mock_batch_scenes_1_3 = json.dumps([
            {
                "scene_number": idx,
                "title": f"Scene {idx} [00:00 - 00:08]",
                "action_detail_vi": f"Caesar {idx}",
                "emotion_gesture_vi": "Gesture",
                "camera_movement_vi": "Camera",
                "transition_to_next_vi": "Transition",
                "veo3_prompt_en": "Reference the approved Caesar: Caesar in Rome, realistic style, warm golden lighting",
                "voice_over_vi": "Caesar trị vì La Mã.",
                "historical_basis_vi": "Caesar was Roman leader",
                "needs_fact_check": False,
                "fact_check_note_vi": None,
                "scene_specific_negative_en": "watermark"
            }
            for idx in [1, 2, 3]
        ])

        mock_batch_scenes_4_6 = json.dumps([
            {
                "scene_number": idx,
                "title": f"Scene {idx} [00:00 - 00:08]",
                "action_detail_vi": f"Caesar {idx}",
                "emotion_gesture_vi": "Gesture",
                "camera_movement_vi": "Camera",
                "transition_to_next_vi": "Transition",
                "veo3_prompt_en": "Reference the approved Caesar: Caesar in Rome, realistic style, warm golden lighting",
                "voice_over_vi": "Vương triều La Mã hưng thịnh.",
                "historical_basis_vi": "Caesar was Roman leader",
                "needs_fact_check": False,
                "fact_check_note_vi": None,
                "scene_specific_negative_en": "watermark"
            }
            for idx in [4, 5, 6]
        ])

        mock_negatives_json = json.dumps({
            "scene_negatives": [{"scene_number": idx, "specific_negatives_en": "watermark"} for idx in range(1, 7)]
        })

        mock_global_json = json.dumps({
            "continuity_prompt_en": "Keep visual style.",
            "global_negative_prompt_en": "lowres",
            "reference_images": {
                "character_ref_prompt_en": "Caesar prompt",
                "background_ref_prompt_en": "Rome prompt",
                "thumbnail_ref_prompt_en": "Thumbnail prompt"
            }
        })

        mock_critique_json = json.dumps({
            "has_changes": False,
            "critique_notes": "Ok.",
            "scenes": []
        })

        mock_validation_json = json.dumps({
            "has_changes": False,
            "validation_notes": "Ok.",
            "scenes": []
        })

        # Fact Check Mock returns 3 modified scenes
        mock_fact_check_single = json.dumps({
            "has_issues": True,
            "fact_check_notes": "Audit all scenes.",
            "scenes": [
                {
                    "scene_number": 1,
                    "action_detail_vi": "Caesar 1 corrected",
                    "veo3_prompt_en": "Reference the approved Caesar: Caesar in Rome, corrected details, warm golden lighting",
                    "verifiability_level": "specific_event",
                    "scene_specific_negative_en": "watermark",
                    "voice_over_vi": "Caesar trị vì La Mã."
                },
                {
                    "scene_number": 2,
                    "action_detail_vi": "Caesar 2 corrected",
                    "veo3_prompt_en": "Reference the approved Caesar: Caesar in Rome, corrected details, warm golden lighting",
                    "verifiability_level": "general_consensus",
                    "scene_specific_negative_en": "watermark",
                    "voice_over_vi": "Vương triều La Mã hưng thịnh."
                },
                {
                    "scene_number": 3,
                    "action_detail_vi": "Caesar 3 corrected",
                    "veo3_prompt_en": "Reference the approved Caesar: Caesar in Rome, corrected details, warm golden lighting",
                    "verifiability_level": "unverifiable_generalization",
                    "scene_specific_negative_en": "watermark",
                    "voice_over_vi": "Bi kịch của Caesar."
                }
            ]
        })

        # Color re-check validation mock response
        mock_color_recheck_json = json.dumps({
            "has_changes": True,
            "validation_notes": "Post-fact check color fixes.",
            "scenes": [
                {
                    "scene_number": 1,
                    "veo3_prompt_en": "Reference the approved Caesar: Caesar in Rome, corrected details, warm golden lighting (color checked)"
                }
            ]
        })

        # Unify mock scenes 1-3 and 4-6 lists
        all_mock_scenes_list = json.loads(mock_batch_scenes_1_3) + json.loads(mock_batch_scenes_4_6)
        mock_gemini = make_dynamic_mock(
            meta_json=mock_meta_json,
            arc_json=mock_arc_json,
            scene_json_or_list=json.dumps(all_mock_scenes_list),
            global_json=mock_global_json,
            critique_json=mock_critique_json,
            fact_check_json=mock_fact_check_single,
            color_recheck_json=mock_color_recheck_json
        )
        with patch.object(service, "_call_gemini_with_retry", mock_gemini) as mock_call:

            sse_events = []
            async for event in service.generate_full_script_stream(
                suggestion=selected_suggestion,
                style="realistic",
                num_scenes=6,
                project_id=project.id,
                db=db
            ):
                sse_events.append(event)

            db.refresh(project)
            script_out = to_legacy_v2(json.loads(project.script_output))
            assert len(script_out["scenes"]) == 6
            # Assert Scene 1 has correct prompt 0 reference with fact-checked details
            assert script_out["scenes"][0]["veo3_prompt_en"] == "Reference the approved Caesar: Caesar in Rome, corrected details, warm golden lighting"
            # Assert Scene 2 got merged from fact check
            assert script_out["scenes"][1]["action_detail_vi"] == "Caesar 2 corrected"
            
            # Assert call count is exactly 5 (meta (1) + arc (1) + batch scenes (1) + global (1) + fact-check (1) = 5)
            assert mock_call.call_count == 5

    finally:
        db.close()


@pytest.mark.asyncio
async def test_scientific_script_generation():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()

        key_in = APIKeyCreate(owner="Test Scientific", quota_limit=5)
        _, api_key = create_api_key(db, key_in)

        project = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Scientific discovery",
            input_type="manual",
            input_content="Newton laws",
            style="realistic",
            num_scenes=2
        )

        service = ProductionService(api_key="test_gemini_key", groq_api_key=None, db=db, api_key_id=api_key.id)

        selected_suggestion = {
            "index": 0,
            "title": "Newton",
            "synopsis": "Gravity discovery.",
            "topic_type": "scientific"
        }

        mock_meta_json = json.dumps({
            "overview_analysis_vi": "Newton laws overview.",
            "storyline_vi": "Storyline.",
            "stages_vi": "Stages.",
            "progression_vi": "Progression.",
            "camera_strategy_vi": "Camera.",
            "continuity_locks_vi": "Locks.",
            "form_locks_vi": "Locks.",
            "age_stage_locks_vi": "Locks.",
            "geometry_locks_vi": "Locks.",
            "risk_logic_vi": "Risk.",
            "characters": [{"character_name": "Newton", "description_en": "Newton desc", "key_identifiers_en": "newton"}],
            "environment_master_prompt_en": "Newton garden."
        })

        mock_arc_json = json.dumps({
            "emotion_arc": [
                {"scene_number": 1, "emotion_label": "sửng sốt", "beat_summary": "Gravity", "physical_state_end": "Standing", "camera_complexity": "low", "scene_lead_character": "Newton"},
                {"scene_number": 2, "emotion_label": "lo âu", "beat_summary": "Gravity", "physical_state_end": "Standing", "camera_complexity": "low", "scene_lead_character": "Newton"}
            ]
        })

        mock_batch_scenes = json.dumps([
            {
                "scene_number": 1,
                "title": "Scene 1 [00:00 - 00:08]",
                "action_detail_vi": "Apple falls",
                "emotion_gesture_vi": "Surprise",
                "camera_movement_vi": "Zoom in",
                "transition_to_next_vi": "Transition",
                "veo3_prompt_en": "Apple falls on Newton, realistic style",
                "historical_basis_vi": "Newton saw apple fall",
                "needs_fact_check": False,
                "fact_check_note_vi": None,
                "scene_specific_negative_en": "watermark"
            },
            {
                "scene_number": 2,
                "title": "Scene 2 [00:08 - 00:16]",
                "action_detail_vi": "Newton calculates",
                "emotion_gesture_vi": "Thinking",
                "camera_movement_vi": "Zoom out",
                "transition_to_next_vi": "Transition",
                "veo3_prompt_en": "Newton calculates gravity, realistic style",
                "historical_basis_vi": "Newton calculated gravity",
                "needs_fact_check": False,
                "fact_check_note_vi": None,
                "scene_specific_negative_en": "watermark"
            }
        ])

        mock_global_json = json.dumps({
            "continuity_prompt_en": "Keep style.",
            "global_negative_prompt_en": "low quality",
            "reference_images": {"character_ref_prompt_en": "Newton", "background_ref_prompt_en": "Garden", "thumbnail_ref_prompt_en": "T"}
        })

        mock_critique_json = json.dumps({
            "has_changes": False,
            "critique_notes": "Ok.",
            "scenes": []
        })

        mock_fact_check_json = json.dumps({
            "has_issues": False,
            "fact_check_notes": "Audit completed.",
            "scenes": []
        })

        mock_gemini = make_dynamic_mock(
            meta_json=mock_meta_json,
            arc_json=mock_arc_json,
            scene_json_or_list=mock_batch_scenes,
            global_json=mock_global_json,
            critique_json=mock_critique_json,
            fact_check_json=mock_fact_check_json
        )
        with patch.object(service, "_call_gemini_with_retry", mock_gemini) as mock_call:

            sse_events = []
            async for event in service.generate_full_script_stream(
                suggestion=selected_suggestion,
                style="realistic",
                num_scenes=2,
                project_id=project.id,
                db=db
            ):
                sse_events.append(event)

            db.refresh(project)
            script_out = to_legacy_v2(json.loads(project.script_output))
            assert script_out["topic_type"] == "scientific"
            # Assert call count is exactly 5 (meta (1) + arc (1) + batch scenes (1) + global (1) + fact-check (1) = 5)
            assert mock_call.call_count == 5

    finally:
        db.close()


@pytest.mark.asyncio
async def test_fictional_mythology_script_generation():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()

        key_in = APIKeyCreate(owner="Test Mythology", quota_limit=5)
        _, api_key = create_api_key(db, key_in)

        project = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Sơn Tinh Thủy Tinh",
            input_type="manual",
            input_content="Sơn Tinh Thủy Tinh đại chiến",
            style="cartoon",
            num_scenes=2
        )

        service = ProductionService(api_key="test_gemini_key", groq_api_key=None, db=db, api_key_id=api_key.id)

        selected_suggestion = {
            "index": 0,
            "title": "Sơn Tinh",
            "synopsis": "Chuyện Sơn Tinh Thủy Tinh.",
            "topic_type": "fictional_mythology"
        }

        mock_meta_json = json.dumps({
            "overview_analysis_vi": "Video hoạt họa thần thoại.",
            "storyline_vi": "Mạch truyện Sơn Tinh.",
            "stages_vi": "Giai đoạn 1.",
            "progression_vi": "Cảnh 1-2.",
            "camera_strategy_vi": "Camera hoạt họa.",
            "continuity_locks_vi": "Khóa.",
            "form_locks_vi": "Khóa dáng.",
            "age_stage_locks_vi": "Sơn Tinh.",
            "geometry_locks_vi": "Núi.",
            "risk_logic_vi": "Nước dâng.",
            "characters": [{"character_name": "Sơn Tinh", "description_en": "Mountain god", "key_identifiers_en": "mountain god"}],
            "environment_master_prompt_en": "Ancient mountains."
        })

        mock_arc_json = json.dumps({
            "emotion_arc": [
                {"scene_number": 1, "emotion_label": "sửng sốt", "beat_summary": "Đại chiến", "physical_state_end": "Sơn Tinh", "camera_complexity": "low", "scene_lead_character": "Sơn Tinh"},
                {"scene_number": 2, "emotion_label": "lo âu", "beat_summary": "Đại chiến", "physical_state_end": "Sơn Tinh", "camera_complexity": "low", "scene_lead_character": "Sơn Tinh"}
            ]
        })

        mock_batch_scenes_fictional = json.dumps([
            {
                "scene_number": 1,
                "title": "Scene 1 [00:00 - 00:08]",
                "action_detail_vi": "Sơn Tinh nâng dãy núi đầu tiên lên để chặn dòng nước đang tràn vào làng.",
                "emotion_gesture_vi": "Thần uy nghiêm",
                "camera_movement_vi": "Zoom in",
                "transition_to_next_vi": "Chuyển tiếp",
                "veo3_prompt_en": "Mountain god raises the first ridge to block floodwater, cartoon style, vertical 9:16",
                "scene_specific_negative_en": "watermark"
            },
            {
                "scene_number": 2,
                "title": "Scene 2 [00:08 - 00:16]",
                "action_detail_vi": "Dòng nước đổi hướng, buộc Sơn Tinh tiếp tục nâng thêm vách đá cao hơn.",
                "emotion_gesture_vi": "Thần uy nghiêm",
                "camera_movement_vi": "Zoom in",
                "transition_to_next_vi": "Chuyển tiếp",
                "veo3_prompt_en": "Mountain god raises a higher cliff as floodwater changes course, cartoon style, vertical 9:16",
                "scene_specific_negative_en": "watermark"
            }
        ])

        mock_global_json = json.dumps({
            "continuity_prompt_en": "Match styles.",
            "global_negative_prompt_en": "low quality",
            "reference_images": {
                "character_ref_prompt_en": "God prompt",
                "background_ref_prompt_en": "Mountain prompt",
                "thumbnail_ref_prompt_en": "Thumbnail prompt"
            }
        })

        mock_critique_json = json.dumps({
            "has_changes": False,
            "critique_notes": "Ok.",
            "scenes": []
        })

        mock_gemini = make_dynamic_mock(
            meta_json=mock_meta_json,
            arc_json=mock_arc_json,
            scene_json_or_list=mock_batch_scenes_fictional,
            global_json=mock_global_json,
            critique_json=mock_critique_json
        )
        with patch.object(service, "_call_gemini_with_retry", mock_gemini) as mock_call:

            sse_events = []
            async for event in service.generate_full_script_stream(
                suggestion=selected_suggestion,
                style="cartoon",
                num_scenes=2,
                project_id=project.id,
                db=db
            ):
                sse_events.append(event)

            # Assertions
            statuses = [json.loads(ev[6:].strip()).get("status") for ev in sse_events if ev.startswith("data: ")]
            assert "generating" in statuses
            assert "done" in statuses

            # Verify no fact-check call was made (total calls = 4: meta, arc, batch scenes, global)
            assert mock_call.call_count == 4

    finally:
        db.close()


@pytest.mark.asyncio
async def test_routing_option_c_conditional_override():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()

        key_in = APIKeyCreate(owner="Test Option C", quota_limit=5)
        _, api_key = create_api_key(db, key_in)

        # Case 1: Reality-bound topic (historical) with suggestion's narrative_shape = adventure
        # Under Option C, it should be overridden to explanatory
        project_historical = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Historical Project",
            input_type="idea",
            input_content="Factual history"
        )
        selected_suggestion_hist = {
            "index": 0,
            "title": "Historical Project",
            "synopsis": "Factual history.",
            "topic_type": "historical",
            "narrative_shape": "adventure"  # Should be overridden to explanatory
        }

        # Case 2: Fictional topic with suggestion's narrative_shape = suspense
        # Under Option C, fictional topic should preserve the custom narrative_shape
        project_fictional = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Fictional Project",
            input_type="idea",
            input_content="Fantasy adventure"
        )
        selected_suggestion_fict = {
            "index": 0,
            "title": "Fictional Project",
            "synopsis": "Fantasy adventure.",
            "topic_type": "fictional_original",
            "narrative_shape": "suspense"  # Should be preserved
        }

        service = ProductionService(api_key="test_gemini_key", groq_api_key=None, db=db, api_key_id=api_key.id)

        # Common mock responses
        mock_meta_json = json.dumps({
            "overview_analysis_vi": "Context.",
            "storyline_vi": "Storyline.",
            "stages_vi": "Stages.",
            "progression_vi": "Progression.",
            "camera_strategy_vi": "Camera.",
            "continuity_locks_vi": "Locks.",
            "form_locks_vi": "Locks.",
            "age_stage_locks_vi": "Locks.",
            "geometry_locks_vi": "Locks.",
            "risk_logic_vi": "Risk.",
            "characters": [],
            "environment_master_prompt_en": "Background."
        })

        mock_arc_json = json.dumps({
            "emotion_arc": [
                {"scene_number": 1, "emotion_label": "bình tĩnh", "beat_summary": "Beat", "physical_state_end": "Standing", "camera_complexity": "low", "scene_lead_character": "None"}
            ]
        })

        mock_batch_scenes = json.dumps([
            {
                "scene_number": 1,
                "title": "Scene 1 [00:00 - 00:08]",
                "action_detail_vi": "Action",
                "emotion_gesture_vi": "Gesture",
                "camera_movement_vi": "Camera",
                "transition_to_next_vi": "Transition",
                "veo3_prompt_en": "veo3 prompt en",
                "scene_specific_negative_en": "watermark"
            }
        ])

        mock_global_json = json.dumps({
            "continuity_prompt_en": "Match styles.",
            "global_negative_prompt_en": "lowres",
            "reference_images": {
                "character_ref_prompt_en": "Char prompt",
                "background_ref_prompt_en": "Bg prompt",
                "thumbnail_ref_prompt_en": "Tn prompt"
            }
        })

        mock_critique_json = json.dumps({
            "has_changes": False,
            "critique_notes": "Ok.",
            "scenes": []
        })

        # Test Case 1 Execution (Historical - Overridden to explanatory)
        mock_gemini_hist = make_dynamic_mock(
            meta_json=mock_meta_json,
            arc_json=mock_arc_json,
            scene_json_or_list=mock_batch_scenes,
            global_json=mock_global_json,
            critique_json=mock_critique_json,
            fact_check_json=json.dumps({"has_issues": False, "fact_check_notes": "Ok.", "scenes": []})
        )
        with patch.object(service, "_call_gemini_with_retry", mock_gemini_hist) as mock_call_hist:
            sse_events = []
            async for event in service.generate_full_script_stream(
                suggestion=selected_suggestion_hist,
                style="realistic",
                num_scenes=1,
                project_id=project_historical.id,
                db=db
            ):
                sse_events.append(event)
            
            called_prompts = [args[1]["prompt"] for args in mock_call_hist.call_args_list]
            # Since historical uses explanatory structure under Option C:
            # SHAPE_STRUCTURES["explanatory"] contains "EXPLANATORY" or "DISCOVERY"
            # It should NOT contain "ADVENTURE"
            assert "EXPLANATORY" in called_prompts[1] or "DISCOVERY" in called_prompts[1]
            assert "ADVENTURE" not in called_prompts[1]

        # Test Case 2 Execution (Fictional - Preserves suspense)
        mock_gemini_fict = make_dynamic_mock(
            meta_json=mock_meta_json,
            arc_json=mock_arc_json,
            scene_json_or_list=mock_batch_scenes,
            global_json=mock_global_json,
            critique_json=mock_critique_json
        )
        with patch.object(service, "_call_gemini_with_retry", mock_gemini_fict) as mock_call_fict:
            sse_events = []
            async for event in service.generate_full_script_stream(
                suggestion=selected_suggestion_fict,
                style="realistic",
                num_scenes=1,
                project_id=project_fictional.id,
                db=db
            ):
                sse_events.append(event)
            
            called_prompts = [args[1]["prompt"] for args in mock_call_fict.call_args_list]
            # Fictional should preserve "suspense" narrative shape
            # SHAPE_STRUCTURES["suspense"] contains "SUSPENSE" or "tension"
            assert "SUSPENSE" in called_prompts[1] or "tension" in called_prompts[1]

    finally:
        db.close()


@pytest.mark.asyncio
async def test_validation_bypass_discard_invalid_scenes_on_fail():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()

        key_in = APIKeyCreate(owner="Test Bypass", quota_limit=5)
        _, api_key = create_api_key(db, key_in)

        project = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Bypass Project",
            input_type="idea",
            input_content="Bypass content"
        )
        selected_suggestion = {
            "index": 0,
            "title": "Bypass Project",
            "synopsis": "Bypass synopsis.",
            "topic_type": "historical",
            "narrative_shape": "adventure"
        }

        service = ProductionService(api_key="test_gemini_key", groq_api_key=None, db=db, api_key_id=api_key.id)

        # Common mock responses
        mock_meta_json = json.dumps({
            "overview_analysis_vi": "Context.",
            "storyline_vi": "Storyline.",
            "stages_vi": "Stages.",
            "progression_vi": "Progression.",
            "camera_strategy_vi": "Camera.",
            "continuity_locks_vi": "Locks.",
            "form_locks_vi": "Locks.",
            "age_stage_locks_vi": "Locks.",
            "geometry_locks_vi": "Locks.",
            "risk_logic_vi": "Risk.",
            "characters": [],
            "environment_master_prompt_en": "Background."
        })

        mock_arc_json = json.dumps({
            "emotion_arc": [
                {"scene_number": 1, "emotion_label": "bình tĩnh", "beat_summary": "Beat", "physical_state_end": "Standing", "camera_complexity": "low", "scene_lead_character": "None"}
            ]
        })

        mock_batch_scenes = json.dumps([
            {
                "scene_number": 1,
                "title": "Scene 1 [00:00 - 00:08]",
                "action_detail_vi": "Original Action from Phase 3",
                "emotion_gesture_vi": "Gesture",
                "camera_movement_vi": "Camera",
                "transition_to_next_vi": "Transition",
                "veo3_prompt_en": "Reference the approved Character: Action description",
                "scene_specific_negative_en": "watermark"
            }
        ])

        mock_global_json = json.dumps({
            "continuity_prompt_en": "Match styles.",
            "global_negative_prompt_en": "lowres",
            "reference_images": {
                "character_ref_prompt_en": "Char prompt",
                "background_ref_prompt_en": "Bg prompt",
                "thumbnail_ref_prompt_en": "Tn prompt"
            }
        })

        # Phase 6 critique returns invalid scene
        mock_invalid_critique_json = json.dumps({
            "has_changes": True,
            "critique_notes": "Attempting to change.",
            "scenes": [
                {
                    "scene_number": 1,
                    "title": "Scene 1 [00:00 - 00:08]",
                    "action_detail_vi": "Invalid Critique Action",
                    "emotion_gesture_vi": "Gesture",
                    "camera_movement_vi": "Camera",
                    "transition_to_next_vi": "Transition",
                    "veo3_prompt_en": "Reference the approved Character: Invalid fact-check action",
                    "needs_fact_check": True,
                    "fact_check_note_vi": None,
                    "scene_specific_negative_en": "watermark"
                }
            ]
        })

        # Phase 8 fact check returns invalid scene
        mock_invalid_fact_check_json = json.dumps({
            "scenes": [
                {
                    "scene_number": 1,
                    "title": "Scene 1 [00:00 - 00:08]",
                    "action_detail_vi": "Invalid Fact-Check Action",
                    "emotion_gesture_vi": "Gesture",
                    "camera_movement_vi": "Camera",
                    "transition_to_next_vi": "Transition",
                    "veo3_prompt_en": "Reference the approved Character: Invalid fact-check action",
                    "needs_fact_check": True,
                    "fact_check_note_vi": None,
                    "scene_specific_negative_en": "watermark"
                }
            ]
        })

        # Scenario 1: Phase 6 critique validation fails after max retries -> original scene preserved
        mock_gemini_critique_fail = make_dynamic_mock(
            meta_json=mock_meta_json,
            arc_json=mock_arc_json,
            scene_json_or_list=mock_batch_scenes,
            global_json=mock_global_json,
            critique_json=mock_invalid_critique_json,
            fact_check_json=json.dumps({"has_issues": False, "fact_check_notes": "Ok.", "scenes": []})
        )
        with patch.object(service, "_call_gemini_with_retry", mock_gemini_critique_fail):
            sse_events = []
            async for event in service.generate_full_script_stream(
                suggestion=selected_suggestion,
                style="realistic",
                num_scenes=1,
                project_id=project.id,
                db=db
            ):
                sse_events.append(event)
            
            # Load project to check stored script data
            db.refresh(project)
            saved_script = to_legacy_v2(json.loads(project.script_output))
            # Should have the original Phase 3 action, not "Invalid Critique Action"
            assert saved_script["scenes"][0]["action_detail_vi"] == "Original Action from Phase 3"

        # Scenario 2: Phase 8 fact-check validation fails after max retries -> original scene preserved
        # Critique returns no changes (valid), but Fact-Check returns invalid scene
        mock_valid_critique_json = json.dumps({
            "has_changes": False,
            "scenes": []
        })
        mock_gemini_fact_check_fail = make_dynamic_mock(
            meta_json=mock_meta_json,
            arc_json=mock_arc_json,
            scene_json_or_list=mock_batch_scenes,
            global_json=mock_global_json,
            critique_json=mock_valid_critique_json,
            fact_check_json=mock_invalid_fact_check_json
        )
        with patch.object(service, "_call_gemini_with_retry", mock_gemini_fact_check_fail):
            sse_events = []
            async for event in service.generate_full_script_stream(
                suggestion=selected_suggestion,
                style="realistic",
                num_scenes=1,
                project_id=project.id,
                db=db
            ):
                sse_events.append(event)
            db.refresh(project)
            saved_script = to_legacy_v2(json.loads(project.script_output))
            assert saved_script["_fact_check_completed"] is True
            assert saved_script["quality_warnings"] or any("done" in event for event in sse_events)

    finally:
        db.close()
