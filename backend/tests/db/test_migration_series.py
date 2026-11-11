import os
import pytest
from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic import command
from app.core.config import settings


# Migration path guard: moved taxonomy tests must locate the backend root by
# sentinel file, not by fixed directory depth.
def backend_root_from(path: str) -> str:
    current = os.path.dirname(os.path.abspath(path))
    while current != os.path.dirname(current):
        if os.path.exists(os.path.join(current, "alembic.ini")):
            return current
        current = os.path.dirname(current)
    raise RuntimeError("Cannot locate backend root with alembic.ini")


def test_migration_up_down():
    # 1. Setup test db URL in settings so alembic uses it
    test_db_file = "test_migration.db"
    test_db_url = f"sqlite:///./{test_db_file}"
    
    if os.path.exists(test_db_file):
        try:
            os.remove(test_db_file)
        except Exception:
            pass
        
    original_db_url = settings.DATABASE_URL
    settings.DATABASE_URL = test_db_url
    
    # Configure alembic
    base_dir = backend_root_from(__file__)
    ini_path = os.path.join(base_dir, "alembic.ini")
    alembic_cfg = Config(ini_path)
    alembic_cfg.set_main_option("script_location", os.path.join(base_dir, "alembic"))
    
    try:
        # 2. Upgrade to initial schema
        command.upgrade(alembic_cfg, "2ba743f1b1b3")
        
        # Connect to verify and insert test data
        engine = create_engine(test_db_url)
        with engine.connect() as conn:
            # Create a test API Key and Project in initial schema
            conn.execute(text("INSERT INTO api_keys (id, key_hash, owner, is_active) VALUES (1, 'hash_test_mig', 'owner_test_mig', 1)"))
            conn.execute(text("INSERT INTO projects (id, api_key_id, title, input_type, style, num_scenes, scene_duration, status) "
                              "VALUES (1, 1, 'Test Project', 'manual', 'anime', 8, 8, 'draft')"))
            conn.commit()
            
            # Verify they exist
            row = conn.execute(text("SELECT title FROM projects WHERE id = 1")).fetchone()
            assert row[0] == "Test Project"
            
            # Verify new columns do NOT exist yet
            with pytest.raises(Exception):
                conn.execute(text("SELECT series_id FROM projects"))
                
        # 3. Upgrade to head, including add-only series v2 tables.
        command.upgrade(alembic_cfg, "head")
        
        # Verify columns exist now and data is preserved
        with engine.connect() as conn:
            row = conn.execute(text("SELECT title, series_id, episode_number, generation_mode FROM projects WHERE id = 1")).fetchone()
            assert row[0] == "Test Project"
            assert row[1] is None  # series_id nullable
            assert row[2] is None  # episode_number nullable
            assert row[3] is None  # existing rows will be NULL (None)
            
            # Verify series and episodes tables exist
            conn.execute(text("INSERT INTO series (id, api_key_id, title, generation_mode) VALUES (1, 1, 'Test Series', 'series_short')"))
            conn.execute(text("INSERT INTO episodes (id, series_id, episode_number, title) VALUES (1, 1, 1, 'Ep 1')"))
            conn.commit()
            
            assert conn.execute(text("SELECT title FROM series WHERE id = 1")).fetchone()[0] == "Test Series"
            assert conn.execute(text("SELECT title FROM episodes WHERE id = 1")).fetchone()[0] == "Ep 1"

            # Series v2 migration guard: new rollout tables exist and can store
            # artifacts without dropping or rewriting legacy rows.
            conn.execute(text(
                "INSERT INTO series_v2 "
                "(id, api_key_id, title, premise, style, topic_type, reality_binding_level, "
                "default_scene_count, scene_duration_sec, target_episode_count, status, "
                "series_bible, season_map, created_at, updated_at) "
                "VALUES (1, 1, 'V2 Series', 'Premise', 'anime', 'fictional_original', 'soft', "
                "8, 8, 3, 'active', '{}', '{\"episode_slots\": []}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ))
            conn.execute(text(
                "INSERT INTO series_episode_v2 "
                "(id, series_id, episode_number, status, title, scene_count, ending_mode, created_at, updated_at) "
                "VALUES (1, 1, 1, 'pending', 'V2 Ep 1', 8, 'open_loop', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ))
            conn.commit()

            assert conn.execute(text("SELECT title FROM series_v2 WHERE id = 1")).fetchone()[0] == "V2 Series"
            assert conn.execute(text("SELECT title FROM series_episode_v2 WHERE id = 1")).fetchone()[0] == "V2 Ep 1"
            assert conn.execute(text("SELECT title FROM projects WHERE id = 1")).fetchone()[0] == "Test Project"
            
        # 4. Downgrade back to initial schema
        command.downgrade(alembic_cfg, "2ba743f1b1b3")
        
        # Verify series and episodes tables are dropped, new columns are dropped, but old data is kept
        with engine.connect() as conn:
            row = conn.execute(text("SELECT title FROM projects WHERE id = 1")).fetchone()
            assert row[0] == "Test Project"
            
            with pytest.raises(Exception):
                conn.execute(text("SELECT series_id FROM projects"))
            with pytest.raises(Exception):
                conn.execute(text("SELECT * FROM series"))
            with pytest.raises(Exception):
                conn.execute(text("SELECT * FROM episodes"))
                
    finally:
        # Restore settings
        settings.DATABASE_URL = original_db_url
        # Cleanup database file
        if os.path.exists(test_db_file):
            try:
                os.remove(test_db_file)
            except Exception:
                pass
