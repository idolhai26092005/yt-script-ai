import pytest
from app.services.production import ProductionService

def test_producer_chunk_split():
    service = ProductionService(api_key="test", groq_api_key=None, db=None, api_key_id=None)
    
    # split(50, 15)
    chunks = service._split_into_chunks(50, 15)
    assert chunks == [(1, 15), (16, 30), (31, 45), (46, 50)]
    
    # split(15, 15)
    chunks_15 = service._split_into_chunks(15, 15)
    assert chunks_15 == [(1, 15)]
    
    # edge case: split(0, 15)
    chunks_0 = service._split_into_chunks(0, 15)
    assert chunks_0 == []
    
    # edge case: split(5, 15)
    chunks_5 = service._split_into_chunks(5, 15)
    assert chunks_5 == [(1, 5)]
