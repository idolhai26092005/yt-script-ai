import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.production.validation.legacy import blocking_messages, validate_scene_generation_issues
from app.services.production import ProductionService


def make_script_data() -> dict:
    return {
        "schema_version": "2.0",
        "topic_type": "fictional_original",
        "reality_binding_level": "soft",
        "quality_warnings": [],
        "prompt_0": {
            "primary_subject_en": "Kael, young hunter",
            "hard_visual_lock_en": "Cinematic prehistoric survival, no modern objects",
            "setting_lock_en": "Frozen valley, stone tools only",
            "character_lock": [{"name": "Kael", "description_en": "Young hunter with obsidian spear"}],
            "camera_lock_en": "Cinematic grounded camera",
            "voice_sound_lock_en": "English narration, short lines",
            "action_story_logic_en": "1. Kael enters valley. 2. The hunt escalates. 3. Kael learns restraint.",
            "scene_function_rules_en": "One purpose per scene",
            "continuity_lock_en": "Kael keeps the obsidian spear; dirt appears only after a fall.",
            "internal_logic_en": "Stone-age physics, no impossible tools.",
            "negative_constraints_en": "No modern objects.",
        },
        "continuity_evolution": {
            "dirt_on_cloak": {
                "initial_state_en": "Clean cloak",
                "first_cause_scene": 2,
                "first_cause_en": "Kael falls on wet ground",
                "evolves_after_en": "Cloak becomes muddy",
                "must_not_appear_before_cause_en": "No muddy cloak before Scene 2",
            }
        },
        "storyline_vi": "Kael học cách sống sót trong thung lũng băng.",
        "stages_vi": "Giai đoạn 1 (Cảnh 1-2): thiết lập và vấp ngã.",
        "characters": [{"character_name": "Kael", "key_identifiers_en": "obsidian spear"}],
        "environment_master_prompt_en": "Frozen valley",
        "emotion_arc": [
            {
                "scene_number": 1,
                "emotion_label": "lo âu",
                "beat_summary": "Kael tiến vào thung lũng.",
                "physical_state_end": "Kael đứng ở mép thung lũng.",
                "camera_complexity": "low",
            },
            {
                "scene_number": 2,
                "emotion_label": "căng thẳng",
                "beat_summary": "Kael trượt ngã trên nền đất ướt.",
                "physical_state_end": "Kael nằm cạnh giáo.",
                "camera_complexity": "medium",
            },
        ],
        "scenes": [
            {
                "scene_number": 1,
                "title": "Scene 1 [00:00 - 00:08]",
                "action_detail_vi": "Kael bước vào thung lũng với áo choàng sạch.",
                "veo3_prompt_en": "Reference the approved Prompt 0 continuity board, wide shot of Kael entering the frozen valley with clean cloak, no modern objects, voice: \"The valley waits in silence.\"",
                "voice_over_en": "The valley waits in silence.",
                "voice_over_vi": "Thung lũng lặng chờ.",
                "scene_specific_negative_en": "No modern objects",
                "needs_fact_check": False,
                "fact_check_note_vi": None,
                "historical_basis_vi": None,
            },
            {
                "scene_number": 2,
                "title": "Scene 2 [00:08 - 00:16]",
                "action_detail_vi": "Kael trượt ngã trên nền đất ướt, áo choàng bắt đầu dính bùn.",
                "veo3_prompt_en": "Reference the approved Prompt 0 continuity board, handheld shot of Kael slipping on wet ground as mud stains the cloak, no modern objects, voice: \"The ground chooses its lesson.\"",
                "voice_over_en": "The ground chooses its lesson.",
                "voice_over_vi": "Mặt đất dạy bài học.",
                "scene_specific_negative_en": "No modern objects",
                "needs_fact_check": False,
                "fact_check_note_vi": None,
                "historical_basis_vi": None,
            },
        ],
        "reference_images": {
            "character_ref_prompt_en": "",
            "background_ref_prompt_en": "",
            "thumbnail_ref_prompt_en": "",
        },
        "continuity_prompt_en": "Kael keeps the obsidian spear; dirt appears only after a fall.",
        "continuity_board": {
            "continuity_prompt_en": "Kael keeps the obsidian spear; dirt appears only after a fall.",
            "continuity_prompt_vi": "",
        },
        "global_negative_prompt_en": "No modern objects.",
    }


