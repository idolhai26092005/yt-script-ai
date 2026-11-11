from app.core.utils import ensure_scene_defaults
# Scene merge guard: support helpers import validation through the production
# package after core validation shim cleanup.
from app.services.production.validation.constraints import scene_specific_negative_from_constraints
from app.services.production.base import extract_voice_from_prompt


# Scene merge guard: cache resume and batch repair rely on scene_number replacing
# prior content deterministically while preserving sorted scene order.
def upsert_scene(script_data: dict, scene: dict) -> None:
    scene_num = scene.get("scene_number")
    if scene_num is None:
        script_data.setdefault("scenes", []).append(scene)
        return
    scenes = [s for s in script_data.get("scenes", []) if s.get("scene_number") != scene_num]
    scenes.append(scene)
    scenes.sort(key=lambda s: s.get("scene_number", 0))
    script_data["scenes"] = scenes


# Scene lookup guard: resume logic must check live work-state before cached state
# so newly generated scenes override old cache without changing call sites.
def find_scene(script_data: dict, scene_num: int, cached_script_data: dict | None = None) -> dict | None:
    for scene in script_data.get("scenes", []) or []:
        if scene.get("scene_number") == scene_num:
            return scene
    cached = cached_script_data or {}
    for scene in cached.get("scenes", []) or []:
        if scene.get("scene_number") == scene_num:
            return scene
    return None


# Scene sync guard: backend-owned title/defaults and embedded voice extraction
# keep source/display fields aligned after semantic or fact-check patches.
def prepare_scene(
    scene: dict,
    scene_duration_sec: int,
    base_negative_prompt: str,
    script_data: dict | None = None,
) -> None:
    scene_num = scene.get("scene_number", 1)
    start_sec = (scene_num - 1) * scene_duration_sec
    end_sec = scene_num * scene_duration_sec
    s_min, s_s = start_sec // 60, start_sec % 60
    e_min, e_s = end_sec // 60, end_sec % 60
    scene["title"] = f"Scene {scene_num} [{s_min:02d}:{s_s:02d} - {e_min:02d}:{e_s:02d}]"
    ensure_scene_defaults(scene, base_negative_prompt)

    if scene.get("veo3_prompt_en"):
        extracted_voice = extract_voice_from_prompt(scene["veo3_prompt_en"])
        if extracted_voice and (
            not scene.get("voice_over_en")
            or scene.get("_semantic_verified_edit")
            or scene.get("verification_status") in ("corrected", "needs_review")
        ):
            scene["voice_over_en"] = extracted_voice

    if not scene.get("voice_over_vi") and scene.get("voice_over_en"):
        scene["voice_over_vi"] = scene["voice_over_en"]

    if script_data and not scene.get("scene_specific_negative_en"):
        scene["scene_specific_negative_en"] = scene_specific_negative_from_constraints(script_data, scene)
