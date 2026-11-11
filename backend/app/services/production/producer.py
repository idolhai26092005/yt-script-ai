"""
ScriptProducer v2.0 — Prompt 0 + Batch Scene Generation Pipeline

Architecture:
  Phase 0: Prompt 0 + Production Blueprint (1 LLM call)
  Phase 1: Emotion Arc (1-N LLM calls depending on size)
  Phase 2: Batch Scene Generation (ceil(N/10) LLM calls)
  Phase 3: Packaging — Reference Images only (1 LLM call)
  Code Critique: Duplicate detection, anchor validation (no LLM calls)
  Phase 4 (historical only): Fact-Check (concurrent chunks)
"""

import json
import asyncio
import re
import time
from sqlalchemy.orm import Session

from app.services.production.base import (
    BaseGeminiService, logger,
    STREAM_DELAY,
    merge_scenes_data,
    standardize_scene_titles,
    sync_emotion_arc_with_scenes,
    build_compact_prompt_0_text,
    build_story_spine,
    extract_voice_from_prompt,
    MAX_BATCH_PROMPT_CHARS,
    scene_handoff_state,
    stage_context_for_range,
    story_spine_context,
    future_targets_context,
)
from app.services.production.state import (
    build_resume_signature,
    hydrate_resume_cache,
    is_resume_cache_compatible,
    new_script_data,
)
from app.services.production.support.sse import sse_event
from app.services.production.support.scene_merge import (
    find_scene,
    prepare_scene,
    upsert_scene,
)
from app.services.production.roles.blueprint import BlueprintRole
from app.services.production.roles.emotion_arc import EmotionArcRole
from app.services.production.roles.fact_check import FactCheckRole
from app.services.production.roles.packaging import PackagingRole
from app.services.production.roles.scene_batch import SceneBatchRole
from app.services.production.roles.semantic_verify import SemanticVerifierRole
from app.core.routing import resolve_routing
from app.core.utils import (
    ensure_scene_defaults,
    parse_llm_json_response,
    to_canonical_v3,
)
from app.services.production.prompts.blueprint import PROMPT_0_GENERATION_TEMPLATE
from app.services.production.prompts.fact_check import (
    HISTORICAL_FACT_CHECK_PROMPT,
    HISTORICAL_SCIENTIFIC_HARD_RULES,
)
from app.services.production.prompts.packaging import (
    POST_GENERATION_SUGGESTION_PROMPT,
    REFERENCE_IMAGES_PROMPT,
)
from app.services.production.prompts.safety import VEO3_CONTENT_SAFETY_RULES
from app.services.production.prompts.scenes import (
    BASE_NEGATIVE_PROMPT,
    BATCH_SCENE_GENERATION_TEMPLATE,
    EMOTION_ARC_BASE_PROMPT,
    SHAPE_STRUCTURES,
)
from app.services.production.prompts.verifier import SEMANTIC_VERIFIER_PROMPT
from app.services.production.validation.adapters import normalize_scene, normalize_script
from app.services.production.validation.blueprint import (
    validate_blueprint_required,
    validate_script_blueprint,
    validate_story_spine_quality,
)
from app.services.production.validation.constraints import (
    build_constraint_model,
    scene_specific_negative_from_constraints,
    validate_state_invariants,
)
from app.services.production.validation.emotion_arc import (
    emotion_arc_state_triggers,
    validate_emotion_arc_constraints,
    validate_emotion_arc_quality,
    validate_emotion_arc_state_machine,
)
from app.services.production.validation.historical import validate_historical_coverage
from app.services.production.validation.legacy import (
    blocking_messages,
    retryable_messages,
    validate_script,
)
from app.services.production.validation.scene import (
    scene_state_triggers,
    validate_scene_generation_issues,
    validate_scene_generation_quality,
    validate_scene_issues,
    validate_scene_lead_character,
)
from app.services.production.validation.story_contract import (
    detect_story_contract_batch_drift,
    validate_story_contract_issues,
)


