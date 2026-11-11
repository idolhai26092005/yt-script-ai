import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base, json_column

class Series(Base):
    """
    Bảng quản lý các chuỗi video (Series) của người dùng.
    """
    __tablename__ = "series"

    id = Column(Integer, primary_key=True, index=True, comment="Khóa chính tự tăng")
    api_key_id = Column(
        Integer,
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID của API Key tạo series"
    )
    title = Column(String(500), nullable=False, comment="Tiêu đề series")
    big_idea = Column(Text, nullable=True, comment="Ý tưởng gốc từ người dùng")
    series_outline = json_column(nullable=True, comment="JSON lưu kế hoạch chuỗi các tập")
    generation_mode = Column(
        String(20),
        nullable=False,
        default="series_short",
        comment="Chế độ sinh: 'series_short' | 'series_long'"
    )
    episode_duration_minutes = Column(Integer, nullable=True, comment="Thời lượng mỗi tập (chỉ dùng cho series_long)")
    style = Column(String(100), default="anime", comment="Phong cách video của series")
    status = Column(String(50), default="active", comment="Trạng thái: 'active' | 'archived'")
    # Fix S5: Character sheet chuẩn từ Episode 1 — bất biến xuyên suốt series để chống drift nhân vật
    canonical_character_sheet = json_column(
        nullable=True,
        comment="JSON lưu danh sách nhân vật chuẩn từ Episode 1 (canonical visual locks)"
    )

    
    created_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        comment="Thời gian tạo"
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        comment="Thời gian cập nhật gần nhất"
    )

    # Relationships
    episodes = relationship("Episode", back_populates="series", cascade="all, delete-orphan")