def test_semantic_verifier_speed_gate_runs_only_when_needed():
    # Durable verifier-cost regression: soft fiction should not pay an extra LLM
    # call unless an existing warning/risk flag says the advisory pass is useful.
    service = ProductionService(api_key="test", groq_api_key=None, db=None, api_key_id=None)
    service.enable_semantic_verifier_test = True
    script_data = make_script_data()

    assert service._semantic_verifier_enabled(script_data, "fictional_original") is False

    script_data["quality_warnings"] = ["Scene 1 needs continuity review."]
    assert service._semantic_verifier_enabled(script_data, "fictional_original") is True

    script_data["quality_warnings"] = ["central_contract_drift: scenes 21-30 underuse central subject."]
    assert service._semantic_verifier_enabled(script_data, "fictional_original") is True

    strict_data = make_script_data()
    strict_data["reality_binding_level"] = "strict"
    assert service._semantic_verifier_enabled(strict_data, "historical") is True


@pytest.mark.asyncio
async def test_semantic_verifier_warning_and_valid_patch_do_not_block():
    service = ProductionService(api_key="test", groq_api_key=None, db=None, api_key_id=None)
    service._repo = MagicMock()
    service.enable_semantic_verifier_test = True
    script_data = make_script_data()
    response = {
        "quality_warnings": [
            {
                "scene_number": 1,
                "message_vi": "Thumbnail không nên bịa cảnh tấn công.",
                "suggested_fix_vi": "Dùng hành động Kael bước vào thung lũng.",
            }
        ],
        "scenes": [
            {
                "scene_number": 1,
                "action_detail_vi": "Kael bước vào thung lũng với áo choàng sạch, chưa có bùn.",
                "veo3_prompt_en": "Reference the approved Prompt 0 continuity board, wide shot of Kael entering the frozen valley with clean cloak and obsidian spear, no modern objects, voice: \"The valley waits in silence.\"",
                "voice_over_en": "The valley waits in silence.",
                "voice_over_vi": "Thung lũng lặng chờ.",
                "scene_specific_negative_en": "No modern objects",
                "needs_fact_check": False,
                "fact_check_note_vi": None,
                "historical_basis_vi": None,
            }
        ],
    }

    with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = json.dumps(response)
        edits = await service._phase25_semantic_verifier(
            {"index": 0},
            "cinematic",
            "gemini-3.1-flash-lite",
            script_data,
            1,
            "fictional_original",
            8,
        )

    assert edits == 1
    assert "chưa có bùn" in script_data["scenes"][0]["action_detail_vi"]
    assert script_data["_semantic_verifier_completed"] is True
    assert script_data["quality_warnings"]
    assert not blocking_messages(validate_scene_generation_issues(script_data))


# Durable verifier-cost regression: central drift should give the verifier the
# story contract and compact scene text, not the full expensive prompt payload.
@pytest.mark.asyncio
async def test_semantic_verifier_uses_compact_payload_for_contract_drift():
    service = ProductionService(api_key="test", groq_api_key=None, db=None, api_key_id=None)
    service._repo = MagicMock()
    service.enable_semantic_verifier_test = True
    script_data = make_script_data()
    script_data["story_contract"] = {
        "main_subject_en": "Giant Ancient Mammoth",
        "central_opponent_or_force_en": "Mammoth intelligence",
        "core_goal_en": "outwit the mammoth",
        "must_remain_visible_terms": ["Mammoth"],
        "allowed_side_threats": ["wolves"],
        "forbidden_takeover_rule": "Wolves cannot replace the mammoth conflict.",
    }
    script_data["quality_warnings"] = ["central_contract_drift: scenes 21-30 underuse central subject."]

    with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = json.dumps({"quality_warnings": [], "scenes": []})
        edits = await service._phase25_semantic_verifier(
            {"index": 0},
            "cinematic",
            "gemini-3.1-flash-lite",
            script_data,
            1,
            "fictional_original",
            8,
        )

    prompt = mock_call.call_args.kwargs["prompt"]
    assert edits == 0
    assert "Giant Ancient Mammoth" in prompt
    assert "Central story contract" in prompt
    assert "wide shot of Kael entering the frozen valley" not in prompt


@pytest.mark.asyncio
async def test_semantic_verifier_rejects_invalid_patch_and_keeps_original():
    service = ProductionService(api_key="test", groq_api_key=None, db=None, api_key_id=None)
    service._repo = MagicMock()
    service.enable_semantic_verifier_test = True
    script_data = make_script_data()
    original_action = script_data["scenes"][0]["action_detail_vi"]
    response = {
        "quality_warnings": ["Scene 1 needs a softer continuity fix."],
        "scenes": [
            {
                "scene_number": 1,
                "action_detail_vi": "Template fallback scene.",
                "veo3_prompt_en": "The story continues.",
                "voice_over_en": "",
            }
        ],
    }

    with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = json.dumps(response)
        edits = await service._phase25_semantic_verifier(
            {"index": 0},
            "cinematic",
            "gemini-3.1-flash-lite",
            script_data,
            1,
            "fictional_original",
            8,
        )

    assert edits == 0
    assert script_data["scenes"][0]["action_detail_vi"] == original_action
    assert any("patch rejected" in warning for warning in script_data["quality_warnings"])


