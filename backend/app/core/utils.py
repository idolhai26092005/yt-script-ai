def clean_json_response(text: str) -> str:
    """
    Cleans markdown json code blocks or extra whitespace from LLM response text.
    """
    if not text:
        return ""

    # Strip leading/trailing whitespaces and newlines
    cleaned = text.strip()

    # Remove markdown code block wrappers
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    cleaned = cleaned.strip()
    return cleaned


def parse_llm_json_response(text: str):
    """
    Parse the first valid JSON value from an LLM response.
    Some providers return a valid JSON object followed by an extra note/object even
    with JSON MIME enabled; callers should validate the parsed shape afterward.
    """
    cleaned = clean_json_response(text)
    try:
        import json
        return json.loads(cleaned)
    except Exception:
        import json
        starts = [idx for idx in (cleaned.find("{"), cleaned.find("[")) if idx >= 0]
        if not starts:
            raise
        parsed, _ = json.JSONDecoder().raw_decode(cleaned[min(starts):])
        return parsed


# Durable schema guard: v2 scenes remain the in-memory work format while
# canonical v3 is saved externally, so aliases from new prompts must normalize here.
def ensure_scene_defaults(scene: dict, base_negative_prompt: str = "") -> dict:
    """
    Ensures that a scene dictionary has all expected fields for schema v2.0 compatibility.
    Legacy fields (emotion_gesture_vi, camera_movement_vi, transition_to_next_vi, veo3_prompt_vi)
    are set to empty string if missing — they are no longer actively generated but kept for
    schema backward compatibility.
    """
    if "action_detail_vi" not in scene and "action_vi" in scene:
        scene["action_detail_vi"] = scene.get("action_vi")
    if "veo3_prompt_en" not in scene and "veo_prompt_en" in scene:
        scene["veo3_prompt_en"] = scene.get("veo_prompt_en")
    if "voice_over_en" not in scene and "voice_en" in scene:
        scene["voice_over_en"] = scene.get("voice_en")
    if "voice_over_vi" not in scene and "voice_vi" in scene:
        scene["voice_over_vi"] = scene.get("voice_vi")
    if "scene_specific_negative_en" not in scene and "scene_negative_en" in scene:
        scene["scene_specific_negative_en"] = scene.get("scene_negative_en")
    if "historical_basis_vi" not in scene and "basis_vi" in scene:
        scene["historical_basis_vi"] = scene.get("basis_vi")

    num = scene.get("scene_number", 1)
    if "scene_number" not in scene or not scene["scene_number"]:
        scene["scene_number"] = num
    if "title" not in scene or not scene["title"]:
        scene["title"] = f"Scene {num}"

    # Core required fields (v2.0)
    required_fields = [
        "action_detail_vi",
        "veo3_prompt_en",
    ]
    for field in required_fields:
        if field not in scene or scene[field] is None:
            scene[field] = ""

    # Voice fields
    if "voice_over_en" not in scene:
        scene["voice_over_en"] = None
    if "voice_over_vi" not in scene:
        scene["voice_over_vi"] = None

    # Legacy fields — kept for schema compatibility, empty by default
    legacy_fields = [
        "emotion_gesture_vi",
        "camera_movement_vi",
        "transition_to_next_vi",
        "veo3_prompt_vi",
    ]
    for field in legacy_fields:
        if field not in scene or scene[field] is None:
            scene[field] = ""

    # Fact-check fields
    if "historical_basis_vi" not in scene:
        scene["historical_basis_vi"] = None
    if "needs_fact_check" not in scene:
        scene["needs_fact_check"] = False
    if "fact_check_note_vi" not in scene:
        scene["fact_check_note_vi"] = None
    if "verifiability_level" not in scene:
        scene["verifiability_level"] = None

    # Negative prompts — scene_specific_negative_en is project-specific in v2.0.
    if "scene_specific_negative_en" not in scene:
        scene["scene_specific_negative_en"] = ""

    # Generation status
    if "generation_failed" not in scene:
        scene["generation_failed"] = False
    if "generation_error" not in scene:
        scene["generation_error"] = None

    # Negative prompt — use base negative if not set
    if "negative_prompt_en" not in scene or not scene["negative_prompt_en"]:
        scene["negative_prompt_en"] = base_negative_prompt

    return scene


