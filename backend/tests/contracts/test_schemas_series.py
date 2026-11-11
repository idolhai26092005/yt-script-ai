import pytest
from pydantic import ValidationError
from app.schemas.script_production import (
    SeriesCreate,
    SeriesResponse,
    EpisodeCreate,
    EpisodeResponse,
    NextSuggestionRequest,
    NextSuggestionResponse
)
import datetime

def test_series_schemas():
    # 1. SeriesCreate success
    sc = SeriesCreate(
        title="Cuộc di cư",
        big_idea="Loài bướm",
        generation_mode="series_short",
        style="anime"
    )
    assert sc.title == "Cuộc di cư"
    assert sc.generation_mode == "series_short"

    # 2. SeriesResponse validation
    now = datetime.datetime.now()
    sr = SeriesResponse(
        id=1,
        title="Cuộc di cư",
        big_idea="Loài bướm",
        generation_mode="series_short",
        episode_duration_minutes=None,
        style="anime",
        status="active",
        created_at=now,
        updated_at=now
    )
    assert sr.id == 1
    assert sr.created_at == now

def test_episode_schemas():
    # 1. EpisodeCreate
    ec = EpisodeCreate(
        series_id=1,
        title="Tập 1",
        user_input="Test"
    )
    assert ec.series_id == 1
    
    # 2. EpisodeResponse
    now = datetime.datetime.now()
    er = EpisodeResponse(
        id=1,
        series_id=2,
        episode_number=3,
        project_id=4,
        title="Tập 3",
        context_summary={"status": "ok"},
        next_suggestions=["Idea 1"],
        user_input="None",
        status="completed",
        created_at=now
    )
    assert er.episode_number == 3
    assert er.context_summary == {"status": "ok"}

def test_script_output_series_bridge_vi_default():
    from app.schemas.script_production import ScriptOutput
    # Check that series_bridge_vi is in annotations and is optional with None default
    assert "series_bridge_vi" in ScriptOutput.model_fields
    field = ScriptOutput.model_fields["series_bridge_vi"]
    assert field.default is None

