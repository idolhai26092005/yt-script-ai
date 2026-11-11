import pytest
import uuid
from sqlalchemy.exc import IntegrityError
from app.core.database import SessionLocal, Base, engine
from app.models.api_key import APIKey
from app.models.series import Series
from app.models.episode import Episode
from app.models.project import Project

def test_episode_model():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 1. Create API key
        unique_hash = f"test_key_hash_ep_{uuid.uuid4()}"
        api_key = APIKey(
            key_hash=unique_hash,
            owner="test_owner_ep",
            quota_limit=10,
            quota_used=0,
            is_active=True
        )
        db.add(api_key)
        db.commit()
        db.refresh(api_key)

        # 2. Create Series
        series = Series(
            api_key_id=api_key.id,
            title="Vũ Trụ Series",
            big_idea="Khám phá vũ trụ",
            generation_mode="series_short"
        )
        db.add(series)
        db.commit()
        db.refresh(series)

        # 3. Create Project
        project = Project(
            api_key_id=api_key.id,
            title="Tập 1 Project",
            input_type="manual",
            style="cinematic"
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        # 4. Create Episode
        ep1 = Episode(
            series_id=series.id,
            episode_number=1,
            project_id=project.id,
            title="Hành tinh Đỏ",
            context_summary={"chars": []},
            next_suggestions=["A", "B", "C"],
            user_input="More action",
            status="completed"
        )
        db.add(ep1)
        db.commit()
        db.refresh(ep1)

        # Assertions
        assert ep1.id is not None
        assert ep1.series_id == series.id
        assert ep1.episode_number == 1
        assert ep1.project_id == project.id
        assert ep1.title == "Hành tinh Đỏ"
        assert ep1.context_summary == {"chars": []}
        assert ep1.next_suggestions == ["A", "B", "C"]
        assert ep1.user_input == "More action"
        assert ep1.status == "completed"

        # 5. Check UniqueConstraint(series_id, episode_number)
        ep2 = Episode(
            series_id=series.id,
            episode_number=1, # Duplicated number
            title="Hành tinh Xanh"
        )
        db.add(ep2)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        # 6. Check CASCADE delete when Series is deleted
        db.delete(series)
        db.commit()

        # Ep1 should be deleted because of cascade
        deleted_ep = db.query(Episode).filter(Episode.id == ep1.id).first()
        assert deleted_ep is None

        # Project should still exist (kept intact because project is not cascade deleted)
        kept_project = db.query(Project).filter(Project.id == project.id).first()
        assert kept_project is not None

        # Cleanup via api_key cascade; deleting project explicitly in the same
        # flush can race DB-level CASCADE from api_keys.
        db.delete(api_key)
        db.commit()

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
