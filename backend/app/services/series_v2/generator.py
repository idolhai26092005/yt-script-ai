import asyncio
import json
import logging
import os
import time
from typing import Any, AsyncGenerator, Callable

from sqlalchemy.orm import Session

from app.deps import increment_quota_after_success
from app.models.api_key import APIKey
from app.models.series_v2 import SeriesEpisodeV2, SeriesV2
from app.schemas.series_v2 import EpisodeBriefUpdate, SeriesV2Create
from app.services.gemini.base import BaseGeminiService
from app.services.production.support.scene_merge import prepare_scene, upsert_scene
from app.services.production.support.sse import sse_event
from app.services.series_v2.contracts import (
    PHASE_CONTINUITY,
    PHASE_FACT_CHECK,
    PHASE_FINAL,
    PHASE_PLANNING,
    PHASE_REVIEW,
    PHASE_SCENES,
    SCENE_BATCH_SIZE,
    SCHEMA_VERSION,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_GENERATING,
    STATUS_NEEDS_REVIEW,
    STATUS_PENDING,
)
from app.services.series_v2.prompts import (
    build_continuity_review_prompt,
    build_episode_plan_prompt,
    build_fact_verification_prompt,
    build_packaging_prompt,
    build_scene_batch_prompt,
    build_setup_prompt,
)
from app.services.series_v2.repository import SeriesV2Repository
from app.services.series_v2.state import build_episode_brief, build_script_output, phase_log_entry
from app.services.series_v2.validators import (
    apply_scene_patches,
    is_strict_topic,
    parse_json_object,
    review_needs_retry,
    validate_continuity_delta,
    validate_episode_plan,
    validate_fact_report,
    validate_packaging,
    validate_review_report,
    validate_scene_batch,
    validate_setup_artifacts,
)

BASE_SERIES_NEGATIVE_PROMPT = "low quality, blurry, distorted face, watermark, text overlay"
logger = logging.getLogger("uvicorn.error")


