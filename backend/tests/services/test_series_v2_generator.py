import json
import os

import pytest

from app.core.config import settings
from app.models.api_key import APIKey
from app.schemas.series_v2 import EpisodeBriefUpdate, SeriesV2Create
from app.services.series_v2 import SeriesV2Generator, SeriesV2Repository


# Fake transport guard: service tests exercise orchestration and persistence
# without network calls or provider-specific retry timing.
class FakeSeriesV2Generator(SeriesV2Generator):
    # Fake dependency guard: constructor keeps the real repository wiring while
    # injecting deterministic phase responses.
    def __init__(self, *, responses: list[dict], **kwargs):
        super().__init__(**kwargs)
        self.responses = list(responses)
        self.phases: list[str] = []

    # LLM fake guard: each phase consumes one deterministic JSON response so the
    # test can verify budget and ordering.
    async def _call_series_llm(self, *, prompt: str, model_name: str, phase: str) -> str:
        self.phases.append(phase)
        return json.dumps(self.responses.pop(0))


# Fixture guard: create an active API key row so quota and foreign-key behavior
# match production repository usage.
@pytest.fixture()
def api_key(db_session):
    key = APIKey(key_hash="series-v2-test-key", owner="series-v2", quota_limit=10, quota_used=0, is_active=True)
    db_session.add(key)
    db_session.commit()
    db_session.refresh(key)
    return key


# Artifact fixture guard: setup response contains exactly two ordered slots so
# deterministic brief creation can be tested without fallback data.
def setup_response() -> dict:
    return {
        "schema_version": "series.v2",
        "reality_binding_level": "soft",
        "series_bible": {
            "world_rules": ["same station"],
            "cast_locks": ["Mira keeps the red coat"],
            "visual_anchor": "approved station, red coat, blue signal light",
            "style_tone": "tense cinematic",
            "central_conflict": "Find the source of the signal",
            "reality_constraints": [],
            "forbidden_drift": [],
        },
        "season_map": {
            "episode_slots": [
                {
                    "episode_number": 1,
                    "title": "Signal Door",
                    "premise": "Mira reaches the locked signal door.",
                    "goal": "Open the first lock",
                    "pressure_increase": "signal grows louder",
                    "required_reveal": "the door recognizes her voice",
                    "required_unresolved_thread": "the door opens to black stairs",
                    "intended_next_start_state": "Mira stands at the stair edge",
                    "must_include": ["red coat", "blue signal"],
                    "must_avoid": ["resolved mystery"],
                    "scene_count": 4,
                    "ending_mode": "open_loop",
                },
                {
                    "episode_number": 2,
                    "title": "Black Stairs",
                    "premise": "Mira descends.",
                    "goal": "Follow the signal",
                    "pressure_increase": "stairs move",
                    "required_reveal": "the station is alive",
                    "required_unresolved_thread": "",
                    "intended_next_start_state": "season complete",
                    "must_include": [],
                    "must_avoid": [],
                    "scene_count": 4,
                    "ending_mode": "season_finale",
                },
            ]
        },
    }


# Artifact fixture guard: planning response returns one beat per accepted scene
# count, matching the hard structural contract.
def plan_response() -> dict:
    return {
        "schema_version": "series.v2",
        "episode_blueprint": {
            "prompt_0_extension": "Keep Mira at the signal door.",
            "story_contract": "Episode ends as stairs appear.",
            "stage_ranges": ["1-2 setup", "3-4 handoff"],
            "visual_constraints": ["red coat", "blue signal"],
            "audio_constraints": ["quiet voice"],
            "handoff_target": "stairs appear",
            "next_start_promise": "Mira stands at the stair edge",
        },
        "emotion_arc": [
            {
                "scene_number": idx,
                "scene_goal": f"beat {idx}",
                "emotion_shift": "pressure rises",
                "physical_state_end": "closer to the door",
                "scene_lead": "signal",
                "anchor_to_cite": "approved station anchor",
            }
            for idx in range(1, 5)
        ],
    }


# Artifact fixture guard: scene response uses render-required fields and approved
# anchor citation so validator coverage stays focused on hard gates.
def scene_response() -> dict:
    return {
        "schema_version": "series.v2",
        "scenes": [
            {
                "scene_number": idx,
                "action_detail_vi": f"Mira tien den canh {idx}.",
                "veo3_prompt_en": "Reference the approved visual anchor: red coat, blue signal, old station.",
                "voice_over_en": f"Mira hears signal {idx}.",
                "continuity_anchor": "approved station anchor",
                "handoff_state": "Mira stands at the stair edge" if idx == 4 else "Mira moves closer",
            }
            for idx in range(1, 5)
        ],
    }