@pytest.mark.asyncio
async def test_emotion_arc_stage_mismatch_does_not_retry_or_block():
    # Arc performance guard: wrong-stage lead characters stay advisory in the arc
    # phase so this check cannot multiply expensive LLM retries.
    service = ProductionService(api_key="test", groq_api_key=None, db=None, api_key_id=None)
    script_data = make_script_data()
    script_data["topic_type"] = "historical"
    script_data["characters"] = [
        {"character_name": "Qin Shi Huang", "description_en": "Black robes"},
        {"character_name": "Napoleon", "description_en": "Bicorne hat"},
    ]
    script_data["story_spine"] = {
        "version": "1.2",
        "mode": "single_journey",
        "total_scenes": 2,
        "stage_ranges": [{"scene_start": 1, "scene_end": 2, "label": "Giai đoạn 1 – Tần Thủy Hoàng"}],
        "steps": [{"step": 1, "scene_start": 1, "scene_end": 2, "label": "Vision"}],
        "allowed_once_triggers": [],
    }
    response = {
        "emotion_arc": [
            {
                "scene_number": 1,
                "emotion_label": "căng thẳng",
                "beat_summary": "Napoleon nhìn bản đồ.",
                "physical_state_end": "Napoleon đứng bên bàn.",
                "camera_complexity": "medium",
                "scene_lead_character": "Napoleon",
            },
            {
                "scene_number": 2,
                "emotion_label": "bình yên",
                "beat_summary": "Napoleon khép bản đồ.",
                "physical_state_end": "Napoleon rời bàn.",
                "camera_complexity": "low",
                "scene_lead_character": "Napoleon",
            },
        ]
    }

    with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = json.dumps(response)
        async for _ in service._phase1_generate_emotion_arc(
            {"index": 0},
            "cinematic",
            2,
            "gemini-3.1-flash-lite",
            script_data,
            1,
            "historical",
            persist=False,
            emit_result=False,
            expected_start=1,
            expected_end=2,
        ):
            pass

    assert mock_call.call_count == 1
    assert script_data["emotion_arc"][0]["scene_lead_character"] == "Napoleon"


@pytest.mark.asyncio
async def test_production_llm_timeout_surfaces_phase_context():
    # Timeout guard: provider stalls become explicit phase failures instead of a
    # silent SSE wait on the current longform step.
    service = ProductionService(api_key="test", groq_api_key=None, db=None, api_key_id=None)
    service.production_llm_timeout_sec = 0.01

    async def slow_call(**_kwargs):
        await asyncio.sleep(0.05)
        return "{}"

    with patch.object(service, "_call_gemini_with_retry", new=AsyncMock(side_effect=slow_call)):
        with pytest.raises(TimeoutError, match="emotion_arc.*1-2"):
            await service._call_production_llm(
                prompt="{}",
                model_name="gemini-3.1-flash-lite",
                generation_config={"response_mime_type": "application/json"},
                phase="emotion_arc",
                scene_range=(1, 2),
            )


@pytest.mark.asyncio
async def test_fact_check_failed_chunk_marks_review_without_stream_error():
    # Phase-4 recovery guard: failed fact-check chunks annotate scenes for review
    # without aborting a valid longform baseline.
    service = ProductionService(api_key="test", groq_api_key=None, db=None, api_key_id=None)
    service._repo = MagicMock()
    script_data = make_script_data()
    script_data["topic_type"] = "historical"
    script_data["scenes"] = [script_data["scenes"][0]]
    script_data["emotion_arc"] = [script_data["emotion_arc"][0]]

    async def failed_chunk(*_args, **_kwargs):
        return [service._fact_check_review_scene_update(script_data["scenes"][0], "unknown scene 31")], {
            "_fact_check_warning": "Fact-check validation failed for scenes [1]: unknown scene 31",
        }

    with patch.object(service, "_fact_check_chunk", side_effect=failed_chunk):
        async for _ in service._phase4_fact_check(
            "cinematic",
            "gemini-3.1-flash-lite",
            script_data,
            1,
            "historical",
            8,
        ):
            pass

    assert script_data["_fact_check_completed"] is True
    assert script_data["scenes"][0]["verification_status"] == "needs_review"
    assert script_data["scenes"][0]["needs_fact_check"] is True


