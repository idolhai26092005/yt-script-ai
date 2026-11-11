import datetime as dt

from sqlalchemy.orm import Session

from app.api.v1.endpoints.history import build_history_page
from app.crud.api_key import create_api_key
from app.models.project import Project
from app.models.series_v2 import SeriesV2
from app.schemas.api_key import APIKeyCreate


# Seed guard: history tests need both row families under multiple API keys so
# ownership and global pagination can fail loudly if the union query regresses.
def _seed_history_rows(db: Session):
    _, owner_key = create_api_key(db, APIKeyCreate(owner="History Owner", quota_limit=20))
    _, other_key = create_api_key(db, APIKeyCreate(owner="History Other", quota_limit=20))
    base = dt.datetime(2026, 1, 1, 12, 0, 0)

    rows = {
        "old_project": Project(
            api_key_id=owner_key.id,
            title="Old single project",
            input_type="manual",
            input_content="A compact old single idea",
            style="cinematic",
            num_scenes=6,
            status="suggestions_generated",
            topic_type="fictional_original",
            created_at=base,
            updated_at=base + dt.timedelta(minutes=1),
        ),
        "mid_project": Project(
            api_key_id=owner_key.id,
            title="Mid single project",
            input_type="topic",
            input_content="A newer single idea",
            style="modern",
            num_scenes=8,
            status="script_generated",
            topic_type="scientific",
            created_at=base,
            updated_at=base + dt.timedelta(minutes=2),
        ),
        "new_series": SeriesV2(
            api_key_id=owner_key.id,
            title="Newest series",
            premise="A linked multi-episode premise",
            style="modern-minimal",
            topic_type="fictional_original",
            default_scene_count=7,
            target_episode_count=5,
            status="active",
            created_at=base,
            updated_at=base + dt.timedelta(minutes=3),
        ),
        "foreign_series": SeriesV2(
            api_key_id=other_key.id,
            title="Foreign series",
            premise="Must never appear for the owner key",
            style="modern-minimal",
            topic_type="historical",
            default_scene_count=9,
            target_episode_count=4,
            status="active",
            created_at=base,
            updated_at=base + dt.timedelta(minutes=9),
        ),
    }
    db.add_all(rows.values())
    db.commit()
    return owner_key, other_key, rows


# Global ordering guard: `all` combines Project and SeriesV2 before paginating
# so the latest row wins even when it comes from a different table.
def test_history_all_returns_owned_rows_sorted_by_updated_at(db_session: Session):
    owner_key, _, _ = _seed_history_rows(db_session)

    page = build_history_page(db_session, owner_key.id, kind="all", skip=0, limit=10)

    assert page.total == 3
    assert page.totals.all == 3
    assert page.totals.single == 2
    assert page.totals.series == 1
    assert [(item.kind, item.title) for item in page.items] == [
        ("series", "Newest series"),
        ("single", "Mid single project"),
        ("single", "Old single project"),
    ]
    assert "Foreign series" not in [item.title for item in page.items]


# Filter guard: single and series filters share the same totals object while
# returning only the requested kind of lightweight history row.
def test_history_filters_single_and_series(db_session: Session):
    owner_key, _, _ = _seed_history_rows(db_session)

    single_page = build_history_page(db_session, owner_key.id, kind="single", skip=0, limit=10)
    series_page = build_history_page(db_session, owner_key.id, kind="series", skip=0, limit=10)

    assert single_page.total == 2
    assert [item.kind for item in single_page.items] == ["single", "single"]
    assert series_page.total == 1
    assert [(item.kind, item.title) for item in series_page.items] == [("series", "Newest series")]
    assert series_page.totals.all == 3


# Page metadata guard: skip/limit/total remain stable for numbered desktop
# pagination and mobile load-more.
def test_history_skip_limit_and_total_are_stable(db_session: Session):
    owner_key, _, _ = _seed_history_rows(db_session)

    page = build_history_page(db_session, owner_key.id, kind="single", skip=1, limit=1)

    assert page.skip == 1
    assert page.limit == 1
    assert page.total == 2
    assert len(page.items) == 1
    assert page.items[0].title == "Old single project"


# Ownership guard: another API key cannot see the owner's projects or series,
# even when rows exist in both tables.
def test_history_api_key_isolation(db_session: Session):
    _, other_key, _ = _seed_history_rows(db_session)

    page = build_history_page(db_session, other_key.id, kind="all", skip=0, limit=10)

    assert page.total == 1
    assert [(item.kind, item.title) for item in page.items] == [("series", "Foreign series")]
