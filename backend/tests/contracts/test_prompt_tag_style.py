from app.services.production.prompts.legacy import (
    BATCH_SCENE_GENERATION_TEMPLATE,
    PROMPT_0_GENERATION_TEMPLATE,
)
from app.services.production.base import build_prompt_0_text


def test_prompt_0_template_requests_tag_block_style():
    assert "TAG-BLOCK STYLE" in PROMPT_0_GENERATION_TEMPLATE
    assert "Primary Subject / Primary Creature" in PROMPT_0_GENERATION_TEMPLATE
    assert "Main Location / Habitat Geometry" in PROMPT_0_GENERATION_TEMPLATE


def test_batch_scene_template_preserves_reference_prefix_but_uses_sample_style():
    assert 'MUST start with EXACTLY: "Reference the approved Prompt 0 continuity board,' in BATCH_SCENE_GENERATION_TEMPLATE
    assert 'WITHOUT adding "scene N:" inside this field' in BATCH_SCENE_GENERATION_TEMPLATE
    assert 'Do NOT write "main character", "protagonist"' in BATCH_SCENE_GENERATION_TEMPLATE
    assert "No bracket-template leakage" in BATCH_SCENE_GENERATION_TEMPLATE
    assert "Kael grips the jagged obsidian spear" in BATCH_SCENE_GENERATION_TEMPLATE


def test_build_prompt_0_text_uses_sample_like_headers():
    prompt_0_text = build_prompt_0_text({
        "primary_subject_en": "Young chief and coordinated hunters.",
        "hard_visual_lock_en": "Cinematic prehistoric survival.",
        "setting_lock_en": "Frozen valley and tribal village.",
        "character_lock": [{"name": "Kael", "description_en": "Obsidian spear, mammoth-hide cloak."}],
        "continuity_lock_en": "Snow accumulation persists.",
    })

    assert prompt_0_text.startswith("Prompt 0\nIdentity / Species Lock")
    assert "Primary Subject: Young chief" in prompt_0_text
    assert "Hard Visual / Form Lock:" in prompt_0_text
    assert "Character Lock — Kael:" in prompt_0_text
