from sqlalchemy import Column, String, DateTime
from app.core.database import Base
from datetime import datetime, timezone

class ProcessingLock(Base):
    __tablename__ = "processing_locks"
    
    lock_key = Column(String(255), primary_key=True)
    locked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    expires_at = Column(DateTime, nullable=False)
