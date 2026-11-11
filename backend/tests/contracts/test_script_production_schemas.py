import sys
import os
import pytest
from pydantic import ValidationError

# Add parent path to path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from app.schemas.script_production import (
    InputType,
    PresetStyle,
    StyleInput,
    GenerateSuggestionsRequest,
    GenerateFullScriptRequest,
    ProjectStatus,
    ScriptSuggestion,
    SceneScript,
    CharacterPrompt,
    EmotionArcEntry,
    ReferenceImagePrompts,
    ScriptOutput
)

def test_style_input_validation():
    # Test valid preset style
    style = StyleInput(preset=PresetStyle.ANIME)
    assert style.preset == PresetStyle.ANIME
    assert style.custom is None
    
    # Test custom style
    style = StyleInput(custom="cyberpunk 1980s neon")
    assert style.preset is None
    assert style.custom == "cyberpunk 1980s neon"
    
    # Test blank / defaults
    style = StyleInput()
    assert style.preset is None
    assert style.custom is None

# Duration contract guard: suggestion creation now carries scene timing so
# restored projects do not silently revert to the old 8-second default.
def test_suggestions_request_validation():
    # Test valid request
    req = GenerateSuggestionsRequest(
        input_type=InputType.MANUAL,
        input_content="Chiến tranh La Mã cổ đại",
        num_scenes=8,
        num_suggestions=5,
        scene_duration_sec=10
    )
    assert req.input_type == InputType.MANUAL
    assert req.num_scenes == 8
    assert req.scene_duration_sec == 10
    assert req.style.preset == PresetStyle.ANIME  # default behavior

    # Test out of bounds num_scenes (le 200)
    with pytest.raises(ValidationError):
        GenerateSuggestionsRequest(
            input_type=InputType.MANUAL,
            input_content="Concept",
            num_scenes=250  # Limit is 200
        )

    # Test out of bounds num_scenes (ge 4)
    with pytest.raises(ValidationError):
        GenerateSuggestionsRequest(
            input_type=InputType.MANUAL,
            input_content="Concept",
            num_scenes=2  # Limit is 4
        )

# Recovery request guard: detailed generation resumes by default and only
# discards cached artifacts when the operator explicitly asks for restart.
def test_full_script_request_accepts_recovery_restart_flag():
    req = GenerateFullScriptRequest(project_id=1, suggestion_index=0, restart=True)

    assert req.restart is True
    assert ProjectStatus.SCRIPT_FAILED.value == "script_failed"

def test_script_output_structure():
    # Build complete valid ScriptOutput object
    output_data = {
        "overview_analysis_vi": "Phân tích nhịp điệu chậm, cinematic.",
        "storyline_vi": "Chim vượt giông tố để dệt tổ.",
        "stages_vi": "Giai đoạn 1: Chuẩn bị",
        "progression_vi": "Cảnh 1-3: Thiết lập",
        "camera_strategy_vi": "Phong cách tài liệu chân thực",
        "continuity_locks_vi": "Cố định 1 chim dệt tổ",
        "form_locks_vi": "Dáng mỏ chim không đổi",
        "age_stage_locks_vi": "Chim trưởng thành",
        "geometry_locks_vi": "Tổ treo trên cành cây sát nước",
        "risk_logic_vi": "Gió mạnh dần theo giai đoạn",
        "characters": [
            {
                "character_name": "Pharaoh Khufu",
                "description_en": "An old Egyptian ruler with a golden crown."
            }
        ],
        "environment_master_prompt_en": "Sandy pyramids under hot sun, golden hour lighting.",
        "scenes": [
            {
                "scene_number": 1,
                "title": "Scene 1 [00:00 - 00:08]",
                "action_detail_vi": "Pharaoh đứng nhìn kim tự tháp",
                "emotion_gesture_vi": "Vẻ mặt trầm ngâm suy tư",
                "camera_movement_vi": "Zoom chậm cận cảnh",
                "transition_to_next_vi": "Fade out sang cảnh tiếp",
                "veo3_prompt_en": "A close up cinematic shot of Pharaoh Khufu looking at pyramids",
                "negative_prompt_en": "low quality, bad anatomy"
            }
        ],
        "continuity_prompt_en": "Keep the clothing identical, light coming from the left.",
        "global_negative_prompt_en": "deformed limbs, noisy, watermark",
        "reference_images": {
            "character_ref_prompt_en": "Character ref sheet",
            "background_ref_prompt_en": "Background ref sheet",
            "thumbnail_ref_prompt_en": "Clickbait thumbnail layout"
        }
    }
    
    script_output = ScriptOutput(**output_data)
    assert script_output.overview_analysis_vi == "Phân tích nhịp điệu chậm, cinematic."
    assert script_output.storyline_vi == "Chim vượt giông tố để dệt tổ."
    assert script_output.stages_vi == "Giai đoạn 1: Chuẩn bị"
    assert script_output.form_locks_vi == "Dáng mỏ chim không đổi"
    assert len(script_output.characters) == 1
    assert script_output.characters[0].character_name == "Pharaoh Khufu"
    assert len(script_output.scenes) == 1
    assert script_output.scenes[0].scene_number == 1
    assert script_output.reference_images.character_ref_prompt_en == "Character ref sheet"

    # Test missing field should raise ValidationError
    bad_data = output_data.copy()
    bad_data.pop("scenes")
    with pytest.raises(ValidationError):
        ScriptOutput(**bad_data)

def test_emotion_arc_entry_validation():
    entry = EmotionArcEntry(
        scene_number=1,
        emotion_label="hùng tráng",
        beat_summary="Đóng cọc gỗ",
        physical_state_end="Đứng chỉ tay",
        camera_complexity="low",
        scene_lead_character="Ngô Quyền"
    )
    assert entry.scene_lead_character == "Ngô Quyền"
