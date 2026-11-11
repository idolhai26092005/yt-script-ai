import pytest
from typing import Literal
from app.schemas.script_production import (
    GenerateSuggestionsRequest,
    GenerateFullScriptRequest,
    CharacterPrompt,
    SceneScript,
    ScriptOutput,
    ReferenceImagePrompts,
    EmotionArcEntry,
    TopicType,
    InputType,
    StyleInput,
    PresetStyle
)

def test_generate_suggestions_request_extended():
    # Verify defaults and new fields
    req = GenerateSuggestionsRequest(
        input_type=InputType.MANUAL,
        input_content="Ý tưởng mới",
        num_scenes=25, # extended scenes accepted
        generation_mode="series_long"
    )
    assert req.num_scenes == 25
    assert req.generation_mode == "series_long"
    assert req.regenerate_with_input is None

def test_generate_full_script_request_extended():
    req = GenerateFullScriptRequest(
        project_id=1,
        suggestion_index=0,
        generation_mode="longform"
    )
    assert req.generation_mode == "longform"

def test_character_prompt_extended():
    # Backward compatibility: should validate without description_vi
    char = CharacterPrompt(
        character_name="Bướm mẹ",
        description_en="A beautiful butterfly"
    )
    assert char.description_vi == ""
    assert char.key_identifiers_vi == ""

    # Should accept _vi fields
    char_new = CharacterPrompt(
        character_name="Bướm mẹ",
        description_en="A beautiful butterfly",
        description_vi="Một con bướm đẹp",
        key_identifiers_en="butterfly wings",
        key_identifiers_vi="cánh bướm"
    )
    assert char_new.description_vi == "Một con bướm đẹp"
    assert char_new.key_identifiers_vi == "cánh bướm"

def test_scene_script_extended():
    # Backward compatibility: should validate without veo3_prompt_vi
    scene = SceneScript(
        scene_number=1,
        title="Scene 1",
        action_detail_vi="Bay",
        emotion_gesture_vi="Vui",
        camera_movement_vi="Tĩnh",
        transition_to_next_vi="Mờ",
        veo3_prompt_en="fly",
        negative_prompt_en="ugly"
    )
    assert scene.veo3_prompt_vi == ""

    # Should accept veo3_prompt_vi
    scene_new = SceneScript(
        scene_number=1,
        title="Scene 1",
        action_detail_vi="Bay",
        emotion_gesture_vi="Vui",
        camera_movement_vi="Tĩnh",
        transition_to_next_vi="Mờ",
        veo3_prompt_en="fly",
        veo3_prompt_vi="bay lượn",
        negative_prompt_en="ugly"
    )
    assert scene_new.veo3_prompt_vi == "bay lượn"
