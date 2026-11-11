from sqlalchemy import Column, String, DateTime, Text, UniqueConstraint
from app.core.database import Base
from datetime import datetime, timezone

class BackgroundTask(Base):
    __tablename__ = "background_tasks"
    
    task_id = Column(String(255), primary_key=True)
    status = Column(String(50), nullable=False)  # pending, processing, completed, failed
    video_id = Column(String(255), nullable=False)
    model_name = Column(String(100), nullable=False)
    result = Column(Text, nullable=True)  # JSON string of suggestions
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    __table_args__ = (
        UniqueConstraint('video_id', 'model_name', name='uq_video_model_task'),
    )
