"""add_series_v2_tables

Revision ID: c7b8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-07-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7b8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Series v2 migration guard: this revision is add-only so hosted deployments can
# roll forward without rewriting legacy series, episodes, or projects rows.
def upgrade() -> None:
    op.create_table(
        "series_v2",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("api_key_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("premise", sa.Text(), nullable=False),
        sa.Column("style", sa.String(length=200), nullable=False),
        sa.Column("topic_type", sa.String(length=50), nullable=False),
        sa.Column("reality_binding_level", sa.String(length=50), nullable=False),
        sa.Column("default_scene_count", sa.Integer(), nullable=False),
        sa.Column("scene_duration_sec", sa.Integer(), nullable=False),
        sa.Column("target_episode_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("series_bible", sa.JSON(), nullable=True),
        sa.Column("season_map", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_series_v2_id"), "series_v2", ["id"], unique=False)
    op.create_index(op.f("ix_series_v2_api_key_id"), "series_v2", ["api_key_id"], unique=False)

    op.create_table(
        "series_episode_v2",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("series_id", sa.Integer(), nullable=False),
        sa.Column("episode_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("brief", sa.JSON(), nullable=True),
        sa.Column("user_revision", sa.JSON(), nullable=True),
        sa.Column("scene_count", sa.Integer(), nullable=False),
        sa.Column("ending_mode", sa.String(length=50), nullable=False),
        sa.Column("episode_blueprint", sa.JSON(), nullable=True),
        sa.Column("emotion_arc", sa.JSON(), nullable=True),
        sa.Column("scenes", sa.JSON(), nullable=True),
        sa.Column("review_report", sa.JSON(), nullable=True),
        sa.Column("continuity_delta", sa.JSON(), nullable=True),
        sa.Column("script_output", sa.JSON(), nullable=True),
        sa.Column("phase_log", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["series_id"], ["series_v2.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("series_id", "episode_number", name="uq_series_v2_episode_number"),
    )
    op.create_index(op.f("ix_series_episode_v2_id"), "series_episode_v2", ["id"], unique=False)
    op.create_index(op.f("ix_series_episode_v2_series_id"), "series_episode_v2", ["series_id"], unique=False)


# Rollback guard: downgrade removes only v2 rollout tables and leaves legacy data
# available for disabling the feature flag.
def downgrade() -> None:
    op.drop_index(op.f("ix_series_episode_v2_series_id"), table_name="series_episode_v2")
    op.drop_index(op.f("ix_series_episode_v2_id"), table_name="series_episode_v2")
    op.drop_table("series_episode_v2")
    op.drop_index(op.f("ix_series_v2_api_key_id"), table_name="series_v2")
    op.drop_index(op.f("ix_series_v2_id"), table_name="series_v2")
    op.drop_table("series_v2")
