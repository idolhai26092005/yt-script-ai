import json
import sys
from unittest.mock import AsyncMock, patch

import pytest

from app.core.database import Base, SessionLocal, engine
from app.crud.api_key import create_api_key
from app.crud.project import create_project
from app.models.api_key import APIKey
from app.models.project import Project
from app.schemas.api_key import APIKeyCreate
from app.services.production.validation.legacy import BLOCK, ValidationIssue, validate_scene_generation_quality
from app.core.utils import to_legacy_v2
from app.services.production.prompts.legacy import BATCH_SCENE_GENERATION_TEMPLATE, VEO3_CONTENT_SAFETY_RULES
from app.services.production.base import (
    build_compact_prompt_0_text,
    build_story_spine,
    story_spine_context,
    future_targets_context,
    MAX_BATCH_PROMPT_CHARS,
)
from app.services.production import ProductionService


def make_prompt_0() -> dict:
    return {
        "primary_subject_en": "Redhaired Hero",
        "hard_visual_lock_en": "Redhaired Hero keeps red hair and leather coat",
        "setting_lock_en": "Ancient stone valley",
        "character_lock": [{"name": "Hero", "description_en": "Redhaired Hero, leather coat"}],
        "camera_lock_en": "Cinematic close and wide shots",
        "voice_sound_lock_en": "Short English narration",
        "action_story_logic_en": "Start, escalate, resolve",
        "scene_function_rules_en": "Each scene has one clear function",
        "continuity_lock_en": "Redhaired Hero in ancient stone valley",
        "internal_logic_en": "No teleportation",
        "negative_constraints_en": "low quality, blurry",
    }


def make_blueprint() -> dict:
    prompt_0 = make_prompt_0()
    return {
        "schema_version": "2.0",
        "topic_type": "fictional_original",
        "prompt_0": prompt_0,
        "overview_analysis_vi": "Tổng quan đã cache.",
        "storyline_vi": "Hero đi qua stone valley.",
        "stages_vi": "Cảnh 1-2: Hero vượt stone valley.",
        "progression_vi": "Cảnh 1 mở đầu, cảnh 2 cao trào.",
        "camera_strategy_vi": "Máy quay điện ảnh.",
        "continuity_locks_vi": "Hero tóc đỏ không đổi.",
        "form_locks_vi": "Áo khoác da không đổi.",
        "age_stage_locks_vi": "Người trưởng thành.",
        "geometry_locks_vi": "Thung lũng đá.",
        "risk_logic_vi": "Đá lở tăng dần.",
        "voice_sound_strategy_vi": "Lời dẫn ngắn.",
        "characters": [{"character_name": "Hero", "description_en": "Redhaired Hero", "key_identifiers_en": "red hair"}],
        "environment_master_prompt_en": "Ancient stone valley, cinematic dust.",
        "environment_master_prompt_vi": "Thung lũng đá cổ.",
        "continuity_board": {"continuity_prompt_en": prompt_0["continuity_lock_en"], "continuity_prompt_vi": ""},
        "continuity_prompt_en": prompt_0["continuity_lock_en"],
        "continuity_prompt_vi": "",
        "global_negative_prompt_en": prompt_0["negative_constraints_en"],
        # Durable resume-fixture guard: cached Phase 0 state must include the
        # central contract so cache-hit tests do not re-enter blueprint generation.
        "story_contract": {
            "main_subject_en": "Hero",
            "protagonist_en": "Hero",
            "central_opponent_or_force_en": "stone valley",
            "core_goal_en": "Hero crosses the stone valley",
            "must_remain_visible_terms": ["Hero", "valley"],
            "forbidden_takeover_rule": "No side obstacle replaces Hero's crossing.",
        },
        "reference_images": {
            "character_ref_prompt_en": "Hero ref",
            "background_ref_prompt_en": "Valley ref",
            "thumbnail_ref_prompt_en": "Thumbnail ref",
        },
        "series_bridge_vi": None,
    }


def make_arc() -> list[dict]:
    return [
        {
            "scene_number": 1,
            "emotion_label": "sửng sốt",
            "beat_summary": "Hero bước vào thung lũng",
            "physical_state_end": "Hero đứng trước vách đá",
            "camera_complexity": "low",
            "scene_lead_character": "Hero",
        },
        {
            "scene_number": 2,
            "emotion_label": "bi tráng",
            "beat_summary": "Hero né đá lở",
            "physical_state_end": "Hero vượt qua vách đá",
            "camera_complexity": "medium",
            "scene_lead_character": "Hero",
        },
    ]


