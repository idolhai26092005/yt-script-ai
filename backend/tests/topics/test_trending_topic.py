import sys
import os

# Add parent path to path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from fastapi.routing import APIRoute

from app.core.database import SessionLocal, Base, engine
from app.api.v1.endpoints.topics import router as topics_router
from app.models.trending_topic import TrendingTopic
from app.models.project import Project
from app.models.api_key import APIKey
from app.crud.topic import (
    create_topic, get_topic_by_id, get_active_topics,
    get_all_topics, update_topic, delete_topic, toggle_topic, reorder_topics
)
from app.crud.project import (
    create_project, get_project, update_project_suggestions,
    update_project_script, update_project_status, list_projects, delete_project
)
from app.crud.api_key import create_api_key
from app.schemas.api_key import APIKeyCreate

def test_db_trending_topics_and_projects():
    # Force metadata creation (creates new tables if not exists)
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Clean up database tables for testing
        db.query(Project).delete()
        db.query(TrendingTopic).delete()
        db.query(APIKey).delete()
        db.commit()

        # 1. Setup API key for ownership
        key_in = APIKeyCreate(owner="Test Owner", quota_limit=10)
        _, api_key = create_api_key(db, key_in)
        assert api_key.id is not None

        # 2. Test TrendingTopic CRUD
        # Create Topic
        topic1 = create_topic(db, name="La Mã cổ đại", description="Bản hùng ca sử Việt", icon="⚔️", display_order=1)
        topic2 = create_topic(db, name="Ai Cập kỳ bí", description="Kim tự tháp pharaoh", icon="🏜️", display_order=0)
        
        assert topic1.id is not None
        assert topic2.id is not None
        
        # Get Topic
        retrieved1 = get_topic_by_id(db, topic1.id)
        assert retrieved1 is not None
        assert retrieved1.name == "La Mã cổ đại"
        
        # List Active Topics (should return both, sorted by display_order: topic2 first)
        active_list = get_active_topics(db)
        assert len(active_list) >= 2
        # Verify ordering
        assert active_list[0].id == topic2.id
        assert active_list[1].id == topic1.id
        
        # Toggle Topic
        toggle_topic(db, topic1.id)
        active_list_after_toggle = get_active_topics(db)
        # topic1 should be inactive, hence not in active list
        assert topic1.id not in [t.id for t in active_list_after_toggle]
        
        # Get all topics (should include inactive topic1)
        all_list = get_all_topics(db)
        assert topic1.id in [t.id for t in all_list]
        
        # Update Topic
        updated = update_topic(db, topic1.id, name="La Mã phục hưng", is_active=True)
        assert updated.name == "La Mã phục hưng"
        assert updated.is_active is True
        
        # Reorder Topics
        reorder_topics(db, [topic1.id, topic2.id])
        reordered_list = get_active_topics(db)
        assert reordered_list[0].id == topic1.id
        assert reordered_list[1].id == topic2.id
        
        # 3. Test Project CRUD
        # Create Project
        proj = create_project(
            db, 
            api_key_id=api_key.id, 
            title="Dự án test", 
            input_type="topic", 
            input_content="Chiến tranh La Mã",
            topic_id=topic1.id,
            style="cinematic",
            num_scenes=8
        )
        assert proj.id is not None
        assert proj.status == "draft"
        assert proj.scene_duration == 8
        
        # Get Project
        proj_retrieved = get_project(db, proj.id, api_key.id)
        assert proj_retrieved is not None
        assert proj_retrieved.title == "Dự án test"
        
        # Security test: get project with wrong api_key_id should return None
        wrong_proj = get_project(db, proj.id, 99999)
        assert wrong_proj is None
        
        # Update Project Suggestions (Step 1)
        proj_updated_sug = update_project_suggestions(
            db, 
            proj.id, 
            suggestions='[{"index": 0, "title": "Option A"}]'
        )
        assert proj_updated_sug.status == "suggestions_generated"
        assert "Option A" in proj_updated_sug.suggestions
        
        # Update Project Script Output (Step 2)
        proj_updated_script = update_project_script(
            db,
            proj.id,
            selected_suggestion_idx=0,
            script_output='{"overview": "lịch sử La Mã"}'
        )
        assert proj_updated_script.status == "script_generated"
        assert proj_updated_script.selected_suggestion_idx == 0
        assert "overview" in proj_updated_script.script_output
        
        # List projects
        proj_list = list_projects(db, api_key.id)
        assert len(proj_list) >= 1
        assert proj_list[0].id == proj.id
        
        # 4. Test delete / constraints
        # Delete Topic -> Project topic_id should become NULL (SET NULL cascade check)
        delete_topic(db, topic1.id)
        db.refresh(proj)
        assert proj.topic_id is None
        
        # Delete Project
        deleted_proj = delete_project(db, proj.id, api_key.id)
        assert deleted_proj is True
        assert get_project(db, proj.id, api_key.id) is None
        
        # Delete api_key -> check cascading delete if database enforces it
        # (SQLite may require PRAGMA foreign_keys = ON, but SQLAlchemy handles session delete Cascade if defined)
        db.delete(api_key)
        db.commit()
        
        print("✓ All Unit Tests for TrendingTopic, Project and CRUD passed!")
    finally:
        db.close()


def test_admin_topic_reorder_route_precedes_dynamic_topic_id_and_uses_body():
    routes = [route for route in topics_router.routes if isinstance(route, APIRoute)]
    put_paths = [route.path for route in routes if "PUT" in route.methods]

    assert put_paths.index("/admin/topics/reorder") < put_paths.index("/admin/topics/{topic_id}")

    reorder_route = next(route for route in routes if route.path == "/admin/topics/reorder")
    body_param_names = {param.name for param in reorder_route.dependant.body_params}
    assert "ids" in body_param_names

if __name__ == "__main__":
    test_db_trending_topics_and_projects()