# Artifact fixture guard: review response asserts strong handoff while keeping
# creative judgment soft and structured.
def review_response() -> dict:
    return {
        "schema_version": "series.v2",
        "handoff_strength": "strong",
        "open_threads": ["the door opens to black stairs"],
        "next_start_state": "Mira stands at the stair edge",
        "review_notes": ["handoff remains open"],
        "too_closed": False,
        "season_alignment": "strong",
    }


# Snapshot settings guard: tests opt into dev snapshots explicitly and restore
# global settings via monkeypatch so production safety cannot depend on sqlite.
def set_snapshot_mode(monkeypatch, *, env: str, enabled: bool) -> None:
    monkeypatch.setattr(settings, "ENV", env)
    monkeypatch.setattr(settings, "DEBUG_SNAPSHOTS", enabled)


# Series setup guard: creation uses one setup call and stores v2 artifacts with a
# pending episode shell.
@pytest.mark.asyncio
async def test_series_v2_setup_persists_bible_season_map_and_pending_episode(db_session, api_key):
    service = FakeSeriesV2Generator(
        api_key="gemini-test",
        db=db_session,
        api_key_id=api_key.id,
        responses=[setup_response()],
    )

    series = await service.create_series(
        SeriesV2Create(title="Signal", premise="A signal in an empty station.", target_episode_count=2, default_scene_count=4)
    )
    first_episode = SeriesV2Repository(db_session).get_episode_by_number(series.id, 1)

    assert service.phases == ["series_setup"]
    assert series.series_bible["visual_anchor"]
    assert len(series.season_map["episode_slots"]) == 2
    assert first_episode.status == "pending"


