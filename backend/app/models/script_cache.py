import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.core.database import Base

class ScriptCache(Base):
    __tablename__ = "script_caches"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String, unique=True, index=True, nullable=False)
    master_outline = Column(Text, nullable=True)  # JSON string of outline structure
    generated_segments = Column(Text, nullable=True)  # JSON string of generated segments: { "index": { "en": "...", "vi": "..." } }
    creative_segments = Column(Text, nullable=True)  # JSON string of creative generated segments: { "index": { "en": "...", "vi": "..." } }
    suggestions = Column(Text, nullable=True)  # JSON string of next video suggestions
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None))