@pytest.mark.asyncio
async def test_fact_check_sparse_success_marks_unchanged_scene_checked():
    # Sparse fact-check guard: accurate unchanged scenes still complete
    # verification without forcing per-scene rewrite patches.
    service = ProductionService(api_key="test", groq_api_key=None, db=None, api_key_id=None)
    service._repo = MagicMock()
    script_data = make_script_data()
    script_data["topic_type"] = "historical"
    script_data["scenes"] = [script_data["scenes"][0]]
    script_data["emotion_arc"] = [script_data["emotion_arc"][0]]

    async def sparse_ok(*_args, **_kwargs):
        return [], {}

    with patch.object(service, "_fact_check_chunk", side_effect=sparse_ok):
        async for _ in service._phase4_fact_check(
            "cinematic",
            "gemini-3.1-flash-lite",
            script_data,
            1,
            "historical",
            8,
        ):
            pass

    assert script_data["_fact_check_completed"] is True
    assert script_data["scenes"][0]["verification_status"] == "checked"


@pytest.mark.asyncio
async def test_fact_check_api_error_marks_chunk_needs_review():
    # Phase-4 recovery guard: provider/API failures should preserve generated
    # scenes and surface review status instead of aborting the stream.
    service = ProductionService(api_key="test", groq_api_key=None, db=None, api_key_id=None)
    script_data = make_script_data()
    script_data["topic_type"] = "historical"
    script_data["scenes"] = [script_data["scenes"][0]]
    script_data["emotion_arc"] = [script_data["emotion_arc"][0]]

    with patch.object(service, "_call_gemini_with_retry", new=AsyncMock(side_effect=RuntimeError("provider down"))):
        res, meta = await service._fact_check_chunk(
            script_data["scenes"],
            "cinematic",
            "gemini-3.1-flash-lite",
            script_data,
            True,
        )

    assert "Fact-check API failed" in meta["_fact_check_warning"]
    assert res[0]["verification_status"] == "needs_review"
    assert res[0]["action_detail_vi"] == script_data["scenes"][0]["action_detail_vi"]


@pytest.mark.asyncio
async def test_fact_check_post_merge_code_gate_still_hard_fails():
    # Final-gate guard: patch recovery is not a bypass for invalid merged scenes
    # when lower-level code validators still catch broken output.
    service = ProductionService(api_key="test", groq_api_key=None, db=None, api_key_id=None)
    service._repo = MagicMock()
    script_data = make_script_data()
    script_data["topic_type"] = "historical"
    script_data["reality_binding_level"] = "strict"
    script_data["scenes"] = [script_data["scenes"][0]]
    script_data["emotion_arc"] = [script_data["emotion_arc"][0]]
    bad_scene = dict(script_data["scenes"][0])
    bad_scene["veo3_prompt_en"] = "Bad prompt without approved anchor"
    bad_scene["verification_status"] = "corrected"
    bad_scene["fact_check_note_vi"] = "Broken correction should fail final gate."

    async def bad_chunk(*_args, **_kwargs):
        return [bad_scene], {}

    with patch.object(service, "_fact_check_chunk", side_effect=bad_chunk):
        with pytest.raises(RuntimeError, match="Fact-check merge validation failed"):
            async for _ in service._phase4_fact_check(
                "cinematic",
                "gemini-3.1-flash-lite",
                script_data,
                1,
                "historical",
                8,
            ):
                pass

    assert script_data["_fact_check_completed"] is False


@pytest.mark.asyncio
async def test_packaging_prompt_receives_quality_warnings_and_final_scene_summary():
    service = ProductionService(api_key="test", groq_api_key=None, db=None, api_key_id=None)
    service._repo = MagicMock()
    script_data = make_script_data()
    script_data["quality_warnings"] = ["Thumbnail must not invent a charging attack."]
    response = {
        "background_ref_prompt_en": "Frozen valley background.",
        "thumbnail_ref_prompt_en": "Kael entering the frozen valley, story-accurate.",
    }

    with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = json.dumps(response)
        async for _ in service._phase3_packaging(
            {"index": 0},
            "cinematic",
            "gemini-3.1-flash-lite",
            script_data,
            1,
            "fictional_original",
            "9:16",
        ):
            pass

    prompt = mock_call.call_args.kwargs["prompt"]
    assert "Quality warnings to respect" in prompt
    assert "Thumbnail must not invent a charging attack." in prompt
    assert "Final scene summary" in prompt
    assert script_data["_packaging_uses_quality_context"] is True
