import copy
import time
from datetime import datetime, timezone
from typing import Any

from app.services.series_v2.contracts import (
    ENDING_HARD_CLIFFHANGER,
    ENDING_OPEN_LOOP,
    ENDING_SEASON_FINALE,
    MAX_SCENE_COUNT,
    MIN_SCENE_COUNT,
    PHASE_BRIEF,
    SCHEMA_VERSION,
)


# Scene-count guard: series v2 keeps flexible episode length while still
# preventing impossible prompt sizes and empty output contracts.
def validate_scene_count(scene_count: int) -> None:
    if scene_count < MIN_SCENE_COUNT or scene_count > MAX_SCENE_COUNT:
        raise ValueError(f"scene_count must be between {MIN_SCENE_COUNT} and {MAX_SCENE_COUNT}")


# Phase-log guard: every generator step records the artifact surface and timing
# without persisting prompts or provider secrets.
def phase_log_entry(
    phase: str,
    *,
    artifact_keys: list[str] | None = None,
    validation_errors: list[str] | None = None,
    warnings: list[str] | None = None,
    started_at: float | None = None,
    cache_hit: bool = False,
) -> dict[str, Any]:
    latency_ms = 0.0 if started_at is None else (time.time() - started_at) * 1000.0
    return {
        "phase": phase,
        "role": phase,
        "schema_version": SCHEMA_VERSION,
        "validation_status": "failed" if validation_errors else "passed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "artifact_keys": artifact_keys or [],
        "validation_errors": validation_errors or [],
        "warnings": warnings or [],
        "latency_ms": latency_ms,
        "cache_hit": cache_hit,
    }


# Brief gate guard: pending episodes start from deterministic season context so
# user edits do not spend an LLM call or create divergent option branches.
def build_episode_brief(
    *,
    series_bible: dict | None,
    season_map: dict | None,
    episode_number: int,
    default_scene_count: int,
    target_episode_count: int,
    prior_delta: dict | None = None,
    user_revision: dict | None = None,
) -> dict[str, Any]:
    validate_scene_count(default_scene_count)
    episode_slots = (season_map or {}).get("episode_slots") or []
    slot = next(
        (item for item in episode_slots if item.get("episode_number") == episode_number),
        {},
    )
    is_final = episode_number >= target_episode_count
    brief = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_BRIEF,
        "episode_number": episode_number,
        "title": slot.get("title") or f"Tap {episode_number}",
        "premise": slot.get("premise") or slot.get("goal") or (series_bible or {}).get("central_conflict") or "",
        "must_include": list(slot.get("must_include") or []),
        "must_avoid": list(slot.get("must_avoid") or []),
        "scene_count": int(slot.get("scene_count") or default_scene_count),
        "ending_mode": slot.get("ending_mode") or (ENDING_SEASON_FINALE if is_final else ENDING_OPEN_LOOP),
        "notes": "",
        "prior_handoff": copy.deepcopy(prior_delta or {}),
        "slot": copy.deepcopy(slot),
    }
    if not is_final and brief["ending_mode"] == ENDING_SEASON_FINALE:
        brief["ending_mode"] = ENDING_HARD_CLIFFHANGER
    for key, value in (user_revision or {}).items():
        if value is not None and key in brief:
            brief[key] = value
    validate_scene_count(int(brief["scene_count"]))
    return brief


# Script output guard: final episode payload stays self-contained and avoids the
# legacy Project cache shape while preserving useful production artifacts.
def build_script_output(episode: Any) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "episode_number": episode.episode_number,
        "title": episode.title,
        "scene_count": episode.scene_count,
        "ending_mode": episode.ending_mode,
        "episode_blueprint": episode.episode_blueprint or {},
        "emotion_arc": episode.emotion_arc or [],
        "scenes": episode.scenes or [],
        "review_report": episode.review_report or {},
        "continuity_delta": episode.continuity_delta or {},
    }