# Series generator guard: the v2 flow subclasses only the shared Gemini transport
# layer and keeps orchestration separate from the single-video facade.
class SeriesV2Generator(BaseGeminiService):
    """Independent series v2 generation service."""

    # Dependency guard: constructor receives only shared transport/database inputs
    # and builds the v2 repository locally to keep endpoint wiring thin.
    def __init__(
        self,
        *,
        api_key: str,
        db: Session,
        api_key_id: int,
        groq_api_key: str | None = None,
        llm_timeout_sec: float = 180.0,
        max_phase_attempts: int = 2,
    ):
        super().__init__(api_key=api_key, groq_api_key=groq_api_key, db=db, api_key_id=api_key_id)
        self.repo = SeriesV2Repository(db)
        self.llm_timeout_sec = llm_timeout_sec
        self.max_phase_attempts = max_phase_attempts

    # Transport guard: all series LLM calls use shared retry/fallback plus a
    # bounded timeout so a stuck provider cannot hold an SSE request forever.
    async def _call_series_llm(self, *, prompt: str, model_name: str, phase: str) -> str:
        started_at = time.time()
        try:
            return await asyncio.wait_for(
                self._call_gemini_with_retry(
                    prompt=prompt,
                    model_name=model_name,
                    generation_config={"response_mime_type": "application/json"},
                ),
                timeout=self.llm_timeout_sec,
            )
        except asyncio.TimeoutError as err:
            elapsed_ms = (time.time() - started_at) * 1000.0
            raise TimeoutError(f"Series v2 LLM timeout during {phase} after {elapsed_ms:.1f}ms") from err

    # Retry guard: every LLM phase gets one targeted repair attempt with exact
    # structural feedback before failing as a structured technical error.
    async def _run_json_phase(
        self,
        *,
        phase: str,
        model_name: str,
        prompt_builder: Callable[[list[str] | None], str],
        validator: Callable[[dict[str, Any]], list[str]],
    ) -> dict[str, Any]:
        feedback: list[str] | None = None
        last_errors: list[str] = []
        for _ in range(self.max_phase_attempts):
            prompt = prompt_builder(feedback)
            raw_text = await self._call_series_llm(prompt=prompt, model_name=model_name, phase=phase)
            try:
                data = parse_json_object(raw_text)
            except Exception as exc:
                last_errors = [str(exc)]
                feedback = last_errors
                continue
            errors = validator(data)
            if not errors:
                return data
            last_errors = errors
            feedback = errors
        raise ValueError(f"{phase}_validation_failed: {'; '.join(last_errors)}")

    # Setup guard: series creation stores only model-produced bible/map artifacts
    # after validating exact episode slot count.
    async def create_series(self, series_in: SeriesV2Create) -> SeriesV2:
        started_at = time.time()
        data = await self._run_json_phase(
            phase="series_setup",
            model_name=series_in.model_name,
            prompt_builder=lambda feedback: build_setup_prompt(series_in, feedback),
            validator=lambda output: validate_setup_artifacts(output, series_in.target_episode_count),
        )
        series = self.repo.create_series(
            series_in,
            self.api_key_id,
            reality_binding_level=str(data.get("reality_binding_level") or "soft"),
            series_bible=data["series_bible"],
            season_map=data["season_map"],
        )
        first_episode = self.repo.get_episode_by_number(series.id, 1)
        if first_episode:
            self.repo.append_phase_log(
                first_episode,
                phase_log_entry(
                    "series_setup",
                    artifact_keys=["series_bible", "season_map"],
                    started_at=started_at,
                ),
            )
            self._save_debug_snapshot(
                series=series,
                episode=first_episode,
                phase_num=0,
                phase_name="series_setup",
                artifact={"series_bible": series.series_bible, "season_map": series.season_map},
            )
        return series

    # Brief guard: editable episode briefs are deterministic and cost no LLM call,
    # preserving user control before generation begins.
    def get_or_create_brief(
        self,
        series: SeriesV2,
        episode_number: int,
        user_revision: dict[str, Any] | None = None,
    ) -> SeriesEpisodeV2:
        if episode_number < 1 or episode_number > series.target_episode_count:
            raise ValueError("episode_number_out_of_range")
        episode = self.repo.get_episode_by_number(series.id, episode_number)
        if not episode:
            episode = self.repo.create_episode_shell(series, episode_number)
            self.db.commit()
            self.db.refresh(episode)
        prior = self.repo.get_episode_by_number(series.id, episode_number - 1) if episode_number > 1 else None
        merged_revision = user_revision or episode.user_revision or None
        brief = build_episode_brief(
            series_bible=series.series_bible,
            season_map=series.season_map,
            episode_number=episode_number,
            default_scene_count=series.default_scene_count,
            target_episode_count=series.target_episode_count,
            prior_delta=prior.continuity_delta if prior else None,
            user_revision=merged_revision,
        )
        updated = self.repo.update_episode(
            episode,
            title=brief["title"],
            brief=brief,
            user_revision=merged_revision,
            scene_count=int(brief["scene_count"]),
            ending_mode=brief["ending_mode"],
            phase_log=[*(episode.phase_log or []), phase_log_entry("episode_brief", artifact_keys=["brief"], cache_hit=True)],
        )
        self._save_debug_snapshot(
            series=series,
            episode=updated,
            phase_num=1,
            phase_name="episode_brief",
            artifact=brief,
        )
        return updated

    # Brief update guard: only editable fields enter generation state, avoiding
    # hidden prompt overrides from legacy suggestion payloads.
    def update_brief(self, series: SeriesV2, episode_number: int, revision: EpisodeBriefUpdate) -> SeriesEpisodeV2:
        revision_data = revision.model_dump(exclude_none=True)
        return self.get_or_create_brief(series, episode_number, revision_data)

    # Streaming guard: structured SSE events expose phase progress without
    # leaking provider prompts or raw response text.
    def _event(self, status: str, *, phase: str | None = None, data: Any = None, message: str | None = None) -> str:
        return sse_event({
            "schema_version": SCHEMA_VERSION,
            "status": status,
            "phase": phase,
            "data": data,
            "message": message,
        })

    # Continuity guard: non-final episode deltas are derived from reviewer
    # artifact plus the last saved scene, keeping the next episode start explicit.
    def _build_continuity_delta(
        self,
        *,
        episode: SeriesEpisodeV2,
        review_report: dict[str, Any],
        is_final_episode: bool,
    ) -> dict[str, Any]:
        scenes = episode.scenes or []
        last_scene = scenes[-1] if scenes else {}
        brief = episode.brief or {}
        delta = {
            "last_physical_state": last_scene.get("handoff_state") or last_scene.get("action_detail_vi") or "",
            "open_threads": list(review_report.get("open_threads") or brief.get("must_include") or []),
            "new_constraints": list(review_report.get("new_constraints") or []),
            "next_start_state": review_report.get("next_start_state") or brief.get("slot", {}).get("intended_next_start_state") or "",
            "handoff_strength": review_report.get("handoff_strength") or "medium",
            "cliffhanger_fact": review_report.get("cliffhanger_fact") or brief.get("slot", {}).get("required_unresolved_thread") or "",
        }
        if is_final_episode:
            delta["next_start_state"] = delta.get("next_start_state") or "season_complete"
        return delta

    # Scene normalization guard: generated aliases are converted before storage
    # and scene titles/timing remain stable for downstream render tooling.
    def _normalize_scene(self, scene: dict[str, Any], scene_duration_sec: int) -> dict[str, Any]:
        normalized = dict(scene)
        temp_script = {"scenes": [], "global_negative_prompt_en": BASE_SERIES_NEGATIVE_PROMPT}
        prepare_scene(normalized, scene_duration_sec, BASE_SERIES_NEGATIVE_PROMPT, temp_script)
        return normalized

    # Quota guard: user API quota increments once after a successful episode
    # generation stream, while model usage remains tracked per provider call.
    def _increment_success_quota(self) -> None:
        api_key = self.db.query(APIKey).filter(APIKey.id == self.api_key_id).first()
        if api_key:
            increment_quota_after_success(self.db, api_key)

    # Snapshot guard: mirror single-video debug snapshots for series phases so
    # sqlite/test runs leave inspectable files without adding storage tables.
    # Dev-only gate guard: series snapshots now require an explicit debug flag
    # and non-production ENV so sqlite deployments never write local artifacts.
    def _debug_snapshots_allowed(self) -> bool:
        try:
            from app.core.config import settings

            env_clean = settings.ENV.strip('\'"').strip().lower()
            return env_clean != "production" and bool(settings.DEBUG_SNAPSHOTS)
        except Exception:
            return False

    # Snapshot artifact guard: files contain parsed phase artifacts only, not
    # prompts or raw provider output, so local debugging avoids secret leakage.
    def _save_debug_snapshot(
        self,
        *,
        series: SeriesV2,
        episode: SeriesEpisodeV2,
        phase_num: int,
        phase_name: str,
        artifact: dict[str, Any] | list[Any],
    ) -> None:
        try:
            if not self._debug_snapshots_allowed():
                return

            snapshot_dir = os.path.join(os.getcwd(), "debug_snapshots")
            os.makedirs(snapshot_dir, exist_ok=True)
            filename = f"series_{series.id}_episode_{episode.episode_number}_phase_{phase_num}_{phase_name}.json"
            filepath = os.path.join(snapshot_dir, filename)
            snapshot_data = {
                "schema_version": SCHEMA_VERSION,
                "series_id": series.id,
                "episode_number": episode.episode_number,
                "phase": phase_name,
                "artifact": artifact,
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(snapshot_data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error("Failed to save series v2 debug snapshot: %s", str(exc))

    # Episode flow guard: generation runs plan -> scene batches -> optional
    # verifier/reviewer -> continuity -> final persistence with checkpoints.
    async def generate_episode_stream(
        self,
        *,
        series: SeriesV2,
        episode: SeriesEpisodeV2,
        model_name: str,
        run_reviewer: bool = True,
        run_packaging: bool = False,
        restart: bool = False,
    ) -> AsyncGenerator[str, None]:
        current_phase = PHASE_PLANNING
        try:
            episode = self.get_or_create_brief(series, episode.episode_number, episode.user_revision)
            if restart:
                episode = self.repo.reset_episode_artifacts(episode)
            episode = self.repo.update_episode(episode, status=STATUS_GENERATING)
            yield self._event("generating", phase=PHASE_PLANNING, message="Planning episode")

            scene_count = int(episode.scene_count)
            slot = (episode.brief or {}).get("slot") or {}
            prior_deltas = [
                ep.continuity_delta for ep in self.repo.list_episodes(series.id)
                if ep.episode_number < episode.episode_number and ep.continuity_delta
            ][-3:]
            plan_cache_errors = validate_episode_plan(
                {"episode_blueprint": episode.episode_blueprint, "emotion_arc": episode.emotion_arc},
                scene_count,
            )
            if not restart and not plan_cache_errors:
                yield self._event("generating", phase=PHASE_PLANNING, message="Using saved episode plan")
                self.repo.append_phase_log(
                    episode,
                    phase_log_entry(PHASE_PLANNING, artifact_keys=["episode_blueprint", "emotion_arc"], cache_hit=True),
                )
            else:
                started_at = time.time()
                plan_data = await self._run_json_phase(
                    phase=PHASE_PLANNING,
                    model_name=model_name,
                    prompt_builder=lambda feedback: build_episode_plan_prompt(
                        series_bible=series.series_bible or {},
                        season_slot=slot,
                        brief=episode.brief or {},
                        prior_deltas=prior_deltas,
                        scene_count=scene_count,
                        feedback=feedback,
                    ),
                    validator=lambda output: validate_episode_plan(output, scene_count),
                )
                episode = self.repo.update_episode(
                    episode,
                    episode_blueprint=plan_data["episode_blueprint"],
                    emotion_arc=plan_data["emotion_arc"],
                )
                self.repo.append_phase_log(
                    episode,
                    phase_log_entry(PHASE_PLANNING, artifact_keys=["episode_blueprint", "emotion_arc"], started_at=started_at),
                )
                self._save_debug_snapshot(
                    series=series,
                    episode=episode,
                    phase_num=2,
                    phase_name="episode_planning",
                    artifact={"episode_blueprint": episode.episode_blueprint, "emotion_arc": episode.emotion_arc},
                )

            script_data = {"scenes": list(episode.scenes or []), "global_negative_prompt_en": BASE_SERIES_NEGATIVE_PROMPT}
            for batch_start in range(1, scene_count + 1, SCENE_BATCH_SIZE):
                current_phase = PHASE_SCENES
                batch_end = min(batch_start + SCENE_BATCH_SIZE - 1, scene_count)
                saved_span = [
                    scene for scene in script_data["scenes"]
                    if batch_start <= int(scene.get("scene_number", 0)) <= batch_end
                ]
                scene_cache_errors = validate_scene_batch({"scenes": saved_span}, batch_start, batch_end)
                if not restart and not scene_cache_errors:
                    for saved_scene in saved_span:
                        yield self._event("scene", phase=PHASE_SCENES, data=saved_scene)
                    self.repo.append_phase_log(
                        episode,
                        phase_log_entry(PHASE_SCENES, artifact_keys=[f"scenes_{batch_start}_{batch_end}"], cache_hit=True),
                    )
                    continue

                yield self._event("generating", phase=PHASE_SCENES, message=f"Generating scenes {batch_start}-{batch_end}")
                batch_arc = [
                    beat for beat in (episode.emotion_arc or [])
                    if batch_start <= int(beat.get("scene_number", 0)) <= batch_end
                ]
                previous_scene = max(
                    [scene for scene in script_data["scenes"] if int(scene.get("scene_number", 0)) < batch_start],
                    key=lambda scene: int(scene.get("scene_number", 0)),
                    default=None,
                )
                previous_handoff = (previous_scene or {}).get("handoff_state") or ""
                started_at = time.time()
                scene_data = await self._run_json_phase(
                    phase=PHASE_SCENES,
                    model_name=model_name,
                    prompt_builder=lambda feedback, bs=batch_start, be=batch_end, arc=batch_arc, handoff=previous_handoff: build_scene_batch_prompt(
                        series_bible=series.series_bible or {},
                        episode_blueprint=episode.episode_blueprint or {},
                        emotion_arc=arc,
                        brief=episode.brief or {},
                        previous_handoff=handoff,
                        batch_start=bs,
                        batch_end=be,
                        feedback=feedback,
                    ),
                    validator=lambda output, bs=batch_start, be=batch_end: validate_scene_batch(output, bs, be),
                )
                for raw_scene in scene_data["scenes"]:
                    scene = self._normalize_scene(raw_scene, series.scene_duration_sec)
                    upsert_scene(script_data, scene)
                    yield self._event("scene", phase=PHASE_SCENES, data=scene)
                episode = self.repo.update_episode(episode, scenes=script_data["scenes"])
                self.repo.append_phase_log(
                    episode,
                    phase_log_entry(PHASE_SCENES, artifact_keys=[f"scenes_{batch_start}_{batch_end}"], started_at=started_at),
                )
                self._save_debug_snapshot(
                    series=series,
                    episode=episode,
                    phase_num=3,
                    phase_name=f"scenes_{batch_start}_{batch_end}",
                    artifact=script_data["scenes"],
                )

            if is_strict_topic(series.topic_type):
                current_phase = PHASE_FACT_CHECK
                yield self._event("generating", phase=PHASE_FACT_CHECK, message="Verifying strict-topic facts")
                started_at = time.time()
                fact_data = await self._run_json_phase(
                    phase=PHASE_FACT_CHECK,
                    model_name=model_name,
                    prompt_builder=lambda feedback: build_fact_verification_prompt(
                        series_bible=series.series_bible or {},
                        scenes=script_data["scenes"],
                        feedback=feedback,
                    ),
                    validator=validate_fact_report,
                )
                patched_scenes = apply_scene_patches(script_data["scenes"], fact_data.get("patches") or [])
                if validate_scene_batch({"scenes": patched_scenes}, 1, scene_count):
                    raise ValueError("fact_patch_invalidated_scene_contract")
                script_data["scenes"] = [
                    self._normalize_scene(scene, series.scene_duration_sec) for scene in patched_scenes
                ]
                episode = self.repo.update_episode(episode, scenes=script_data["scenes"])
                self.repo.append_phase_log(
                    episode,
                    phase_log_entry(PHASE_FACT_CHECK, artifact_keys=["patches", "warnings"], warnings=fact_data.get("warnings") or [], started_at=started_at),
                )
                self._save_debug_snapshot(
                    series=series,
                    episode=episode,
                    phase_num=4,
                    phase_name="fact_check",
                    artifact={"patches": fact_data.get("patches") or [], "warnings": fact_data.get("warnings") or []},
                )

            is_final_episode = episode.episode_number >= series.target_episode_count
            review_report: dict[str, Any] = {
                "schema_version": SCHEMA_VERSION,
                "handoff_strength": "strong" if is_final_episode else "medium",
                "open_threads": [] if is_final_episode else [slot.get("required_unresolved_thread") or (episode.brief or {}).get("premise") or "next episode continuation"],
                "next_start_state": "season_complete" if is_final_episode else slot.get("intended_next_start_state") or "",
                "review_notes": [],
                "too_closed": False,
                "season_alignment": "medium",
            }
            if run_reviewer or not is_final_episode:
                current_phase = PHASE_REVIEW
                review_cache_errors = validate_review_report(episode.review_report or {}, is_final_episode)
                if not restart and not review_cache_errors:
                    review_report = episode.review_report or review_report
                    yield self._event("review", phase=PHASE_REVIEW, message="Using saved continuity review")
                    self.repo.append_phase_log(
                        episode,
                        phase_log_entry(PHASE_REVIEW, artifact_keys=["review_report"], cache_hit=True),
                    )
                else:
                    yield self._event("review", phase=PHASE_REVIEW, message="Reviewing continuity")
                    started_at = time.time()
                    review_data = await self._run_json_phase(
                        phase=PHASE_REVIEW,
                        model_name=model_name,
                        prompt_builder=lambda feedback: build_continuity_review_prompt(
                            series_bible=series.series_bible or {},
                            season_slot=slot,
                            brief=episode.brief or {},
                            scenes=script_data["scenes"],
                            is_final_episode=is_final_episode,
                            feedback=feedback,
                        ),
                        validator=lambda output: validate_review_report(output, is_final_episode),
                    )
                    if review_needs_retry(review_data, is_final_episode):
                        review_data = await self._run_json_phase(
                            phase=PHASE_REVIEW,
                            model_name=model_name,
                            prompt_builder=lambda feedback: build_continuity_review_prompt(
                                series_bible=series.series_bible or {},
                                season_slot=slot,
                                brief=episode.brief or {},
                                scenes=script_data["scenes"],
                                is_final_episode=is_final_episode,
                                feedback=feedback or ["handoff_is_weak_or_too_closed"],
                            ),
                            validator=lambda output: validate_review_report(output, is_final_episode),
                        )
                    review_report = review_data
                    episode = self.repo.update_episode(episode, review_report=review_report)
                    self.repo.append_phase_log(
                        episode,
                        phase_log_entry(PHASE_REVIEW, artifact_keys=["review_report"], warnings=review_report.get("review_notes") or [], started_at=started_at),
                    )
                    self._save_debug_snapshot(
                        series=series,
                        episode=episode,
                        phase_num=5,
                        phase_name="continuity_review",
                        artifact=review_report,
                    )

            current_phase = PHASE_CONTINUITY
            saved_continuity = episode.continuity_delta or {}
            continuity_errors = validate_continuity_delta(saved_continuity, is_final_episode)
            if not restart and not continuity_errors:
                continuity_delta = saved_continuity
                self.repo.append_phase_log(
                    episode,
                    phase_log_entry(PHASE_CONTINUITY, artifact_keys=["continuity_delta"], cache_hit=True),
                )
            else:
                continuity_delta = self._build_continuity_delta(
                    episode=episode,
                    review_report=review_report,
                    is_final_episode=is_final_episode,
                )
                continuity_errors = validate_continuity_delta(continuity_delta, is_final_episode)
                if continuity_errors:
                    raise ValueError(f"continuity_delta_invalid: {'; '.join(continuity_errors)}")
                episode = self.repo.update_episode(episode, continuity_delta=continuity_delta)
                self.repo.append_phase_log(
                    episode,
                    phase_log_entry(PHASE_CONTINUITY, artifact_keys=["continuity_delta"]),
                )
                self._save_debug_snapshot(
                    series=series,
                    episode=episode,
                    phase_num=6,
                    phase_name="continuity_delta",
                    artifact=continuity_delta,
                )

            current_phase = PHASE_FINAL
            script_output = build_script_output(episode)
            if run_packaging:
                package_data = await self._run_json_phase(
                    phase="packaging",
                    model_name=model_name,
                    prompt_builder=lambda feedback: build_packaging_prompt(script_output=script_output, feedback=feedback),
                    validator=validate_packaging,
                )
                script_output["packaging"] = package_data
                self._save_debug_snapshot(
                    series=series,
                    episode=episode,
                    phase_num=7,
                    phase_name="packaging",
                    artifact=package_data,
                )
            final_status = STATUS_NEEDS_REVIEW if review_needs_retry(review_report, is_final_episode) else STATUS_COMPLETED
            episode = self.repo.update_episode(
                episode,
                script_output=script_output,
                status=final_status,
            )
            self.repo.append_phase_log(
                episode,
                phase_log_entry(PHASE_FINAL, artifact_keys=["script_output", "status"]),
            )
            self._save_debug_snapshot(
                series=series,
                episode=episode,
                phase_num=8,
                phase_name="final_script",
                artifact=script_output,
            )
            if final_status == STATUS_COMPLETED and episode.episode_number < series.target_episode_count:
                next_episode = self.repo.get_episode_by_number(series.id, episode.episode_number + 1)
                if not next_episode:
                    self.repo.create_episode_shell(series, episode.episode_number + 1)
                    self.db.commit()
            self._increment_success_quota()
            yield self._event("done", phase=PHASE_FINAL, data=build_script_output(episode), message=final_status)
        except Exception as exc:
            episode = self.repo.update_episode(episode, status=STATUS_FAILED)
            self.repo.append_phase_log(
                episode,
                phase_log_entry(current_phase, validation_errors=[str(exc)]),
            )
            yield self._event("error", phase=current_phase, message=str(exc))
