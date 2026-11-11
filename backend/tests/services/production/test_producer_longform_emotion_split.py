import pytest
import json
import re
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.production import ProductionService
from app.services.production.base import build_story_spine
from app.models.project import Project

@pytest.mark.asyncio
async def test_producer_longform_emotion_split():
    # Setup mock project and DB
    mock_db = MagicMock()
    mock_project = Project(id=1, title="Test", status="generating")
    mock_db.query.return_value.filter.return_value.first.return_value = mock_project
    
    service = ProductionService(api_key="test", groq_api_key=None, db=mock_db, api_key_id=None)
    service.enable_post_suggestions_test = True
    
    suggestion = {"index": 0, "title": "Long series", "synopsis": "Desc", "topic_type": "fictional_original"}
    
    async def mock_phase0(*args, **kwargs):
        script_data = args[6]
        script_data.update({
            "prompt_0": {
                "primary_subject_en": "Longform hero",
                "hard_visual_lock_en": "Anime visual lock",
                "setting_lock_en": "Longform world",
                "character_lock": [{"name": "Hero", "description_en": "Hero desc"}],
                "camera_lock_en": "Camera lock",
                "voice_sound_lock_en": "Voice lock",
                "action_story_logic_en": "1. Start 2. Continue 3. End",
                "scene_function_rules_en": "One function per scene",
                "continuity_lock_en": "Continuity lock",
                "internal_logic_en": "No teleportation",
                "negative_constraints_en": "No modern objects",
            },
            "overview_analysis_vi": "overview",
            "storyline_vi": "story",
            "stages_vi": "stages",
            "progression_vi": "progression",
            "camera_strategy_vi": "camera",
            "continuity_locks_vi": "continuity",
            "form_locks_vi": "form",
            "age_stage_locks_vi": "age",
            "geometry_locks_vi": "geometry",
            "risk_logic_vi": "risk",
            "voice_sound_strategy_vi": "voice",
            "characters": [{"character_name": "Hero", "description_en": "Hero desc", "key_identifiers_en": "hero"}],
            "environment_master_prompt_en": "World",
            "environment_master_prompt_vi": "Bối cảnh",
            "continuity_prompt_en": "Continuity lock",
            "continuity_board": {"continuity_prompt_en": "Continuity lock", "continuity_prompt_vi": ""},
            "global_negative_prompt_en": "No modern objects",
            # Durable longform fixture guard: Phase 0 mocks must include the
            # central story contract so tests exercise arc splitting, not blueprint retry gates.
            "story_contract": {
                "main_subject_en": "Longform hero",
                "protagonist_en": "Longform hero",
                "central_opponent_or_force_en": "Longform world",
                "core_goal_en": "Longform hero completes the mission",
                "must_remain_visible_terms": ["Longform hero"],
                "forbidden_takeover_rule": "No side threat replaces the hero.",
            },
        })
        if False:
            yield None

    async def mock_phase2(*args, **kwargs):
        script_data = args[4]
        script_data["scenes"] = [
            {
                "scene_number": i,
                "title": f"Scene {i}",
                "action_detail_vi": f"Hành động {i}",
                "veo3_prompt_en": f"Reference the approved Prompt 0 continuity board, Hero performs action {i}, anime style, voice: \"Scene {i} advances.\"",
                "voice_over_en": f"Scene {i} advances.",
                "needs_fact_check": False,
                "fact_check_note_vi": None,
                "historical_basis_vi": None,
            }
            for i in range(1, 51)
        ]
        if False:
            yield None

    async def mock_generator(*args, **kwargs):
        script_data = args[3]
        script_data["reference_images"] = {
            "character_ref_prompt_en": "Hero reference",
            "background_ref_prompt_en": "World reference",
            "thumbnail_ref_prompt_en": "Thumbnail reference",
        }
        if False:
            yield None
            
    service._phase0_prompt0_and_blueprint = mock_phase0
    service._phase2_batch_generate_scenes = mock_phase2
    service._phase3_packaging = mock_generator
    service._phase4_fact_check = mock_generator

    # Mock emotion arc generator to return custom entries
    # The splitting code splits num_scenes=50 into chunk size 20: Part 1: 1-20, Part 2: 21-40, Part 3: 41-50
    mock_part1_arc = json.dumps({
        "emotion_arc": [
            {
                "scene_number": i,
                "emotion_label": "bi tráng" if i % 2 == 0 else f"hào hứng {i}",
                "beat_summary": "Tóm tắt",
                "physical_state_end": "Ok",
                "camera_complexity": "low",
                "scene_lead_character": "None"
            }
            for i in range(1, 21)
        ]
    })
    mock_part2_arc = json.dumps({
        "emotion_arc": [
            {
                "scene_number": i,
                "emotion_label": "căng thẳng" if i % 2 == 0 else f"kịch tính {i}",
                "beat_summary": "Tóm tắt 2",
                "physical_state_end": "Ok 2",
                "camera_complexity": "medium",
                "scene_lead_character": "None"
            }
            for i in range(1, 21)  # Generates 1-20 which will be shifted to 21-40
        ]
    })
    mock_part3_arc = json.dumps({
        "emotion_arc": [
            {
                "scene_number": i,
                "emotion_label": "sửng sốt" if i == 1 else f"nhịp điệu {i}",
                "beat_summary": "Tóm tắt 3",
                "physical_state_end": "Ok 3",
                "camera_complexity": "high",
                "scene_lead_character": "None"
            }
            for i in range(1, 11)  # Generates 1-10 which will be shifted to 41-50
        ]
    })
    
    mock_post_json = json.dumps({"suggestions": []})
    
    with patch("app.services.gemini.base.BaseGeminiService._call_gemini_with_retry", new_callable=AsyncMock) as mock_call, \
         patch.object(service, "_save_script") as mock_save:
        # Mock returns part 1 arc, then part 2 arc, then part 3 arc, then suggestions
        mock_call.side_effect = [
            mock_part1_arc,
            mock_part2_arc,
            mock_part3_arc,
            mock_post_json
        ]
        
        events = []
        async for event in service.generate_full_script_stream(
            suggestion=suggestion,
            style="anime",
            num_scenes=50,  # Trigger splitting (> 40 scenes)
            project_id=1,
            db=mock_db,
            aspect_ratio="9:16"
        ):
            events.append(event)
            
        # Check call count is 4 (part 1, part 2, part 3, suggestions)
        assert mock_call.call_count == 4
        
        # Verify emotion arc got merged and shifted
        saved_data = mock_save.call_args[0][2]
        assert len(saved_data["emotion_arc"]) == 50
        assert saved_data["emotion_arc"][0]["scene_number"] == 1
        assert saved_data["emotion_arc"][19]["scene_number"] == 20
        assert saved_data["emotion_arc"][20]["scene_number"] == 21
        assert saved_data["emotion_arc"][49]["scene_number"] == 50
        assert saved_data["emotion_arc"][20]["emotion_label"] == "kịch tính 1"
        saved_arc_lengths = [
            len(call.args[2].get("emotion_arc") or [])
            for call in mock_save.call_args_list
            if len(call.args) >= 3
        ]
        assert all(length in (0, 50) for length in saved_arc_lengths)