# Durable schema guard: titles are backend-owned timing data, never an LLM contract.
def scene_timing(scene_number: int, scene_duration_sec: int) -> dict:
    start_sec = (scene_number - 1) * scene_duration_sec
    end_sec = scene_number * scene_duration_sec
    start_min, start_s = start_sec // 60, start_sec % 60
    end_min, end_s = end_sec // 60, end_sec % 60
    return {
        "start_sec": start_sec,
        "end_sec": end_sec,
        "title": f"Scene {scene_number} [{start_min:02d}:{start_s:02d} - {end_min:02d}:{end_s:02d}]",
    }


# Durable schema guard: v3 source/display/verification must always have safe containers
# without pretending that missing fact-check data came from the model.
def ensure_scene_v3_defaults(scene: dict) -> dict:
    scene.setdefault("source", {})
    scene.setdefault("display", {})
    scene.setdefault("verification", {})
    scene.setdefault("generation", {})
    scene.setdefault("meta", {})
    scene["verification"].setdefault("status", "unverified")
    scene["verification"].setdefault("level", None)
    scene["verification"].setdefault("basis_vi", None)
    scene["verification"].setdefault("risk_flags", [])
    scene["verification"].setdefault("notes_vi", [])
    scene["generation"].setdefault("failed", False)
    scene["generation"].setdefault("error", None)
    scene["meta"].setdefault("field_origin", {})
    scene["meta"].setdefault("edited_by", [])
    return scene


# Durable schema guard: legacy UI/API consumers still read flat v2 fields while
# the database can store the cleaner v3 contract.
def to_legacy_v2(script_data: dict | None) -> dict:
    if not isinstance(script_data, dict):
        return {}
    if script_data.get("schema_version") != "3.0":
        import json
        return json.loads(json.dumps(script_data, ensure_ascii=False))

    import json
    topic = script_data.get("topic") or {}
    plan = script_data.get("production_plan") or {}
    anchors = script_data.get("anchors") or {}
    internal = script_data.get("internal") or {}
    pipeline = internal.get("pipeline") or {}
    validation = internal.get("validation") or {}
    cache = internal.get("cache") or {}

    legacy = {
        "schema_version": "2.0",
        "topic_type": topic.get("type") or "fictional_original",
        "reality_binding_level": topic.get("reality_binding_level") or "soft",
        "narrative_shape": topic.get("narrative_shape"),
        "overview_analysis_vi": plan.get("overview_vi") or "",
        "storyline_vi": plan.get("storyline_vi") or "",
        "stages_vi": plan.get("stages_vi") or "",
        "progression_vi": plan.get("progression_vi") or "",
        "camera_strategy_vi": plan.get("camera_strategy_vi") or "",
        "continuity_locks_vi": plan.get("continuity_locks_vi") or "",
        "form_locks_vi": plan.get("form_locks_vi") or "",
        "age_stage_locks_vi": plan.get("age_stage_locks_vi") or "",
        "geometry_locks_vi": plan.get("geometry_locks_vi") or "",
        "risk_logic_vi": plan.get("risk_logic_vi") or "",
        "voice_sound_strategy_vi": plan.get("voice_sound_strategy_vi") or "",
        "prompt_0": anchors.get("prompt_0") or {},
        "continuity_evolution": anchors.get("continuity_evolution") or {},
        "characters": anchors.get("characters") or [],
        "environment_master_prompt_en": anchors.get("environment_master_prompt_en") or "",
        "environment_master_prompt_vi": anchors.get("environment_master_prompt_vi") or "",
        "continuity_prompt_en": anchors.get("continuity_prompt_en") or "",
        "continuity_prompt_vi": anchors.get("continuity_prompt_vi") or "",
        "continuity_board": {
            "continuity_prompt_en": anchors.get("continuity_prompt_en") or "",
            "continuity_prompt_vi": anchors.get("continuity_prompt_vi") or "",
        },
        "global_negative_prompt_en": anchors.get("global_negative_prompt_en") or "",
        "emotion_arc": script_data.get("emotion_arc") or [],
        "scenes": [],
        "reference_images": script_data.get("reference_images") or {},
        "story_spine": internal.get("story_spine") or {},
        "quality_warnings": validation.get("quality_warnings") or [],
        "_resume_signature": cache.get("resume_signature") or {},
        "_semantic_verifier_completed": bool(pipeline.get("semantic_verifier_completed")),
        "_fact_check_completed": bool(pipeline.get("fact_check_completed")),
        "_packaging_uses_quality_context": bool(pipeline.get("packaging_uses_quality_context")),
        "series_bridge_vi": script_data.get("series_bridge_vi"),
    }
    if "post_suggestions" in script_data:
        legacy["post_suggestions"] = script_data.get("post_suggestions")

    for scene in script_data.get("scenes") or []:
        source = scene.get("source") or {}
        display = scene.get("display") or {}
        verification = scene.get("verification") or {}
        generation = scene.get("generation") or {}
        meta = scene.get("meta") or {}
        notes = verification.get("notes_vi") or []
        note = "; ".join(str(n) for n in notes if n) or None
        risk_flags = verification.get("risk_flags") or []
        legacy_scene = {
            "scene_number": scene.get("scene_number"),
            "title": (scene.get("timing") or {}).get("title") or f"Scene {scene.get('scene_number')}",
            "action_detail_vi": source.get("action_vi") or "",
            "veo3_prompt_en": source.get("veo_prompt_en") or "",
            "voice_over_en": source.get("voice_en"),
            "voice_over_vi": display.get("voice_vi"),
            "scene_specific_negative_en": source.get("scene_negative_en") or "",
            "emotion_gesture_vi": display.get("emotion_vi") or "",
            "camera_movement_vi": display.get("camera_vi") or "",
            "transition_to_next_vi": display.get("transition_vi") or "",
            "veo3_prompt_vi": display.get("prompt_summary_vi") or "",
            "negative_prompt_en": legacy.get("global_negative_prompt_en") or "",
            "historical_basis_vi": verification.get("basis_vi"),
            "verifiability_level": verification.get("level"),
            "needs_fact_check": verification.get("status") == "needs_review" or bool(risk_flags),
            "fact_check_note_vi": note,
            "generation_failed": bool(generation.get("failed")),
            "generation_error": generation.get("error"),
        }
        if "semantic_verifier" in (meta.get("edited_by") or []):
            legacy_scene["_semantic_verified_edit"] = True
        ensure_scene_defaults(legacy_scene, legacy.get("global_negative_prompt_en") or "")
        legacy["scenes"].append(legacy_scene)
    return json.loads(json.dumps(legacy, ensure_ascii=False))


