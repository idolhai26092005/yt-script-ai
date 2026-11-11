from sqlalchemy.orm import Session
from app.models.project import Project
import datetime

def get_project(db: Session, project_id: int, api_key_id: int) -> Project | None:
    """Lấy chi tiết dự án (có kiểm tra quyền sở hữu bằng api_key_id)."""
    return db.query(Project).filter(Project.id == project_id, Project.api_key_id == api_key_id).first()

# Project-duration guard: suggestion-time UI settings must persist so restoring
# a project from history keeps the user's scene timing instead of hardcoding 8s.
def create_project(
    db: Session,
    api_key_id: int,
    title: str,
    input_type: str,
    input_content: str,
    topic_id: int | None = None,
    style: str = "anime",
    num_scenes: int = 8,
    topic_type: str | None = None,
    generation_mode: str | None = None,
    scene_duration_sec: int | None = None
) -> Project:
    """Tạo mới một dự án ở trạng thái nháp (draft)."""
    db_project = Project(
        api_key_id=api_key_id,
        title=title,
        input_type=input_type,
        input_content=input_content,
        topic_id=topic_id,
        style=style,
        num_scenes=num_scenes,
        scene_duration=scene_duration_sec or 8,
        status="draft",
        topic_type=topic_type,
        generation_mode=generation_mode
    )
    try:
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        return db_project
    except Exception as e:
        db.rollback()
        raise e

def update_project_suggestions(
    db: Session,
    project_id: int,
    suggestions: str,
    status: str = "suggestions_generated"
) -> Project | None:
    """Cập nhật danh sách gợi ý kịch bản được sinh ra ở Bước 1."""
    db_project = db.query(Project).filter(Project.id == project_id).first()
    if not db_project:
        return None
    db_project.suggestions = suggestions
    db_project.status = status
    db_project.updated_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    try:
        db.commit()
        db.refresh(db_project)
        return db_project
    except Exception as e:
        db.rollback()
        raise e

# Selection-title guard: the archive title should reflect the suggestion the
# user actually chose, while draft placeholders remain until that choice exists.
def update_project_selection(
    db: Session,
    project_id: int,
    selected_suggestion_idx: int,
    title: str | None = None,
    topic_type: str | None = None
) -> Project | None:
    """Lưu gợi ý được chọn và cập nhật title dự án nếu suggestion có title hợp lệ."""
    db_project = db.query(Project).filter(Project.id == project_id).first()
    if not db_project:
        return None
    db_project.selected_suggestion_idx = selected_suggestion_idx
    clean_title = " ".join(str(title or "").split())
    if clean_title:
        db_project.title = clean_title[:500]
    if topic_type:
        db_project.topic_type = topic_type
    db_project.updated_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    try:
        db.commit()
        db.refresh(db_project)
        return db_project
    except Exception as e:
        db.rollback()
        raise e

def update_project_script(
    db: Session,
    project_id: int,
    selected_suggestion_idx: int,
    script_output: str,
    status: str = "script_generated",
    topic_type: str | None = None
) -> Project | None:
    """Cập nhật kịch bản đầy đủ được sinh ra ở Bước 2 kèm index gợi ý đã chọn."""
    db_project = db.query(Project).filter(Project.id == project_id).first()
    if not db_project:
        return None
    db_project.selected_suggestion_idx = selected_suggestion_idx
    db_project.script_output = script_output
    db_project.status = status
    if topic_type:
        db_project.topic_type = topic_type
    db_project.updated_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    try:
        db.commit()
        db.refresh(db_project)
        return db_project
    except Exception as e:
        db.rollback()
        raise e

def update_project_status(
    db: Session,
    project_id: int,
    status: str
) -> Project | None:
    """Cập nhật nhanh trạng thái của dự án."""
    db_project = db.query(Project).filter(Project.id == project_id).first()
    if not db_project:
        return None
    db_project.status = status
    db_project.updated_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    try:
        db.commit()
        db.refresh(db_project)
        return db_project
    except Exception as e:
        db.rollback()
        raise e

def list_projects(db: Session, api_key_id: int, limit: int = 20, skip: int = 0) -> list[Project]:
    """Lấy danh sách các dự án của một user (API Key), sắp xếp theo thời gian mới nhất."""
    return db.query(Project).filter(Project.api_key_id == api_key_id).order_by(
        Project.updated_at.desc()
    ).offset(skip).limit(limit).all()

# Pagination guard: history UI needs a stable total without loading every row.
def count_projects(db: Session, api_key_id: int) -> int:
    """Đếm tổng số dự án của một user để phân trang phía server."""
    return db.query(Project).filter(Project.api_key_id == api_key_id).count()

def delete_project(db: Session, project_id: int, api_key_id: int) -> bool:
    """Xóa dự án (có kiểm tra quyền sở hữu)."""
    db_project = get_project(db, project_id, api_key_id)
    if db_project:
        try:
            db.delete(db_project)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e
    return False
