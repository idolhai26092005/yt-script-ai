import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.core.database import Base

class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key_hash = Column(String, unique=True, index=True, nullable=False)
    owner = Column(String, nullable=False)
    quota_limit = Column(Integer, default=100)
    quota_used = Column(Integer, default=0)
    expiry = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None))