def make_arc_entries(start: int, end: int) -> list[dict]:
    return [
        {
            "scene_number": i,
            "emotion_label": "bi tráng" if i == start else f"nhịp {i}",
            "beat_summary": f"Arthur advances through one continuous mission beat {i}.",
            "physical_state_end": f"Arthur ends at position {i}.",
            "camera_complexity": "medium",
            "scene_lead_character": "Arthur Miller",
        }
        for i in range(start, end + 1)
    ]


@pytest.mark.asyncio
async def test_longform_emotion_arc_uses_absolute_chunk_numbers_project22_style():
    mock_db = MagicMock()
    mock_project = Project(id=22, title="Project 22", status="generating")
    mock_db.query.return_value.filter.return_value.first.return_value = mock_project
    service = ProductionService(api_key="test", groq_api_key=None, db=mock_db, api_key_id=None)
    service.enable_post_suggestions_test = True

    suggestion = {
        "index": 0,
        "title": "Arthur Fire Trial",
        "synopsis": "Arthur completes one continuous fire rescue mission.",
        "topic_type": "fictional_original",
    }

    async def mock_phase0(*args, **kwargs):
        script_data = args[6]
        prompt_0 = {
            "primary_subject_en": "Arthur Miller",
            "hard_visual_lock_en": "1920 firefighter realism",
            "setting_lock_en": "1920 New York warehouse fire",
            "character_lock": [{"name": "Arthur Miller", "description_en": "Rookie firefighter"}],
            "camera_lock_en": "POV realism",
            "voice_sound_lock_en": "Short English narration",
            "action_story_logic_en": (
                "1. Station bell alarms. 2. Arthur boards the steam-pump engine. "
                "3. Arriving at the raging inferno. 4. First attempt to enter the warehouse. "
                "5. Arthur discovers a trapped victim. 6. Rescuing the victim. 7. Calm after the chaos."
            ),
            "scene_function_rules_en": "One beat per scene",
            "continuity_lock_en": "Soot increases; axe stays on Arthur right side",
            "internal_logic_en": "No teleportation",
            "negative_constraints_en": "No modern gear",
        }
        stages = (
            "Giai đoạn 1 - Triệu tập (Cảnh 1-10): tiếng chuông báo động.\n"
            "Giai đoạn 2 - Tiếp cận (Cảnh 11-20): xe tới hiện trường.\n"
            "Giai đoạn 3 - Xâm nhập (Cảnh 21-35): bước vào nhà kho.\n"
            "Giai đoạn 4 - Khủng hoảng (Cảnh 36-50): sập trần chia cắt.\n"
            "Giai đoạn 5 - Giải cứu (Cảnh 51-65): tìm thấy nạn nhân.\n"
            "Giai đoạn 6 - Thoát hiểm và Kết thúc (Cảnh 66-80): đưa nạn nhân ra ngoài."
        )
        script_data.update({
            "prompt_0": prompt_0,
            "overview_analysis_vi": "overview",
            "storyline_vi": "story",
            "stages_vi": stages,
            "progression_vi": "progression",
            "camera_strategy_vi": "camera",
            "continuity_locks_vi": "locks",
            "form_locks_vi": "form",
            "age_stage_locks_vi": "age",
            "geometry_locks_vi": "geometry",
            "risk_logic_vi": "risk",
            "voice_sound_strategy_vi": "voice",
            "characters": [{"character_name": "Arthur Miller", "description_en": "Rookie firefighter", "key_identifiers_en": "fire axe"}],
            "environment_master_prompt_en": "warehouse",
            "environment_master_prompt_vi": "nhà kho",
            "continuity_prompt_en": prompt_0["continuity_lock_en"],
            "continuity_board": {"continuity_prompt_en": prompt_0["continuity_lock_en"], "continuity_prompt_vi": ""},
            "global_negative_prompt_en": prompt_0["negative_constraints_en"],
            # Durable longform fixture guard: Phase 0 mocks must include the
            # central story contract so tests exercise absolute arc numbering.
            "story_contract": {
                "main_subject_en": "Arthur Miller",
                "protagonist_en": "Arthur Miller",
                "central_opponent_or_force_en": "warehouse fire",
                "core_goal_en": "Arthur rescues the trapped victim",
                "must_remain_visible_terms": ["Arthur", "fire"],
                "forbidden_takeover_rule": "No side threat replaces Arthur's rescue mission.",
            },
        })
        if False:
            yield None

    async def mock_phase2(*args, **kwargs):
        script_data = args[4]
        script_data["scenes"] = [
            {
                "scene_number": i,
                "title": f"Scene {i}",
                "action_detail_vi": f"Arthur continues scene {i}.",
                "veo3_prompt_en": f"Reference the approved Prompt 0 continuity board, Arthur scene {i}, realistic style, voice: \"Duty carries him.\"",
                "voice_over_en": "Duty carries him.",
                "needs_fact_check": False,
                "fact_check_note_vi": None,
                "historical_basis_vi": None,
            }
            for i in range(1, 81)
        ]
        if False:
            yield None

    async def mock_phase3(*args, **kwargs):
        script_data = args[3]
        script_data["reference_images"] = {
            "character_ref_prompt_en": "Arthur reference",
            "background_ref_prompt_en": "Warehouse reference",
            "thumbnail_ref_prompt_en": "Thumbnail reference",
        }
        if False:
            yield None

    service._phase0_prompt0_and_blueprint = mock_phase0
    service._phase2_batch_generate_scenes = mock_phase2
    service._phase3_packaging = mock_phase3

    async def mock_gemini(prompt, **kwargs):
        match = re.search(r"Return scene_number exactly (\d+) through (\d+)", prompt)
        assert match, prompt
        start, end = int(match.group(1)), int(match.group(2))
        return json.dumps({"emotion_arc": make_arc_entries(start, end)})

    with patch("app.services.gemini.base.BaseGeminiService._call_gemini_with_retry", new_callable=AsyncMock) as mock_call, \
         patch.object(service, "_save_script") as mock_save:
        mock_call.side_effect = mock_gemini
        events = [
            event async for event in service.generate_full_script_stream(
                suggestion=suggestion,
                style="realistic",
                num_scenes=80,
                project_id=22,
                db=mock_db,
                aspect_ratio="9:16",
            )
        ]

    saved_data = mock_save.call_args[0][2]
    nums = [entry["scene_number"] for entry in saved_data["emotion_arc"]]
    assert nums == list(range(1, 81))
    assert max(nums) == 80
    assert any("emotion_arc_chunk_1_of_4" in event for event in events)
    assert any("emotion_arc_chunk_4_of_4" in event for event in events)


