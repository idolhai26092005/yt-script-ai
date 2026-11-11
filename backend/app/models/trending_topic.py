import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from app.core.database import Base

class TrendingTopic(Base):
    """
    Bảng quản lý các chủ đề nóng (Trending Topics).
    Admin có thể CRUD các chủ đề này thủ công.
    Người dùng sẽ chọn các chủ đề này trên trang chủ để AI sinh gợi ý kịch bản.
    """
    __tablename__ = "trending_topics"

    id = Column(Integer, primary_key=True, index=True, comment="Khóa chính tự tăng")
    name = Column(String(255), nullable=False, comment="Tên chủ đề hiển thị trên UI")
    description = Column(Text, nullable=True, comment="Mô tả chi tiết về chủ đề")
    icon = Column(String(10), default="🔥", comment="Emoji hoặc ký tự đại diện")
    display_order = Column(Integer, default=0, comment="Thứ tự hiển thị (nhỏ đứng trước)")
    is_active = Column(Boolean, default=True, comment="Cờ bật/tắt hiển thị trên client")
    created_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        comment="Thời gian tạo bản ghi"
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        comment="Thời gian cập nhật gần nhất"
    )
