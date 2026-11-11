from typing import Any, Iterable

from app.core.utils import parse_llm_json_response
from app.services.series_v2.contracts import (
    ENDING_SEASON_FINALE,
    SCHEMA_VERSION,
    STRICT_TOPIC_TYPES,
)


# JSON gate guard: empty or non-object LLM output is a technical failure and
# should be retried with exact feedback instead of receiving fabricated fallback.
def parse_json_object(raw_text: str) -> dict[str, Any]:
    if not raw_text or not raw_text.strip():
        raise ValueError("empty_output")
    parsed = parse_llm_json_response(raw_text)
    if not isinstance(parsed, dict):
        raise ValueError("output_must_be_object")
    return parsed


# Required-key guard: validators report exact missing paths so retry prompts can
# be targeted and tests can assert narrow hard-gate behavior.
def _require_mapping(data: dict[str, Any], key: str, errors: list[str]) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        errors.append(f"{key}_must_be_object")
        return {}
    return value


# Required-list guard: list artifacts carry cardinality contracts for season
# slots, emotion arcs, scenes, review threads, and fact patches.
def _require_list(data: dict[str, Any], key: str, errors: list[str]) -> list[Any]:
    value = data.get(key)
    if not isinstance(value, list):
        errors.append(f"{key}_must_be_list")
        return []
    return value


# Setup validator guard: setup must return real season slots from the model and
# never silently synthesize fallback episode maps.
def validate_setup_artifacts(data: dict[str, Any], target_episode_count: int) -> list[str]:
    errors: list[str] = []
    _require_mapping(data, "series_bible", errors)
    season_map = _require_mapping(data, "season_map", errors)
    slots = _require_list(season_map, "episode_slots", errors)
    if len(slots) != target_episode_count:
        errors.append(f"episode_slots_count_must_equal_{target_episode_count}")
    seen: set[int] = set()
    for idx, slot in enumerate(slots, start=1):
        if not isinstance(slot, dict):
            errors.append(f"episode_slot_{idx}_must_be_object")
            continue
        if slot.get("episode_number") != idx:
            errors.append(f"episode_slot_{idx}_number_must_be_{idx}")
        if not slot.get("title"):
            errors.append(f"episode_slot_{idx}_title_required")
        if not slot.get("intended_next_start_state") and idx < target_episode_count:
            errors.append(f"episode_slot_{idx}_next_start_state_required")
        if slot.get("episode_number") in seen:
            errors.append(f"episode_slot_{idx}_duplicate_number")
        seen.add(slot.get("episode_number"))
        if idx < target_episode_count and slot.get("ending_mode") == ENDING_SEASON_FINALE:
            errors.append(f"episode_slot_{idx}_season_finale_not_allowed")
    return errors


# Episode plan validator guard: the accepted scene count is the source of truth
# for both planning and later scene generation.
def validate_episode_plan(data: dict[str, Any], scene_count: int) -> list[str]:
    errors: list[str] = []
    _require_mapping(data, "episode_blueprint", errors)
    emotion_arc = _require_list(data, "emotion_arc", errors)
    if len(emotion_arc) != scene_count:
        errors.append(f"emotion_arc_count_must_equal_{scene_count}")
    for idx, beat in enumerate(emotion_arc, start=1):
        if not isinstance(beat, dict):
            errors.append(f"emotion_arc_{idx}_must_be_object")
            continue
        if beat.get("scene_number") != idx:
            errors.append(f"emotion_arc_{idx}_scene_number_must_be_{idx}")
        if not beat.get("anchor_to_cite"):
            errors.append(f"emotion_arc_{idx}_anchor_to_cite_required")
    return errors


# Scene validator guard: only measurable rendering prerequisites hard-fail; no
# creative-quality wording is blocked in code.
def validate_scene_batch(data: dict[str, Any], batch_start: int, batch_end: int) -> list[str]:
    errors: list[str] = []
    scenes = _require_list(data, "scenes", errors)
    expected_numbers = list(range(batch_start, batch_end + 1))
    actual_numbers = [scene.get("scene_number") for scene in scenes if isinstance(scene, dict)]
    if actual_numbers != expected_numbers:
        errors.append(f"scene_numbers_must_equal_{expected_numbers}")
    for scene_number, scene in zip(expected_numbers, scenes):
        if not isinstance(scene, dict):
            errors.append(f"scene_{scene_number}_must_be_object")
            continue
        if not scene.get("action_detail_vi") and not scene.get("action_vi"):
            errors.append(f"scene_{scene_number}_action_required")
        veo_prompt = scene.get("veo3_prompt_en") or scene.get("veo_prompt_en") or ""
        if not veo_prompt:
            errors.append(f"scene_{scene_number}_veo3_prompt_required")
        elif not veo_prompt.startswith("Reference the approved"):
            errors.append(f"scene_{scene_number}_veo3_prompt_must_reference_approved_anchor")
        if not scene.get("voice_over_en") and not scene.get("voice_en"):
            errors.append(f"scene_{scene_number}_voice_over_required")
        if not scene.get("continuity_anchor"):
            errors.append(f"scene_{scene_number}_continuity_anchor_required")
    return errors


