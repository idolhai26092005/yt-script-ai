from sqlalchemy.orm import Session
from app.models.trending_topic import TrendingTopic
import datetime

def get_topic_by_id(db: Session, topic_id: int) -> TrendingTopic | None:
    """Lấy thông tin chi tiết một chủ đề bằng ID."""
    return db.query(TrendingTopic).filter(TrendingTopic.id == topic_id).first()

def get_active_topics(db: Session) -> list[TrendingTopic]:
    """Lấy danh sách các chủ đề đang hiển thị (is_active=True), sắp xếp theo display_order."""
    return db.query(TrendingTopic).filter(TrendingTopic.is_active == True).order_by(
        TrendingTopic.display_order.asc(),
        TrendingTopic.id.asc()
    ).all()

def get_all_topics(db: Session) -> list[TrendingTopic]:
    """Lấy tất cả các chủ đề (bao gồm cả ẩn), sắp xếp theo display_order."""
    return db.query(TrendingTopic).order_by(
        TrendingTopic.display_order.asc(),
        TrendingTopic.id.asc()
    ).all()

def create_topic(
    db: Session,
    name: str,
    description: str = "",
    icon: str = "🔥",
    display_order: int = 0
) -> TrendingTopic:
    """Tạo mới một chủ đề nóng."""
    db_topic = TrendingTopic(
        name=name,
        description=description,
        icon=icon,
        display_order=display_order,
        is_active=True
    )
    db.add(db_topic)
    db.commit()
    db.refresh(db_topic)
    return db_topic

def update_topic(
    db: Session,
    topic_id: int,
    name: str | None = None,
    description: str | None = None,
    icon: str | None = None,
    display_order: int | None = None,
    is_active: bool | None = None
) -> TrendingTopic | None:
    """Cập nhật thông tin chủ đề nóng."""
    db_topic = get_topic_by_id(db, topic_id)
    if not db_topic:
        return None

    if name is not None:
        db_topic.name = name
    if description is not None:
        db_topic.description = description
    if icon is not None:
        db_topic.icon = icon
    if display_order is not None:
        db_topic.display_order = display_order
    if is_active is not None:
        db_topic.is_active = is_active

    db_topic.updated_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(db_topic)
    return db_topic

def delete_topic(db: Session, topic_id: int) -> bool:
    """Xóa chủ đề nóng khỏi database."""
    db_topic = get_topic_by_id(db, topic_id)
    if db_topic:
        db.delete(db_topic)
        db.commit()
        return True
    return False

def toggle_topic(db: Session, topic_id: int) -> TrendingTopic | None:
    """Bật/tắt trạng thái hiển thị (is_active) của chủ đề."""
    db_topic = get_topic_by_id(db, topic_id)
    if not db_topic:
        return None
    db_topic.is_active = not db_topic.is_active
    db_topic.updated_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(db_topic)
    return db_topic

def reorder_topics(db: Session, ids: list[int]) -> bool:
    """Sắp xếp lại display_order dựa trên danh sách ID truyền xuống."""
    for idx, topic_id in enumerate(ids):
        db_topic = get_topic_by_id(db, topic_id)
        if db_topic:
            db_topic.display_order = idx
            db_topic.updated_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    db.commit()
    return True
