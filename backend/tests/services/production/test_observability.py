import pytest
from datetime import datetime
from app.core.database import SessionLocal, Base, engine
from app.models.project import Project
from app.core.repository import SQLAlchemyScreenplayRepository, StubScreenplayRepository

def setup_module(module):
    # Ensure test database schema is clean and contains new columns
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_stub_repository_observability():

    repo = StubScreenplayRepository()
    
    # 1. Reset log
    repo.reset_phase_log(1)
    assert repo.projects[1]["phase_log"] == []
    
    # 2. Append log
    repo.append_phase_log(1, "metadata", "1.1", [], 120.5)
    assert len(repo.projects[1]["phase_log"]) == 1
    assert repo.projects[1]["phase_log"][0]["stage_role"] == "metadata"
    assert repo.projects[1]["phase_log"][0]["schema_version"] == "1.1"
    datetime.fromisoformat(repo.projects[1]["phase_log"][0]["timestamp"])
    assert repo.projects[1]["phase_log"][0]["validation_errors"] == []
    assert repo.projects[1]["phase_log"][0]["latency_ms"] == 120.5
    
    # 3. Append another
    repo.append_phase_log(1, "scenes", "1.1", ["Error 1"], 340.0)
    assert len(repo.projects[1]["phase_log"]) == 2
    assert repo.projects[1]["phase_log"][1]["stage_role"] == "scenes"
    assert repo.projects[1]["phase_log"][1]["validation_errors"] == ["Error 1"]
    
    # 4. Reset again
    repo.reset_phase_log(1)
    assert repo.projects[1]["phase_log"] == []

def test_sql_repository_observability():
    db = SessionLocal()
    try:
        # Create a temp project
        proj = Project(
            api_key_id=1,  # Must match a valid API Key in db or ignore FK for stub testing if FK constraint is off, but wait, FK constraint is on.
            title="Test project for logging",
            input_type="manual",
            status="draft"
        )
        # Find a valid API key first to satisfy foreign key constraint
        from app.models.api_key import APIKey
        key = db.query(APIKey).first()
        if not key:
            key = APIKey(key_hash="test_key_obs", owner="test_user_obs")

            db.add(key)
            db.commit()
            db.refresh(key)
            
        proj.api_key_id = key.id
        db.add(proj)
        db.commit()
        db.refresh(proj)
        
        repo = SQLAlchemyScreenplayRepository(db_session=db)
        
        # 1. Reset log
        repo.reset_phase_log(proj.id)
        db.refresh(proj)
        assert proj.phase_log == []
        
        # 2. Append log
        repo.append_phase_log(proj.id, "metadata", "1.1", ["Err!"], 150.0)
        db.refresh(proj)
        assert len(proj.phase_log) == 1
        assert proj.phase_log[0]["stage_role"] == "metadata"
        datetime.fromisoformat(proj.phase_log[0]["timestamp"])
        assert proj.phase_log[0]["validation_errors"] == ["Err!"]
        assert proj.phase_log[0]["latency_ms"] == 150.0
        
        # Clean up
        db.delete(proj)
        db.commit()
    finally:
        db.close()
