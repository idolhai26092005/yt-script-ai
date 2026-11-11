from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, UniqueConstraint
from app.core.database import Base


class ModelUsage(Base):
    __tablename__ = "model_usage"

    id = Column(Integer, primary_key=True, index=True)
    api_key_id = Column(
        Integer,
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    model_name = Column(String, nullable=False)
    usage_date = Column(Date, nullable=False)
    request_count = Column(Integer, default=0)
    last_request_at = Column(
        DateTime,
        nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            'api_key_id', 'model_name', 'usage_date',
            name='uq_usage_per_day'
        ),
    )
