import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


SCHEMA_VERSION = "series.v2"
EpisodeEndingMode = Literal["open_loop", "soft_cliffhanger", "hard_cliffhanger", "season_finale"]
SeriesTopicType = Literal["historical", "scientific", "fictional_mythology", "fictional_original"]


# Series v2 schema guard: create requests carry enough planning knobs to avoid
# hidden old defaults such as `series_long == 30 scenes`.
class SeriesV2Create(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    premise: str = Field(..., min_length=1, max_length=60000)
    style: str = Field("anime", min_length=1, max_length=200)
    topic_type: SeriesTopicType = "fictional_original"
    target_episode_count: int = Field(5, ge=2, le=30)
    default_scene_count: int = Field(8, ge=4, le=200)
    scene_duration_sec: int = Field(8, ge=4, le=12)
    model_name: str = Field("gemini-3.1-flash-lite", min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._:-]+$")


# Legacy payload rejection guard: accepting `big_idea` or `generation_mode`
# would silently preserve the old API contract under the new route.
class SeriesV2CreatePayload(SeriesV2Create):
    @model_validator(mode="before")
    @classmethod
    def reject_legacy_series_payload(cls, data: Any) -> Any:
        if isinstance(data, dict) and ("big_idea" in data or "generation_mode" in data):
            raise ValueError("Legacy series payload is not supported by series.v2")
        return data


# Episode brief guard: user revisions are constrained to the editable handoff
# surface and are applied before any paid episode-generation LLM call.
class EpisodeBriefUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    premise: str | None = Field(None, min_length=1, max_length=60000)
    must_include: list[str] | None = None
    must_avoid: list[str] | None = None
    scene_count: int | None = Field(None, ge=4, le=200)
    ending_mode: EpisodeEndingMode | None = None
    notes: str | None = Field(None, max_length=4000)


# Episode generation request guard: generation starts from an accepted brief,
# while optional switches keep expensive review/packaging calls controllable.
class EpisodeGenerateRequest(BaseModel):
    model_name: str = Field("gemini-3.1-flash-lite", min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._:-]+$")
    run_reviewer: bool = True
    run_packaging: bool = False
    # Recovery guard: retry resumes from valid episode artifacts; restart keeps
    # the edited brief but clears generated output without a separate reset API.
    restart: bool = False


# Review schema guard: soft continuity review has a stable public shape while
# creative-quality decisions remain outside hard-coded endpoint validation.
class SeriesReviewReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    handoff_strength: Literal["strong", "medium", "weak"]
    open_threads: list[str]
    next_start_state: str | None = None
    review_notes: list[str]
    too_closed: bool = False
    season_alignment: Literal["strong", "medium", "weak"] = "medium"


# Response guard: all public series v2 responses carry an explicit schema marker
# so rebuilt frontend code cannot confuse them with legacy `/series` payloads.
class SeriesV2Response(BaseModel):
    schema_version: str = SCHEMA_VERSION
    id: int
    title: str
    premise: str
    style: str
    topic_type: str
    reality_binding_level: str
    default_scene_count: int
    scene_duration_sec: int
    target_episode_count: int
    status: str
    series_bible: dict | None = None
    season_map: dict | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


# Episode response guard: artifact fields are exposed without legacy Project
# identifiers because v2 stores episode output directly.
class SeriesEpisodeV2Response(BaseModel):
    schema_version: str = SCHEMA_VERSION
    id: int
    series_id: int
    episode_number: int
    status: str
    title: str | None
    brief: dict | None = None
    user_revision: dict | None = None
    scene_count: int
    ending_mode: str
    episode_blueprint: dict | None = None
    emotion_arc: list[dict] | None = None
    scenes: list[dict] | None = None
    review_report: dict | None = None
    continuity_delta: dict | None = None
    script_output: dict | None = None
    phase_log: list[dict] | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


# Stream payload guard: tests and frontend progress handling can validate v2 SSE
# without depending on free-form internal generator state.
class SeriesStreamEvent(BaseModel):
    schema_version: str = SCHEMA_VERSION
    status: Literal["generating", "scene", "review", "done", "error"]
    phase: str | None = None
    data: dict | list | None = None
    message: str | None = None
