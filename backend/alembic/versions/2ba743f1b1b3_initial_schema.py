"""Initial schema

Revision ID: 2ba743f1b1b3
Revises: 
Create Date: 2026-07-02 21:37:45.914251

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ba743f1b1b3'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. api_keys
    if 'api_keys' not in tables:
        op.create_table('api_keys',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('key_hash', sa.String(), nullable=False),
            sa.Column('owner', sa.String(), nullable=False),
            sa.Column('quota_limit', sa.Integer(), nullable=True),
            sa.Column('quota_used', sa.Integer(), nullable=True),
            sa.Column('expiry', sa.DateTime(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_api_keys_id'), 'api_keys', ['id'], unique=False)
        op.create_index(op.f('ix_api_keys_key_hash'), 'api_keys', ['key_hash'], unique=True)

    # 2. background_tasks
    if 'background_tasks' not in tables:
        op.create_table('background_tasks',
            sa.Column('task_id', sa.String(length=255), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('video_id', sa.String(length=255), nullable=False),
            sa.Column('model_name', sa.String(length=100), nullable=False),
            sa.Column('result', sa.Text(), nullable=True),
            sa.Column('error', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('task_id')
        )

    # 3. processing_locks
    if 'processing_locks' not in tables:
        op.create_table('processing_locks',
            sa.Column('lock_key', sa.String(length=255), nullable=False),
            sa.Column('locked_at', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('lock_key')
        )

    # 4. script_caches
    if 'script_caches' not in tables:
        op.create_table('script_caches',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('video_id', sa.String(), nullable=False),
            sa.Column('master_outline', sa.Text(), nullable=True),
            sa.Column('generated_segments', sa.Text(), nullable=True),
            sa.Column('creative_segments', sa.Text(), nullable=True),
            sa.Column('suggestions', sa.Text(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_script_caches_id'), 'script_caches', ['id'], unique=False)
        op.create_index(op.f('ix_script_caches_video_id'), 'script_caches', ['video_id'], unique=True)

    # 5. transcripts
    if 'transcripts' not in tables:
        op.create_table('transcripts',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('video_id', sa.String(), nullable=False),
            sa.Column('url', sa.String(), nullable=False),
            sa.Column('transcript', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_transcripts_id'), 'transcripts', ['id'], unique=False)
        op.create_index(op.f('ix_transcripts_video_id'), 'transcripts', ['video_id'], unique=True)

    # 6. trending_topics
    if 'trending_topics' not in tables:
        op.create_table('trending_topics',
            sa.Column('id', sa.Integer(), nullable=False, comment='Khóa chính tự tăng'),
            sa.Column('name', sa.String(length=255), nullable=False, comment='Tên chủ đề hiển thị trên UI'),
            sa.Column('description', sa.Text(), nullable=True, comment='Mô tả chi tiết về chủ đề'),
            sa.Column('icon', sa.String(length=10), nullable=True, comment='Emoji hoặc ký tự đại diện'),
            sa.Column('display_order', sa.Integer(), nullable=True, comment='Thứ tự hiển thị (nhỏ đứng trước)'),
            sa.Column('is_active', sa.Boolean(), nullable=True, comment='Cờ bật/tắt hiển thị trên client'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='Thời gian tạo bản ghi'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='Thời gian cập nhật gần nhất'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_trending_topics_id'), 'trending_topics', ['id'], unique=False)

    # 7. model_usage
    if 'model_usage' not in tables:
        op.create_table('model_usage',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('api_key_id', sa.Integer(), nullable=False),
            sa.Column('model_name', sa.String(), nullable=False),
            sa.Column('usage_date', sa.Date(), nullable=False),
            sa.Column('request_count', sa.Integer(), nullable=True),
            sa.Column('last_request_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('api_key_id', 'model_name', 'usage_date', name='uq_usage_per_day')
        )
        op.create_index(op.f('ix_model_usage_api_key_id'), 'model_usage', ['api_key_id'], unique=False)
        op.create_index(op.f('ix_model_usage_id'), 'model_usage', ['id'], unique=False)

    # 8. projects
    if 'projects' not in tables:
        op.create_table('projects',
            sa.Column('id', sa.Integer(), nullable=False, comment='Khóa chính tự tăng'),
            sa.Column('api_key_id', sa.Integer(), nullable=False, comment='ID của API Key tạo dự án (Xác thực chủ sở hữu)'),
            sa.Column('title', sa.String(length=500), nullable=False, comment='Tiêu đề dự án'),
            sa.Column('input_type', sa.String(length=50), nullable=False, comment="Loại nguồn đầu vào: 'topic' | 'manual' | 'youtube_url'"),
            sa.Column('input_content', sa.Text(), nullable=True, comment='Nội dung ý tưởng gốc / Text transcript / URL YouTube'),
            sa.Column('topic_id', sa.Integer(), nullable=True, comment='ID chủ đề nóng liên kết nếu chọn từ chủ đề nóng'),
            sa.Column('style', sa.String(length=100), nullable=True, comment='Phong cách video (anime, realistic, cinematic, cartoon, hoặc custom)'),
            sa.Column('num_scenes', sa.Integer(), nullable=True, comment='Số lượng phân cảnh mong muốn trong kịch bản (4/6/8/10/12)'),
            sa.Column('scene_duration', sa.Integer(), nullable=True, comment='Thời lượng mỗi phân cảnh tính bằng giây (Veo 3 mặc định 8 giây)'),
            sa.Column('suggestions', sa.Text(), nullable=True, comment='Chuỗi JSON danh sách 5 gợi ý kịch bản được sinh ở Bước 1'),
            sa.Column('selected_suggestion_idx', sa.Integer(), nullable=True, comment='Index của gợi ý được chọn để sinh kịch bản chi tiết (0-4)'),
            sa.Column('script_output', sa.Text(), nullable=True, comment='Chuỗi JSON kịch bản chi tiết 9 phần (A-I) hoàn thiện ở Bước 2'),
            sa.Column('status', sa.String(length=50), nullable=True, comment="Trạng thái dự án: 'draft' | 'suggestions_generated' | 'generating_script' | 'script_generated'"),
            sa.Column('topic_type', sa.String(length=50), nullable=True, comment='Phân loại loại hình chủ đề của dự án'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='Thời gian tạo dự án'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='Thời gian cập nhật dự án gần nhất'),
            sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['topic_id'], ['trending_topics.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_projects_api_key_id'), 'projects', ['api_key_id'], unique=False)
        op.create_index(op.f('ix_projects_id'), 'projects', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # Drop in reverse dependency order
    if 'projects' in tables:
        op.drop_index(op.f('ix_projects_id'), table_name='projects')
        op.drop_index(op.f('ix_projects_api_key_id'), table_name='projects')
        op.drop_table('projects')

    if 'model_usage' in tables:
        op.drop_index(op.f('ix_model_usage_id'), table_name='model_usage')
        op.drop_index(op.f('ix_model_usage_api_key_id'), table_name='model_usage')
        op.drop_table('model_usage')

    if 'trending_topics' in tables:
        op.drop_index(op.f('ix_trending_topics_id'), table_name='trending_topics')
        op.drop_table('trending_topics')

    if 'transcripts' in tables:
        op.drop_index(op.f('ix_transcripts_video_id'), table_name='transcripts')
        op.drop_index(op.f('ix_transcripts_id'), table_name='transcripts')
        op.drop_table('transcripts')

    if 'script_caches' in tables:
        op.drop_index(op.f('ix_script_caches_video_id'), table_name='script_caches')
        op.drop_index(op.f('ix_script_caches_id'), table_name='script_caches')
        op.drop_table('script_caches')

    if 'processing_locks' in tables:
        op.drop_table('processing_locks')

    if 'background_tasks' in tables:
        op.drop_table('background_tasks')

    if 'api_keys' in tables:
        op.drop_index(op.f('ix_api_keys_key_hash'), table_name='api_keys')
        op.drop_index(op.f('ix_api_keys_id'), table_name='api_keys')
        op.drop_table('api_keys')
