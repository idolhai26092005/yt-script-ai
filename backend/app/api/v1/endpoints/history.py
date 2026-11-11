from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Integer, String, cast, desc, func, literal, select, union_all
from sqlalchemy.orm import Session

from app.deps import get_db, verify_api_key_no_quota
from app.models.api_key import APIKey
from app.models.project import Project
from app.models.series_v2 import SeriesV2
from app.schemas.history import HistoryFilter, HistoryItem, HistoryPageResponse, HistoryTotals


router = APIRouter()


# Count guard: totals are computed from owned rows only and reused for filter
# badges plus page bounds.
def _history_counts(db: Session, api_key_id: int) -> HistoryTotals:
    single_total = db.query(func.count(Project.id)).filter(Project.api_key_id == api_key_id).scalar() or 0
    series_total = db.query(func.count(SeriesV2.id)).filter(SeriesV2.api_key_id == api_key_id).scalar() or 0
    return HistoryTotals(all=single_total + series_total, single=single_total, series=series_total)


# Preview guard: list rows cap user-entered text so history stays lightweight
# and cannot accidentally become an artifact-export endpoint.
def _preview(value: Any, fallback: str) -> str:
    text = str(value or "").strip() or fallback
    collapsed = " ".join(text.split())
    return collapsed[:237] + "..." if len(collapsed) > 240 else collapsed


# Metadata guard: shared history rows keep type-specific detail readable while
# preserving a single frontend rendering contract.
def _meta(row: dict[str, Any]) -> str:
    if row["kind"] == "single":
        input_label = {
            "youtube_url": "YouTube",
            "topic": "Chủ đề",
            "manual": "Thủ công",
        }.get(row.get("input_type") or "", "Thủ công")
        return f"{input_label} · {row.get('num_scenes') or 0} cảnh · {row.get('style') or 'style mặc định'}"

    return (
        f"{row.get('target_episode_count') or 0} tập · "
        f"{row.get('default_scene_count') or 0} scene/tập · "
        f"{row.get('topic_type') or 'fictional_original'}"
    )


# Union query guard: `all` history must paginate after global updated_at sort,
# not after the frontend merges two independently-paginated endpoint results.
def _history_union_query(api_key_id: int):
    project_select = select(
        literal("single").label("kind"),
        Project.id.label("id"),
        Project.title.label("title"),
        Project.status.label("status"),
        Project.updated_at.label("updated_at"),
        Project.created_at.label("created_at"),
        Project.input_content.label("preview_source"),
        Project.input_type.label("input_type"),
        Project.style.label("style"),
        Project.num_scenes.label("num_scenes"),
        cast(literal(None), Integer).label("target_episode_count"),
        cast(literal(None), Integer).label("default_scene_count"),
        Project.topic_type.label("topic_type"),
    ).where(Project.api_key_id == api_key_id)

    series_select = select(
        literal("series").label("kind"),
        SeriesV2.id.label("id"),
        SeriesV2.title.label("title"),
        SeriesV2.status.label("status"),
        SeriesV2.updated_at.label("updated_at"),
        SeriesV2.created_at.label("created_at"),
        SeriesV2.premise.label("preview_source"),
        cast(literal(None), String).label("input_type"),
        SeriesV2.style.label("style"),
        cast(literal(None), Integer).label("num_scenes"),
        SeriesV2.target_episode_count.label("target_episode_count"),
        SeriesV2.default_scene_count.label("default_scene_count"),
        SeriesV2.topic_type.label("topic_type"),
    ).where(SeriesV2.api_key_id == api_key_id)

    return union_all(project_select, series_select).subquery()


# Page builder guard: tests exercise this directly so API pagination semantics
# remain stable independent of FastAPI dependency wiring.
def build_history_page(
    db: Session,
    api_key_id: int,
    kind: HistoryFilter = "all",
    skip: int = 0,
    limit: int = 20,
) -> HistoryPageResponse:
    totals = _history_counts(db, api_key_id)
    total = getattr(totals, kind)
    history = _history_union_query(api_key_id)

    stmt = select(history)
    if kind in {"single", "series"}:
        stmt = stmt.where(history.c.kind == kind)

    stmt = stmt.order_by(
        desc(history.c.updated_at),
        desc(history.c.created_at),
        desc(history.c.id),
    ).offset(skip).limit(limit)

    rows = db.execute(stmt).mappings().all()
    items = [
        HistoryItem(
            kind=row["kind"],
            id=row["id"],
            title=row["title"],
            status=row["status"],
            updated_at=row["updated_at"],
            created_at=row["created_at"],
            preview=_preview(row.get("preview_source"), "Không có mô tả."),
            meta=_meta(dict(row)),
        )
        for row in rows
    ]

    return HistoryPageResponse(
        items=items,
        total=total,
        totals=totals,
        skip=skip,
        limit=limit,
    )


# Endpoint guard: this route is read-only/no-quota and intentionally separate
# from production/series generation routes.
@router.get("", response_model=HistoryPageResponse)
def list_history(
    kind: HistoryFilter = Query("all"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    api_key_check: APIKey = Depends(verify_api_key_no_quota),
) -> HistoryPageResponse:
    """Return a globally sorted, paginated archive of single projects and series.v2."""
    return build_history_page(db, api_key_check.id, kind, skip, limit)
