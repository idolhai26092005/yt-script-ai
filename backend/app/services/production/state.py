import json

from app.core.utils import to_legacy_v2


# Work-state factory guard: the producer still uses the flat v2 shape internally,
# so extraction must preserve every default key until the role graph owns state.
def new_script_data(topic_type: str) -> dict:
    return {
        "schema_version": "2.0",
        "topic_type": topic_type,
        "prompt_0": {},
        "overview_analysis_vi": "",
        "storyline_vi": "",
        "stages_vi": "",
        "progression_vi": "",
        "camera_strategy_vi": "",
        "continuity_locks_vi": "",
        "form_locks_vi": "",
        "age_stage_locks_vi": "",
        "geometry_locks_vi": "",
        "risk_logic_vi": "",
        "voice_sound_strategy_vi": "",
        "characters": [],
        "environment_master_prompt_en": "",
        "environment_master_prompt_vi": "",
        "emotion_arc": [],
        "scenes": [],
        "story_spine": {},
        "story_contract": {},
        "quality_warnings": [],
        "narrative_shape": None,
        "reality_binding_level": "soft",
        "continuity_evolution": {},
        "_semantic_verifier_completed": False,
        "continuity_board": {"continuity_prompt_en": "", "continuity_prompt_vi": ""},
        "continuity_prompt_en": "",
        "continuity_prompt_vi": "",
        "global_negative_prompt_en": "",
        "reference_images": {
            "character_ref_prompt_en": "",
            "background_ref_prompt_en": "",
            "thumbnail_ref_prompt_en": "",
        },
        "series_bridge_vi": None,
        "_fact_check_completed": False,
    }


# Resume-cache guard: signatures describe the public saved artifact contract, not
# the temporary producer work-state, so cache checks survive later module moves.
def build_resume_signature(
    suggestion: dict,
    style: str,
    num_scenes: int,
    topic_type: str,
    aspect_ratio: str,
    scene_duration_sec: int,
    generation_mode: str,
) -> dict:
    return {
        "schema_version": "3.0",
        "suggestion_index": suggestion.get("index", 0),
        "suggestion_title": suggestion.get("title", ""),
        "suggestion_synopsis": suggestion.get("synopsis", ""),
        "style": style,
        "num_scenes": num_scenes,
        "topic_type": topic_type,
        "aspect_ratio": aspect_ratio,
        "scene_duration_sec": scene_duration_sec,
        "generation_mode": generation_mode,
    }


# Resume-cache guard: legacy v2 cache signatures remain valid while canonical v3
# persistence is rolled out and producer internals are split into modules.
def is_resume_cache_compatible(cached: dict | None, signature: dict) -> bool:
    cached_v2 = to_legacy_v2(cached)
    if not isinstance(cached_v2, dict):
        return False
    cached_signature = cached_v2.get("_resume_signature")
    legacy_signature = dict(signature)
    legacy_signature["schema_version"] = "2.0"
    return cached_signature in (signature, legacy_signature)


# Resume-cache guard: hydration intentionally preserves current v2 work-state
# behavior so state extraction is a pure move before role contracts change.
def hydrate_resume_cache(script_data: dict, cached: dict) -> None:
    cached = to_legacy_v2(cached)
    for key, value in cached.items():
        if key in script_data or key in ("schema_version", "topic_type", "_resume_signature", "post_suggestions"):
            script_data[key] = json.loads(json.dumps(value, ensure_ascii=False))
    script_data["schema_version"] = "2.0"
    script_data.setdefault("continuity_board", {"continuity_prompt_en": "", "continuity_prompt_vi": ""})
    script_data.setdefault("reference_images", {
        "character_ref_prompt_en": "",
        "background_ref_prompt_en": "",
        "thumbnail_ref_prompt_en": "",
    })
    script_data.setdefault("quality_warnings", [])
    if isinstance(cached, dict) and cached.get("schema_version") == "3.0":
        internal_contract = ((cached.get("internal") or {}).get("story_contract") or {})
        if internal_contract:
            script_data["story_contract"] = json.loads(json.dumps(internal_contract, ensure_ascii=False))
    script_data.setdefault("story_contract", {})
    script_data.setdefault("narrative_shape", None)
    script_data.setdefault("reality_binding_level", "soft")
    script_data.setdefault("continuity_evolution", {})
    script_data.setdefault("_semantic_verifier_completed", False)
