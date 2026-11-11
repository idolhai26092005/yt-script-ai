"""add_canonical_character_sheet_to_series

Revision ID: a1b2c3d4e5f6
Revises: 8d63d0f7732b
Create Date: 2026-07-17

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '8d63d0f7732b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add canonical_character_sheet column to series table."""
    op.add_column('series',
        sa.Column(
            'canonical_character_sheet',
            sa.JSON(),
            nullable=True,
            comment="JSON luu danh sach nhan vat chuan tu Episode 1"
        )
    )


def downgrade() -> None:
    """Remove canonical_character_sheet column from series table."""
    op.drop_column('series', 'canonical_character_sheet')
