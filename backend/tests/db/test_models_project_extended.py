import pytest
import uuid
from app.core.database import SessionLocal, Base, engine
from app.models.api_key import APIKey
from app.models.project import Project
from app.models.series import Series

def test_project_extended_model():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Create API Key
        unique_hash = f"test_key_hash_proj_ext_{uuid.uuid4()}"
        api_key = APIKey(
            key_hash=unique_hash,
            owner="test_owner_proj_ext",
            quota_limit=10,
            quota_used=0,
            is_active=True
        )
        db.add(api_key)
        db.commit()
        db.refresh(api_key)

        # 1. Test backward compatibility: project without series data (all NULL / defaults)
        project_old = Project(
            api_key_id=api_key.id,
            title="Old style project",
            input_type="manual"
        )
        db.add(project_old)
        db.commit()
        db.refresh(project_old)

        assert project_old.series_id is None
        assert project_old.episode_number is None
        assert project_old.generation_mode == "single"
        assert project_old.post_suggestions is None

        # 2. Test project linked to a series
        series = Series(
            api_key_id=api_key.id,
            title="Cuộc Di Cư 2",
            big_idea="Bướm đi cư",
            generation_mode="series_short"
        )
        db.add(series)
        db.commit()
        db.refresh(series)

        project_new = Project(
            api_key_id=api_key.id,
            title="Tập 1",
            input_type="manual",
            series_id=series.id,
            episode_number=1,
            generation_mode="series_short",
            post_suggestions=[{"title": "Gợi ý 1"}]
        )
        db.add(project_new)
        db.commit()
        db.refresh(project_new)

        assert project_new.series_id == series.id
        assert project_new.episode_number == 1
        assert project_new.generation_mode == "series_short"
        assert project_new.post_suggestions == [{"title": "Gợi ý 1"}]

        # Cleanup: only delete api_key, CASCADE deletes projects and series
        db.delete(api_key)
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
