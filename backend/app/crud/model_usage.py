from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.model_usage import ModelUsage


def get_today_usage(db: Session, api_key_id: int, model_name: str) -> ModelUsage | None:
    """Lấy usage record của model hôm nay. Trả về None nếu chưa có."""
    today = datetime.now(timezone.utc).date()
    return db.query(ModelUsage).filter(
        ModelUsage.api_key_id == api_key_id,
        ModelUsage.model_name == model_name,
        ModelUsage.usage_date == today
    ).first()


def increment_model_usage(db: Session, api_key_id: int, model_name: str) -> ModelUsage | None:
    """Tăng request_count cho model hôm nay. Tạo mới nếu chưa có record."""
    today = datetime.now(timezone.utc).date()
    try:
        record = get_today_usage(db, api_key_id, model_name)
        if record:
            record.request_count += 1
            record.last_request_at = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            record = ModelUsage(
                api_key_id=api_key_id,
                model_name=model_name,
                usage_date=today,
                request_count=1,
                last_request_at=datetime.now(timezone.utc).replace(tzinfo=None)
            )
            db.add(record)
        db.commit()
        db.refresh(record)
        return record
    except Exception:
        db.rollback()
        # If it failed (likely concurrent insert), try to update the existing record
        try:
            record = get_today_usage(db, api_key_id, model_name)
            if record:
                record.request_count += 1
                record.last_request_at = datetime.now(timezone.utc).replace(tzinfo=None)
                db.commit()
                db.refresh(record)
                return record
        except Exception:
            db.rollback()
    return None


def get_all_today_usage(db: Session, api_key_id: int) -> list[ModelUsage]:
    """Lấy tất cả usage record hôm nay cho một API key."""
    today = datetime.now(timezone.utc).date()
    return db.query(ModelUsage).filter(
        ModelUsage.api_key_id == api_key_id,
        ModelUsage.usage_date == today
    ).all()


def cleanup_old_usage(db: Session, days_to_keep: int = 7):
    """Xóa record cũ hơn N ngày."""
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=days_to_keep)
    db.query(ModelUsage).filter(ModelUsage.usage_date < cutoff).delete()
    db.commit()