@pytest.mark.asyncio
async def test_emotion_arc_chunk_rejects_mini_story_before_merge():
    service = ProductionService(api_key="test", groq_api_key=None, db=MagicMock(), api_key_id=None)
    prompt_0 = {
        "action_story_logic_en": (
            "1. Station bell alarms. 2. Arthur boards the engine. 3. First attempt to enter. "
            "4. Arthur discovers a trapped victim. 5. Rescuing the victim. 6. Calm after the chaos."
        )
    }
    stages = (
        "Giai đoạn 1 - Triệu tập (Cảnh 1-10). "
        "Giai đoạn 2 - Tiếp cận (Cảnh 11-20). "
        "Giai đoạn 3 - Xâm nhập (Cảnh 21-35). "
        "Giai đoạn 4 - Khủng hoảng (Cảnh 36-50). "
        "Giai đoạn 5 - Giải cứu (Cảnh 51-65). "
        "Giai đoạn 6 - Thoát hiểm và Kết thúc (Cảnh 66-80)."
    )
    script_data = {
        "characters": [{"character_name": "Arthur Miller", "description_en": "Rookie firefighter"}],
        "story_spine": build_story_spine(prompt_0, stages, 80),
    }
    bad_arc = make_arc_entries(1, 20)
    bad_arc[14]["beat_summary"] = "Arthur discovers a trapped victim and starts rescuing the victim too early."
    bad_arc[17]["beat_summary"] = "Arthur reaches a peaceful resolution outside and treats the mission as finished too early."

    with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = json.dumps({"emotion_arc": bad_arc})
        async for _ in service._phase1_generate_emotion_arc(
            suggestion={"synopsis": "A fire rescue", "topic_type": "fictional_original"},
            style="realistic",
            num_scenes=20,
            model_name="test-model",
            script_data=script_data,
            project_id=22,
            topic_type="fictional_original",
            persist=False,
            emit_result=False,
            expected_start=1,
            expected_end=20,
        ):
            pass

    assert script_data["emotion_arc"] == bad_arc


@pytest.mark.asyncio
async def test_emotion_arc_chunk_parses_first_json_when_model_appends_extra_data():
    service = ProductionService(api_key="test", groq_api_key=None, db=MagicMock(), api_key_id=None)
    script_data = {
        "characters": [{"character_name": "Arthur Miller", "description_en": "Rookie firefighter"}],
        "story_spine": {"version": "1.2", "total_scenes": 80, "steps": [], "stage_ranges": []},
    }
    valid_json = json.dumps({"emotion_arc": make_arc_entries(21, 40)})
    extra_payload = json.dumps({"note": "second object that used to trigger JSON Extra data"})

    with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = valid_json + "\n" + extra_payload
        async for _ in service._phase1_generate_emotion_arc(
            suggestion={"synopsis": "A fire rescue", "topic_type": "fictional_original"},
            style="realistic",
            num_scenes=20,
            model_name="test-model",
            script_data=script_data,
            project_id=22,
            topic_type="fictional_original",
            persist=False,
            emit_result=False,
            expected_start=21,
            expected_end=40,
        ):
            pass

    nums = [entry["scene_number"] for entry in script_data["emotion_arc"]]
    assert nums == list(range(21, 41))
