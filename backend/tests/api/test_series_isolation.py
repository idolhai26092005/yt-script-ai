import importlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


# Series route guard test reloads the router after forcing the flag off so the
# disabled series API cannot leak into production routes by import side effect.
def test_series_routes_disabled_while_production_routes_stay_mounted(monkeypatch):
    from app.core.config import settings
    import app.api.v1.router as router_module

    monkeypatch.setattr(settings, "ENABLE_SERIES_FLOW", False)
    reloaded = importlib.reload(router_module)

    paths = {
        route_context.path
        for included_router in reloaded.api_router.routes
        for route_context in included_router.effective_route_contexts()
    }

    assert "/series/" not in paths
    assert "/production/script/generate" in paths


# Series v2 mount guard proves the feature flag exposes the rebuilt contract on
# the stable route path instead of preserving the legacy endpoint shape.
def test_series_routes_enabled_mounts_v2_contract(monkeypatch):
    from app.core.config import settings
    import app.api.v1.router as router_module
    from app.schemas.series_v2 import SeriesV2CreatePayload

    monkeypatch.setattr(settings, "ENABLE_SERIES_FLOW", True)
    reloaded = importlib.reload(router_module)
    paths = {
        route_context.path
        for included_router in reloaded.api_router.routes
        for route_context in included_router.effective_route_contexts()
    }

    assert "/series/" in paths
    assert SeriesV2CreatePayload.model_fields["title"].is_required()

    monkeypatch.setattr(settings, "ENABLE_SERIES_FLOW", False)
    importlib.reload(router_module)


# Selection-title guard: starting detailed generation is the first backend-owned
# moment where the user's chosen suggestion is known and can name the project.
@pytest.mark.asyncio
async def test_full_generation_updates_project_title_from_selected_suggestion(monkeypatch, db_session):
    import json

    from app.api.v1.endpoints import script_production
    from app.crud.api_key import create_api_key
    from app.crud.project import create_project, get_project, update_project_suggestions
    from app.schemas.api_key import APIKeyCreate
    from app.schemas.script_production import GenerateFullScriptRequest

    _, api_key = create_api_key(db_session, APIKeyCreate(owner="Selected Title Owner", quota_limit=20))
    project = create_project(
        db=db_session,
        api_key_id=api_key.id,
        title="Dự án kịch bản phong cách PresetStyle.REALISTIC",
        input_type="manual",
        input_content="Một ý tưởng cần chọn đúng title.",
        style="realistic",
        num_scenes=20,
        generation_mode="single",
        scene_duration_sec=8,
    )
    update_project_suggestions(
        db_session,
        project.id,
        json.dumps([
            {"index": 0, "title": "Title không chọn", "synopsis": "A", "topic_type": "fictional_original"},
            {"index": 1, "title": "Title user đã chọn", "synopsis": "B", "topic_type": "scientific"},
        ], ensure_ascii=False),
    )

    class StubProductionService:
        def __init__(self, *_args, **_kwargs):
            pass

        def generate_full_script_stream(self, **_kwargs):
            async def stream():
                yield 'data: {"status":"connected"}\n\n'

            return stream()

    monkeypatch.setattr(script_production, "ProductionService", StubProductionService)

    response = await script_production.generate_full_production_script.__wrapped__(
        req=GenerateFullScriptRequest(project_id=project.id, suggestion_index=1),
        request=SimpleNamespace(),
        db=db_session,
        api_key_check=api_key,
        gemini_api_key="test-gemini-key",
    )

    saved = get_project(db_session, project.id, api_key.id)
    assert response.media_type == "text/event-stream"
    assert saved.title == "Title user đã chọn"
    assert saved.selected_suggestion_idx == 1
    assert saved.topic_type == "scientific"


# Series generation guard protects the single production pipeline from direct
# `series_*` calls even when a legacy project row still stores a series mode.
@pytest.mark.asyncio
async def test_series_generation_mode_rejected_before_service_creation(monkeypatch):
    from app.api.v1.endpoints import script_production
    from app.schemas.script_production import GenerateFullScriptRequest

    req = GenerateFullScriptRequest(
        project_id=1,
        suggestion_index=0,
        generation_mode="series_short",
    )
    project = SimpleNamespace(
        id=1,
        style="anime",
        num_scenes=8,
        scene_duration=8,
        generation_mode="series_short",
        suggestions='[{"index": 0, "title": "Series", "synopsis": "Story"}]',
    )

    monkeypatch.setattr(script_production, "get_project", lambda *_args, **_kwargs: project)
    monkeypatch.setattr(script_production, "select_project_suggestion", lambda *_args, **_kwargs: {"index": 0})

    def fail_service_creation(*_args, **_kwargs):
        raise AssertionError("ProductionService must not be created for disabled series flow")

    monkeypatch.setattr(script_production, "ProductionService", fail_service_creation)

    with pytest.raises(HTTPException) as exc:
        await script_production.generate_full_production_script.__wrapped__(
            req=req,
            request=SimpleNamespace(),
            db=SimpleNamespace(),
            api_key_check=SimpleNamespace(id=99),
            gemini_api_key="test-key",
        )

    assert exc.value.status_code == 409
    assert "/api/v1/series" in exc.value.detail
