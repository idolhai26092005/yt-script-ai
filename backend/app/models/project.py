import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from app.core.database import Base, json_column

class Project(Base):
    """
    Bảng quản lý các dự án sinh kịch bản của người dùng (Projects).
    Lưu trữ toàn bộ vòng đời của một dự án từ lúc nhập ý tưởng đầu vào,
    các gợi ý kịch bản được sinh ra bởi AI, gợi ý được chọn,
    và kịch bản chi tiết định dạng Veo 3 cuối cùng.
    """
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True, comment="Khóa chính tự tăng")
    api_key_id = Column(
        Integer,
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID của API Key tạo dự án (Xác thực chủ sở hữu)"
    )
    title = Column(String(500), nullable=False, comment="Tiêu đề dự án")
    input_type = Column(
        String(50),
        nullable=False,
        comment="Loại nguồn đầu vào: 'topic' | 'manual' | 'youtube_url'"
    )
    input_content = Column(
        Text,
        nullable=True,
        comment="Nội dung ý tưởng gốc / Text transcript / URL YouTube"
    )
    topic_id = Column(
        Integer,
        ForeignKey("trending_topics.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID chủ đề nóng liên kết nếu chọn từ chủ đề nóng"
    )
    style = Column(
        String(100),
        default="anime",
        comment="Phong cách video (anime, realistic, cinematic, cartoon, hoặc custom)"
    )
    num_scenes = Column(
        Integer,
        default=8,
        comment="Số lượng phân cảnh mong muốn trong kịch bản (4/6/8/10/12/15/20)"
    )
    scene_duration = Column(
        Integer,
        default=8,
        comment="Thời lượng mỗi phân cảnh tính bằng giây (Veo 3 mặc định 8 giây)"
    )
    suggestions = Column(
        Text,
        nullable=True,
        comment="Chuỗi JSON danh sách 5 gợi ý kịch bản được sinh ở Bước 1"
    )
    selected_suggestion_idx = Column(
        Integer,
        nullable=True,
        comment="Index của gợi ý được chọn để sinh kịch bản chi tiết (0-4)"
    )
    script_output = Column(
        Text,
        nullable=True,
        comment="Chuỗi JSON kịch bản chi tiết 9 phần (A-I) hoàn thiện ở Bước 2"
    )
    status = Column(
        String(50),
        default="draft",
        comment="Trạng thái dự án: 'draft' | 'suggestions_generated' | 'generating_script' | 'script_generated'"
    )
    topic_type = Column(
        String(50),
        nullable=True,
        default="fictional_original",
        comment="Phân loại loại hình chủ đề của dự án"
    )
    series_id = Column(
        Integer,
        ForeignKey("series.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID của chuỗi series liên kết"
    )
    episode_number = Column(
        Integer,
        nullable=True,
        comment="Số thứ tự tập trong series"
    )
    generation_mode = Column(
        String(20),
        default="single",
        comment="Chế độ sinh: 'single' | 'longform' | 'series_short' | 'series_long'"
    )
    post_suggestions = json_column(
        nullable=True,
        comment="Các gợi ý kịch bản liên quan được sinh thêm sau khi hoàn thành"
    )
    phase_log = json_column(
        nullable=True,
        comment="Structured observability log per pipeline phase (list of dicts)"
    )

    created_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        comment="Thời gian tạo dự án"
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        comment="Thời gian cập nhật dự án gần nhất"
    )
