import pytest
from sqlalchemy import Column, Integer
from app.core.database import SessionLocal, Base, engine, json_column

class DummyModel(Base):
    __tablename__ = "test_dummy_json"
    id = Column(Integer, primary_key=True)
    data = json_column()

def test_json_column_crud():
    # Force tables creation
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        # Create
        dummy = DummyModel(data={"key": "value", "list": [1, 2, 3]})
        db.add(dummy)
        db.commit()
        
        # Query
        db.refresh(dummy)
        assert dummy.data == {"key": "value", "list": [1, 2, 3]}
        assert isinstance(dummy.data, dict)
        assert dummy.data["list"] == [1, 2, 3]
        
        # Update
        dummy.data = {"updated": True}
        db.commit()
        
        # Verify update
        retrieved = db.query(DummyModel).filter(DummyModel.id == dummy.id).first()
        assert retrieved.data == {"updated": True}
        
    finally:
        # Cleanup
        # We need to drop table safely
        db.rollback()
        DummyModel.__table__.drop(bind=engine)
        db.close()
