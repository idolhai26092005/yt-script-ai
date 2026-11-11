import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.core.database import Base

class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String, unique=True, index=True, nullable=False)
    url = Column(String, nullable=False)
    transcript = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None))
