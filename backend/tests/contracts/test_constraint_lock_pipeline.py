from app.services.production.validation.legacy import (
    scene_specific_negative_from_constraints,
    validate_emotion_arc_constraints,
    validate_scene_generation_quality,
)


def _base_script():
    return {
        "prompt_0": {
            "negative_constraints_en": "No fire. No superhuman strength.",
            "internal_logic_en": "Human bodies have normal limits; no extreme heat source exists.",
            "setting_lock_en": "Ice Age forest and snow valley.",
            "continuity_lock_en": "approved continuity",
        },
        "continuity_prompt_en": "approved continuity",
        "characters": [{"character_name": "Kaelen", "key_identifiers_en": "chalk paint"}],
        "environment_master_prompt_en": "snow valley",
        "emotion_arc": [],
        "scenes": [],
    }


def test_emotion_arc_rejects_forbidden_fire_solution():
    script = _base_script()
    script["emotion_arc"] = [{
        "scene_number": 66,
        "emotion_label": "căng thẳng",
        "beat_summary": "Kaelen đốt lửa tạm thời để làm mồi nhử.",
        "physical_state_end": "Ngọn lửa bùng lên cạnh rêu khô.",
        "camera_complexity": "medium",
    }]

    errors = validate_emotion_arc_constraints(script)

    assert any("No fire" in err for err in errors)


def test_scene_generation_requires_project_specific_negative_when_constraints_exist():
    script = _base_script()
    script["scenes"] = [{
        "scene_number": 1,
        "action_detail_vi": "Kaelen bước qua tuyết.",
        "veo3_prompt_en": 'Reference the approved Prompt 0 continuity board, wide shot, Kaelen crosses snow, no modern objects, voice: "The valley waits."',
        "voice_over_en": "The valley waits.",
        "needs_fact_check": False,
    }]

    errors = validate_scene_generation_quality(script)

    assert any("missing scene_specific_negative_en" in err for err in errors)


def test_scene_generation_rejects_hot_metal_and_bare_handed_heavy_lift():
    script = _base_script()
    negative = scene_specific_negative_from_constraints(script)
    script["scenes"] = [{
        "scene_number": 1,
        "action_detail_vi": "Kaelen tay không nâng xà sắt đỏ nóng khỏi lối đi.",
        "veo3_prompt_en": 'Reference the approved Prompt 0 continuity board, close shot, Kaelen lifts a red-hot iron beam with bare hands, voice: "Strength has limits."',
        "voice_over_en": "Strength has limits.",
        "scene_specific_negative_en": negative,
        "needs_fact_check": False,
    }]

    errors = validate_scene_generation_quality(script)

    assert any("No superhuman strength" in err for err in errors)
    assert any("hot metal" in err for err in errors)


def test_scene_specific_negative_backfill_uses_prompt0_constraints():
    script = _base_script()
    scene = {"action_detail_vi": "Kaelen tránh rêu khô.", "veo3_prompt_en": "Reference the approved shot"}

    negative = scene_specific_negative_from_constraints(script, scene)

    assert "No fire" in negative
    assert "No superhuman strength" in negative
