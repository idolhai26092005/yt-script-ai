from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Header, Path, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.limiter import limiter
from app.deps import get_db, get_gemini_api_key, verify_api_key, verify_api_key_no_quota
from app.models.api_key import APIKey
from app.models.series_v2 import SeriesEpisodeV2, SeriesV2
from app.schemas.series_v2 import (
    EpisodeBriefUpdate,
    EpisodeGenerateRequest,
    SeriesEpisodeV2Response,
    SeriesV2CreatePayload,
    SeriesV2Response,
)
from app.services.production.support.sse import safe_sse_stream
from app.services.series_v2 import SeriesV2Generator, SeriesV2Repository


router = APIRouter()


# Ownership guard: every route resolves the v2 series through api_key_id before
# touching episode artifacts or starting generation.
def _get_owned_series_or_404(db: Session, series_id: int, api_key_id: int) -> SeriesV2:
    repo = SeriesV2Repository(db)
    series = repo.get_series(series_id, api_key_id)
    if not series:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Khong tim thay series.v2 hoac khong co quyen truy cap",
        )
    return series


# Episode guard: endpoints create only bounded v2 episode shells and keep all
# generation behavior inside the series v2 service.
def _get_episode_or_404(db: Session, series: SeriesV2, episode_number: int) -> SeriesEpisodeV2:
    if episode_number < 1 or episode_number > series.target_episode_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="episode_number nam ngoai target_episode_count",
        )
    repo = SeriesV2Repository(db)
    episode = repo.get_episode_by_number(series.id, episode_number)
    if not episode:
        episode = repo.create_episode_shell(series, episode_number)
        db.commit()
        db.refresh(episode)
    return episode


# Service factory guard: endpoint owns auth/header wiring only; generation
# orchestration stays in `app.services.series_v2`.
def _series_service(
    *,
    db: Session,
    api_key_check: APIKey,
    gemini_api_key: str,
    groq_api_key: str | None,
) -> SeriesV2Generator:
    return SeriesV2Generator(
        api_key=gemini_api_key,
        groq_api_key=groq_api_key,
        db=db,
        api_key_id=api_key_check.id,
    )


@router.post("/", response_model=SeriesV2Response)
@limiter.limit("5/minute")
async def create_new_series(
    series_in: SeriesV2CreatePayload,
    request: Request,
    x_groq_api_key: str | None = Header(None, alias="X-Groq-API-Key"),
    db: Session = Depends(get_db),
    api_key_check: APIKey = Depends(verify_api_key),
    gemini_api_key: str = Depends(get_gemini_api_key),
):
    """Create a series.v2 row with setup artifacts."""
    service = _series_service(
        db=db,
        api_key_check=api_key_check,
        gemini_api_key=gemini_api_key,
        groq_api_key=x_groq_api_key,
    )
    try:
        return await service.create_series(series_in)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


# Pagination response guard: rebuilt series history needs total metadata while
# preserving v2-only rows under the existing `/series` path.
@router.get("/")
def list_user_series(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    api_key_check: APIKey = Depends(verify_api_key_no_quota),
):
    """List owned series.v2 rows."""
    repo = SeriesV2Repository(db)
    return {
        "items": repo.list_series(api_key_check.id, skip=skip, limit=limit),
        "total": repo.count_series(api_key_check.id),
        "skip": skip,
        "limit": limit,
    }


# Delete guard: frontend can remove only owned series.v2 rows; cascade handles
# episode artifacts and legacy data remains untouched for rollback.
@router.delete("/{series_id}")
def delete_series(
    series_id: int,
    db: Session = Depends(get_db),
    api_key_check: APIKey = Depends(verify_api_key),
):
    """Delete one owned series.v2 row and its v2 episodes."""
    if not SeriesV2Repository(db).delete_series(series_id, api_key_check.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Khong tim thay series.v2 de xoa hoac khong co quyen truy cap",
        )
    return {"success": True, "message": "Xoa series.v2 thanh cong"}


@router.get("/{series_id}", response_model=SeriesV2Response)
def get_series_detail(
    series_id: int,
    db: Session = Depends(get_db),
    api_key_check: APIKey = Depends(verify_api_key_no_quota),
):
    """Read one owned series.v2 row."""
    return _get_owned_series_or_404(db, series_id, api_key_check.id)


@router.get("/{series_id}/episodes", response_model=List[SeriesEpisodeV2Response])
def list_episodes(
    series_id: int,
    db: Session = Depends(get_db),
    api_key_check: APIKey = Depends(verify_api_key_no_quota),
):
    """List v2 episodes in deterministic episode_number order."""
    series = _get_owned_series_or_404(db, series_id, api_key_check.id)
    return SeriesV2Repository(db).list_episodes(series.id)


@router.get("/{series_id}/episodes/{episode_number}/brief", response_model=SeriesEpisodeV2Response)
def get_episode_brief(
    series_id: int,
    episode_number: int = Path(..., ge=1, le=30),
    db: Session = Depends(get_db),
    api_key_check: APIKey = Depends(verify_api_key_no_quota),
    gemini_api_key: str = Depends(get_gemini_api_key),
):
    """Build or return one editable deterministic episode brief."""
    series = _get_owned_series_or_404(db, series_id, api_key_check.id)
    service = _series_service(
        db=db,
        api_key_check=api_key_check,
        gemini_api_key=gemini_api_key,
        groq_api_key=None,
    )
    try:
        return service.get_or_create_brief(series, episode_number)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# Brief-candidate guard: the rebuilt four-step UI keeps a "choose suggestion"
