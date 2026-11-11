import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.series_v2 import SeriesEpisodeV2, SeriesV2
from app.schemas.series_v2 import SeriesV2Create
from app.services.series_v2.contracts import STATUS_ACTIVE, STATUS_PENDING


# Repository guard: all v2 writes stay on v2 tables so legacy series/project rows
# remain untouched during rollout and rollback.
class SeriesV2Repository:
    """Thin SQLAlchemy repository for series v2 data."""

    def __init__(self, db: Session):
        self.db = db

    # Create guard: series setup artifacts are saved atomically with the first
    # pending episode shell so clients can immediately edit episode 1's brief.
    def create_series(
        self,
        series_in: SeriesV2Create,
        api_key_id: int,
        *,
        reality_binding_level: str,
        series_bible: dict,
        season_map: dict,
    ) -> SeriesV2:
        db_series = SeriesV2(
            api_key_id=api_key_id,
            title=series_in.title,
            premise=series_in.premise,
            style=series_in.style,
            topic_type=series_in.topic_type,
            reality_binding_level=reality_binding_level,
            default_scene_count=series_in.default_scene_count,
            scene_duration_sec=series_in.scene_duration_sec,
            target_episode_count=series_in.target_episode_count,
            status=STATUS_ACTIVE,
            series_bible=series_bible,
            season_map=season_map,
        )
        self.db.add(db_series)
        self.db.flush()
        self.create_episode_shell(db_series, 1)
        self.db.commit()
        self.db.refresh(db_series)
        return db_series

    # Lookup guard: every series read includes api_key ownership to keep v2
    # routes from exposing artifacts across users.
    def get_series(self, series_id: int, api_key_id: int) -> SeriesV2 | None:
        return self.db.query(SeriesV2).filter(
            SeriesV2.id == series_id,
            SeriesV2.api_key_id == api_key_id,
        ).first()

    # List guard: v2 list never reads legacy tables, preventing mixed contracts
    # under the same `/series` path.
    def list_series(self, api_key_id: int, skip: int = 0, limit: int = 100) -> list[SeriesV2]:
        return self.db.query(SeriesV2).filter(
            SeriesV2.api_key_id == api_key_id,
        ).order_by(SeriesV2.updated_at.desc()).offset(skip).limit(limit).all()

    # Pagination guard: series history needs a total count without mixing in
    # legacy `series` rows that share the public route prefix.
    def count_series(self, api_key_id: int) -> int:
        return self.db.query(SeriesV2).filter(SeriesV2.api_key_id == api_key_id).count()

    # Delete guard: only owned series.v2 rows are deleted; cascade removes v2
    # episodes while legacy tables and Project rows remain untouched.
    def delete_series(self, series_id: int, api_key_id: int) -> bool:
        db_series = self.get_series(series_id, api_key_id)
        if not db_series:
            return False
        self.db.delete(db_series)
        self.db.commit()
        return True

    # Episode shell guard: IntegrityError fallback makes reconnect or repeated
    # next-episode creation idempotent without skipping episode numbers.
    def create_episode_shell(self, series: SeriesV2, episode_number: int) -> SeriesEpisodeV2:
        slot = next(
            (
                item for item in (series.season_map or {}).get("episode_slots", [])
                if item.get("episode_number") == episode_number
            ),
            {},
        )
        db_episode = SeriesEpisodeV2(
            series_id=series.id,
            episode_number=episode_number,
            status=STATUS_PENDING,
            title=slot.get("title") or f"Tap {episode_number}",
            scene_count=int(slot.get("scene_count") or series.default_scene_count),
            ending_mode=slot.get("ending_mode") or ("season_finale" if episode_number >= series.target_episode_count else "open_loop"),
            phase_log=[],
        )
        self.db.add(db_episode)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            existing = self.get_episode_by_number(series.id, episode_number)
            if existing:
                return existing
            raise
        return db_episode

    # Episode lookup guard: episode numbers are the public ordered contract,
    # separate from database row ids.
    def get_episode_by_number(self, series_id: int, episode_number: int) -> SeriesEpisodeV2 | None:
        return self.db.query(SeriesEpisodeV2).filter(
            SeriesEpisodeV2.series_id == series_id,
            SeriesEpisodeV2.episode_number == episode_number,
        ).first()

    # Episode list guard: clients and brief builder receive deterministic order.
    def list_episodes(self, series_id: int) -> list[SeriesEpisodeV2]:
        return self.db.query(SeriesEpisodeV2).filter(
            SeriesEpisodeV2.series_id == series_id,
        ).order_by(SeriesEpisodeV2.episode_number.asc()).all()

    # Artifact update guard: centralizing field writes keeps phase checkpoints
    # reviewable and avoids endpoint-side mutation.
    def update_episode(self, episode: SeriesEpisodeV2, **fields: Any) -> SeriesEpisodeV2:
        for key, value in fields.items():
            setattr(episode, key, value)
        episode.updated_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        self.db.commit()
        self.db.refresh(episode)
        return episode

    # Recovery reset guard: restart may clear generated artifacts, but it must
    # preserve the accepted brief/user revision that the operator approved.
    def reset_episode_artifacts(self, episode: SeriesEpisodeV2) -> SeriesEpisodeV2:
        return self.update_episode(
            episode,
            episode_blueprint=None,
            emotion_arc=None,
            scenes=None,
            review_report=None,
            continuity_delta=None,
            script_output=None,
            phase_log=[],
            status=STATUS_PENDING,
        )

    # Phase-log guard: append by copying the list so JSON mutation is detected by
    # SQLAlchemy across SQLite and PostgreSQL.
    def append_phase_log(self, episode: SeriesEpisodeV2, entry: dict[str, Any]) -> SeriesEpisodeV2:
        current = episode.phase_log if isinstance(episode.phase_log, list) else []
        episode.phase_log = [*current, entry]
        episode.updated_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        self.db.commit()
        self.db.refresh(episode)
        return episode