def make_arc_n(count: int) -> list[dict]:
    labels = ["căng thẳng", "quyết tâm", "lo âu", "bi tráng"]
    return [
        {
            "scene_number": i,
            "emotion_label": labels[i % len(labels)],
            "beat_summary": f"Hero tiếp tục vượt thử thách cảnh {i}",
            "physical_state_end": f"Hero giữ vị trí sau cảnh {i}",
            "camera_complexity": "medium" if i % 2 else "low",
            "scene_lead_character": "Hero",
        }
        for i in range(1, count + 1)
    ]


def make_scene(scene_number: int, action: str) -> dict:
    return {
        "scene_number": scene_number,
        "title": f"Scene {scene_number}",
        "action_detail_vi": action,
        "emotion_gesture_vi": "Hero căng thẳng",
        "camera_movement_vi": "Tracking shot",
        "transition_to_next_vi": "Cut",
        "veo3_prompt_en": f"Reference the approved Redhaired Hero crosses ancient stones, anime style, voice: \"The valley tests him.\"",
        "voice_over_en": "The valley tests him.",
        "voice_over_vi": "The valley tests him.",
        "scene_specific_negative_en": "watermark",
        "historical_basis_vi": None,
        "needs_fact_check": False,
        "fact_check_note_vi": None,
    }


def make_historical_cached_script(count: int = 10) -> dict:
    cached = make_blueprint()
    cached["topic_type"] = "historical"
    cached["prompt_0"]["action_story_logic_en"] = (
        "1. Fire alarm rings. 2. Thomas climbs truck. 3. Arrive at inferno. "
        "4. Smoke barrier entry. 5. Finding survivor. 6. Successful extraction. "
        "7. Exhaustion in street."
    )
    cached["stages_vi"] = (
        "Giai đoạn 1 - Báo động (Cảnh 1-2). "
        "Giai đoạn 2 - Tiếp cận (Cảnh 3-4). "
        "Giai đoạn 3 - Mắc kẹt (Cảnh 5-6). "
        "Giai đoạn 4 - Giải cứu (Cảnh 7-8). "
        "Giai đoạn 5 - Sống sót (Cảnh 9-10)."
    )
    cached["story_spine"] = build_story_spine(cached["prompt_0"], cached["stages_vi"], count)
    cached["emotion_arc"] = make_arc_n(count)
    cached["scenes"] = []
    actions = [
        "Thomas kiểm tra đồng hồ nước và gọi đội hình.",
        "Thomas kéo dây áo bảo hộ trước khi rời sân trạm.",
        "Thomas quan sát mái nhà cháy từ phố hẹp.",
        "Thomas mở vòi nước để chặn khói ở mép tường.",
        "Thomas bò thấp qua hành lang phủ bụi nóng.",
        "Thomas đánh dấu cầu thang yếu bằng rìu gỗ.",
        "Thomas nghe âm thanh yếu dưới tấm ván cháy.",
        "Thomas kéo một bóng người qua mép sàn nứt.",
        "Thomas đặt chiếc cáng gỗ cạnh đội y tế.",
        "Thomas tháo mũ dưới bình minh sau nhiệm vụ.",
    ]
    for i in range(1, count + 1):
        scene = make_scene(i, actions[(i - 1) % len(actions)])
        scene["historical_basis_vi"] = "Mô tả dựa trên đồng thuận lịch sử."
        scene["verifiability_level"] = "general_consensus"
        cached["scenes"].append(scene)
    return cached


def test_scene_adjacency_validation_rejects_timeline_reset_after_exit():
    script_data = make_blueprint()
    script_data["emotion_arc"] = make_arc_n(21)
    script_data["scenes"] = [
        make_scene(20, "Arthur tháo mũ nhìn lại nhà kho đang cháy."),
        make_scene(21, "Arthur leo lên xe ngựa cứu hỏa chuẩn bị xuất phát."),
    ]

    errors = validate_scene_generation_quality(script_data)

    assert any("timeline reset" in err for err in errors)