class ScriptProducer(BaseGeminiService):
    """Dịch vụ sinh kịch bản Veo 3 — Phiên bản 2.0 (Prompt 0 + Batch Scenes)."""

    production_llm_timeout_sec = 180.0

    # ─── UTILITIES ────────────────────────────────────────────────────────────

    # Durable topic-contract guard: the work-state carries a lightweight internal
    # story contract so later phases can detect drift without extra LLM calls.
    def _new_script_data(self, topic_type: str) -> dict:
        return new_script_data(topic_type)

    # Durable schema guard: resume signatures track canonical v3 saves even though
    # the live producer still uses a flat v2 work object internally.
    def _build_resume_signature(
        self,
        suggestion: dict,
        style: str,
        num_scenes: int,
        topic_type: str,
        aspect_ratio: str,
        scene_duration_sec: int,
        generation_mode: str,
    ) -> dict:
        return build_resume_signature(
            suggestion,
            style,
            num_scenes,
            topic_type,
            aspect_ratio,
            scene_duration_sec,
            generation_mode,
        )

    # Durable schema guard: old v2 and new v3 cache must compare through the legacy
    # work adapter so schema migration does not force full regeneration.
    def _is_resume_cache_compatible(self, cached: dict | None, signature: dict) -> bool:
        return is_resume_cache_compatible(cached, signature)

    # Durable schema guard: hydrate converts canonical v3 back to the producer's
    # current v2 work shape before any phase-specific validator touches it.
    # Durable topic-contract guard: v3 resume keeps internal story_contract for
    # quality routing, while the public legacy adapter can remain UI-compatible.
    def _hydrate_resume_cache(self, script_data: dict, cached: dict) -> None:
        hydrate_resume_cache(script_data, cached)

    def _stream_event(self, payload: dict) -> str:
        return sse_event(payload)

    def _metadata_payload(self, script_data: dict) -> dict:
        return {
            "overview_analysis_vi": script_data["overview_analysis_vi"],
            "storyline_vi": script_data["storyline_vi"],
            "stages_vi": script_data["stages_vi"],
            "progression_vi": script_data["progression_vi"],
            "camera_strategy_vi": script_data["camera_strategy_vi"],
            "continuity_locks_vi": script_data["continuity_locks_vi"],
            "form_locks_vi": script_data["form_locks_vi"],
            "age_stage_locks_vi": script_data["age_stage_locks_vi"],
            "geometry_locks_vi": script_data["geometry_locks_vi"],
            "risk_logic_vi": script_data["risk_logic_vi"],
            "voice_sound_strategy_vi": script_data.get("voice_sound_strategy_vi", ""),
            "characters": script_data["characters"],
            "environment_master_prompt_en": script_data["environment_master_prompt_en"],
            "environment_master_prompt_vi": script_data.get("environment_master_prompt_vi", ""),
            "prompt_0": script_data.get("prompt_0", {}),
            "story_spine": script_data.get("story_spine", {}),
        }

    # Durable observability guard: phase logs advertise the saved artifact schema,
    # not the temporary in-memory work representation.
    def _append_phase_log(self, project_id: int, stage_role: str, validation_errors: list[str], latency_ms: float = 0.0) -> None:
        if hasattr(self, "_repo") and self._repo:
            self._repo.append_phase_log(project_id, stage_role, "3.0", validation_errors, latency_ms)

    def _has_packaging_cache(self, script_data: dict) -> bool:
        refs = script_data.get("reference_images") or {}
        return all(refs.get(k) for k in [
            "character_ref_prompt_en",
            "background_ref_prompt_en",
            "thumbnail_ref_prompt_en",
        ])

    def _validate_packaging_refs(self, script_data: dict) -> list[str]:
        refs = script_data.get("reference_images") or {}
        required = [
            "character_ref_prompt_en",
            "background_ref_prompt_en",
            "thumbnail_ref_prompt_en",
        ]
        return [f"reference_images.{key} is empty after packaging" for key in required if not refs.get(key)]

    def _valid_scene_cache_complete(self, script_data: dict, num_scenes: int, style: str) -> bool:
        scenes = script_data.get("scenes") or []
        nums = {s.get("scene_number") for s in scenes}
        if nums != set(range(1, num_scenes + 1)):
            return False
        errors = (
            validate_script(normalize_script(script_data))
            + blocking_messages(validate_scene_generation_issues(script_data))
        )
        if errors:
            logger.info(f"Scene cache rejected: {errors[:5]}")
            return False
        for scene in scenes:
            prompt_en = scene.get("veo3_prompt_en", "")
            if style.lower() not in prompt_en.lower():
                logger.info(f"Scene cache rejected: style mismatch at scene {scene.get('scene_number')}")
                return False
        return True

    def _ensure_story_spine(self, script_data: dict, num_scenes: int) -> dict:
        spine = script_data.get("story_spine")
        stage_ranges = spine.get("stage_ranges") if isinstance(spine, dict) else []
        has_only_fallback_stage = (
            len(stage_ranges or []) == 1
            and (stage_ranges or [{}])[0].get("source") == "fallback"
        )
        stages_text = script_data.get("stages_vi", "") or ""
        has_parseable_stage_ranges = bool(re.search(
            r"(?:\(\s*(?:(?:Cảnh|Scene)\s*)?\d+\s*[-–]\s*\d+\s*\)|(?:Cảnh|Scene)\s*\d+\s*[-–]\s*\d+)",
            stages_text,
            re.IGNORECASE,
        ))
        if (
            isinstance(spine, dict)
            and spine.get("version") == "1.2"
            and spine.get("steps")
            and spine.get("total_scenes") == num_scenes
            and not (has_only_fallback_stage and has_parseable_stage_ranges)
        ):
            return spine
        spine = build_story_spine(script_data.get("prompt_0", {}), script_data.get("stages_vi", ""), num_scenes)
        script_data["story_spine"] = spine
        return spine

    def _used_triggers_from_scenes(self, script_data: dict, before_scene: int) -> list[str]:
        used: list[str] = []
        for scene in sorted(script_data.get("scenes") or [], key=lambda s: s.get("scene_number", 0)):
            if scene.get("scene_number", 0) >= before_scene:
                continue
            for trigger in scene_state_triggers(scene):
                if trigger not in used:
                    used.append(trigger)
        return used

    def _upsert_scene(self, script_data: dict, scene: dict) -> None:
        upsert_scene(script_data, scene)

    def _find_scene(self, script_data: dict, scene_num: int) -> dict | None:
        return find_scene(script_data, scene_num, getattr(self, "cached_script_data", None))

    def _scene_handoff_for_number(self, script_data: dict, scene_num: int, fallback: str) -> str:
        return scene_handoff_state(self._find_scene(script_data, scene_num), fallback)

    def _validate_candidate_scenes(
        self,
        script_data: dict,
        generated_scenes: list[dict],
        scene_duration_sec: int,
        base_negative_prompt: str,
    ) -> list[str]:
        temp_script = json.loads(json.dumps(script_data, ensure_ascii=False))
        generated_nums = {s.get("scene_number") for s in generated_scenes}
        for scene in generated_scenes:
            self._prepare_scene(scene, scene_duration_sec, base_negative_prompt, temp_script)
            self._upsert_scene(temp_script, scene)

        issues = validate_scene_generation_issues(temp_script)
        scoped_issues = []
        for issue in issues:
            err = issue.message
            scene_match = re.search(r"Scene (\d+)", err)
            pair_match = re.search(r"Scenes (\d+)->(\d+)", err)
            if scene_match and int(scene_match.group(1)) in generated_nums:
                scoped_issues.append(issue)
            elif pair_match:
                left, right = int(pair_match.group(1)), int(pair_match.group(2))
                if left in generated_nums or right in generated_nums:
                    scoped_issues.append(issue)
            else:
                state_match = re.search(r"at scenes \[([^\]]+)\]", err)
                if state_match:
                    nums = {
                        int(n)
                        for n in re.findall(r"\d+", state_match.group(1))
                    }
                    if nums & generated_nums:
                        scoped_issues.append(issue)
        return retryable_messages(scoped_issues)

    def _hard_critique_errors(self, critique_errors: list[str]) -> list[str]:
        return [err for err in critique_errors if err.startswith("Hard duplicate")]

    def _parse_llm_json_object(self, raw_text: str):
        return parse_llm_json_response(raw_text)

    # Durable production-timeout guard: long provider calls must fail with phase
    # context instead of leaving the SSE stream apparently stuck on one step.
    async def _call_production_llm(
        self,
        *,
        prompt,
        model_name: str,
        generation_config: dict | None,
        phase: str,
        scene_range: tuple[int, int] | None = None,
    ) -> str:
        started_at = time.time()
        timeout_sec = float(getattr(self, "production_llm_timeout_sec", 180.0))
        range_text = f" scenes {scene_range[0]}-{scene_range[1]}" if scene_range else ""
        try:
            result = await asyncio.wait_for(
                self._call_gemini_with_retry(
                    prompt=prompt,
                    model_name=model_name,
                    generation_config=generation_config,
                ),
                timeout=timeout_sec,
            )
            logger.info(
                "Production LLM completed: phase=%s%s model=%s latency_ms=%.1f",
                phase,
                range_text,
                model_name,
                (time.time() - started_at) * 1000.0,
            )
            return result
        except asyncio.TimeoutError as err:
            elapsed_ms = (time.time() - started_at) * 1000.0
            logger.error(
                "Production LLM timeout: phase=%s%s model=%s timeout_sec=%.1f latency_ms=%.1f",
                phase,
                range_text,
                model_name,
                timeout_sec,
                elapsed_ms,
            )
            raise TimeoutError(
                f"Production LLM timeout during {phase}{range_text} after {timeout_sec:.1f}s"
            ) from err

    def _constraint_context(self, script_data: dict) -> str:
        model = build_constraint_model(script_data)
        constraints = model.get("constraints") or []
        if not constraints:
            return "No extra project-specific negative constraints beyond Prompt 0."
        lines = [
            "- " + c[:180]
            for c in constraints[:6]
        ]
        return (
            "\n".join(lines)
            + "\nEvery scene must fill scene_specific_negative_en from these constraints when relevant. "
            "Never solve a story beat by using a forbidden object, force, material, or physics."
        )

    def _backfill_scene_level_fields(self, script_data: dict) -> None:
        scenes = sorted(script_data.get("scenes") or [], key=lambda s: s.get("scene_number", 0))
        arc_by_num = {
            entry.get("scene_number"): entry
            for entry in script_data.get("emotion_arc") or []
        }
        for index, scene in enumerate(scenes):
            ensure_scene_defaults(scene, BASE_NEGATIVE_PROMPT)
            num = scene.get("scene_number")
            arc = arc_by_num.get(num) or {}
            action_vi = (scene.get("action_detail_vi") or "").strip()
            prompt_en = (scene.get("veo3_prompt_en") or "").strip()

            if not scene.get("scene_specific_negative_en"):
                scene["scene_specific_negative_en"] = scene_specific_negative_from_constraints(script_data, scene)
            if not scene.get("veo3_prompt_vi"):
                scene["veo3_prompt_vi"] = action_vi or f"Cảnh {num} tiếp tục mạch hình ảnh đã khóa trong Prompt 0."
            if not scene.get("emotion_gesture_vi"):
                label = arc.get("emotion_label") or "căng thẳng"
                state = arc.get("physical_state_end") or "trạng thái tiếp tục từ cảnh trước"
                scene["emotion_gesture_vi"] = f"Cảm xúc {label}; cuối cảnh: {state}."
            if not scene.get("camera_movement_vi"):
                camera_part = prompt_en.split(",", 2)[1].strip() if prompt_en.count(",") >= 2 else "cinematic anchored shot"
                scene["camera_movement_vi"] = f"Góc quay theo mô tả: {camera_part}."
            if not scene.get("transition_to_next_vi"):
                if index + 1 < len(scenes):
                    next_action = (scenes[index + 1].get("action_detail_vi") or "").strip()
                    scene["transition_to_next_vi"] = (
                        "Chuyển tiếp bằng hệ quả trực tiếp sang cảnh sau: "
                        + (next_action[:140] if next_action else "hành động tiếp theo tiếp tục ngay sau đó.")
                    )
                else:
                    scene["transition_to_next_vi"] = "Kết cảnh bằng nhịp giải quyết cuối cùng của hành trình."

    def _story_spine_trigger_ranges(self, story_spine: dict) -> dict[str, list[tuple[int, int]]]:
        ranges: dict[str, list[tuple[int, int]]] = {}
        total = int(story_spine.get("total_scenes") or 9999)
        for source in (story_spine.get("stage_ranges") or []) + (story_spine.get("steps") or []):
            trigger = source.get("trigger")
            if not trigger:
                continue
            trigger_range = (
                int(source.get("scene_start") or 1),
                int(source.get("scene_end") or total),
            )
            if trigger_range not in ranges.setdefault(trigger, []):
                ranges[trigger].append(trigger_range)
        return ranges

    def _normalize_arc_chunk_numbers(
        self,
        emotion_arc: list[dict],
        expected_start: int,
        expected_end: int,
    ) -> tuple[list[dict], list[str]]:
        expected_nums = list(range(expected_start, expected_end + 1))
        chunk_size = len(expected_nums)
        returned_nums = [entry.get("scene_number") for entry in emotion_arc]
        if returned_nums == expected_nums:
            return emotion_arc, []

        local_nums = list(range(1, chunk_size + 1))
        if returned_nums == local_nums:
            normalized = json.loads(json.dumps(emotion_arc, ensure_ascii=False))
            for entry in normalized:
                entry["scene_number"] = int(entry["scene_number"]) + expected_start - 1
            logger.info(
                f"Normalized local emotion_arc numbering {local_nums[0]}-{local_nums[-1]} "
                f"to absolute {expected_start}-{expected_end}."
            )
            return normalized, []

        return emotion_arc, [
            f"emotion_arc chunk scene_number mismatch: expected {expected_nums}, got {returned_nums}"
        ]

    def _validate_arc_chunk_state(
        self,
        emotion_arc: list[dict],
        story_spine: dict,
    ) -> list[str]:
        errors: list[str] = []
        trigger_ranges = self._story_spine_trigger_ranges(story_spine)
        allowed_once = list(dict.fromkeys(
            (story_spine.get("allowed_once_triggers") or [])
            + list(trigger_ranges.keys())
        ))
        hits: dict[str, list[int]] = {trigger: [] for trigger in allowed_once}

        for entry in emotion_arc:
            scene_num = entry.get("scene_number")
            if not isinstance(scene_num, int):
                continue
            for trigger in emotion_arc_state_triggers(entry):
                if trigger in hits:
                    hits[trigger].append(scene_num)

        for trigger, scene_nums in hits.items():
            ranges = trigger_ranges.get(trigger) or []
            if ranges:
                out_of_range = [
                    num for num in scene_nums
                    if not any(start <= num <= end for start, end in ranges)
                ]
                if out_of_range:
                    range_text = ", ".join(f"{start}-{end}" for start, end in ranges)
                    errors.append(
                        f"Emotion arc chunk trigger '{trigger}' appears outside assigned range {range_text} at scenes {out_of_range}"
                    )
            if len(scene_nums) <= 1:
                continue
            if trigger == "resolution" and ranges and all(
                any(start <= num <= end for start, end in ranges)
                for num in scene_nums
            ):
                continue
            clusters: list[list[int]] = []
            current = [scene_nums[0]]
            for num in scene_nums[1:]:
                if num <= current[-1] + 2:
                    current.append(num)
                else:
                    clusters.append(current)
                    current = [num]
            clusters.append(current)
            if len(clusters) > 1:
                errors.append(
                    f"Emotion arc chunk trigger '{trigger}' repeats across separate cycles at scenes {[c[0] for c in clusters]}"
                )
        return errors

    def _batch_mode_allowed(self) -> bool:
        import sys
        if "pytest" in sys.modules:
            return True
        try:
            from app.core.config import settings
            return settings.ENV.strip("'\"").strip().lower() != "production"
        except Exception:
            return False

    # Durable scene sync guard: backend-owned title/defaults and embedded voice extraction
    # keep source/display fields aligned after semantic or fact-check patches.
    def _prepare_scene(
        self,
        scene: dict,
        scene_duration_sec: int,
        base_negative_prompt: str,
        script_data: dict | None = None,
    ) -> None:
        prepare_scene(scene, scene_duration_sec, base_negative_prompt, script_data)

    # Durable schema guard: persistence is canonical v3; callers may keep using
    # the flatter work object until frontend and validators are fully migrated.
    # Durable performance guard: hot progress checkpoints can persist the flat
    # work-state, while phase/final saves still publish canonical v3.
    def _save_script(
        self,
        project_id: int,
        suggestion_idx: int,
        script_data: dict,
        status: str,
        topic_type: str | None = None,
        canonical: bool = True,
    ):
        post_suggestions = script_data.get("post_suggestions") if "post_suggestions" in script_data else None
        saved_script = (
            to_canonical_v3(script_data, getattr(self, "_scene_duration_sec", 8))
            if canonical or status == "script_generated"
            else script_data
        )
        self._repo.save_script(
            project_id,
            suggestion_idx,
            json.dumps(saved_script, ensure_ascii=False),
            status,
            topic_type=topic_type,
            post_suggestions=post_suggestions,
        )

    async def _maybe_sleep(self, delay: float):
        if not getattr(self, "batch_mode", False):
            await asyncio.sleep(delay)

    # Durable schema guard: debug snapshots mirror persisted canonical v3 so
    # investigation uses the same contract as the stored backend output.
    def _save_debug_snapshot(self, phase_num: int, phase_name: str, script_data: dict, project_id: int):
        import os
        try:
            from app.core.config import settings
            db_url = settings.DATABASE_URL.strip('\'"').strip().lower()
            if not settings.DEBUG_SNAPSHOTS and not db_url.startswith("sqlite"):
                return

            snapshot_dir = os.path.join(os.getcwd(), "debug_snapshots")
            os.makedirs(snapshot_dir, exist_ok=True)
            filename = f"project_{project_id}_phase_{phase_num}_{phase_name}.json"
            filepath = os.path.join(snapshot_dir, filename)
            snapshot_data = to_canonical_v3(script_data, getattr(self, "_scene_duration_sec", 8))
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(snapshot_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save debug snapshot: {str(e)}")

    def _restore_locked_blueprint(self, script_data: dict, locked_blueprint: dict | None) -> None:
        """Keep Phase 0 artifacts immutable across downstream roles."""
        if not locked_blueprint:
            return
        for key in [
            "prompt_0",
            "narrative_shape",
            "story_contract",
            "overview_analysis_vi",
            "storyline_vi",
            "stages_vi",
            "progression_vi",
            "camera_strategy_vi",
            "continuity_locks_vi",
            "form_locks_vi",
            "age_stage_locks_vi",
            "geometry_locks_vi",
            "risk_logic_vi",
            "voice_sound_strategy_vi",
            "characters",
            "environment_master_prompt_en",
            "environment_master_prompt_vi",
            "continuity_evolution",
            "continuity_prompt_en",
            "continuity_prompt_vi",
            "continuity_board",
            "global_negative_prompt_en",
        ]:
            locked_value = locked_blueprint.get(key)
            current_value = script_data.get(key)
            if locked_value and not current_value:
                script_data[key] = json.loads(json.dumps(locked_value, ensure_ascii=False))

    def _raise_gate_errors(self, phase: str, errors: list[str]) -> None:
        if not errors:
            return
        short = "; ".join(errors[:8])
        logger.error(f"{phase} hard gate failed: {short}")
        raise RuntimeError(f"{phase} hard gate failed: {short}")

    def _story_spine_blocking_errors(self, errors: list[str]) -> list[str]:
        """Coverage gaps are parser/guide quality warnings, not Phase 0 blockers."""
        warnings = [
            err for err in errors
            if "story_spine coverage error" in err or "story_spine stage coverage missing scenes" in err
        ]
        if warnings:
            logger.warning(f"Story spine coverage warnings: {warnings[:8]}")
        return [err for err in errors if err not in warnings]

    # Durable topic-contract guard: downstream prompts receive a compact contract
    # instead of re-inferring the main story from long blueprint prose.
    def _story_contract_context(self, script_data: dict, max_chars: int = 1800) -> str:
        contract = script_data.get("story_contract") or {}
        if not contract:
            return "No central story contract available."
        return json.dumps(contract, ensure_ascii=False)[:max_chars]

    # Durable topic-contract guard: legacy/mock Phase 0 responses may not include
    # story_contract yet, so derive a minimal one from user-facing title/synopsis.
    def _ensure_story_contract_defaults(self, script_data: dict, suggestion: dict) -> None:
        contract = script_data.get("story_contract")
        if isinstance(contract, dict) and contract.get("main_subject_en") and contract.get("core_goal_en"):
            return
        title = (suggestion.get("title") or "").strip()
        synopsis = (suggestion.get("synopsis") or "").strip()
        p0 = script_data.get("prompt_0") or {}
        character_names = ", ".join(
            c.get("character_name", "")
            for c in script_data.get("characters") or []
            if c.get("character_name")
        )
        p0_subject = str(p0.get("primary_subject_en") or "").strip()
        subject = next(
            (candidate for candidate in [title, p0_subject, character_names, synopsis[:120]] if len(candidate) >= 3),
            "Central story subject",
        )
        goal = next(
            (candidate for candidate in [synopsis, script_data.get("storyline_vi", ""), title, p0_subject] if len(str(candidate).strip()) >= 3),
            "Maintain the original story goal.",
        )
        script_data["story_contract"] = {
            "main_subject_en": subject,
            "main_subject_vi": subject,
            "protagonist_en": subject,
            "protagonist_vi": subject,
            "central_opponent_or_force_en": synopsis or subject,
            "central_opponent_or_force_vi": synopsis or subject,
            "core_goal_en": goal,
            "core_goal_vi": goal,
            "must_remain_visible_terms": [subject],
            "allowed_side_threats": [],
            "forbidden_takeover_rule": "Do not let a secondary obstacle replace the original title/synopsis subject.",
            "_source": "backend_fallback",
        }

    # Durable topic-contract guard: Phase 0 gets one cheap correction pass for
    # central drift, then soft topics continue with warnings rather than blocking.
    def _phase0_story_contract_errors(
        self,
        script_data: dict,
        attempt: int,
        topic_type: str,
    ) -> tuple[list[str], list[str]]:
        issues = validate_story_contract_issues(script_data)
        retry_errors = retryable_messages(issues)
        drift_warnings = [issue.message for issue in issues if issue.severity == "WARN"]
        fallback_contract = (script_data.get("story_contract") or {}).get("_source") == "backend_fallback"
        if fallback_contract and drift_warnings:
            return retry_errors, []
        if drift_warnings and attempt == 0:
            retry_errors.extend(drift_warnings)
            return retry_errors, []
        if drift_warnings:
            warnings = [f"central_contract_drift: {warning}" for warning in drift_warnings]
            if topic_type in {"historical", "scientific"} or (script_data.get("reality_binding_level") == "strict"):
                warnings.append("central_contract_drift: strict topic will be reviewed by semantic verifier.")
            return retry_errors, warnings
        return retry_errors, []

    def _build_context_str(self, context_from_previous: dict | None) -> str:
        """Build series context string for Prompt 0 generation."""
        if not context_from_previous:
            return ""

        context_str = "\n=== SERIES CONTEXT FROM PREVIOUS EPISODES ===\n"

        if context_from_previous.get("master_summary"):
            context_str += f"Previous episodes summary: {context_from_previous['master_summary']}\n"

        recent_eps = context_from_previous.get("recent_episodes", [])
        for ep in recent_eps:
            ep_num = ep.get("episode_number")
            ep_title = ep.get("title")
            ep_sum = ep.get("summary", {})
            context_str += f"- Episode {ep_num} ({ep_title}):\n"
            context_str += f"  + Plot: {ep_sum.get('plot_summary')}\n"
            context_str += f"  + Character states: {ep_sum.get('character_states')}\n"
            context_str += f"  + Cliffhanger: {ep_sum.get('cliffhanger')}\n"

        v_locks = context_from_previous.get("visual_locks", {})
        if v_locks:
            context_str += "\n=== LOCKED VISUAL IDENTITY (MUST KEEP CONSISTENT) ===\n"
            if v_locks.get("characters"):
                context_str += f"Locked characters: {json.dumps(v_locks['characters'], ensure_ascii=False)}\n"
            if v_locks.get("environment_master_prompt_en"):
                context_str += f"Locked environment EN: {v_locks['environment_master_prompt_en']}\n"

        context_str += "\n=== STORY CONTINUATION REQUIREMENTS ===\n"
        context_str += "1. Continue the narrative directly from previous episode's cliffhanger.\n"
        context_str += "2. KEEP the same characters with identical appearance (description_en/description_vi).\n"
        context_str += "3. KEEP the same environment/world consistency.\n"
        return context_str

    def _merge_series_characters(
        self,
        generated_chars: list,
        context_from_previous: dict | None,
    ) -> list:
        """Protect character continuity across series episodes."""
        if not context_from_previous or "visual_locks" not in context_from_previous:
            return generated_chars

        v_locks = context_from_previous["visual_locks"]
        locked_chars = v_locks.get("characters", [])
        if not locked_chars:
            return generated_chars

        locked_names = {c["character_name"] for c in locked_chars}
        generated_names = {c["character_name"] for c in generated_chars}
        missing_names = locked_names - generated_names
        if missing_names:
            logger.warning(f"[SeriesLock] Gemini dropped locked characters: {missing_names}. Merging back.")

        merged_chars = []
        for lc in locked_chars:
            gen_match = next(
                (gc for gc in generated_chars if gc["character_name"] == lc["character_name"]),
                None
            )
            if gen_match:
                merged_chars.append({
                    **gen_match,
                    "description_en": lc.get("description_en", gen_match.get("description_en", "")),
                    "key_identifiers_en": lc.get("key_identifiers_en", gen_match.get("key_identifiers_en", "")),
                })
            else:
                merged_chars.append(lc)

        for gc in generated_chars:
            if gc["character_name"] not in locked_names:
                merged_chars.append(gc)

        return merged_chars

    # ─── MAIN ORCHESTRATOR ────────────────────────────────────────────────────

    # Durable schema guard: orchestration may stream legacy events for today's UI,
    # while every persisted artifact is normalized to canonical v3 at save time.
    async def generate_full_script_stream(
        self,
        suggestion: dict,
        style: str,
        num_scenes: int,
        project_id: int,
        db: Session,
        model_name: str = "gemini-3.1-flash-lite",
        topic_type_override: str | None = None,
        aspect_ratio: str = "9:16",
        scene_duration_sec: int = 8,
        batch_mode: bool = False,
        context_from_previous: dict | None = None,
        generation_mode: str = "single",
        restart: bool = False,
    ):
        self.batch_mode = bool(batch_mode and self._batch_mode_allowed())
        self._scene_duration_sec = scene_duration_sec
        topic_type = topic_type_override or suggestion.get("topic_type") or "fictional_original"

        has_named_figure = suggestion.get("has_named_historical_figure", False)
        rule = resolve_routing(topic_type, has_named_historical_figure=has_named_figure)
        is_historical_or_scientific = rule.fact_check_enabled
        narrative_shape = (
            rule.narrative_shape_default
            if rule.fact_check_enabled
            else suggestion.get("narrative_shape") or rule.narrative_shape_default
        )
        resume_signature = self._build_resume_signature(
            suggestion=suggestion,
            style=style,
            num_scenes=num_scenes,
            topic_type=topic_type,
            aspect_ratio=aspect_ratio,
            scene_duration_sec=scene_duration_sec,
            generation_mode=generation_mode,
        )

        # ── Load cached script data ──
        self.cached_script_data = None
        # Recovery cache guard: restart deliberately ignores saved partials;
        # normal retry keeps the existing phase-level resume behavior.
        cached_script = None if restart else (self._repo.load_cached_script(project_id) if hasattr(self, "_repo") and self._repo else None)
        if self._is_resume_cache_compatible(cached_script, resume_signature):
            self.cached_script_data = cached_script
            logger.info(f"Project {project_id}: resume cache accepted.")
        elif cached_script:
            logger.info(f"Project {project_id}: resume cache ignored because signature/schema does not match.")

        # ── Initialize script_data (v2.0 schema) ──
        script_data = self._new_script_data(topic_type)
        # Durable routing guard: canonical v3 saves must expose the resolved shape
        # instead of losing strict historical routing as narrative_shape=null.
        script_data["narrative_shape"] = narrative_shape
        script_data["reality_binding_level"] = rule.reality_binding_level
        script_data["_resume_signature"] = resume_signature

        # ── Load visual locks from series context ──
        if context_from_previous and "visual_locks" in context_from_previous:
            v_locks = context_from_previous["visual_locks"]
            script_data["characters"] = v_locks.get("characters", [])
            script_data["environment_master_prompt_en"] = v_locks.get("environment_master_prompt_en", "")
            script_data["environment_master_prompt_vi"] = v_locks.get("environment_master_prompt_vi", "")
            script_data["continuity_prompt_en"] = v_locks.get("continuity_prompt_en", "")
            script_data["continuity_prompt_vi"] = v_locks.get("continuity_prompt_vi", "")
            script_data["continuity_board"] = {
                "continuity_prompt_en": v_locks.get("continuity_prompt_en", ""),
                "continuity_prompt_vi": v_locks.get("continuity_prompt_vi", ""),
            }
            script_data["global_negative_prompt_en"] = v_locks.get("global_negative_prompt_en", "")
            script_data["reference_images"] = v_locks.get("reference_images", script_data["reference_images"])
            # Carry forward prompt_0 from previous episode if available
            if v_locks.get("prompt_0"):
                script_data["prompt_0"] = v_locks["prompt_0"]

        if self.cached_script_data:
            self._hydrate_resume_cache(script_data, self.cached_script_data)
            script_data["_resume_signature"] = resume_signature
            script_data["narrative_shape"] = narrative_shape
            script_data["reality_binding_level"] = rule.reality_binding_level

        # ── Setup DB status ──
        self._repo.set_status(project_id, "generating_script")

        # ── Reset phase logs ──
        if hasattr(self, "_repo") and self._repo:
            if self.cached_script_data:
                self._repo.append_phase_log(project_id, "resume_cache", "3.0", [], 0.0)
            else:
                self._repo.reset_phase_log(project_id)

        import time

        # Role delegation guard: generation phases are routed through behavior-free
        # adapters while the actual phase logic remains in the legacy methods below.
        blueprint_role = BlueprintRole(self)
        emotion_arc_role = EmotionArcRole(self)
        scene_batch_role = SceneBatchRole(self)
        semantic_verifier_role = SemanticVerifierRole(self)
        packaging_role = PackagingRole(self)
        fact_check_role = FactCheckRole(self)

        # ── Phase 0: Prompt 0 + Blueprint ──
        blueprint_errors = (
            validate_blueprint_required(script_data)
            + retryable_messages(validate_story_contract_issues(script_data))
        )
        if not blueprint_errors:
            logger.info(f"Project {project_id}: Phase 0 cache hit.")
            self._ensure_story_spine(script_data, num_scenes)
            blueprint_errors = self._story_spine_blocking_errors(validate_story_spine_quality(script_data))
            yield self._stream_event({"status": "generating", "group": "metadata", "step": "cache_hit_prompt0_blueprint"})
            yield self._stream_event({"status": "metadata", "data": self._metadata_payload(script_data)})
            self._append_phase_log(project_id, "cache_hit_prompt0_blueprint", [])
        else:
            phase_start = time.time()
            async for event in blueprint_role.run_stream(
                suggestion, style, num_scenes, scene_duration_sec,
                is_historical_or_scientific, model_name, script_data, project_id, topic_type,
                context_from_previous=context_from_previous,
            ):
                yield event
            self._save_debug_snapshot(0, "prompt0_blueprint", script_data, project_id)
            self._ensure_story_spine(script_data, num_scenes)
            blueprint_errors = (
                validate_blueprint_required(script_data)
                + retryable_messages(validate_story_contract_issues(script_data))
                + self._story_spine_blocking_errors(validate_story_spine_quality(script_data))
            )
            elapsed_ms = (time.time() - phase_start) * 1000.0
            self._append_phase_log(project_id, "prompt0_blueprint", blueprint_errors, elapsed_ms)
        self._raise_gate_errors("Phase 0 blueprint", blueprint_errors)
        self._ensure_story_spine(script_data, num_scenes)
        locked_blueprint = json.loads(json.dumps({
            k: script_data.get(k)
            for k in [
                "prompt_0",
                "narrative_shape",
                "story_contract",
                "story_spine",
                "overview_analysis_vi",
                "storyline_vi",
                "stages_vi",
                "progression_vi",
                "camera_strategy_vi",
                "continuity_locks_vi",
                "form_locks_vi",
                "age_stage_locks_vi",
                "geometry_locks_vi",
                "risk_logic_vi",
                "voice_sound_strategy_vi",
                "characters",
                "environment_master_prompt_en",
                "environment_master_prompt_vi",
                "continuity_evolution",
                "continuity_prompt_en",
                "continuity_prompt_vi",
                "continuity_board",
                "global_negative_prompt_en",
            ]
        }, ensure_ascii=False))

        # ── Phase 1: Emotion Arc (chunked for large scripts) ──
        ARC_CHUNK_SIZE = 20
        arc_errors = validate_emotion_arc_quality(script_data.get("emotion_arc", []), num_scenes)
        if not arc_errors:
            logger.info(f"Project {project_id}: Phase 1 cache hit.")
            yield self._stream_event({"status": "generating", "group": "metadata", "step": "cache_hit_emotion_arc"})
            yield self._stream_event({"status": "emotion_arc", "data": script_data.get("emotion_arc", [])})
            self._append_phase_log(project_id, "cache_hit_emotion_arc", [])
        else:
            phase_start = time.time()
            arc_generated = False
            if script_data.get("emotion_arc"):
                logger.info(f"Project {project_id}: clearing invalid partial emotion_arc before regeneration.")
                script_data["emotion_arc"] = []
                self._save_script(project_id, suggestion.get("index", 0), script_data, "generating_script", topic_type)
            if num_scenes > ARC_CHUNK_SIZE:
                arc_chunks = [
                    (s, min(s + ARC_CHUNK_SIZE - 1, num_scenes))
                    for s in range(1, num_scenes + 1, ARC_CHUNK_SIZE)
                ]
                full_arc = []
                prev_arc_last_entry = None

                for chunk_idx, (arc_start, arc_end) in enumerate(arc_chunks):
                    chunk_num_scenes = arc_end - arc_start + 1
                    arc_suggestion = suggestion.copy()
                    arc_suggestion["_story_spine_context"] = story_spine_context(
                        script_data.get("story_spine", {}),
                        arc_start,
                        arc_end,
                        [],
                    )
                    arc_suggestion["_future_targets_context"] = future_targets_context(
                        script_data.get("story_spine", {}),
                        arc_start,
                        arc_end,
                    )
                    if prev_arc_last_entry:
                        arc_suggestion["_arc_handoff"] = {
                            "prev_end_scene": arc_start - 1,
                            "prev_emotion_label": prev_arc_last_entry.get("emotion_label"),
                            "prev_physical_state_end": prev_arc_last_entry.get("physical_state_end"),
                            "prev_beat_summary": prev_arc_last_entry.get("beat_summary"),
                        }

                    script_data["emotion_arc"] = []
                    async for event in emotion_arc_role.run_stream(
                        arc_suggestion, style, chunk_num_scenes, model_name, script_data, project_id, topic_type,
                        persist=False,
                        emit_result=False,
                        expected_start=arc_start,
                        expected_end=arc_end,
                        progress_step=f"emotion_arc_chunk_{chunk_idx + 1}_of_{len(arc_chunks)}",
                    ):
                        yield event

                    arc_part = script_data["emotion_arc"]
                    chunk_warnings = (
                        self._validate_arc_chunk_state(arc_part, script_data.get("story_spine", {}))
                        + validate_emotion_arc_constraints({**script_data, "emotion_arc": arc_part})
                    )
                    if chunk_warnings:
                        logger.warning(f"Emotion arc chunk warnings {arc_start}-{arc_end}: {chunk_warnings[:8]}")
                    chunk_errors = validate_emotion_arc_quality(arc_part, chunk_num_scenes)
                    if chunk_errors:
                        self._raise_gate_errors(
                            f"Phase 1 emotion_arc chunk {arc_start}-{arc_end}",
                            chunk_errors,
                        )
                    full_arc.extend(arc_part)
                    prev_arc_last_entry = arc_part[-1] if arc_part else None

                script_data["emotion_arc"] = full_arc
                arc_generated = True
            else:
                arc_suggestion = suggestion.copy()
                arc_suggestion["_story_spine_context"] = story_spine_context(
                    script_data.get("story_spine", {}),
                    1,
                    num_scenes,
                    [],
                )
                arc_suggestion["_future_targets_context"] = future_targets_context(
                    script_data.get("story_spine", {}),
                    1,
                    num_scenes,
                )
                async for event in emotion_arc_role.run_stream(
                    arc_suggestion, style, num_scenes, model_name, script_data, project_id, topic_type,
                    persist=False,
                    emit_result=False,
                    expected_start=1,
                    expected_end=num_scenes,
                ):
                    yield event
                arc_generated = True

            self._restore_locked_blueprint(script_data, locked_blueprint)
            self._save_debug_snapshot(1, "emotion_arc", script_data, project_id)
            arc_errors = (
                validate_state_invariants(script_data, locked_blueprint)
                + validate_emotion_arc_quality(script_data.get("emotion_arc", []), num_scenes)
            )
            arc_warnings = (
                validate_emotion_arc_state_machine(script_data.get("emotion_arc", []), script_data.get("story_spine", {}))
                + validate_emotion_arc_constraints(script_data)
            )
            if arc_warnings:
                logger.warning(f"Emotion arc semantic warnings: {arc_warnings[:8]}")
            elapsed_ms = (time.time() - phase_start) * 1000.0
            self._append_phase_log(project_id, "emotion_arc", arc_errors, elapsed_ms)
            self._raise_gate_errors("Phase 1 emotion_arc", arc_errors)
            if arc_generated:
                self._save_script(project_id, suggestion.get("index", 0), script_data, "generating_script", topic_type)
                yield self._stream_event({"status": "emotion_arc", "data": script_data.get("emotion_arc", [])})
                await self._maybe_sleep(STREAM_DELAY)
        self._raise_gate_errors("Phase 1 emotion_arc", arc_errors)

        # ── Phase 2: Batch Scene Generation ──
        if self._valid_scene_cache_complete(script_data, num_scenes, style):
            logger.info(f"Project {project_id}: Phase 2 cache hit.")
            script_errors = []
            yield self._stream_event({"status": "generating", "group": "scenes", "step": "cache_hit_scenes"})
            for scene in sorted(script_data.get("scenes", []), key=lambda s: s.get("scene_number", 0)):
                yield self._stream_event({"status": "scene", "data": scene})
            self._append_phase_log(project_id, "cache_hit_batch_scenes", [])
        else:
            phase_start = time.time()
            async for event in scene_batch_role.run_stream(
                suggestion, style, num_scenes, model_name, script_data, project_id, topic_type,
                is_historical_or_scientific, aspect_ratio, scene_duration_sec,
            ):
                yield event
            self._restore_locked_blueprint(script_data, locked_blueprint)
            self._backfill_scene_level_fields(script_data)
            self._save_debug_snapshot(2, "scenes", script_data, project_id)

            scene_issues = validate_scene_generation_issues(script_data)
            scene_warnings = [issue.message for issue in scene_issues if issue.severity == "WARN"]
            if scene_warnings:
                logger.warning(f"Scene validation warnings after Phase 2: {scene_warnings[:8]}")
            script_errors = (
                validate_state_invariants(script_data, locked_blueprint)
                + validate_script(normalize_script(script_data))
                + blocking_messages(scene_issues)
            )
            if script_errors:
                logger.warning(f"Script-level validation issues after Phase 2: {script_errors}")
            elapsed_ms = (time.time() - phase_start) * 1000.0
            self._append_phase_log(project_id, "batch_scenes", script_errors, elapsed_ms)
        self._raise_gate_errors("Phase 2 scenes", script_errors)

        # ── Phase 2.5: Soft Semantic Verifier ──
        # Durable verifier cost guard: strict topics still get the full verifier,
        # while soft fiction spends the extra LLM call only when warnings/flags exist.
        if self._semantic_verifier_enabled(script_data, topic_type) and not script_data.get("_semantic_verifier_completed"):
            phase_start = time.time()
            yield self._stream_event({"status": "generating", "group": "global", "step": "semantic_verifier"})
            before_semantic = {
                "scenes": json.loads(json.dumps(script_data.get("scenes") or [], ensure_ascii=False)),
                "emotion_arc": json.loads(json.dumps(script_data.get("emotion_arc") or [], ensure_ascii=False)),
            }
            edit_count = await semantic_verifier_role.run_legacy(
                suggestion, style, model_name, script_data, project_id, topic_type, scene_duration_sec
            )
            self._restore_locked_blueprint(script_data, locked_blueprint)
            semantic_contract_errors = (
                validate_state_invariants(script_data, locked_blueprint)
                + validate_script(normalize_script(script_data))
                + blocking_messages(validate_scene_generation_issues(script_data))
            )
            if semantic_contract_errors:
                script_data["scenes"] = before_semantic["scenes"]
                script_data["emotion_arc"] = before_semantic["emotion_arc"]
                script_data["_semantic_verifier_completed"] = True
                self._append_quality_warnings(
                    script_data,
                    [
                        "Semantic verifier changes rolled back due to technical validation: "
                        + "; ".join(semantic_contract_errors[:6])
                    ],
                )
                edit_count = 0
            self._save_debug_snapshot(25, "semantic_verifier", script_data, project_id)
            elapsed_ms = (time.time() - phase_start) * 1000.0
            self._append_phase_log(
                project_id,
                "semantic_verifier",
                [f"{edit_count} scene edits merged"] if edit_count else [],
                elapsed_ms,
            )
            self._save_script(project_id, suggestion.get("index", 0), script_data, "generating_script", topic_type)
        elif not script_data.get("_semantic_verifier_completed"):
            logger.info(
                "Project %s: Semantic verifier skipped by speed gate for topic=%s reality_binding=%s",
                project_id,
                topic_type,
                script_data.get("reality_binding_level"),
            )
            self._append_phase_log(project_id, "semantic_verifier_skipped", [], 0.0)

        # ── Phase 3: Packaging ──
        if self._has_packaging_cache(script_data):
            logger.info(f"Project {project_id}: Phase 3 cache hit.")
            self._backfill_scene_level_fields(script_data)
            packaging_errors = (
                validate_state_invariants(script_data, locked_blueprint)
                + self._validate_packaging_refs(script_data)
                + validate_script(normalize_script(script_data))
                + blocking_messages(validate_scene_generation_issues(script_data))
            )
            yield self._stream_event({"status": "generating", "group": "global", "step": "cache_hit_packaging"})
            self._append_phase_log(project_id, "cache_hit_packaging", packaging_errors)
            if not packaging_errors:
                self._save_script(project_id, suggestion.get("index", 0), script_data, "generating_script", topic_type)
        else:
            phase_start = time.time()
            async for event in packaging_role.run_stream(
                suggestion, style, model_name, script_data, project_id, topic_type, aspect_ratio,
                context_from_previous=context_from_previous,
            ):
                yield event
            self._restore_locked_blueprint(script_data, locked_blueprint)
            self._save_debug_snapshot(3, "packaging", script_data, project_id)
            packaging_errors = (
                validate_state_invariants(script_data, locked_blueprint)
                + self._validate_packaging_refs(script_data)
                + validate_script(normalize_script(script_data))
                + blocking_messages(validate_scene_generation_issues(script_data))
            )
            elapsed_ms = (time.time() - phase_start) * 1000.0
            self._append_phase_log(project_id, "packaging", packaging_errors, elapsed_ms)
        self._raise_gate_errors("Phase 3 packaging", packaging_errors)

        # ── Code Critique (no LLM) ──
        phase_start = time.time()
        critique_errors = self._code_critique(script_data, scene_duration_sec)
        elapsed_ms = (time.time() - phase_start) * 1000.0
        if hasattr(self, "_repo") and self._repo:
            self._repo.append_phase_log(project_id, "code_critique", "3.0", critique_errors, elapsed_ms)
        self._raise_gate_errors("Code critique", self._hard_critique_errors(critique_errors))

        # ── Phase 4: Fact-Check (historical/scientific only) ──
        if is_historical_or_scientific:
            fc_errors = (
                validate_state_invariants(script_data, locked_blueprint)
                + validate_script(normalize_script(script_data))
                + blocking_messages(validate_scene_generation_issues(script_data))
                + validate_historical_coverage(script_data)
            )
            if script_data.get("_fact_check_completed") is True and not fc_errors:
                logger.info(f"Project {project_id}: Phase 4 cache hit.")
                yield self._stream_event({"status": "generating", "group": "global", "step": "cache_hit_fact_check"})
                self._append_phase_log(project_id, "cache_hit_fact_check", [])
            else:
                phase_start = time.time()
                async for event in fact_check_role.run_stream(
                    style, model_name, script_data, project_id, topic_type, scene_duration_sec, suggestion.get("index", 0)
                ):
                    yield event
                self._restore_locked_blueprint(script_data, locked_blueprint)
                self._save_debug_snapshot(4, "fact_check", script_data, project_id)
                fc_errors = (
                    validate_state_invariants(script_data, locked_blueprint)
                    + validate_script(normalize_script(script_data))
                    + blocking_messages(validate_scene_generation_issues(script_data))
                    + validate_historical_coverage(script_data)
                )
                anchor = {"continuity_prompt_en": script_data.get("continuity_prompt_en", "")}
                for s in script_data.get("scenes", []):
                    s_errors = retryable_messages(
                        validate_scene_issues(normalize_scene(s), anchor, s.get("scene_number"))
                    )
                    for e in s_errors:
                        fc_errors.append(f"Scene {s.get('scene_number', 'unknown')}: {e}")
                elapsed_ms = (time.time() - phase_start) * 1000.0
                self._append_phase_log(project_id, "fact_check", fc_errors, elapsed_ms)
            self._raise_gate_errors("Phase 4 fact_check", fc_errors)

        # ── Post-generation suggestions ──
        import sys
        is_testing = "pytest" in sys.modules and not getattr(self, "enable_post_suggestions_test", False)
        if not is_testing:
            yield f"data: {json.dumps({'status': 'generating', 'group': 'global', 'step': 'post_suggestions'}, ensure_ascii=False)}\n\n"
            try:
                prompt_post = POST_GENERATION_SUGGESTION_PROMPT.format(
                    script_json=json.dumps({
                        "topic_type": script_data.get("topic_type"),
                        "storyline_vi": script_data.get("storyline_vi"),
                        "characters": script_data.get("characters"),
                    }, ensure_ascii=False)
                )
                res_post_raw = await self._call_production_llm(
                    prompt=prompt_post,
                    model_name=model_name,
                    generation_config={"response_mime_type": "application/json"},
                    phase="post_suggestions",
                )
                post_data = self._parse_llm_json_object(res_post_raw)
                script_data["post_suggestions"] = post_data.get("suggestions", [])
            except Exception as post_err:
                logger.error(f"Failed to generate post-generation suggestions: {post_err}")
                script_data["post_suggestions"] = []

        # ── Final Save + Done ──
        self._save_script(
            project_id, suggestion.get("index", 0), script_data, "script_generated", topic_type=topic_type
        )

        yield f"data: {json.dumps({'status': 'global', 'data': {'continuity_prompt_en': script_data['continuity_prompt_en'], 'global_negative_prompt_en': script_data['global_negative_prompt_en'], 'reference_images': script_data['reference_images'], 'prompt_0': script_data.get('prompt_0', {})}}, ensure_ascii=False)}\n\n"
        await self._maybe_sleep(STREAM_DELAY)
        yield f"data: {json.dumps({'status': 'done'}, ensure_ascii=False)}\n\n"

        # API Key quota
        if self.api_key_id:
            self._repo.increment_api_key_quota(self.api_key_id)

    # ─── PHASE 0: PROMPT 0 + BLUEPRINT ───────────────────────────────────────

    async def _phase0_prompt0_and_blueprint(
        self,
        suggestion, style, num_scenes, scene_duration_sec,
        is_historical, model_name, script_data, project_id, topic_type,
        context_from_previous=None,
    ):
        logger.info(f"Phase 0 (Prompt 0 + Blueprint) for project {project_id}")
        yield f"data: {json.dumps({'status': 'generating', 'group': 'metadata', 'step': 'prompt0_blueprint'}, ensure_ascii=False)}\n\n"

        has_named_figure = suggestion.get("has_named_historical_figure", False)
        rule = resolve_routing(topic_type, has_named_historical_figure=has_named_figure)
        if rule.fact_check_enabled:
            narrative_shape = rule.narrative_shape_default
        else:
            narrative_shape = suggestion.get("narrative_shape") or rule.narrative_shape_default
        shape_structure = SHAPE_STRUCTURES.get(narrative_shape, SHAPE_STRUCTURES["adventure"])

        context_str = self._build_context_str(context_from_previous)

        # If series mode with locked prompt_0, skip generation and reuse
        has_locked_prompt0 = (
            context_from_previous
            and "visual_locks" in context_from_previous
            and context_from_previous["visual_locks"].get("prompt_0")
        )

        if has_locked_prompt0:
            logger.info(f"Phase 0: Using locked Prompt 0 from previous episode.")
            # Still need to regenerate the Vietnamese blueprint for this episode
            prompt = PROMPT_0_GENERATION_TEMPLATE.format(
                title=suggestion.get("title", ""),
                synopsis=suggestion.get("synopsis", ""),
                style=style,
                num_scenes=num_scenes,
                scene_duration_sec=scene_duration_sec,
                topic_type=topic_type,
                shape_structure=shape_structure,
                context_str=context_str,
                historical_rules=HISTORICAL_SCIENTIFIC_HARD_RULES if is_historical else "",
                safety_rules=VEO3_CONTENT_SAFETY_RULES,
            )
        else:
            prompt = PROMPT_0_GENERATION_TEMPLATE.format(
                title=suggestion.get("title", ""),
                synopsis=suggestion.get("synopsis", ""),
                style=style,
                num_scenes=num_scenes,
                scene_duration_sec=scene_duration_sec,
                topic_type=topic_type,
                shape_structure=shape_structure,
                context_str=context_str,
                historical_rules=HISTORICAL_SCIENTIFIC_HARD_RULES if is_historical else "",
                safety_rules=VEO3_CONTENT_SAFETY_RULES,
            )

        current_prompt = prompt
        phase0_errors: list[str] = []
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                res_raw = await self._call_production_llm(
                    prompt=current_prompt,
                    model_name=model_name,
                    generation_config={"response_mime_type": "application/json"},
                    phase="prompt0_blueprint",
                )
                res = self._parse_llm_json_object(res_raw)

                # Only update prompt_0 if not locked from series
                if not has_locked_prompt0:
                    script_data["prompt_0"] = res.get("prompt_0", {})
                evolution = res.get("continuity_evolution")
                if isinstance(evolution, dict):
                    script_data["continuity_evolution"] = evolution
                elif isinstance((res.get("prompt_0") or {}).get("continuity_evolution"), dict):
                    script_data["continuity_evolution"] = res["prompt_0"]["continuity_evolution"]
                contract = res.get("story_contract")
                if isinstance(contract, dict):
                    script_data["story_contract"] = contract
                elif isinstance((res.get("prompt_0") or {}).get("story_contract"), dict):
                    script_data["story_contract"] = res["prompt_0"]["story_contract"]

                # Production plan fields
                script_data["overview_analysis_vi"] = res.get("overview_analysis_vi") or res.get("storyline_vi", "")
                script_data["storyline_vi"] = res.get("storyline_vi", "")
                script_data["stages_vi"] = res.get("stages_vi", "")
                script_data["progression_vi"] = res.get("progression_vi", "")
                script_data["camera_strategy_vi"] = res.get("camera_strategy_vi", "")
                script_data["continuity_locks_vi"] = res.get("continuity_locks_vi", "")
                script_data["form_locks_vi"] = res.get("form_locks_vi", "")
                script_data["age_stage_locks_vi"] = res.get("age_stage_locks_vi", "")
                script_data["geometry_locks_vi"] = res.get("geometry_locks_vi", "")
                script_data["risk_logic_vi"] = res.get("risk_logic_vi", "")
                script_data["voice_sound_strategy_vi"] = res.get("voice_sound_strategy_vi", "")

                # Characters (with series lock protection)
                generated_chars = res.get("characters", [])
                script_data["characters"] = self._merge_series_characters(generated_chars, context_from_previous)

                # Environment
                if not has_locked_prompt0:
                    script_data["environment_master_prompt_en"] = res.get("environment_master_prompt_en", "")
                    script_data["environment_master_prompt_vi"] = res.get("environment_master_prompt_vi", "")

                # Pre-populate continuity + global_negative from prompt_0
                p0 = script_data.get("prompt_0", {})
                if p0.get("continuity_lock_en"):
                    script_data["continuity_prompt_en"] = p0["continuity_lock_en"]
                    script_data["continuity_board"]["continuity_prompt_en"] = p0["continuity_lock_en"]
                if p0.get("negative_constraints_en"):
                    script_data["global_negative_prompt_en"] = p0["negative_constraints_en"]
                self._ensure_story_contract_defaults(script_data, suggestion)

                phase0_errors = validate_blueprint_required(script_data)
                contract_errors, contract_warnings = self._phase0_story_contract_errors(
                    script_data,
                    attempt,
                    topic_type,
                )
                phase0_errors.extend(contract_errors)
                if contract_warnings:
                    self._append_quality_warnings(script_data, contract_warnings)
                if not phase0_errors:
                    break
                logger.warning(f"Phase 0 validation attempt {attempt + 1} failed: {phase0_errors}")
                error_context = "\n\n=== VALIDATION ERRORS FROM PREVIOUS ATTEMPT ===\n"
                error_context += "\n".join(f"- {e}" for e in phase0_errors)
                error_context += "\nReturn a COMPLETE corrected JSON. Do not omit prompt_0 or production plan fields.\n"
                current_prompt = prompt + error_context
            except Exception as e:
                phase0_errors = [f"Phase 0 generation/parse error: {str(e)}"]
                logger.warning(f"Phase 0 attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_attempts - 1:
                    current_prompt = prompt + "\n\nReturn ONLY valid complete JSON matching the required schema."
                    await asyncio.sleep(2.0)
                    continue
            if attempt < max_attempts - 1:
                await asyncio.sleep(2.0)

        if phase0_errors:
            self._raise_gate_errors("Phase 0 blueprint", phase0_errors)

        self._save_script(project_id, suggestion.get("index", 0), script_data, "generating_script", topic_type)

        # ── Fix 2: Validate prompt_0 is not empty after Phase 0 ──
        p0_check = script_data.get("prompt_0", {})
        if not p0_check or p0_check == {}:
            logger.warning(
                f"[Project {project_id}] prompt_0 is empty after Phase 0 — "
                "blueprint generation may have failed silently. Pipeline will continue with degraded quality."
            )
        else:
            logger.info(f"[Project {project_id}] prompt_0 validated OK (has {len(p0_check)} keys).")

        # ── Fix 8: Validate blueprint metadata fields are not empty ──
        empty_fields = [
            f for f in ["stages_vi", "progression_vi", "camera_strategy_vi"]
            if not script_data.get(f)
        ]
        if empty_fields:
            logger.warning(
                f"[Project {project_id}] Blueprint metadata fields are empty after Phase 0: {empty_fields}. "
                "This may indicate a partial generation failure."
            )

        # ── Fix 3: Reset continuity_prompt_en if main character changed across series ──
        if context_from_previous and "visual_locks" in context_from_previous:
            v_locks = context_from_previous["visual_locks"]
            locked_chars = v_locks.get("characters", [])
            current_chars = script_data.get("characters", [])
            if locked_chars and current_chars:
                locked_names = {c.get("character_name") for c in locked_chars}
                current_names = {c.get("character_name") for c in current_chars}
                # If entirely new main character (no overlap at all)
                if locked_names and current_names and not locked_names.intersection(current_names):
                    logger.info(
                        f"[Project {project_id}] Series character changed: "
                        f"{locked_names} → {current_names}. Rebuilding continuity_prompt_en from new prompt_0."
                    )
                    new_p0 = script_data.get("prompt_0", {})
                    if new_p0.get("continuity_lock_en"):
                        script_data["continuity_prompt_en"] = new_p0["continuity_lock_en"]
                        script_data["continuity_board"]["continuity_prompt_en"] = new_p0["continuity_lock_en"]
                    if new_p0.get("negative_constraints_en"):
                        script_data["global_negative_prompt_en"] = new_p0["negative_constraints_en"]

        yield f"data: {json.dumps({'status': 'metadata', 'data': {'overview_analysis_vi': script_data['overview_analysis_vi'], 'storyline_vi': script_data['storyline_vi'], 'stages_vi': script_data['stages_vi'], 'camera_strategy_vi': script_data['camera_strategy_vi'], 'continuity_locks_vi': script_data['continuity_locks_vi'], 'form_locks_vi': script_data['form_locks_vi'], 'age_stage_locks_vi': script_data['age_stage_locks_vi'], 'geometry_locks_vi': script_data['geometry_locks_vi'], 'risk_logic_vi': script_data['risk_logic_vi'], 'characters': script_data['characters'], 'environment_master_prompt_en': script_data['environment_master_prompt_en'], 'environment_master_prompt_vi': script_data.get('environment_master_prompt_vi', ''), 'prompt_0': script_data.get('prompt_0', {})}}, ensure_ascii=False)}\n\n"
        await self._maybe_sleep(STREAM_DELAY)

    # ─── PHASE 1: EMOTION ARC ─────────────────────────────────────────────────

    async def _phase1_generate_emotion_arc(
        self, suggestion, style, num_scenes, model_name, script_data, project_id, topic_type,
        persist: bool = True,
        emit_result: bool = True,
        expected_start: int = 1,
        expected_end: int | None = None,
        progress_step: str = "emotion_arc",
    ):
        logger.info(f"Phase 1 (Emotion Arc) for project {project_id}")
        yield f"data: {json.dumps({'status': 'generating', 'group': 'metadata', 'step': progress_step, 'batch_start': expected_start, 'batch_end': expected_end or num_scenes}, ensure_ascii=False)}\n\n"

        has_named_figure = suggestion.get("has_named_historical_figure", False)
        rule = resolve_routing(topic_type, has_named_historical_figure=has_named_figure)
        if rule.fact_check_enabled:
            narrative_shape = rule.narrative_shape_default
        else:
            narrative_shape = suggestion.get("narrative_shape") or rule.narrative_shape_default
        shape_structure = SHAPE_STRUCTURES.get(narrative_shape, SHAPE_STRUCTURES["adventure"])

        chars_list = script_data.get("characters", [])
        characters_detail_str = "\n".join([
            f"- {c['character_name']}: {c.get('description_en', '')}" for c in chars_list
        ]) if chars_list else "No characters specified."
        characters_names_str = ", ".join([f'"{c["character_name"]}"' for c in chars_list]) if chars_list else '"None"'
        expected_end = expected_end or (expected_start + num_scenes - 1)
        scene_number_rule = (
            f"Return scene_number exactly {expected_start} through {expected_end}. "
            f"Do NOT return 1 through {num_scenes} unless the requested range is 1 through {num_scenes}."
        )

        prompt_emotion_arc = EMOTION_ARC_BASE_PROMPT.format(
            synopsis=suggestion.get("synopsis", ""),
            style=style,
            num_scenes=num_scenes,
            characters=characters_detail_str,
            characters_list=characters_names_str,
            shape_structure=shape_structure,
            scene_number_rule=scene_number_rule,
            story_contract_context=self._story_contract_context(script_data),
        )

        # Arc handoff for chunked generation
        arc_handoff = suggestion.get("_arc_handoff")
        if arc_handoff:
            prompt_emotion_arc += (
                f"\n\n=== CONTINUITY FROM SCENE {arc_handoff.get('prev_end_scene')} ===\n"
                f"Last emotion: {arc_handoff.get('prev_emotion_label')}\n"
                f"Last physical state: {arc_handoff.get('prev_physical_state_end')}\n"
                f"Last beat: {arc_handoff.get('prev_beat_summary')}\n"
                "REQUIRED: First scene in this arc chunk MUST naturally continue from the above state. "
                "Do not restart an earlier setup, location state, objective, conflict step, or completed phase.\n"
            )

        if suggestion.get("_story_spine_context"):
            prompt_emotion_arc += (
                "\n\n"
                + suggestion["_story_spine_context"]
                + "\nREQUIRED: The emotion arc chunk must follow this spine position. "
                "Do not create a complete intro-to-resolution mini-story inside this chunk.\n"
            )
        if suggestion.get("_future_targets_context"):
            prompt_emotion_arc += (
                "\n\n"
                + suggestion["_future_targets_context"]
                + "\nREQUIRED: Do not spend future targets early. Current scenes may only set up later payoffs.\n"
            )

        emotion_arc = []
        max_attempts = 3
        retry_feedback = ""
        last_error = ""
        for attempt in range(max_attempts):
            try:
                res_arc_raw = await self._call_production_llm(
                    prompt=prompt_emotion_arc + retry_feedback,
                    model_name=model_name,
                    generation_config={"response_mime_type": "application/json"},
                    phase="emotion_arc",
                    scene_range=(expected_start, expected_end),
                )
                res_arc = self._parse_llm_json_object(res_arc_raw)
                emotion_arc = res_arc if isinstance(res_arc, list) else res_arc.get("emotion_arc", [])
                if not emotion_arc:
                    raise ValueError("Emotion arc response contained no emotion_arc entries")

                # Validate intensity variation
                HIGH_INTENSITY = {"đau đớn", "phẫn nộ", "sửng sốt", "tuyệt vọng", "bi tráng", "sợ hãi", "hoảng hốt", "kinh ngạc", "căng thẳng"}
                labels = [e.get("emotion_label", "").lower() for e in emotion_arc]
                has_peak = any(any(h in l for h in HIGH_INTENSITY) for l in labels)
                unique_ratio = len(set(labels)) / max(len(labels), 1)

                if len(emotion_arc) == num_scenes and (not has_peak or unique_ratio < 0.5):
                    logger.warning("Emotion arc too flat, retrying with intensity warning.")
                    res_arc_raw = await self._call_production_llm(
                        prompt=prompt_emotion_arc + retry_feedback + "\n\nCRITICAL: Previous arc was too flat. Add at least one high-intensity peak (sửng sốt, bi tráng, hoảng hốt) and ensure emotional variety.",
                        model_name=model_name,
                        generation_config={"response_mime_type": "application/json"},
                        phase="emotion_arc_flat_retry",
                        scene_range=(expected_start, expected_end),
                    )
                    res_arc = self._parse_llm_json_object(res_arc_raw)
                    emotion_arc = res_arc if isinstance(res_arc, list) else res_arc.get("emotion_arc", [])

                if len(emotion_arc) != num_scenes:
                    raise ValueError(f"Emotion arc length mismatch: expected {num_scenes}, got {len(emotion_arc)}")
                emotion_arc, number_errors = self._normalize_arc_chunk_numbers(
                    emotion_arc,
                    expected_start,
                    expected_end,
                )
                if number_errors:
                    raise ValueError("; ".join(number_errors))
                state_warnings = self._validate_arc_chunk_state(
                    emotion_arc,
                    script_data.get("story_spine", {}),
                )
                constraint_warnings = validate_emotion_arc_constraints({**script_data, "emotion_arc": emotion_arc})
                if state_warnings or constraint_warnings:
                    logger.warning(
                        f"Emotion arc semantic warnings: {(state_warnings + constraint_warnings)[:8]}"
                    )
                break
            except Exception as e:
                error_message = str(e)
                last_error = error_message
                logger.warning(f"Emotion arc generation attempt {attempt + 1} failed: {error_message}")
                if attempt == max_attempts - 1:
                    logger.error(f"Emotion arc generation completely failed: {error_message}")
                    emotion_arc = []
                else:
                    retry_feedback = (
                        "\n\n=== PREVIOUS ATTEMPT ERRORS - FIX THESE EXACTLY ===\n"
                        f"{error_message}\n"
                        f"Return exactly {num_scenes} entries with scene_number {expected_start}-{expected_end}. "
                        "Do not restart a mini-story. Do not use completed or out-of-range story triggers. "
                        "Remove any story beat that depends on a Prompt 0 forbidden object, force, material, or physics.\n"
                    )
                    await asyncio.sleep(2.0)

        if not emotion_arc or len(emotion_arc) != num_scenes:
            detail = f": {last_error}" if last_error else ""
            raise RuntimeError(
                f"Emotion arc generation failed for scenes {expected_start}-{expected_end}: "
                f"expected {num_scenes}, got {len(emotion_arc)}{detail}"
            )

        script_data["emotion_arc"] = emotion_arc
        if persist:
            self._save_script(project_id, suggestion.get("index", 0), script_data, "generating_script", topic_type)
        if emit_result:
            yield f"data: {json.dumps({'status': 'emotion_arc', 'data': emotion_arc}, ensure_ascii=False)}\n\n"
            await self._maybe_sleep(STREAM_DELAY)

    # ─── PHASE 2: BATCH SCENE GENERATION ─────────────────────────────────────

    async def _phase2_batch_generate_scenes(
        self, suggestion, style, num_scenes, model_name, script_data, project_id, topic_type,
        is_historical, aspect_ratio, scene_duration_sec,
    ):
        logger.info(f"Phase 2 (Batch Scenes) for project {project_id}, {num_scenes} scenes")

        BATCH_SIZE = 10
        prompt_0_base_text = build_compact_prompt_0_text(script_data.get("prompt_0", {}))
        if prompt_0_base_text == "No Prompt 0 available." or not script_data.get("continuity_prompt_en"):
            raise RuntimeError("Scene generation blocked: Prompt 0 or continuity anchor is empty")
        story_spine = self._ensure_story_spine(script_data, num_scenes)
        cached_scene_errors = (
            blocking_messages(validate_scene_generation_issues(script_data))
            if script_data.get("scenes") else []
        )
        if cached_scene_errors:
            logger.info(
                f"Cached scene set has validation issues before Phase 2 resume; "
                f"will keep individually reusable scenes only: {cached_scene_errors[:5]}"
            )
            reusable_scenes = [
                cached
                for scene_num in range(1, num_scenes + 1)
                if (cached := self._get_cached_scene(scene_num, script_data, style))
            ]
            script_data["scenes"] = reusable_scenes

        batches = [
            (s, min(s + BATCH_SIZE - 1, num_scenes))
            for s in range(1, num_scenes + 1, BATCH_SIZE)
        ]
        total_batches = len(batches)
        prev_physical_state_end = "Câu chuyện bắt đầu"
        contract_drift_streak = 0

        for batch_idx, (batch_start, batch_end) in enumerate(batches):
            batch_started_at = time.time()
            batch_size = batch_end - batch_start + 1
            yield f"data: {json.dumps({'status': 'generating', 'group': 'scenes', 'step': f'batch_{batch_idx+1}_of_{total_batches}', 'batch_start': batch_start, 'batch_end': batch_end}, ensure_ascii=False)}\n\n"

            # Check cached scenes in this batch. Missing scenes are generated as
            # compact contiguous spans so a reconnect never burns tokens on old work.
            cached_scenes_in_batch = {}
            for scene_num in range(batch_start, batch_end + 1):
                cached = self._get_cached_scene(scene_num, script_data, style)
                if cached:
                    cached_scenes_in_batch[scene_num] = cached

            missing_scene_nums = [
                n for n in range(batch_start, batch_end + 1)
                if n not in cached_scenes_in_batch
            ]

            if not missing_scene_nums:
                logger.info(f"Batch {batch_start}-{batch_end} is fully cached.")
            else:
                spans = []
                span_start = missing_scene_nums[0]
                prev_num = span_start
                for scene_num in missing_scene_nums[1:]:
                    if scene_num == prev_num + 1:
                        prev_num = scene_num
                        continue
                    spans.append((span_start, prev_num))
                    span_start = scene_num
                    prev_num = scene_num
                spans.append((span_start, prev_num))

                for span_start, span_end in spans:
                    # Add pacing delay to prevent hitting API Rate Limits (RPM) on consecutive calls.
                    if batch_idx > 0 or span_start != missing_scene_nums[0]:
                        logger.info(f"Pacing delay before scenes {span_start}-{span_end}...")
                        await asyncio.sleep(1.5)

                    span_size = span_end - span_start + 1
                    batch_emotion_arc = [
                        e for e in script_data.get("emotion_arc", [])
                        if span_start <= e.get("scene_number", 0) <= span_end
                    ]
                    lead_names = [
                        e.get("scene_lead_character")
                        for e in batch_emotion_arc
                        if e.get("scene_lead_character") and e.get("scene_lead_character") != "None"
                    ]
                    prompt_0_text = build_compact_prompt_0_text(script_data.get("prompt_0", {}), lead_names)

                    stage_context = self._extract_stage_context(
                        script_data.get("stages_vi", ""), span_start, span_end, story_spine
                    )

                    if span_start == 1:
                        prev_context = "This is the FIRST scene batch. Begin the story from the beginning."
                    else:
                        actual_handoff = self._scene_handoff_for_number(
                            script_data,
                            span_start - 1,
                            prev_physical_state_end,
                        )
                        prev_context = (
                            f"Scene {span_start - 1} ended with: {actual_handoff}. "
                            f"Scene {span_start} MUST physically continue from this exact saved scene state. "
                            "If this conflicts with the emotion arc, the saved scene state wins. "
                            "Do not restart an earlier journey step, arrival, preparation, or entry beat."
                        )

                    is_final_batch = (batch_idx == total_batches - 1)
                    if is_final_batch:
                        batch_position_instruction = (
                            f"This is the FINAL batch (batch {batch_idx + 1} of {total_batches}). "
                            "You SHOULD write a proper narrative conclusion for this batch. "
                            "The last scene should feel like a meaningful ending."
                        )
                    else:
                        batch_position_instruction = (
                            f"This is batch {batch_idx + 1} of {total_batches} — NOT the final batch. "
                            "STRICTLY FORBIDDEN in this batch: farewell scenes, drone-away shots, "
                            "reflective 'looking back' conclusions, silhouette-against-sunset endings, "
                            "or ANY scene implying the story is over. "
                            "The story must actively CONTINUE into the next batch."
                        )

                    already_generated = script_data.get("scenes", [])
                    if already_generated:
                        last_10 = already_generated[-5:]
                        used_summaries = [
                            f"- Scene {s.get('scene_number', '?')}: {(s.get('action_detail_vi', '') or '')[:120]}"
                            for s in last_10
                        ]
                        used_actions_context = (
                            "=== PREVIOUSLY GENERATED ACTIONS (DO NOT REPEAT THESE) ===\n"
                            + "\n".join(used_summaries)
                            + "\n=== END USED ACTIONS ===\n"
                        )
                    else:
                        used_actions_context = ""

                    story_spine_state = story_spine_context(
                        story_spine,
                        span_start,
                        span_end,
                        self._used_triggers_from_scenes(script_data, span_start),
                    )
                    future_targets_state = future_targets_context(
                        story_spine,
                        span_start,
                        span_end,
                    )

                    base_prompt = BATCH_SCENE_GENERATION_TEMPLATE.format(
                        batch_size=span_size,
                        batch_start=span_start,
                        batch_end=span_end,
                        prompt_0_full_text=prompt_0_text,
                        title=suggestion.get("title", ""),
                        style=style,
                        num_scenes=num_scenes,
                        stage_context=stage_context,
                        story_contract_context=self._story_contract_context(script_data),
                        emotion_arc_json=json.dumps(batch_emotion_arc, ensure_ascii=False),
                        story_spine_context=story_spine_state,
                        future_targets_context=future_targets_state,
                        prev_context=prev_context,
                        constraint_context=self._constraint_context(script_data),
                        aspect_ratio=aspect_ratio,
                        scene_duration_sec=scene_duration_sec,
                        historical_rules=HISTORICAL_SCIENTIFIC_HARD_RULES if is_historical else "",
                        safety_rules=VEO3_CONTENT_SAFETY_RULES,
                        batch_position_instruction=batch_position_instruction,
                        used_actions_context=used_actions_context,
                    )
                    if len(base_prompt) > MAX_BATCH_PROMPT_CHARS:
                        raise RuntimeError(
                            f"Batch prompt too large for scenes {span_start}-{span_end}: "
                            f"{len(base_prompt)} chars > {MAX_BATCH_PROMPT_CHARS}"
                        )

                    generated_scenes = []
                    max_attempts = 3
                    retry_feedback = ""
                    for attempt in range(max_attempts):
                        try:
                            prompt = base_prompt + retry_feedback
                            res_raw = await self._call_production_llm(
                                prompt=prompt,
                                model_name=model_name,
                                generation_config={
                                    "response_mime_type": "application/json",
                                    "max_output_tokens": 8192,
                                },
                                phase="batch_scenes",
                                scene_range=(span_start, span_end),
                            )
                            res = self._parse_llm_json_object(res_raw)
                            generated_scenes = res if isinstance(res, list) else res.get("scenes", [])
                            returned_nums = {s.get("scene_number") for s in generated_scenes}
                            expected_nums = set(range(span_start, span_end + 1))
                            if returned_nums != expected_nums:
                                raise ValueError(
                                    f"Scene span mismatch: expected {sorted(expected_nums)}, got {sorted(returned_nums)}"
                                )
                            span_errors = self._validate_candidate_scenes(
                                script_data,
                                generated_scenes,
                                scene_duration_sec,
                                BASE_NEGATIVE_PROMPT,
                            )
                            if span_errors:
                                raise ValueError(
                                    "Scene quality validation failed: "
                                    + "; ".join(span_errors[:8])
                                )
                            break
                        except Exception as e:
                            logger.warning(f"Scenes {span_start}-{span_end} generation attempt {attempt + 1} failed: {str(e)}")
                            if attempt == max_attempts - 1:
                                logger.error(f"Scenes {span_start}-{span_end} generation completely failed: {str(e)}")
                                raise RuntimeError(
                                    f"Batch scene generation failed for scenes {span_start}-{span_end}: {str(e)}"
                                )
                            retry_feedback = (
                                "\n\n=== PREVIOUS ATTEMPT ERRORS - FIX THESE EXACTLY ===\n"
                                f"{str(e)}\n"
                                "Return the same requested scene numbers only. Preserve the saved handoff state, "
                                "remove repeated/reset actions, and keep every veo3_prompt_en anchored.\n"
                            )
                            await asyncio.sleep(2.5)

                    for scene in generated_scenes:
                        self._prepare_scene(scene, scene_duration_sec, BASE_NEGATIVE_PROMPT, script_data)
                        self._upsert_scene(script_data, scene)
                        yield f"data: {json.dumps({'status': 'scene', 'data': scene}, ensure_ascii=False)}\n\n"

            scenes_batch = [
                self._get_cached_scene(n, script_data, style)
                or next((s for s in script_data.get("scenes", []) if s.get("scene_number") == n), None)
                for n in range(batch_start, batch_end + 1)
            ]
            scenes_batch = [s for s in scenes_batch if s]

            # Durable stream/save guard: cached scenes are replayed to reconnecting
            # clients, but generated scenes are already streamed and are saved once per batch.
            for scene in [cached_scenes_in_batch[n] for n in sorted(cached_scenes_in_batch)]:
                scene_num = scene.get("scene_number", batch_start)
                self._prepare_scene(scene, scene_duration_sec, BASE_NEGATIVE_PROMPT, script_data)
                self._upsert_scene(script_data, scene)
                yield f"data: {json.dumps({'status': 'scene', 'data': scene}, ensure_ascii=False)}\n\n"

            # Update physical state handoff from the actual saved final scene in this batch.
            last_scene_num = scenes_batch[-1].get("scene_number", batch_end) if scenes_batch else batch_end
            arc_entry = next(
                (e for e in script_data.get("emotion_arc", []) if e.get("scene_number") == last_scene_num),
                None
            )
            prev_physical_state_end = scene_handoff_state(
                self._find_scene(script_data, last_scene_num),
                (arc_entry or {}).get("physical_state_end", prev_physical_state_end),
            )
            drift_warning = detect_story_contract_batch_drift(script_data, scenes_batch)
            if drift_warning:
                contract_drift_streak += 1
                logger.warning(f"Story contract drift candidate after batch {batch_idx + 1}: {drift_warning}")
                if contract_drift_streak >= 2 or total_batches == 1:
                    self._append_quality_warnings(script_data, [drift_warning])
            else:
                contract_drift_streak = 0
            self._save_script(
                project_id,
                suggestion.get("index", 0),
                script_data,
                "generating_script",
                topic_type,
                canonical=False,
            )
            logger.info(
                "Project %s: Phase 2 batch %s/%s scenes %s-%s checkpoint saved in %.1fms",
                project_id,
                batch_idx + 1,
                total_batches,
                batch_start,
                batch_end,
                (time.time() - batch_started_at) * 1000.0,
            )

            await self._maybe_sleep(STREAM_DELAY)

        # Finalize: sort and standardize
        script_data["scenes"].sort(key=lambda s: s.get("scene_number", 0))
        script_data["scenes"] = standardize_scene_titles(script_data["scenes"], scene_duration_sec)
        for s in script_data["scenes"]:
            ensure_scene_defaults(s, BASE_NEGATIVE_PROMPT)
        self._backfill_scene_level_fields(script_data)
        self._save_script(project_id, suggestion.get("index", 0), script_data, "generating_script", topic_type)

    # Durable longform-stage guard: this legacy method now delegates to the
    # parsed story spine, preventing all chapter headers from leaking into each batch.
    def _extract_stage_context(
        self,
        stages_vi: str,
        batch_start: int,
        batch_end: int,
        story_spine: dict | None = None,
    ) -> str:
        if story_spine:
            return stage_context_for_range(story_spine, batch_start, batch_end)
        return f"Scenes {batch_start}-{batch_end} of the story."

    def _fallback_batch_scenes(
        self, batch_start: int, batch_end: int, scene_duration_sec: int, style: str, aspect_ratio: str
    ) -> list:
        """Generate minimal fallback scenes when batch API call fails."""
        scenes = []
        for scene_num in range(batch_start, batch_end + 1):
            start_sec = (scene_num - 1) * scene_duration_sec
            end_sec = scene_num * scene_duration_sec
            s_min, s_s = start_sec // 60, start_sec % 60
            e_min, e_s = end_sec // 60, end_sec % 60
            scenes.append({
                "scene_number": scene_num,
                "title": f"Scene {scene_num} [{s_min:02d}:{s_s:02d} - {e_min:02d}:{e_s:02d}]",
                "action_detail_vi": f"Hành động diễn tiến trong phân cảnh {scene_num}.",
                "veo3_prompt_en": f"Reference the approved Prompt 0 continuity board, cinematic shot of scene {scene_num}, {style} style, aspect ratio {aspect_ratio}, voice: \"The story continues.\"",
                "voice_over_en": "The story continues.",
                "needs_fact_check": False,
                "fact_check_note_vi": None,
                "historical_basis_vi": None,
                "generation_failed": True,
                "generation_error": "Batch generation failed — fallback used",
            })
        return scenes

    # ─── PHASE 2.5: SOFT SEMANTIC VERIFIER ───────────────────────────────────

    # Durable verifier cost guard: pytest keeps the expensive role opt-in, and
    # production soft topics skip it unless upstream warnings or risk flags exist.
    def _semantic_verifier_enabled(self, script_data: dict | None = None, topic_type: str | None = None) -> bool:
        import sys
        if "pytest" in sys.modules and not getattr(self, "enable_semantic_verifier_test", False):
            return False
        if script_data is None:
            return True
        if (script_data.get("reality_binding_level") or "").lower() == "strict":
            return True
        if topic_type in {"historical", "scientific"}:
            return True
        return self._semantic_verifier_has_flags(script_data)

    # Durable verifier cost guard: flags come from existing validation/fact fields
    # only, so this avoids adding another hard-coded semantic rule layer.
    def _semantic_verifier_has_flags(self, script_data: dict) -> bool:
        if script_data.get("quality_warnings"):
            return True
        for scene in script_data.get("scenes") or []:
            verification = scene.get("verification") if isinstance(scene.get("verification"), dict) else {}
            risk_flags = (
                verification.get("risk_flags")
                or scene.get("verification_risk_flags")
                or []
            )
            status = verification.get("status") or scene.get("verification_status")
            if risk_flags or scene.get("needs_fact_check") or status in {"needs_review", "corrected"}:
                return True
        return False

    def _quality_warning_text(self, raw_warning) -> str:
        if isinstance(raw_warning, str):
            return raw_warning.strip()
        if not isinstance(raw_warning, dict):
            return ""
        scene_num = raw_warning.get("scene_number")
        message = (
            raw_warning.get("message_vi")
            or raw_warning.get("message")
            or raw_warning.get("warning")
            or ""
        )
        fix = raw_warning.get("suggested_fix_vi") or raw_warning.get("suggested_fix") or ""
        prefix = f"Scene {scene_num}: " if scene_num else ""
        suffix = f" Fix: {fix}" if fix else ""
        return f"{prefix}{message}{suffix}".strip()

    def _append_quality_warnings(self, script_data: dict, warnings) -> None:
        if not warnings:
            return
        existing = [
            self._quality_warning_text(w)
            for w in script_data.setdefault("quality_warnings", [])
        ]
        seen = {w for w in existing if w}
        normalized = [w for w in existing if w]
        warning_items = warnings if isinstance(warnings, list) else [warnings]
        for item in warning_items:
            text = self._quality_warning_text(item)
            if text and text not in seen:
                normalized.append(text)
                seen.add(text)
        script_data["quality_warnings"] = normalized

    # Durable verifier cost guard: drift-triggered verification uses compact
    # scene summaries so topic repair does not reintroduce the slow full audit path.
    def _semantic_scene_payload(self, script_data: dict, max_chars: int = 24000, compact: bool = False) -> str:
        scenes = []
        for scene in sorted(script_data.get("scenes") or [], key=lambda s: s.get("scene_number", 0)):
            if compact:
                scenes.append({
                    "scene_number": scene.get("scene_number"),
                    "action_detail_vi": scene.get("action_detail_vi"),
                    "voice_over_en": scene.get("voice_over_en"),
                })
            else:
                scenes.append({
                    "scene_number": scene.get("scene_number"),
                    "title": scene.get("title"),
                    "action_detail_vi": scene.get("action_detail_vi"),
                    "veo3_prompt_en": scene.get("veo3_prompt_en"),
                    "voice_over_en": scene.get("voice_over_en"),
                    "voice_over_vi": scene.get("voice_over_vi"),
                    "scene_specific_negative_en": scene.get("scene_specific_negative_en"),
                })
        payload = json.dumps(scenes, ensure_ascii=False)
        if len(payload) <= max_chars:
            return payload
        head = scenes[:4]
        tail = scenes[-8:]
        return json.dumps({
            "truncated": True,
            "first_scenes": head,
            "last_scenes": tail,
            "note": "Middle scenes omitted from verifier prompt due to prompt size.",
        }, ensure_ascii=False)

    def _final_scene_summary(self, script_data: dict, max_scenes: int = 12) -> str:
        scenes = sorted(script_data.get("scenes") or [], key=lambda s: s.get("scene_number", 0))
        if not scenes:
            return "No final scenes available."
        if len(scenes) > max_scenes:
            selected = scenes[:3] + scenes[-(max_scenes - 3):]
        else:
            selected = scenes
        rows = [
            {
                "scene_number": s.get("scene_number"),
                "action_detail_vi": s.get("action_detail_vi"),
                "voice_over_en": s.get("voice_over_en"),
            }
            for s in selected
        ]
        return json.dumps(rows, ensure_ascii=False)[:6000]

    async def _phase25_semantic_verifier(
        self,
        suggestion: dict,
        style: str,
        model_name: str,
        script_data: dict,
        project_id: int,
        topic_type: str,
        scene_duration_sec: int,
    ) -> int:
        """Run advisory semantic verification and merge only contract-safe fixes."""
        if not script_data.get("scenes"):
            self._append_quality_warnings(script_data, ["Semantic verifier skipped: no scenes available."])
            script_data["_semantic_verifier_completed"] = True
            return 0

        level = script_data.get("reality_binding_level") or "soft"
        verifier_mode = "strict" if level == "strict" else "soft"
        drift_triggered = any(
            "central_contract_drift" in str(w)
            for w in script_data.get("quality_warnings") or []
        )
        prompt = SEMANTIC_VERIFIER_PROMPT.format(
            verifier_mode=verifier_mode,
            reality_binding_level=level,
            story_contract=self._story_contract_context(script_data),
            prompt_0=json.dumps(script_data.get("prompt_0") or {}, ensure_ascii=False)[:8000],
            continuity_evolution=json.dumps(script_data.get("continuity_evolution") or {}, ensure_ascii=False)[:4000],
            storyline=script_data.get("storyline_vi", ""),
            stages=script_data.get("stages_vi", ""),
            emotion_arc=json.dumps(script_data.get("emotion_arc") or [], ensure_ascii=False)[:12000],
            scenes=self._semantic_scene_payload(script_data, max_chars=12000 if drift_triggered else 24000, compact=drift_triggered),
        )

        edit_count = 0
        try:
            res_raw = await self._call_production_llm(
                prompt=prompt,
                model_name=model_name,
                generation_config={
                    "response_mime_type": "application/json",
                    "max_output_tokens": 8192,
                },
                phase="semantic_verifier",
            )
            res = self._parse_llm_json_object(res_raw)
            if not isinstance(res, dict):
                raise ValueError("semantic verifier returned non-object JSON")
        except Exception as e:
            logger.warning(f"Semantic verifier failed softly: {str(e)}")
            self._append_quality_warnings(script_data, [f"Semantic verifier failed softly: {str(e)}"])
            script_data["_semantic_verifier_completed"] = True
            return 0

        self._append_quality_warnings(script_data, res.get("quality_warnings") or [])
        fixes = res.get("scenes") or []
        if not isinstance(fixes, list):
            self._append_quality_warnings(script_data, ["Semantic verifier returned invalid scenes patch list."])
            fixes = []

        existing_nums = {
            s.get("scene_number")
            for s in script_data.get("scenes") or []
            if isinstance(s.get("scene_number"), int)
        }
        for patch_scene in fixes:
            if not isinstance(patch_scene, dict):
                self._append_quality_warnings(script_data, ["Semantic verifier returned a non-object scene patch."])
                continue
            scene_num = patch_scene.get("scene_number")
            if not isinstance(scene_num, int) or scene_num not in existing_nums:
                self._append_quality_warnings(script_data, [f"Semantic verifier ignored unknown scene patch: {scene_num}"])
                continue

            original = self._find_scene(script_data, scene_num) or {}
            candidate = json.loads(json.dumps(original, ensure_ascii=False))
            for key, value in patch_scene.items():
                if value is not None:
                    candidate[key] = value
            candidate["scene_number"] = scene_num
            candidate.setdefault("title", original.get("title"))
            candidate["_semantic_verified_edit"] = True

            patch_errors = self._validate_candidate_scenes(
                script_data,
                [candidate],
                scene_duration_sec,
                BASE_NEGATIVE_PROMPT,
            )
            if patch_errors:
                self._append_quality_warnings(
                    script_data,
                    [f"Scene {scene_num}: semantic verifier patch rejected: {'; '.join(patch_errors[:4])}"],
                )
                continue

            self._prepare_scene(candidate, scene_duration_sec, BASE_NEGATIVE_PROMPT, script_data)
            self._upsert_scene(script_data, candidate)
            edit_count += 1

        if edit_count:
            sync_emotion_arc_with_scenes(script_data)
            self._backfill_scene_level_fields(script_data)

        script_data["_semantic_verifier_completed"] = True
        self._save_script(project_id, suggestion.get("index", 0), script_data, "generating_script", topic_type)
        return edit_count

    # ─── PHASE 3: PACKAGING ───────────────────────────────────────────────────

    async def _phase3_packaging(
        self, suggestion, style, model_name, script_data, project_id, topic_type, aspect_ratio,
        context_from_previous=None,
    ):
        logger.info(f"Phase 3 (Packaging) for project {project_id}")
        yield f"data: {json.dumps({'status': 'generating', 'group': 'global', 'step': 'packaging'}, ensure_ascii=False)}\n\n"

        # Finalize continuity from prompt_0
        p0 = script_data.get("prompt_0", {})
        if p0.get("continuity_lock_en") and not script_data.get("continuity_prompt_en"):
            script_data["continuity_prompt_en"] = p0["continuity_lock_en"]
            script_data["continuity_board"]["continuity_prompt_en"] = p0["continuity_lock_en"]
        if p0.get("negative_constraints_en") and not script_data.get("global_negative_prompt_en"):
            script_data["global_negative_prompt_en"] = p0["negative_constraints_en"]

        self._backfill_scene_level_fields(script_data)

        # Series bridge
        script_data["series_bridge_vi"] = None
        if context_from_previous and "recent_episodes" in context_from_previous:
            recent_eps = context_from_previous["recent_episodes"]
            if recent_eps:
                last_ep = recent_eps[-1]
                summary = last_ep.get("summary") or {}
                cliffhanger = summary.get("cliffhanger")
                char_states = summary.get("character_states")
                ep_num = last_ep.get("episode_number")
                if cliffhanger:
                    script_data["series_bridge_vi"] = (
                        f"Tập {ep_num}: {char_states or 'nhân vật ở trạng thái bình thường'}. "
                        f"Kết thúc với: {cliffhanger}."
                    )

        # Character ref prompt (no LLM needed)
        chars = script_data.get("characters", [])
        all_chars_desc = "; ".join([
            f"{c.get('character_name', '')}: {c.get('description_en', '')}" for c in chars
        ]) if chars else "main characters"
        script_data["reference_images"]["character_ref_prompt_en"] = (
            f"Character sheet, multiple views, of {all_chars_desc}, "
            f"{style} style, consistent design, white background, {aspect_ratio}"
        )

        # Generate background + thumbnail via LLM
        story_overview = script_data.get("storyline_vi", "") or script_data.get("overview_analysis_vi", "")
        prompt_ref = REFERENCE_IMAGES_PROMPT.format(
            environment_prompt=script_data.get("environment_master_prompt_en", ""),
            style=style,
            aspect_ratio=aspect_ratio,
            story_overview=story_overview[:300],
            quality_warnings=json.dumps(script_data.get("quality_warnings", [])[:12], ensure_ascii=False),
            final_scene_summary=self._final_scene_summary(script_data),
        )

        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                res_raw = await self._call_production_llm(
                    prompt=prompt_ref,
                    model_name=model_name,
                    generation_config={"response_mime_type": "application/json"},
                    phase="packaging",
                )
                res = self._parse_llm_json_object(res_raw)
                refs = res.get("reference_images") if isinstance(res, dict) else None
                if not isinstance(refs, dict):
                    refs = res
                script_data["reference_images"]["background_ref_prompt_en"] = refs.get("background_ref_prompt_en", "")
                script_data["reference_images"]["thumbnail_ref_prompt_en"] = refs.get("thumbnail_ref_prompt_en", "")
                script_data["_packaging_uses_quality_context"] = True
                break
            except Exception as e:
                logger.warning(f"Packaging reference images attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_attempts - 1:
                    logger.error(f"Packaging reference images completely failed: {str(e)}")

        self._save_script(project_id, suggestion.get("index", 0), script_data, "generating_script", topic_type)
        await self._maybe_sleep(STREAM_DELAY)

    # ─── CODE CRITIQUE (NO LLM) ───────────────────────────────────────────────

    def _code_critique(self, script_data: dict, scene_duration_sec: int) -> list:
        """Code-only quality checks — no LLM call. Returns list of warnings."""
        warnings = []
        scenes = script_data.get("scenes", [])

        # 1. Anchor citation check
        for s in scenes:
            veo3 = s.get("veo3_prompt_en", "")
            if veo3 and not veo3.startswith("Reference the approved"):
                warnings.append(f"Scene {s.get('scene_number')}: missing Prompt 0 anchor citation")

        # 2. Semantic duplicate detection
        def overlap_ratio(a: str, b: str) -> float:
            wa = set(w for w in a.lower().split() if len(w) > 2)
            wb = set(w for w in b.lower().split() if len(w) > 2)
            if not wa or not wb:
                return 0.0
            return len(wa & wb) / min(len(wa), len(wb))

        def meaningful_token_count(value: str) -> int:
            normalized = re.sub(r"[^\w\sàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ-]", " ", value.lower())
            return len({w for w in normalized.split() if len(w) > 2 and not w.isdigit()})

        for i in range(len(scenes)):
            for j in range(i + 1, len(scenes)):
                ratio = overlap_ratio(
                    scenes[i].get("action_detail_vi", ""),
                    scenes[j].get("action_detail_vi", ""),
                )
                if ratio > 0.65:
                    warnings.append(
                        f"Potential duplicate: Scene {scenes[i].get('scene_number')} "
                        f"and Scene {scenes[j].get('scene_number')} (overlap={ratio:.2f})"
                    )
                    logger.warning(warnings[-1])
                if (
                    ratio > 0.88
                    and abs((scenes[j].get("scene_number") or j) - (scenes[i].get("scene_number") or i)) > 2
                    and min(
                        meaningful_token_count(scenes[i].get("action_detail_vi", "")),
                        meaningful_token_count(scenes[j].get("action_detail_vi", "")),
                    ) >= 10
                ):
                    warnings.append(
                        f"Hard duplicate: Scene {scenes[i].get('scene_number')} "
                        f"and Scene {scenes[j].get('scene_number')} repeat the same distant action (overlap={ratio:.2f})"
                    )
                    logger.warning(warnings[-1])

        if warnings:
            logger.info(f"Code critique: {len(warnings)} issues found.")

        # 3. Fix 7: scene_lead_character semantic check
        char_names = [c.get("character_name", "") for c in script_data.get("characters", [])]
        for s in scenes:
            char_warnings = validate_scene_lead_character(s, char_names)
            for w in char_warnings:
                warnings.append(w)
                logger.warning(f"[CharacterCheck] {w}")

        # 4. Fix 8: Blueprint metadata validation
        blueprint_warnings = validate_script_blueprint(script_data)
        for w in blueprint_warnings:
            warnings.append(w)
            logger.warning(f"[BlueprintCheck] {w}")

        # 5. Finalize: standardize titles and apply defaults
        script_data["scenes"] = standardize_scene_titles(scenes, scene_duration_sec)
        for s in script_data["scenes"]:
            ensure_scene_defaults(s, BASE_NEGATIVE_PROMPT)

        return warnings

    # ─── PHASE 4: FACT-CHECK (HISTORICAL) ────────────────────────────────────

    # Durable fact-check guard: verification patches are sparse and may use v3 field
    # names; normalize them back into the temporary v2 scene shape before merging.
    # Durable compatibility guard: legacy tests/caches may still send v2 field names,
    # so keep both aliases until the old contract is fully removed.
    # Durable patch-safety guard: correction patches are validated before merge,
    # while metadata-only verification notes can annotate the original scene safely.
    def _fact_check_patch_to_scene_update(self, patch: dict, original: dict | None = None) -> dict:
        scene_num = patch.get("scene_number")
        update = json.loads(json.dumps(original or {"scene_number": scene_num}, ensure_ascii=False))
        update["scene_number"] = scene_num
        if patch.get("action_vi") is not None:
            update["action_detail_vi"] = patch.get("action_vi")
        if patch.get("action_detail_vi") is not None:
            update["action_detail_vi"] = patch.get("action_detail_vi")
        if patch.get("veo_prompt_en") is not None:
            update["veo3_prompt_en"] = patch.get("veo_prompt_en")
        if patch.get("veo3_prompt_en") is not None:
            update["veo3_prompt_en"] = patch.get("veo3_prompt_en")
        if patch.get("voice_en") is not None:
            update["voice_over_en"] = patch.get("voice_en")
        if patch.get("voice_over_en") is not None:
            update["voice_over_en"] = patch.get("voice_over_en")
        if patch.get("voice_vi") is not None:
            update["voice_over_vi"] = patch.get("voice_vi")
        if patch.get("voice_over_vi") is not None:
            update["voice_over_vi"] = patch.get("voice_over_vi")
        if patch.get("scene_specific_negative_en") is not None:
            update["scene_specific_negative_en"] = patch.get("scene_specific_negative_en")
        if update.get("veo3_prompt_en") and not update.get("voice_over_en"):
            update["voice_over_en"] = extract_voice_from_prompt(update["veo3_prompt_en"])
        if patch.get("basis_vi") is not None:
            update["historical_basis_vi"] = patch.get("basis_vi")
        if patch.get("historical_basis_vi") is not None:
            update["historical_basis_vi"] = patch.get("historical_basis_vi")
        if patch.get("level") is not None:
            update["verifiability_level"] = patch.get("level")
        if patch.get("verifiability_level") is not None:
            update["verifiability_level"] = patch.get("verifiability_level")

        status = patch.get("status")
        risk_flags = patch.get("risk_flags") or []
        notes = patch.get("notes_vi")
        if notes is None and patch.get("fact_check_note_vi"):
            notes = [patch.get("fact_check_note_vi")]
        if isinstance(notes, str):
            notes = [notes]
        notes = [str(note) for note in (notes or []) if note]
        update["verification_status"] = status or ("needs_review" if risk_flags or notes else "checked")
        update["verification_risk_flags"] = risk_flags if isinstance(risk_flags, list) else [str(risk_flags)]
        update["verification_notes_vi"] = notes
        update["needs_fact_check"] = update["verification_status"] in ("needs_review", "corrected") or bool(update["verification_risk_flags"])
        update["fact_check_note_vi"] = "; ".join(notes) if notes else None
        if original:
            update.setdefault("action_detail_vi", original.get("action_detail_vi"))
            update.setdefault("veo3_prompt_en", original.get("veo3_prompt_en"))
            update.setdefault("voice_over_en", original.get("voice_over_en"))
            update.setdefault("voice_over_vi", original.get("voice_over_vi"))
            update.setdefault("scene_specific_negative_en", original.get("scene_specific_negative_en"))
        return update

    # Durable fact-check guard: only patches that rewrite scene payload need full
    # scene validation; metadata-only risk notes must not fail as incomplete scenes.
    def _fact_check_patch_rewrites_scene(self, patch: dict) -> bool:
        return any(
            patch.get(key) is not None
            for key in (
                "action_vi",
                "action_detail_vi",
                "veo_prompt_en",
                "veo3_prompt_en",
                "voice_en",
                "voice_over_en",
                "voice_vi",
                "voice_over_vi",
                "scene_specific_negative_en",
            )
        )

    # Durable fact-check guard: failed verification attempts become explicit
    # scene-level review status instead of falsely passing or killing a full chunk.
    def _fact_check_review_scene_update(self, scene: dict, reason: str) -> dict:
        update = json.loads(json.dumps(scene, ensure_ascii=False))
        notes = update.get("verification_notes_vi") or []
        if isinstance(notes, str):
            notes = [notes]
        notes = [str(note) for note in notes if note]
        if reason and reason not in notes:
            notes.append(reason)
        risk_flags = update.get("verification_risk_flags") or []
        if isinstance(risk_flags, str):
            risk_flags = [risk_flags]
        if "fact_check_patch_rejected" not in risk_flags:
            risk_flags.append("fact_check_patch_rejected")
        update["verification_status"] = "needs_review"
        update["verification_risk_flags"] = risk_flags
        update["verification_notes_vi"] = notes
        update["needs_fact_check"] = True
        update["fact_check_note_vi"] = "; ".join(notes) if notes else reason
        return update

    # Durable fact-check guard: chunk prompts must carry only chunk-local arc and
    # stage context so longform audits do not drift into scenes outside the batch.
    def _fact_check_chunk_payload(self, chunk: list[dict], script_data: dict) -> dict:
        chunk_nums = [s.get("scene_number") for s in chunk if isinstance(s.get("scene_number"), int)]
        allowed = sorted(chunk_nums)
        allowed_set = set(allowed)
        stage_ranges = [
            stage for stage in (script_data.get("story_spine") or {}).get("stage_ranges") or []
            if int(stage.get("scene_start") or 0) <= (allowed[-1] if allowed else 0)
            and int(stage.get("scene_end") or 0) >= (allowed[0] if allowed else 0)
        ]
        return {
            "topic_type": script_data.get("topic_type"),
            "overview_analysis_vi": script_data.get("overview_analysis_vi"),
            "characters": script_data.get("characters"),
            "environment_master_prompt_en": script_data.get("environment_master_prompt_en"),
            "emotion_arc": [
                entry for entry in script_data.get("emotion_arc") or []
                if entry.get("scene_number") in allowed_set
            ],
            "scene_number_allowed": allowed,
            "stage_ranges": stage_ranges,
            "scenes": chunk,
            "continuity_prompt_en": script_data.get("continuity_prompt_en"),
            "global_negative_prompt_en": script_data.get("global_negative_prompt_en"),
            "reference_images": script_data.get("reference_images"),
        }

    # Durable fact-check guard: chunk validation now blocks only malformed/unsafe patches,
    # not missing labels for unchanged scenes that the sparse protocol intentionally omits.
    # Durable longform recovery guard: bad fact-check patches are rejected at patch
    # granularity so a model response for scene 31 cannot fail chunk scenes 1-12.
    async def _fact_check_chunk(self, chunk, style, model_name, script_data, is_historical_or_scientific):
        chunk_nums = [s["scene_number"] for s in chunk]
        logger.info(f"Fact-checking scenes {chunk_nums}")

        full_script_data = self._fact_check_chunk_payload(chunk, script_data)

        prompt_fact_check = HISTORICAL_FACT_CHECK_PROMPT.format(
            script_json=json.dumps(full_script_data, ensure_ascii=False)
        ) + (
            "\n\nAllowed scene_number values for this chunk: "
            f"{full_script_data.get('scene_number_allowed')}. "
            "Ignore and omit any patch outside this list; the backend will reject it."
        )

        anchor = {"continuity_prompt_en": script_data.get("continuity_board", {}).get("continuity_prompt_en", "")}

        retry_count = 0
        max_retries = 1
        current_prompt = prompt_fact_check

        while retry_count <= max_retries:
            try:
                res_raw = await self._call_production_llm(
                    prompt=current_prompt,
                    model_name=model_name,
                    generation_config={
                        "response_mime_type": "application/json",
                        "max_output_tokens": 8192,
                    },
                    phase="fact_check",
                    scene_range=(chunk_nums[0], chunk_nums[-1]) if chunk_nums else None,
                )
                fact_check_data = self._parse_llm_json_object(res_raw)

                ref_imgs = {}
                if "reference_images" in fact_check_data and isinstance(fact_check_data["reference_images"], dict):
                    for k, v in fact_check_data["reference_images"].items():
                        if v and v not in ("Unchanged", "unchanged"):
                            ref_imgs[k] = v

                raw_patches = fact_check_data.get("verification_patches")
                if raw_patches is None:
                    raw_patches = fact_check_data.get("scenes", [])
                if not isinstance(raw_patches, list):
                    raw_patches = []
                logger.info(f"Fact-check {chunk_nums}: {len(raw_patches)} verification patches returned.")

                retry_errors = []
                warnings = []
                modified_scenes = []
                originals = {s.get("scene_number"): s for s in chunk}
                invalid_review_updates = {}
                for raw_patch in raw_patches:
                    if not isinstance(raw_patch, dict):
                        warnings.append("fact_check_malformed_patch: non-object patch ignored")
                        continue
                    scene_num = raw_patch.get("scene_number", "unknown")
                    if scene_num not in originals:
                        warnings.append(f"fact_check_unknown_scene_patch: scene {scene_num} ignored for chunk {chunk_nums}")
                        continue
                    s_raw = self._fact_check_patch_to_scene_update(raw_patch, originals.get(scene_num))
                    ensure_scene_defaults(s_raw, BASE_NEGATIVE_PROMPT)
                    if not s_raw.get("scene_specific_negative_en"):
                        s_raw["scene_specific_negative_en"] = scene_specific_negative_from_constraints(script_data, s_raw)
                    s_errors = (
                        retryable_messages(
                            validate_scene_issues(normalize_scene(s_raw), anchor, scene_num if isinstance(scene_num, int) else None)
                        )
                        if self._fact_check_patch_rewrites_scene(raw_patch)
                        else []
                    )
                    for err in s_errors:
                        retry_errors.append(f"Scene {scene_num}: {err}")
                    if s_errors:
                        invalid_review_updates[scene_num] = self._fact_check_review_scene_update(
                            originals[scene_num],
                            f"Fact-check correction rejected: {'; '.join(s_errors[:3])}",
                        )
                        continue
                    modified_scenes.append(s_raw)

                if retry_errors:
                    logger.warning(f"Fact-check validation errors (attempt {retry_count}): {retry_errors}")
                    if retry_count < max_retries:
                        retry_count += 1
                        error_context = "\n\n=== VALIDATION ERRORS FROM PREVIOUS ATTEMPT ===\n"
                        error_context += "\n".join(f"- {e}" for e in retry_errors)
                        error_context += "\n=== FIX ALL ERRORS ABOVE. RETURN ONLY VALID PATCHES FOR SCENES THAT NEED THEM. ===\n"
                        current_prompt = prompt_fact_check + error_context
                        continue
                    else:
                        logger.warning(f"Fact-check correction patches rejected after max retries for {chunk_nums}")
                        modified_scenes.extend(invalid_review_updates.values())

                if warnings:
                    ref_imgs["_fact_check_warnings"] = warnings
                return modified_scenes, ref_imgs
            except Exception as err:
                logger.error(f"Fact-check API error for {chunk_nums} (attempt {retry_count}): {str(err)}")
                review_updates = [
                    self._fact_check_review_scene_update(
                        scene,
                        f"Fact-check API failed for chunk {chunk_nums}: {str(err)}",
                    )
                    for scene in chunk
                ]
                return review_updates, {
                    "_fact_check_warning": f"Fact-check API failed for scenes {chunk_nums}: {str(err)}",
                }

        review_updates = [
            self._fact_check_review_scene_update(
                scene,
                f"Fact-check did not complete for chunk {chunk_nums}",
            )
            for scene in chunk
        ]
        return review_updates, {
            "_fact_check_warning": f"Fact-check did not complete for scenes {chunk_nums}",
        }

    # Durable fact-check guard: Phase 4 applies sparse verification patches and
    # records warnings for failed chunks instead of rolling back on missing labels.
    # Durable strict-verification guard: malformed chunks now fail historical runs
    # cleanly so `_fact_check_completed` cannot mean "partly unchecked".
    # Durable longform recovery guard: patch-level rejection keeps safe baseline
    # scenes while final code gates still block truly invalid merged output.
    async def _phase4_fact_check(
        self, style, model_name, script_data, project_id, topic_type, scene_duration_sec, suggestion_idx: int = 0
    ):
        logger.info(f"Phase 4 (Fact-Check) for project {project_id}")
        yield f"data: {json.dumps({'status': 'generating', 'group': 'global', 'step': 'fact_check'}, ensure_ascii=False)}\n\n"
        await self._maybe_sleep(STREAM_DELAY)

        scenes = script_data.get("scenes", [])
        if not scenes:
            return

        chunk_size = 12
        chunks = [scenes[i:i + chunk_size] for i in range(0, len(scenes), chunk_size)]
        backup = json.loads(json.dumps({
            "scenes": script_data.get("scenes", []),
            "emotion_arc": script_data.get("emotion_arc", []),
            "reference_images": script_data.get("reference_images", {}),
            "_fact_check_completed": script_data.get("_fact_check_completed", False),
        }, ensure_ascii=False))

        tasks = [
            self._fact_check_chunk(
                chunk, style, model_name, script_data,
                (topic_type in ["historical", "scientific"])
            )
            for chunk in chunks
        ]
        results = await asyncio.gather(*tasks)

        for modified_scenes, ref_imgs in results:
            ref_imgs = dict(ref_imgs or {})
            warning = ref_imgs.pop("_fact_check_warning", None)
            warnings = ref_imgs.pop("_fact_check_warnings", [])
            if warning:
                self._append_quality_warnings(script_data, [warning])
            if isinstance(warnings, list) and warnings:
                self._append_quality_warnings(script_data, [str(w) for w in warnings if w])
            if ref_imgs:
                for k, v in ref_imgs.items():
                    script_data["reference_images"][k] = v
            if modified_scenes:
                script_data["scenes"] = merge_scenes_data(script_data["scenes"], modified_scenes)
                sync_emotion_arc_with_scenes(script_data)

        # Fact-check sparse patches intentionally omit accurate scenes; mark those
        # as checked without inventing basis/level values that the model did not supply.
        for scene in script_data.get("scenes") or []:
            scene.setdefault("verification_status", "checked")
            scene.setdefault("verification_risk_flags", [])
            scene.setdefault("verification_notes_vi", [])
        script_data["_fact_check_completed"] = True

        script_data["scenes"] = standardize_scene_titles(script_data["scenes"], scene_duration_sec)
        for s in script_data["scenes"]:
            ensure_scene_defaults(s, BASE_NEGATIVE_PROMPT)
        self._backfill_scene_level_fields(script_data)
        # Durable final-gate guard: direct Phase 4 callers and the orchestrator
        # must both reject merged scenes that still break measurable scene rules.
        post_merge_errors = (
            validate_script(normalize_script(script_data))
            + blocking_messages(validate_scene_generation_issues(script_data))
            + validate_historical_coverage(script_data)
        )
        anchor = {"continuity_prompt_en": script_data.get("continuity_prompt_en", "")}
        for s in script_data.get("scenes", []):
            s_errors = retryable_messages(
                validate_scene_issues(normalize_scene(s), anchor, s.get("scene_number"))
            )
            for e in s_errors:
                post_merge_errors.append(f"Scene {s.get('scene_number', 'unknown')}: {e}")
        if post_merge_errors:
            script_data["scenes"] = backup["scenes"]
            script_data["emotion_arc"] = backup["emotion_arc"]
            script_data["reference_images"] = backup["reference_images"]
            script_data["_fact_check_completed"] = False
            self._save_script(project_id, suggestion_idx, script_data, "generating_script", topic_type)
            short = "; ".join(post_merge_errors[:8])
            raise RuntimeError(f"Phase 4 fact_check hard gate failed: Fact-check merge validation failed: {short}")

        for s in script_data["scenes"]:
            yield f"data: {json.dumps({'status': 'scene', 'data': s}, ensure_ascii=False)}\n\n"
            await self._maybe_sleep(STREAM_DELAY)
        self._save_script(project_id, suggestion_idx, script_data, "generating_script", topic_type)

    def _split_into_chunks(self, total_scenes: int, chunk_size: int = 15) -> list[tuple[int, int]]:
        chunks = []
        for i in range(1, total_scenes + 1, chunk_size):
            end = min(i + chunk_size - 1, total_scenes)
            chunks.append((i, end))
        return chunks

    def _get_cached_scene(self, i: int, script_data: dict, style: str) -> dict | None:
        if not getattr(self, "cached_script_data", None):
            return None

        cached = self.cached_script_data

        # 1. Verify general metadata
        if cached.get("environment_master_prompt_en") != script_data.get("environment_master_prompt_en"):
            return None

        cached_chars = {c.get("character_name"): c.get("key_identifiers_en") for c in cached.get("characters", [])}
        new_chars = {c.get("character_name"): c.get("key_identifiers_en") for c in script_data.get("characters", [])}
        if cached_chars != new_chars:
            return None

        # 2. Verify emotion arc entry for scene i
        if not cached.get("emotion_arc") or len(cached["emotion_arc"]) < i:
            return None
        if not script_data.get("emotion_arc") or len(script_data["emotion_arc"]) < i:
            return None

        cached_arc = cached["emotion_arc"][i-1]
        new_arc = script_data["emotion_arc"][i-1]

        keys_to_compare = [
            "beat_summary",
            "emotion_label",
            "physical_state_end",
            "camera_complexity",
            "scene_lead_character",
        ]
        for k in keys_to_compare:
            if cached_arc.get(k) != new_arc.get(k):
                return None

        # 3. Find the scene in cached["scenes"]
        for scene in cached.get("scenes", []):
            if scene.get("scene_number") == i:
                prompt_en = scene.get("veo3_prompt_en", "")
                if style.lower() not in prompt_en.lower():
                    return None
                if not prompt_en.startswith("Reference the approved"):
                    return None
                generation_failed = scene.get("generation_failed")
                if generation_failed is True or str(generation_failed).lower() == "true":
                    return None
                if not scene.get("voice_over_en") and not scene.get("voice_over_vi") and not extract_voice_from_prompt(prompt_en):
                    return None
                ensure_scene_defaults(scene, BASE_NEGATIVE_PROMPT)
                if not scene.get("scene_specific_negative_en"):
                    scene["scene_specific_negative_en"] = scene_specific_negative_from_constraints(script_data, scene)
                anchor = {"continuity_prompt_en": script_data.get("continuity_prompt_en", "")}
                if retryable_messages(validate_scene_issues(normalize_scene(scene), anchor, scene.get("scene_number"))):
                    return None
                return scene

        return None