# Episode flow guard: brief creation spends no call, generation checkpoints
# planning/scenes/review, persists continuity, and increments quota once.
# Snapshot guard: series v2 mirrors single-flow debug files for phase inspection
# during local development when explicitly enabled.
@pytest.mark.asyncio
async def test_series_v2_episode_generation_persists_continuity_quota_and_snapshots(db_session, api_key, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    set_snapshot_mode(monkeypatch, env="development", enabled=True)
    service = FakeSeriesV2Generator(
        api_key="gemini-test",
        db=db_session,
        api_key_id=api_key.id,
        responses=[setup_response(), plan_response(), scene_response(), review_response()],
    )
    series = await service.create_series(
        SeriesV2Create(title="Signal", premise="A signal in an empty station.", target_episode_count=2, default_scene_count=4)
    )
    phase_count_after_setup = len(service.phases)

    episode = service.update_brief(
        series,
        1,
        EpisodeBriefUpdate(notes="Keep ending open.", scene_count=4),
    )
    assert len(service.phases) == phase_count_after_setup

    events = [
        chunk async for chunk in service.generate_episode_stream(
            series=series,
            episode=episode,
            model_name="gemini-3.1-flash-lite",
        )
    ]
    stored_episode = SeriesV2Repository(db_session).get_episode_by_number(series.id, 1)
    next_episode = SeriesV2Repository(db_session).get_episode_by_number(series.id, 2)
    db_session.refresh(api_key)

    assert service.phases == ["series_setup", "episode_planning", "episode_scenes", "continuity_review"]
    assert any('"status": "scene"' in event for event in events)
    assert any('"status": "done"' in event for event in events)
    assert stored_episode.status == "completed"
    assert len(stored_episode.scenes) == 4
    assert stored_episode.continuity_delta["next_start_state"] == "Mira stands at the stair edge"
    assert stored_episode.phase_log[-1]["role"] == "final_persist"
    assert stored_episode.phase_log[-1]["validation_status"] == "passed"
    assert next_episode is not None
    assert api_key.quota_used == 1
    snapshot_dir = tmp_path / "debug_snapshots"
    snapshot_names = sorted(os.listdir(snapshot_dir))
    assert any("phase_0_series_setup" in name for name in snapshot_names)
    assert any("phase_1_episode_brief" in name for name in snapshot_names)
    assert any("phase_2_episode_planning" in name for name in snapshot_names)
    assert any("phase_3_scenes_1_4" in name for name in snapshot_names)
    assert any("phase_5_continuity_review" in name for name in snapshot_names)
    assert any("phase_6_continuity_delta" in name for name in snapshot_names)
    assert any("phase_8_final_script" in name for name in snapshot_names)


# Recovery cache guard: a failed episode with valid plan/scenes should resume at
# review/continuity instead of spending calls on already persisted artifacts.
@pytest.mark.asyncio
async def test_series_v2_failed_episode_resumes_from_valid_cached_scenes(db_session, api_key):
    service = FakeSeriesV2Generator(
        api_key="gemini-test",
        db=db_session,
        api_key_id=api_key.id,
        responses=[setup_response(), review_response()],
    )
    series = await service.create_series(
        SeriesV2Create(title="Signal", premise="A signal in an empty station.", target_episode_count=2, default_scene_count=4)
    )
    episode = service.update_brief(series, 1, EpisodeBriefUpdate(notes="Keep ending open.", scene_count=4))
    repo = SeriesV2Repository(db_session)
    plan = plan_response()
    episode = repo.update_episode(
        episode,
        status="failed",
        episode_blueprint=plan["episode_blueprint"],
        emotion_arc=plan["emotion_arc"],
        scenes=scene_response()["scenes"],
    )
    service.phases = []

    events = [
        chunk async for chunk in service.generate_episode_stream(
            series=series,
            episode=episode,
            model_name="gemini-3.1-flash-lite",
            restart=False,
        )
    ]
    stored_episode = repo.get_episode_by_number(series.id, 1)

    assert service.phases == ["continuity_review"]
    assert any('"status": "scene"' in event for event in events)
    assert stored_episode.status == "completed"
    assert stored_episode.script_output["scenes"][0]["scene_number"] == 1


# Restart guard: sinh lại từ đầu clears generated artifacts but preserves the
# accepted brief, forcing plan/scenes/review to run again.
@pytest.mark.asyncio
async def test_series_v2_restart_clears_generated_artifacts_but_keeps_brief(db_session, api_key):
    service = FakeSeriesV2Generator(
        api_key="gemini-test",
        db=db_session,
        api_key_id=api_key.id,
        responses=[setup_response(), plan_response(), scene_response(), review_response()],
    )
    series = await service.create_series(
        SeriesV2Create(title="Signal", premise="A signal in an empty station.", target_episode_count=2, default_scene_count=4)
    )
    episode = service.update_brief(series, 1, EpisodeBriefUpdate(notes="Keep ending open.", scene_count=4))
    repo = SeriesV2Repository(db_session)
    plan = plan_response()
    old_scene = {**scene_response()["scenes"][0], "action_detail_vi": "OLD cached scene"}
    episode = repo.update_episode(
        episode,
        status="failed",
        episode_blueprint=plan["episode_blueprint"],
        emotion_arc=plan["emotion_arc"],
        scenes=[old_scene],
        review_report=review_response(),
        continuity_delta={"last_physical_state": "old", "handoff_strength": "strong", "cliffhanger_fact": "old", "open_threads": ["old"], "new_constraints": [], "next_start_state": "old"},
        script_output={"scenes": [old_scene]},
    )
    service.phases = []

    events = [
        chunk async for chunk in service.generate_episode_stream(
            series=series,
            episode=episode,
            model_name="gemini-3.1-flash-lite",
            restart=True,
        )
    ]
    stored_episode = repo.get_episode_by_number(series.id, 1)

    assert service.phases[-3:] == ["episode_planning", "episode_scenes", "continuity_review"]
    assert any('"status": "done"' in event for event in events)
    assert stored_episode.brief["notes"] == "Keep ending open."
    assert stored_episode.scenes[0]["action_detail_vi"] != "OLD cached scene"


# Snapshot flag guard: development runs stay clean unless the debug flag is
# intentionally enabled for local investigation.
@pytest.mark.asyncio
async def test_series_v2_debug_snapshots_disabled_in_development_without_flag(db_session, api_key, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    set_snapshot_mode(monkeypatch, env="development", enabled=False)
    service = FakeSeriesV2Generator(
        api_key="gemini-test",
        db=db_session,
        api_key_id=api_key.id,
        responses=[setup_response()],
    )

    await service.create_series(
        SeriesV2Create(title="Signal", premise="A signal in an empty station.", target_episode_count=2, default_scene_count=4)
    )

    assert not (tmp_path / "debug_snapshots").exists()


# Production snapshot guard: production never writes local debug artifacts even
# if the flag is accidentally enabled and the database URL is sqlite.
@pytest.mark.asyncio
async def test_series_v2_debug_snapshots_blocked_in_production(db_session, api_key, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    set_snapshot_mode(monkeypatch, env="production", enabled=True)
    service = FakeSeriesV2Generator(
        api_key="gemini-test",
        db=db_session,
        api_key_id=api_key.id,
        responses=[setup_response()],
    )

    await service.create_series(
        SeriesV2Create(title="Signal", premise="A signal in an empty station.", target_episode_count=2, default_scene_count=4)
    )

    assert not (tmp_path / "debug_snapshots").exists()
