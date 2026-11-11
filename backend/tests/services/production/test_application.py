from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.crud.api_key import create_api_key
from app.crud.project import get_project
from app.schemas.api_key import APIKeyCreate
from app.schemas.script_production import GenerateSuggestionsRequest, InputType, PresetStyle, StyleInput
from app.services.production.application import generate_script_suggestions_response


# Duration persistence guard: the application service owns project creation, so
# this test catches regressions where UI timing is accepted but not saved.
@pytest.mark.asyncio
async def test_generate_script_suggestions_persists_scene_duration(db_session):
    _, api_key = create_api_key(db_session, APIKeyCreate(owner="Duration Owner", quota_limit=20))
    service = SimpleNamespace(
        generate_suggestions=AsyncMock(return_value=[
            {
                "index": 0,
                "title": "Clockwork City",
                "synopsis": "A city wakes one district at a time.",
                "mood": "Tense",
                "hook": "The first bell rings underground.",
                "is_original": True,
                "topic_type": "fictional_original",
            },
            {
                "index": 1,
                "title": "Silent Signal",
                "synopsis": "A lost signal guides a courier home.",
                "mood": "Reflective",
                "hook": "No one remembers sending the message.",
                "is_original": False,
                "topic_type": "fictional_original",
            },
        ])
    )
    req = GenerateSuggestionsRequest(
        input_type=InputType.MANUAL,
        input_content="A compact sci-fi idea",
        style=StyleInput(preset=PresetStyle.CINEMATIC),
        num_scenes=12,
        num_suggestions=2,
        model_name="gemini-3.1-flash-lite",
        generation_mode="single",
        scene_duration_sec=10,
    )

    response = await generate_script_suggestions_response(
        req=req,
        service=service,
        db=db_session,
        api_key_check=api_key,
    )

    project = get_project(db_session, response.project_id, api_key.id)
    assert response.success is True
    assert project is not None
    assert project.scene_duration == 10
    assert project.generation_mode == "single"
