import datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.series_v2 import (
    EpisodeBriefUpdate,
    EpisodeGenerateRequest,
    SCHEMA_VERSION,
    SeriesEpisodeV2Response,
    SeriesReviewReport,
    SeriesStreamEvent,
    SeriesV2CreatePayload,
    SeriesV2Response,
)


# Schema create guard: v2 payloads must expose explicit planning knobs and reject
# legacy-only fields before generation can spend an LLM call.
def test_series_v2_create_schema_accepts_v2_and_rejects_legacy_payloads():
    payload = SeriesV2CreatePayload(
        title="Arc",
        premise="A serialized rescue mission.",
        style="cinematic",
        topic_type="fictional_original",
        target_episode_count=4,
        default_scene_count=12,
        scene_duration_sec=8,
    )

    assert payload.target_episode_count == 4
    assert payload.default_scene_count == 12

    with pytest.raises(ValidationError):
        SeriesV2CreatePayload(
            title="Old",
            premise="Old contract",
            big_idea="legacy field",
            generation_mode="series_short",
        )


# Brief schema guard: editable user input is constrained to the handoff surface
# and out-of-bounds scene counts fail before generation.
def test_episode_brief_update_and_generation_schema_contracts():
    brief = EpisodeBriefUpdate(
        title="Episode 2",
        premise="Continue from the open door.",
        must_include=["same door"],
        must_avoid=["new random villain"],
        scene_count=50,
        ending_mode="soft_cliffhanger",
    )
    generation = EpisodeGenerateRequest(model_name="gemini-3.1-flash-lite")

    assert brief.scene_count == 50
    assert generation.run_reviewer is True

    with pytest.raises(ValidationError):
        EpisodeBriefUpdate(scene_count=201)


# Public response guard: v2 responses carry schema_version so frontend code can
# distinguish them from legacy series rows during the route replacement.
def test_series_v2_response_shapes_include_schema_version():
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    series = SeriesV2Response.model_validate(
        SimpleNamespace(
            id=1,
            title="Series",
            premise="Premise",
            style="anime",
            topic_type="fictional_original",
            reality_binding_level="soft",
            default_scene_count=8,
            scene_duration_sec=8,
            target_episode_count=5,
            status="active",
            series_bible={"visual_anchor": "approved look"},
            season_map={"episode_slots": []},
            created_at=now,
            updated_at=now,
        )
    )
    episode = SeriesEpisodeV2Response.model_validate(
        SimpleNamespace(
            id=2,
            series_id=1,
            episode_number=1,
            status="pending",
            title="Tap 1",
            brief={"scene_count": 8},
            user_revision=None,
            scene_count=8,
            ending_mode="open_loop",
            episode_blueprint=None,
            emotion_arc=[],
            scenes=[],
            review_report=None,
            continuity_delta=None,
            script_output=None,
            phase_log=[],
            created_at=now,
            updated_at=now,
        )
    )

    assert series.schema_version == SCHEMA_VERSION
    assert episode.schema_version == SCHEMA_VERSION


# Stream/review schema guard: SSE and reviewer payloads stay structured without
# endpoint-specific free-form parsing.
def test_series_v2_stream_and_review_payload_contracts():
    review = SeriesReviewReport(
        handoff_strength="strong",
        open_threads=["door remains open"],
        next_start_state="episode starts at the door",
        review_notes=["handoff clear"],
    )
    event = SeriesStreamEvent(status="done", phase="final_persist", data={"episode_number": 1})

    assert review.schema_version == SCHEMA_VERSION
    assert event.schema_version == SCHEMA_VERSION
