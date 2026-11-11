import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base, json_column


# Series v2 storage guard: keep the rebuilt series pipeline on add-only tables so
# legacy series rows remain available for rollback and no Project coupling leaks in.
class SeriesV2(Base):
    """Database row for the v2 series-level artifacts."""

    __tablename__ = "series_v2"

    id = Column(Integer, primary_key=True, index=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    premise = Column(Text, nullable=False)
    style = Column(String(200), nullable=False, default="anime")
    topic_type = Column(String(50), nullable=False, default="fictional_original")
    reality_binding_level = Column(String(50), nullable=False, default="soft")
    default_scene_count = Column(Integer, nullable=False, default=8)
    scene_duration_sec = Column(Integer, nullable=False, default=8)
    target_episode_count = Column(Integer, nullable=False, default=5)
    status = Column(String(50), nullable=False, default="active")
    series_bible = json_column(nullable=True)
    season_map = json_column(nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    episodes = relationship("SeriesEpisodeV2", back_populates="series", cascade="all, delete-orphan")


# Episode v2 storage guard: all per-episode artifacts live beside the series row
# so generation can resume without creating legacy Project rows.
class SeriesEpisodeV2(Base):
    """Database row for one generated or pending v2 series episode."""

    __tablename__ = "series_episode_v2"
    __table_args__ = (
        UniqueConstraint("series_id", "episode_number", name="uq_series_v2_episode_number"),
    )

    id = Column(Integer, primary_key=True, index=True)
    series_id = Column(Integer, ForeignKey("series_v2.id", ondelete="CASCADE"), nullable=False, index=True)
    episode_number = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    title = Column(String(500), nullable=True)
    brief = json_column(nullable=True)
    user_revision = json_column(nullable=True)
    scene_count = Column(Integer, nullable=False, default=8)
    ending_mode = Column(String(50), nullable=False, default="open_loop")
    episode_blueprint = json_column(nullable=True)
    emotion_arc = json_column(nullable=True)
    scenes = json_column(nullable=True)
    review_report = json_column(nullable=True)
    continuity_delta = json_column(nullable=True)
    script_output = json_column(nullable=True)
    phase_log = json_column(nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    series = relationship("SeriesV2", back_populates="episodes")
