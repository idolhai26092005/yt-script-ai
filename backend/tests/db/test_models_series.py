import pytest
import uuid
from app.core.database import SessionLocal, Base, engine
from app.models.api_key import APIKey
from app.models.series import Series

def test_series_model():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Create an API key first with unique key_hash
        unique_hash = f"test_key_hash_series_{uuid.uuid4()}"
        api_key = APIKey(
            key_hash=unique_hash,
            owner="test_owner_series",
            quota_limit=10,
            quota_used=0,
            is_active=True
        )
        db.add(api_key)
        db.commit()
        db.refresh(api_key)

        # Create series
        series = Series(
            api_key_id=api_key.id,
            title="Cuộc Di Cư Vĩ Đại",
            big_idea="Loài bướm di cư",
            series_outline={"episodes": [{"num": 1, "title": "Bắt đầu"}]},
            generation_mode="series_short",
            style="anime"
        )
        db.add(series)
        db.commit()
        db.refresh(series)

        # Assert fields
        assert series.id is not None
        assert series.title == "Cuộc Di Cư Vĩ Đại"
        assert series.big_idea == "Loài bướm di cư"
        assert series.series_outline["episodes"][0]["title"] == "Bắt đầu"
        assert series.generation_mode == "series_short"
        assert series.style == "anime"
        assert series.status == "active"
        assert series.created_at is not None

        # Clean up via api_key cascade to avoid double-deleting the series row.
        db.delete(api_key)
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