# Review validator guard: semantic review must expose handoff data for later
# episodes without turning creative quality into rigid code rules.
def validate_review_report(data: dict[str, Any], is_final_episode: bool) -> list[str]:
    errors: list[str] = []
    if data.get("handoff_strength") not in {"strong", "medium", "weak"}:
        errors.append("handoff_strength_required")
    if not isinstance(data.get("review_notes"), list):
        errors.append("review_notes_must_be_list")
    open_threads = data.get("open_threads")
    if not isinstance(open_threads, list):
        errors.append("open_threads_must_be_list")
    elif not is_final_episode and len(open_threads) == 0:
        errors.append("open_threads_required_for_non_final")
    if not is_final_episode and not data.get("next_start_state"):
        errors.append("next_start_state_required_for_non_final")
    return errors


# Review retry guard: weak handoff is a soft failure; one repair attempt is
# allowed, then output is saved as needs_review rather than discarded.
def review_needs_retry(data: dict[str, Any], is_final_episode: bool) -> bool:
    if is_final_episode:
        return False
    return data.get("handoff_strength") == "weak" or bool(data.get("too_closed"))


# Continuity validator guard: persisted deltas are the only cross-episode memory
# contract, so required handoff keys stay explicit and compact.
def validate_continuity_delta(delta: dict[str, Any], is_final_episode: bool) -> list[str]:
    errors: list[str] = []
    for key in ("last_physical_state", "handoff_strength", "cliffhanger_fact"):
        if not delta.get(key):
            errors.append(f"{key}_required")
    if not isinstance(delta.get("open_threads"), list):
        errors.append("open_threads_must_be_list")
    elif not is_final_episode and len(delta["open_threads"]) == 0:
        errors.append("open_threads_required_for_non_final")
    if not isinstance(delta.get("new_constraints"), list):
        errors.append("new_constraints_must_be_list")
    if not is_final_episode and not delta.get("next_start_state"):
        errors.append("next_start_state_required_for_non_final")
    return errors


# Fact-review guard: strict verification only runs for topics where factual drift
# is a product risk, keeping fictional episodes on the cheaper path.
def is_strict_topic(topic_type: str) -> bool:
    return topic_type in STRICT_TOPIC_TYPES


# Fact patch guard: optional verifier may only return per-scene patches and
# warnings, never a full hidden rewrite of the script.
def validate_fact_report(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    patches = data.get("patches", [])
    warnings = data.get("warnings", [])
    if not isinstance(patches, list):
        errors.append("patches_must_be_list")
    if not isinstance(warnings, list):
        errors.append("warnings_must_be_list")
    for idx, patch in enumerate(patches, start=1):
        if not isinstance(patch, dict):
            errors.append(f"patch_{idx}_must_be_object")
            continue
        if not isinstance(patch.get("scene_number"), int):
            errors.append(f"patch_{idx}_scene_number_required")
        if not isinstance(patch.get("fields"), dict):
            errors.append(f"patch_{idx}_fields_must_be_object")
    return errors


# Packaging validator guard: metadata generation is optional and must not become
# a hidden content rewrite step.
def validate_packaging(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("video_title", "description", "thumbnail_prompt_en"):
        if not data.get(key):
            errors.append(f"{key}_required")
    if not isinstance(data.get("tags"), list):
        errors.append("tags_must_be_list")
    return errors


# Patch application guard: fact-check patches merge only declared fields on the
# addressed scene and then the caller revalidates the full scene list.
def apply_scene_patches(scenes: list[dict[str, Any]], patches: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_number = {scene.get("scene_number"): dict(scene) for scene in scenes}
    for patch in patches:
        scene_number = patch.get("scene_number")
        fields = patch.get("fields") or {}
        if scene_number in by_number and isinstance(fields, dict):
            by_number[scene_number].update(fields)
    return [by_number[num] for num in sorted(by_number)]
