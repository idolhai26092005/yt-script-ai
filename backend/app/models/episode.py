import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base, json_column

class Episode(Base):
    """
    Bảng quản lý các tập (Episode) trong một chuỗi video (Series).
    """
    __tablename__ = "episodes"

    id = Column(Integer, primary_key=True, index=True, comment="Khóa chính tự tăng")
    series_id = Column(
        Integer,
        ForeignKey("series.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID của Series quản lý"
    )
    episode_number = Column(Integer, nullable=False, comment="Số thứ tự tập (bắt đầu từ 1)")
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Dự án kịch bản tương ứng của tập này"
    )
    title = Column(String(500), nullable=True, comment="Tiêu đề của tập này")
    context_summary = json_column(nullable=True, comment="JSON lưu ngữ cảnh nén của tập này")
    next_suggestions = json_column(nullable=True, comment="JSON lưu 3 gợi ý cho tập tiếp theo")
    user_input = Column(Text, nullable=True, comment="Ý kiến/phản hồi tùy chỉnh của người dùng cho tập này")
    status = Column(String(50), default="pending", comment="Trạng thái tập: 'pending' | 'generating' | 'completed'")
    
    created_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        comment="Thời gian tạo"
    )

    # Relationships
    series = relationship("Series", back_populates="episodes")
    project = relationship("Project")

    # Constraints
    __table_args__ = (
        UniqueConstraint("series_id", "episode_number", name="uq_series_episode"),
    )