# screen without reviving legacy LLM option generation or ProductionService coupling.
@router.post("/{series_id}/episodes/{episode_number}/suggestions")
def get_episode_brief_suggestions(
    series_id: int,
    episode_number: int = Path(..., ge=1, le=30),
    db: Session = Depends(get_db),
    api_key_check: APIKey = Depends(verify_api_key_no_quota),
    gemini_api_key: str = Depends(get_gemini_api_key),
):
    """Return deterministic v2 brief candidates for one episode."""
    series = _get_owned_series_or_404(db, series_id, api_key_check.id)
    service = _series_service(
        db=db,
        api_key_check=api_key_check,
        gemini_api_key=gemini_api_key,
        groq_api_key=None,
    )
    try:
        episode = service.get_or_create_brief(series, episode_number)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    brief = episode.brief or {}
    is_final = episode_number >= series.target_episode_count
    base_scene_count = int(brief.get("scene_count") or series.default_scene_count)
    base_title = brief.get("title") or episode.title or f"Tap {episode_number}"
    base_premise = brief.get("premise") or series.premise
    base_include = list(brief.get("must_include") or [])
    base_avoid = list(brief.get("must_avoid") or [])
    default_ending = "season_finale" if is_final else "open_loop"
    candidates = [
        {
            "index": 0,
            "title": base_title,
            "synopsis": base_premise,
            "mood": "Can bang",
            "hook": brief.get("slot", {}).get("required_reveal") or brief.get("notes") or base_premise[:160],
            "brief": {
                "title": base_title,
                "premise": base_premise,
                "must_include": base_include,
                "must_avoid": base_avoid,
                "scene_count": base_scene_count,
                "ending_mode": brief.get("ending_mode") or default_ending,
                "notes": brief.get("notes") or "",
            },
        },
        {
            "index": 1,
            "title": f"{base_title} - ap luc cao",
            "synopsis": f"{base_premise}\n\nTang ap luc som hon, giu ro mach unresolved thread cho tap tiep theo.",
            "mood": "Cang thang",
            "hook": brief.get("slot", {}).get("required_unresolved_thread") or "Day manh cau hoi chua giai quyet.",
            "brief": {
                "title": f"{base_title} - ap luc cao",
                "premise": base_premise,
                "must_include": base_include,
                "must_avoid": [*base_avoid, "ket thuc qua tron ven"] if not is_final else base_avoid,
                "scene_count": base_scene_count,
                "ending_mode": "hard_cliffhanger" if not is_final else "season_finale",
                "notes": "Tang nhip, uu tien canh cuoi co luc day sang tap sau.",
            },
        },
        {
            "index": 2,
            "title": f"{base_title} - ban gon",
            "synopsis": f"{base_premise}\n\nTap trung vao truc chinh, giam nhanh canh phu de sinh kich ban gon hon.",
            "mood": "Tap trung",
            "hook": brief.get("slot", {}).get("episode_goal") or "Giu mot muc tieu tap ro rang.",
            "brief": {
                "title": f"{base_title} - ban gon",
                "premise": base_premise,
                "must_include": base_include,
                "must_avoid": [*base_avoid, "phan nhanh khong can thiet"],
                "scene_count": max(4, min(base_scene_count, series.default_scene_count)),
                "ending_mode": "soft_cliffhanger" if not is_final else "season_finale",
                "notes": "Ban gon de de kiem soat chat luong va continuity.",
            },
        },
    ]
    return {"success": True, "suggestions": candidates}


@router.put("/{series_id}/episodes/{episode_number}/brief", response_model=SeriesEpisodeV2Response)
def update_episode_brief(
    series_id: int,
    revision: EpisodeBriefUpdate,
    episode_number: int = Path(..., ge=1, le=30),
    db: Session = Depends(get_db),
    api_key_check: APIKey = Depends(verify_api_key),
    gemini_api_key: str = Depends(get_gemini_api_key),
):
    """Persist user edits to the episode brief before generation."""
    series = _get_owned_series_or_404(db, series_id, api_key_check.id)
    service = _series_service(
        db=db,
        api_key_check=api_key_check,
        gemini_api_key=gemini_api_key,
        groq_api_key=None,
    )
    try:
        return service.update_brief(series, episode_number, revision)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{series_id}/episodes/{episode_number}/generate")
@limiter.limit("5/minute")
async def generate_episode(
    series_id: int,
    request: Request,
    episode_number: int = Path(..., ge=1, le=30),
    req: EpisodeGenerateRequest | None = Body(default=None),
    x_groq_api_key: str | None = Header(None, alias="X-Groq-API-Key"),
    db: Session = Depends(get_db),
    api_key_check: APIKey = Depends(verify_api_key),
    gemini_api_key: str = Depends(get_gemini_api_key),
):
    """Stream one v2 episode generation run."""
    req = req or EpisodeGenerateRequest()
    series = _get_owned_series_or_404(db, series_id, api_key_check.id)
    episode = _get_episode_or_404(db, series, episode_number)
    service = _series_service(
        db=db,
        api_key_check=api_key_check,
        gemini_api_key=gemini_api_key,
        groq_api_key=x_groq_api_key,
    )
    stream = service.generate_episode_stream(
        series=series,
        episode=episode,
        model_name=req.model_name,
        run_reviewer=req.run_reviewer,
        run_packaging=req.run_packaging,
        restart=req.restart,
    )
    return StreamingResponse(
        safe_sse_stream(stream),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