def test_story_state_machine_rejects_project17_style_macro_loop():
    script_data = make_blueprint()
    script_data["prompt_0"]["action_story_logic_en"] = (
        "1. Fire alarm rings. 2. Thomas climbs truck. 3. Arrive at inferno. "
        "4. Smoke barrier entry. 5. Finding survivor. 6. Successful extraction. "
        "7. Exhaustion in street."
    )
    script_data["stages_vi"] = (
        "Giai đoạn 1 – Báo động (Cảnh 1-10). "
        "Giai đoạn 2 – Tiếp cận (Cảnh 11-25). "
        "Giai đoạn 3 – Mắc kẹt (Cảnh 26-45). "
        "Giai đoạn 4 – Giải cứu (Cảnh 46-65). "
        "Giai đoạn 5 – Sống sót (Cảnh 66-80)."
    )
    script_data["story_spine"] = build_story_spine(script_data["prompt_0"], script_data["stages_vi"], 80)
    script_data["emotion_arc"] = make_arc_n(80)
    actions = {
        1: "Thomas kiểm tra trang phục trước ca trực.",
        2: "Tiếng chuông báo cháy vang lên, Thomas lao ra xe.",
        3: "Xe dừng lại, Thomas bước xuống trước nhà kho cháy.",
        4: "Thomas bước vào nhà kho giữa khói dày.",
        10: "Thomas tìm thấy nạn nhân dưới đống đổ nát.",
        17: "Thomas đặt nạn nhân xuống an toàn ngoài phố.",
        20: "Thomas tháo mũ nhìn bình minh và nghỉ ngơi.",
        21: "Chuông báo cháy lại vang lên, Thomas leo lên xe cứu hỏa.",
        23: "Xe dừng lại, Thomas bước xuống trước một nhà kho cháy khác.",
        25: "Thomas lại lao vào cổng chính để cứu người.",
    }
    script_data["scenes"] = [
        make_scene(i, actions.get(i, f"Thomas tiếp tục chịu áp lực cảnh {i}."))
        for i in range(1, 26)
    ]

    errors = validate_scene_generation_quality(script_data)

    assert any("Story state trigger 'alarm' repeats" in err for err in errors)


def test_project21_snapshot_macro_loop_is_rejected():
    import os
    if not os.path.exists("backend/debug_snapshots/project_21_phase_2_scenes.json"):
        pytest.skip("project_21 debug snapshot is not present in this checkout")
    with open("backend/debug_snapshots/project_21_phase_2_scenes.json", encoding="utf-8") as f:
        script_data = json.load(f)

    errors = validate_scene_generation_quality(script_data)

    assert any("Story state trigger 'resolution'" in err for err in errors)


def test_batch_prompt_budget_for_80_120_200_scenes():
    prompt_0 = make_prompt_0()
    prompt_0["character_lock"] = [
        {"name": f"Hero{i}", "description_en": f"Hero{i} red hair leather coat marker {i}"}
        for i in range(1, 13)
    ]
    for total in [80, 120, 200]:
        stages = f"Cảnh 1-{total}: một hành trình liên tục không reset."
        spine = build_story_spine(prompt_0, stages, total)
        arc = [
            {
                "scene_number": i,
                "emotion_label": "căng thẳng",
                "beat_summary": f"Hero{i % 12 + 1} tiến tiếp cảnh {i}",
                "physical_state_end": f"Hero ở vị trí {i}",
                "camera_complexity": "medium",
                "scene_lead_character": f"Hero{i % 12 + 1}",
            }
            for i in range(1, 11)
        ]
        # Durable prompt-budget regression: the central contract must stay compact
        # enough that adding topic adherence does not break large-script batching.
        prompt = BATCH_SCENE_GENERATION_TEMPLATE.format(
            batch_size=10,
            batch_start=1,
            batch_end=10,
            prompt_0_full_text=build_compact_prompt_0_text(prompt_0, [e["scene_lead_character"] for e in arc]),
            title="Budget Test",
            style="anime",
            num_scenes=total,
            stage_context="Cảnh 1-10: mở hành trình.",
            story_contract_context='{"main_subject_en":"Hero journey","central_opponent_or_force_en":"the central trial"}',
            emotion_arc_json=json.dumps(arc, ensure_ascii=False),
            story_spine_context=story_spine_context(spine, 1, 10, []),
            future_targets_context=future_targets_context(spine, 1, 10),
            prev_context="This is the FIRST scene batch. Begin the story from the beginning.",
            constraint_context="No extra project-specific negative constraints beyond Prompt 0.",
            aspect_ratio="9:16",
            scene_duration_sec=8,
            historical_rules="",
            safety_rules=VEO3_CONTENT_SAFETY_RULES,
            batch_position_instruction="This is batch 1 of many — NOT the final batch.",
            used_actions_context="",
        )
        assert len(prompt) < MAX_BATCH_PROMPT_CHARS


def test_story_spine_coverage_errors_are_not_phase0_blockers():
    service = ProductionService(api_key="test_key", db=None)
    errors = [
        "story_spine coverage error: Stage ranges leave gap 11-60",
        "story_spine stage coverage missing scenes [11, 12]",
        "story_spine version must be 1.2",
    ]

    blocking = service._story_spine_blocking_errors(errors)

    assert blocking == ["story_spine version must be 1.2"]


