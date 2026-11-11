from app.models import ScriptCache


# ScriptCache contract guard: keep the table schema exercised without retaining
# the removed test-only CRUD helper as runtime source.
def test_script_cache_model_crud_contract(db_session):
    video_id = "test_vid_123"
    cache = ScriptCache(
        video_id=video_id,
        master_outline='{"sections": ["hook", "body"]}',
        generated_segments='{"0": {"en": "Hello", "vi": "Xin chao"}}',
    )
    db_session.add(cache)
    db_session.commit()
    db_session.refresh(cache)

    retrieved = db_session.query(ScriptCache).filter(ScriptCache.video_id == video_id).first()
    assert retrieved is not None
    assert retrieved.id == cache.id

    retrieved.generated_segments = (
        '{"0": {"en": "Hello", "vi": "Xin chao"}, '
        '"1": {"en": "World", "vi": "The gioi"}}'
    )
    db_session.commit()

    updated = db_session.query(ScriptCache).filter(ScriptCache.video_id == video_id).first()
    assert updated is not None
    assert "World" in updated.generated_segments
    assert "hook" in updated.master_outline

    db_session.delete(updated)
    db_session.commit()

    retrieved_again = db_session.query(ScriptCache).filter(ScriptCache.video_id == video_id).first()
    assert retrieved_again is None
