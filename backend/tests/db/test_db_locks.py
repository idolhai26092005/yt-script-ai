import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, Base, engine
from app.models.processing_lock import ProcessingLock
from unittest.mock import MagicMock, patch

@pytest.mark.asyncio
async def test_processing_lock_lifecycle():
    # Setup clean tables
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    lock_key = "test_integration_lock_key"
    try:
        # 1. Clean existing
        db.query(ProcessingLock).filter(ProcessingLock.lock_key == lock_key).delete()
        db.commit()

        # 2. Acquire lock
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        lock = ProcessingLock(
            lock_key=lock_key,
            expires_at=now_utc + timedelta(minutes=5)
        )
        db.add(lock)
        db.commit()

        # Check lock exists and is active
        db_lock = db.query(ProcessingLock).filter(ProcessingLock.lock_key == lock_key).first()
        assert db_lock is not None
        assert db_lock.lock_key == lock_key
        assert db_lock.expires_at > datetime.now(timezone.utc).replace(tzinfo=None)

        # 3. Release lock
        db.query(ProcessingLock).filter(ProcessingLock.lock_key == lock_key).delete()
        db.commit()

        db_lock_after = db.query(ProcessingLock).filter(ProcessingLock.lock_key == lock_key).first()
        assert db_lock_after is None
    finally:
        db.close()