def test_future_targets_context_reserves_later_payoffs():
    prompt_0 = make_prompt_0()
    prompt_0["action_story_logic_en"] = (
        "1. Start. 2. Failed trap. 3. Tactical retreat. 4. Final showdown. 5. Resolution and departure."
    )
    spine = build_story_spine(
        prompt_0,
        "Giai đoạn 1 - Xuất phát (Cảnh 1-20). "
        "Giai đoạn 2 - Đối đầu (Cảnh 21-60). "
        "Giai đoạn 3 - Kết thúc (Cảnh 61-80).",
        80,
    )

    context = future_targets_context(spine, 1, 10)

    assert "FUTURE TARGETS" in context
    assert "Scenes 61-80" in context
    assert "Resolution and departure" in context
    assert "MUST NOT resolve" in context


def test_ensure_story_spine_rebuilds_stale_fallback_stage_cache():
    service = ProductionService(api_key="test_key", db=None, api_key_id=None)
    script_data = make_blueprint()
    script_data["prompt_0"]["action_story_logic_en"] = (
        "1. Start. 2. Failed trap. 3. Tactical retreat. 4. Peaceful coexistence established."
    )
    script_data["stages_vi"] = (
        "Giai đoạn 1 – Dẫn dắt (1-20): Thiết lập môi trường. "
        "Giai đoạn 2 – Đối đầu (21-40): Bẫy thất bại. "
        "Giai đoạn 3 – Bước ngoặt (41-60): Đổi chiến thuật. "
        "Giai đoạn 4 – Hòa hợp (61-80): Kết thúc."
    )
    script_data["story_spine"] = {
        "version": "1.2",
        "mode": "single_journey",
        "total_scenes": 80,
        "steps": [{"step": 1, "label": "Start", "scene_start": 1, "scene_end": 80}],
        "stage_ranges": [{
            "scene_start": 1,
            "scene_end": 80,
            "label": "Full continuous journey",
            "trigger": None,
            "source": "fallback",
        }],
        "coverage_errors": [],
        "allowed_once_triggers": [],
    }

    spine = service._ensure_story_spine(script_data, 80)

    assert [s["scene_start"] for s in spine["stage_ranges"]] == [1, 21, 41, 61]
    assert spine["stage_ranges"][-1]["trigger"] == "resolution"


@pytest.mark.asyncio
async def test_resume_skips_cached_phase0_and_generates_only_missing_scene():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()

        _, api_key = create_api_key(db, APIKeyCreate(owner="Resume Owner", quota_limit=5))
        project = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Resume project",
            input_type="manual",
            input_content="Hero valley",
            style="anime",
            num_scenes=2,
        )

        suggestion = {
            "index": 0,
            "title": "Hero Valley",
            "synopsis": "Hero crosses a stone valley.",
            "topic_type": "fictional_original",
        }
        service = ProductionService(api_key="test_key", db=db, api_key_id=api_key.id)

        cached = make_blueprint()
        cached["emotion_arc"] = make_arc()
        cached["scenes"] = [make_scene(1, "Hero bước vào thung lũng từ cache")]
        cached["_resume_signature"] = service._build_resume_signature(
            suggestion=suggestion,
            style="anime",
            num_scenes=2,
            topic_type="fictional_original",
            aspect_ratio="9:16",
            scene_duration_sec=8,
            generation_mode="single",
        )
        project.script_output = json.dumps(cached, ensure_ascii=False)
        project.selected_suggestion_idx = 0
        project.status = "generating_script"
        db.commit()

        async def mock_gemini(prompt, **kwargs):
            assert "PROMPT 0 (Identity Lock" not in prompt
            assert "emotion_arc" not in prompt
            assert "This batch: Scenes 2 to 2" in prompt
            return json.dumps({"scenes": [make_scene(2, "Hero né đá lở mới sinh")]})

        with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = mock_gemini
            events = [
                event async for event in service.generate_full_script_stream(
                    suggestion=suggestion,
                    style="anime",
                    num_scenes=2,
                    project_id=project.id,
                    db=db,
                    aspect_ratio="9:16",
                    scene_duration_sec=8,
                )
            ]

        db.refresh(project)
        script_out = to_legacy_v2(json.loads(project.script_output))
        assert [s["action_detail_vi"] for s in script_out["scenes"]] == [
            "Hero bước vào thung lũng từ cache",
            "Hero né đá lở mới sinh",
        ]
        assert mock_call.call_count == 1
        assert any("cache_hit_prompt0_blueprint" in event for event in events)
        assert any("cache_hit_emotion_arc" in event for event in events)
        assert project.status == "script_generated"
    finally:
        db.close()