# Durable schema guard: every save path funnels v2 work data into one canonical v3 layout,
# keeping field origin explicit and preventing silent null fact-check fields in source.
# Durable topic-contract guard: internal.story_contract is persisted for quality routing
# but stays out of the legacy UI shape until the frontend intentionally adopts it.
def to_canonical_v3(script_data: dict | None, scene_duration_sec: int = 8) -> dict:
    if not isinstance(script_data, dict):
        script_data = {}
    if script_data.get("schema_version") == "3.0":
        import json
        cloned = json.loads(json.dumps(script_data, ensure_ascii=False))
        cloned.setdefault("internal", {}).setdefault("story_contract", {})
        for scene in cloned.get("scenes") or []:
            ensure_scene_v3_defaults(scene)
        return cloned

    import json
    script = json.loads(json.dumps(script_data, ensure_ascii=False))
    topic_type = script.get("topic_type") or "fictional_original"
    v3 = {
        "schema_version": "3.0",
        "topic": {
            "type": topic_type,
            "reality_binding_level": script.get("reality_binding_level") or "soft",
            "narrative_shape": script.get("narrative_shape"),
        },
        "production_plan": {
            "overview_vi": script.get("overview_analysis_vi") or "",
            "storyline_vi": script.get("storyline_vi") or "",
            "stages_vi": script.get("stages_vi") or "",
            "progression_vi": script.get("progression_vi") or "",
            "camera_strategy_vi": script.get("camera_strategy_vi") or "",
            "continuity_locks_vi": script.get("continuity_locks_vi") or "",
            "form_locks_vi": script.get("form_locks_vi") or "",
            "age_stage_locks_vi": script.get("age_stage_locks_vi") or "",
            "geometry_locks_vi": script.get("geometry_locks_vi") or "",
            "risk_logic_vi": script.get("risk_logic_vi") or "",
            "voice_sound_strategy_vi": script.get("voice_sound_strategy_vi") or "",
        },
        "anchors": {
            "prompt_0": script.get("prompt_0") or {},
            "continuity_evolution": script.get("continuity_evolution") or {},
            "continuity_prompt_en": script.get("continuity_prompt_en") or (script.get("continuity_board") or {}).get("continuity_prompt_en") or "",
            "continuity_prompt_vi": script.get("continuity_prompt_vi") or (script.get("continuity_board") or {}).get("continuity_prompt_vi") or "",
            "global_negative_prompt_en": script.get("global_negative_prompt_en") or "",
            "characters": script.get("characters") or [],
            "environment_master_prompt_en": script.get("environment_master_prompt_en") or "",
            "environment_master_prompt_vi": script.get("environment_master_prompt_vi") or "",
        },
        "emotion_arc": script.get("emotion_arc") or [],
        "scenes": [],
        "reference_images": script.get("reference_images") or {},
        "internal": {
            "pipeline": {
                "semantic_verifier_completed": bool(script.get("_semantic_verifier_completed")),
                "fact_check_completed": bool(script.get("_fact_check_completed")),
                "packaging_uses_quality_context": bool(script.get("_packaging_uses_quality_context")),
            },
            "validation": {
                "quality_warnings": script.get("quality_warnings") or [],
            },
            "cache": {
                "resume_signature": script.get("_resume_signature") or {},
            },
            "story_spine": script.get("story_spine") or {},
            "story_contract": script.get("story_contract") or {},
        },
    }
    if "post_suggestions" in script:
        v3["post_suggestions"] = script.get("post_suggestions")
    if script.get("series_bridge_vi") is not None:
        v3["series_bridge_vi"] = script.get("series_bridge_vi")

    for scene in sorted(script.get("scenes") or [], key=lambda s: s.get("scene_number", 0)):
        ensure_scene_defaults(scene, script.get("global_negative_prompt_en") or "")
        num = scene.get("scene_number") or 1
        status = scene.get("verification_status")
        risk_flags = scene.get("verification_risk_flags") or []
        if not status:
            if scene.get("needs_fact_check"):
                status = "needs_review"
            elif script.get("_fact_check_completed") and topic_type in ("historical", "scientific"):
                status = "checked"
            else:
                status = "unverified"
        notes = scene.get("verification_notes_vi")
        if notes is None:
            note = scene.get("fact_check_note_vi")
            notes = [note] if note else []
        v3_scene = {
            "scene_number": num,
            "timing": scene_timing(num, scene_duration_sec),
            "source": {
                "action_vi": scene.get("action_detail_vi") or "",
                "veo_prompt_en": scene.get("veo3_prompt_en") or "",
                "voice_en": scene.get("voice_over_en"),
                "scene_negative_en": scene.get("scene_specific_negative_en") or "",
            },
            "display": {
                "voice_vi": scene.get("voice_over_vi"),
                "camera_vi": scene.get("camera_movement_vi") or "",
                "emotion_vi": scene.get("emotion_gesture_vi") or "",
                "transition_vi": scene.get("transition_to_next_vi") or "",
                "prompt_summary_vi": scene.get("veo3_prompt_vi") or "",
            },
            "verification": {
                "status": status,
                "level": scene.get("verifiability_level"),
                "basis_vi": scene.get("historical_basis_vi"),
                "risk_flags": risk_flags,
                "notes_vi": notes,
            },
            "generation": {
                "failed": bool(scene.get("generation_failed")),
                "error": scene.get("generation_error"),
            },
            "meta": {
                "field_origin": {
                    "source.action_vi": "llm_phase_2",
                    "source.veo_prompt_en": "llm_phase_2",
                    "source.voice_en": "llm_phase_2",
                    "source.scene_negative_en": "llm_phase_2_or_backend_derived",
                    "timing.title": "backend",
                    "display": "backend_derived",
                    "verification": "phase_4_fact_check" if status != "unverified" else "not_checked",
                },
                "edited_by": ["semantic_verifier"] if scene.get("_semantic_verified_edit") else [],
            },
        }
        ensure_scene_v3_defaults(v3_scene)
        v3["scenes"].append(v3_scene)
    return v3
