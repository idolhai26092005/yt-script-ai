import os

import pytest

os.environ.setdefault("TESTING", "True")
os.environ.setdefault("TEST_DATABASE_URL", "sqlite:////tmp/yt_script_ai_pytest.db")

from app.core.database import Base, SessionLocal, engine
from app.models import *  # noqa: F403,F401


# Shared DB fixture guard: new DB-facing tests must use one isolated lifecycle
# instead of touching the developer SQLite file or leaking rows across tests.
@pytest.fixture()
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