# Recovery restart guard: "Sinh lai tu dau" must ignore even compatible cached
# artifacts while keeping the same project/suggestion contract.
@pytest.mark.asyncio
async def test_restart_ignores_compatible_cache_and_regenerates_from_phase0():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()

        _, api_key = create_api_key(db, APIKeyCreate(owner="Restart Owner", quota_limit=5))
        project = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Restart project",
            input_type="manual",
            input_content="Hero valley",
            style="anime",
            num_scenes=2,
        )

        suggestion = {
            "index": 0,
            "title": "Hero Valley",
            "synopsis": "Hero crosses a stone valley.",
            "topic_type": "fictional_original",
        }
        service = ProductionService(api_key="test_key", db=db, api_key_id=api_key.id)
        cached = make_blueprint()
        cached["emotion_arc"] = make_arc()
        cached["scenes"] = [make_scene(1, "OLD cached scene")]
        cached["_resume_signature"] = service._build_resume_signature(
            suggestion=suggestion,
            style="anime",
            num_scenes=2,
            topic_type="fictional_original",
            aspect_ratio="9:16",
            scene_duration_sec=8,
            generation_mode="single",
        )
        project.script_output = json.dumps(cached, ensure_ascii=False)
        project.selected_suggestion_idx = 0
        project.status = "generating_script"
        db.commit()

        blueprint = make_blueprint()
        blueprint["emotion_arc"] = []
        new_scenes = [
            make_scene(1, "NEW scene one"),
            make_scene(2, "NEW scene two"),
        ]
        with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = [
                json.dumps(blueprint),
                json.dumps({"emotion_arc": make_arc()}),
                json.dumps({"scenes": new_scenes}),
                json.dumps(blueprint["reference_images"]),
            ]
            events = [
                event async for event in service.generate_full_script_stream(
                    suggestion=suggestion,
                    style="anime",
                    num_scenes=2,
                    project_id=project.id,
                    db=db,
                    aspect_ratio="9:16",
                    scene_duration_sec=8,
                    restart=True,
                )
            ]

        db.refresh(project)
        script_out = to_legacy_v2(json.loads(project.script_output))
        assert mock_call.call_count == 4
        assert script_out["scenes"][0]["action_detail_vi"] == "NEW scene one"
        assert all("cache_hit_" not in event for event in events)
        assert project.status == "script_generated"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_resume_after_scene_20_generates_only_remaining_scenes_with_real_handoff():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()

        _, api_key = create_api_key(db, APIKeyCreate(owner="Resume Boundary Owner", quota_limit=5))
        project = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Resume boundary project",
            input_type="manual",
            input_content="Hero long valley",
            style="anime",
            num_scenes=40,
        )

        suggestion = {
            "index": 0,
            "title": "Hero Long Valley",
            "synopsis": "Hero crosses a long stone valley without restarting the journey.",
            "topic_type": "fictional_original",
        }
        service = ProductionService(api_key="test_key", db=db, api_key_id=api_key.id)

        cached = make_blueprint()
        cached["stages_vi"] = "Cảnh 1-40: Hero vượt thung lũng theo một mạch liên tục."
        cached["progression_vi"] = "Mỗi cảnh đẩy Hero tiến xa hơn."
        cached["emotion_arc"] = make_arc_n(40)
        cached["scenes"] = [
            make_scene(i, f"Hero giữ vị trí sau cảnh {i}.")
            for i in range(1, 21)
        ]
        cached["_resume_signature"] = service._build_resume_signature(
            suggestion=suggestion,
            style="anime",
            num_scenes=40,
            topic_type="fictional_original",
            aspect_ratio="9:16",
            scene_duration_sec=8,
            generation_mode="single",
        )
        project.script_output = json.dumps(cached, ensure_ascii=False)
        project.selected_suggestion_idx = 0
        project.status = "generating_script"
        db.commit()

        seen_prompts: list[str] = []

        async def mock_gemini(prompt, **kwargs):
            seen_prompts.append(prompt)
            if "This batch: Scenes 21 to 30" in prompt:
                assert "Scene 20 ended with: Hero giữ vị trí sau cảnh 20" in prompt
                return json.dumps({
                    "scenes": [
                        make_scene(i, f"Hero tiếp tục tiến lên sau cảnh {i - 1}.")
                        for i in range(21, 31)
                    ]
                })
            if "This batch: Scenes 31 to 40" in prompt:
                assert "Scene 30 ended with: Hero tiếp tục tiến lên sau cảnh 29" in prompt
                return json.dumps({
                    "scenes": [
                        make_scene(i, f"Hero tiếp tục tiến lên sau cảnh {i - 1}.")
                        for i in range(31, 41)
                    ]
                })
            raise AssertionError("Unexpected generation prompt")

        with (
            patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call,
            patch("app.services.production.producer.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_call.side_effect = mock_gemini
            async for _ in service.generate_full_script_stream(
                suggestion=suggestion,
                style="anime",
                num_scenes=40,
                project_id=project.id,
                db=db,
                aspect_ratio="9:16",
                scene_duration_sec=8,
            ):
                pass

        db.refresh(project)
        script_out = to_legacy_v2(json.loads(project.script_output))
        assert [s["scene_number"] for s in script_out["scenes"]] == list(range(1, 41))
        assert mock_call.call_count == 2
        assert all("This batch: Scenes 1 to 10" not in prompt for prompt in seen_prompts)
        assert all("This batch: Scenes 11 to 20" not in prompt for prompt in seen_prompts)
        assert all(len(prompt) < MAX_BATCH_PROMPT_CHARS for prompt in seen_prompts)
    finally:
        db.close()


@pytest.mark.asyncio
async def test_phase2_resume_prunes_invalid_cache_without_regenerating_valid_prefix():
    service = ProductionService(api_key="test_key", db=None, api_key_id=None)
    cached = make_blueprint()
    cached["stages_vi"] = "Cảnh 1-30: Hero vượt thung lũng theo một mạch liên tục."
    cached["story_spine"] = build_story_spine(cached["prompt_0"], cached["stages_vi"], 30)
    cached["emotion_arc"] = make_arc_n(30)
    cached["scenes"] = [
        make_scene(i, f"Hero giữ vị trí sau cảnh {i}.")
        for i in range(1, 21)
    ]
    service.cached_script_data = json.loads(json.dumps(cached, ensure_ascii=False))
    script_data = json.loads(json.dumps(cached, ensure_ascii=False))

    seen_prompts: list[str] = []

    async def mock_gemini(prompt, **kwargs):
        seen_prompts.append(prompt)
        assert "This batch: Scenes 1 to 10" not in prompt
        assert "This batch: Scenes 11 to 20" not in prompt
        assert "This batch: Scenes 21 to 30" in prompt
        return json.dumps({
            "scenes": [
                make_scene(i, f"Hero tiếp tục tiến lên sau cảnh {i - 1}.")
                for i in range(21, 31)
            ]
        })

    with (
        patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call,
        patch("app.services.production.producer.validate_scene_generation_issues") as mock_quality,
        patch("app.services.production.producer.asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_call.side_effect = mock_gemini
        mock_quality.side_effect = [[ValidationIssue("whole cached set has a scoped issue", BLOCK)], []]
        async for _ in service._phase2_batch_generate_scenes(
            suggestion={"index": 0, "title": "Hero Long Valley", "synopsis": "Hero continues."},
            style="anime",
            num_scenes=30,
            model_name="test-model",
            script_data=script_data,
            project_id=1,
            topic_type="fictional_original",
            is_historical=False,
            aspect_ratio="9:16",
            scene_duration_sec=8,
        ):
            pass

    assert mock_call.call_count == 1
    assert [s["scene_number"] for s in script_data["scenes"]] == list(range(1, 31))
    assert all("This batch: Scenes 1 to 10" not in prompt for prompt in seen_prompts)
    assert all("This batch: Scenes 11 to 20" not in prompt for prompt in seen_prompts)


@pytest.mark.asyncio
async def test_phase2_saves_once_per_batch_plus_final_checkpoint():
    # Durable save-amplification regression: Phase 2 streams every scene, but
    # persistence must stay at batch granularity to avoid repeated full JSON V3 dumps.
    service = ProductionService(api_key="test_key", db=None, api_key_id=None)
    script_data = make_blueprint()
    script_data["stages_vi"] = "Cảnh 1-20: Hero vượt thung lũng theo một mạch liên tục."
    script_data["story_spine"] = build_story_spine(script_data["prompt_0"], script_data["stages_vi"], 20)
    script_data["emotion_arc"] = make_arc_n(20)
    script_data["scenes"] = []

    async def mock_gemini(prompt, **kwargs):
        if "This batch: Scenes 1 to 10" in prompt:
            return json.dumps({"scenes": [make_scene(i, f"Hero tiến qua cảnh {i}.") for i in range(1, 11)]})
        if "This batch: Scenes 11 to 20" in prompt:
            return json.dumps({"scenes": [make_scene(i, f"Hero tiến qua cảnh {i}.") for i in range(11, 21)]})
        raise AssertionError("Unexpected generation prompt")

    with (
        patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call,
        patch.object(service, "_save_script") as mock_save,
        patch("app.services.production.producer.asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_call.side_effect = mock_gemini
        events = [
            event async for event in service._phase2_batch_generate_scenes(
                suggestion={"index": 0, "title": "Hero Long Valley", "synopsis": "Hero continues."},
                style="anime",
                num_scenes=20,
                model_name="test-model",
                script_data=script_data,
                project_id=1,
                topic_type="fictional_original",
                is_historical=False,
                aspect_ratio="9:16",
                scene_duration_sec=8,
            )
        ]

    assert mock_call.call_count == 2
    assert mock_save.call_count == 3
    assert [call.kwargs.get("canonical", True) for call in mock_save.call_args_list] == [False, False, True]
    assert sum('"status": "scene"' in event for event in events) == 20
    assert [s["scene_number"] for s in script_data["scenes"]] == list(range(1, 21))


@pytest.mark.asyncio
async def test_old_schema_cache_is_ignored():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()

        _, api_key = create_api_key(db, APIKeyCreate(owner="Old Cache Owner", quota_limit=5))
        project = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Old cache project",
            input_type="manual",
            input_content="Hero valley",
            style="anime",
            num_scenes=1,
        )
        project.script_output = json.dumps({"schema_version": "1.0", "scenes": [make_scene(1, "old")]}, ensure_ascii=False)
        db.commit()

        suggestion = {
            "index": 0,
            "title": "Hero Valley",
            "synopsis": "Hero crosses a stone valley.",
            "topic_type": "fictional_original",
        }
        service = ProductionService(api_key="test_key", db=db, api_key_id=api_key.id)

        blueprint = make_blueprint()
        blueprint["emotion_arc"] = []
        scene = make_scene(1, "Sinh mới vì cache cũ")

        with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = [
                json.dumps(blueprint),
                json.dumps({"emotion_arc": make_arc()[:1]}),
                json.dumps({"scenes": [scene]}),
                json.dumps(blueprint["reference_images"]),
            ]
            async for _ in service.generate_full_script_stream(
                suggestion=suggestion,
                style="anime",
                num_scenes=1,
                project_id=project.id,
                db=db,
                aspect_ratio="9:16",
                scene_duration_sec=8,
            ):
                pass

        db.refresh(project)
        script_out = to_legacy_v2(json.loads(project.script_output))
        assert script_out["scenes"][0]["action_detail_vi"] == "Sinh mới vì cache cũ"
        assert mock_call.call_count == 4
    finally:
        db.close()


@pytest.mark.asyncio
async def test_packaging_missing_reference_prompts_hard_fails():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()

        _, api_key = create_api_key(db, APIKeyCreate(owner="Packaging Gate Owner", quota_limit=5))
        project = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Packaging gate project",
            input_type="manual",
            input_content="Hero valley",
            style="anime",
            num_scenes=2,
        )

        suggestion = {
            "index": 0,
            "title": "Hero Valley",
            "synopsis": "Hero crosses a stone valley.",
            "topic_type": "fictional_original",
        }
        service = ProductionService(api_key="test_key", db=db, api_key_id=api_key.id)
        cached = make_blueprint()
        cached["emotion_arc"] = make_arc()
        cached["scenes"] = [make_scene(1, "Hero bước vào thung lũng"), make_scene(2, "Hero vượt qua vách đá")]
        cached["reference_images"] = {
            "character_ref_prompt_en": "",
            "background_ref_prompt_en": "",
            "thumbnail_ref_prompt_en": "",
        }
        cached["_resume_signature"] = service._build_resume_signature(
            suggestion=suggestion,
            style="anime",
            num_scenes=2,
            topic_type="fictional_original",
            aspect_ratio="9:16",
            scene_duration_sec=8,
            generation_mode="single",
        )
        project.script_output = json.dumps(cached, ensure_ascii=False)
        project.selected_suggestion_idx = 0
        project.status = "generating_script"
        db.commit()

        with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = json.dumps({})
            with pytest.raises(RuntimeError, match="Phase 3 packaging hard gate failed"):
                async for _ in service.generate_full_script_stream(
                    suggestion=suggestion,
                    style="anime",
                    num_scenes=2,
                    project_id=project.id,
                    db=db,
                    aspect_ratio="9:16",
                    scene_duration_sec=8,
                ):
                    pass
    finally:
        db.close()


@pytest.mark.asyncio
async def test_fact_check_reset_is_restored_and_rejected():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()

        _, api_key = create_api_key(db, APIKeyCreate(owner="Fact Reset Owner", quota_limit=5))
        project = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Fact reset project",
            input_type="manual",
            input_content="Historical fire rescue",
            style="anime",
            num_scenes=10,
        )
        suggestion = {
            "index": 0,
            "title": "Historical Fire Rescue",
            "synopsis": "A verified rescue mission.",
            "topic_type": "historical",
        }
        service = ProductionService(api_key="test_key", db=db, api_key_id=api_key.id)
        cached = make_historical_cached_script(10)
        original_scene_9 = cached["scenes"][8]["action_detail_vi"]
        cached["_resume_signature"] = service._build_resume_signature(
            suggestion=suggestion,
            style="anime",
            num_scenes=10,
            topic_type="historical",
            aspect_ratio="9:16",
            scene_duration_sec=8,
            generation_mode="single",
        )
        project.script_output = json.dumps(cached, ensure_ascii=False)
        project.selected_suggestion_idx = 0
        project.status = "generating_script"
        db.commit()

        async def mock_fact_check_chunk(chunk, *args, **kwargs):
            modified = [dict(scene) for scene in chunk]
            for scene in modified:
                scene["historical_basis_vi"] = "Mô tả dựa trên đồng thuận lịch sử."
                scene["verifiability_level"] = "general_consensus"
                if scene["scene_number"] == 9:
                    scene["action_detail_vi"] = "Chuông báo cháy vang lên như một nhiệm vụ mới."
            return modified, {}

        with patch.object(service, "_fact_check_chunk", side_effect=mock_fact_check_chunk):
            async for _ in service.generate_full_script_stream(
                suggestion=suggestion,
                style="anime",
                num_scenes=10,
                project_id=project.id,
                db=db,
                aspect_ratio="9:16",
                scene_duration_sec=8,
            ):
                pass

        db.refresh(project)
        script_out = to_legacy_v2(json.loads(project.script_output))
        assert script_out["scenes"][8]["action_detail_vi"] != original_scene_9
        assert script_out["_fact_check_completed"] is True
    finally:
        db.close()


def test_batch_mode_disallowed_in_production_without_pytest():
    service = ProductionService(api_key="test_key", db=None)
    pytest_module = sys.modules.pop("pytest", None)
    try:
        from app.core.config import settings
        old_env = settings.ENV
        try:
            settings.ENV = "production"
            assert service._batch_mode_allowed() is False
        finally:
            settings.ENV = old_env
    finally:
        if pytest_module is not None:
            sys.modules["pytest"] = pytest_module


@pytest.mark.asyncio
async def test_resume_skips_completed_fact_check_cache():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()

        _, api_key = create_api_key(db, APIKeyCreate(owner="Fact Cache Owner", quota_limit=5))
        project = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Historical cache project",
            input_type="manual",
            input_content="Old battle",
            style="anime",
            num_scenes=1,
        )

        suggestion = {
            "index": 0,
            "title": "Old Battle",
            "synopsis": "A verified historical battle.",
            "topic_type": "historical",
        }
        service = ProductionService(api_key="test_key", db=db, api_key_id=api_key.id)

        cached = make_blueprint()
        cached["topic_type"] = "historical"
        cached["emotion_arc"] = make_arc()[:1]
        scene = make_scene(1, "Hero tái hiện trận đánh đã fact-check")
        scene["historical_basis_vi"] = "Có ghi chép lịch sử rõ ràng."
        scene["verifiability_level"] = "specific_event"
        cached["scenes"] = [scene]
        cached["_fact_check_completed"] = True
        cached["_resume_signature"] = service._build_resume_signature(
            suggestion=suggestion,
            style="anime",
            num_scenes=1,
            topic_type="historical",
            aspect_ratio="9:16",
            scene_duration_sec=8,
            generation_mode="single",
        )
        project.script_output = json.dumps(cached, ensure_ascii=False)
        project.selected_suggestion_idx = 0
        project.status = "generating_script"
        db.commit()

        with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
            events = [
                event async for event in service.generate_full_script_stream(
                    suggestion=suggestion,
                    style="anime",
                    num_scenes=1,
                    project_id=project.id,
                    db=db,
                    aspect_ratio="9:16",
                    scene_duration_sec=8,
                )
            ]

        assert mock_call.call_count == 0
        assert any("cache_hit_fact_check" in event for event in events)
        db.refresh(project)
        script_out = to_legacy_v2(json.loads(project.script_output))
        assert script_out["_fact_check_completed"] is True
        assert script_out["scenes"][0]["verifiability_level"] == "specific_event"
    finally:
        db.close()
