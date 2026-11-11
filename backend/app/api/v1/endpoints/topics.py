from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.deps import get_db, verify_api_key_no_quota
from app.models.api_key import APIKey
from app.core.limiter import limiter
from app.schemas.script_production import (
    TrendingTopicCreate,
    TrendingTopicUpdate,
    TrendingTopicResponse
)
from app.crud.topic import (
    get_active_topics,
    get_all_topics,
    create_topic,
    update_topic,
    delete_topic,
    toggle_topic,
    reorder_topics
)
from app.api.v1.endpoints.admin_keys import verify_admin_secret

router = APIRouter()

# ─── PUBLIC ENDPOINTS ───────────────────────────────────

@router.get("", response_model=list[TrendingTopicResponse])
@limiter.limit("60/minute")
def get_active_hot_topics(
    request: Request,
    db: Session = Depends(get_db),
    api_key_check: APIKey = Depends(verify_api_key_no_quota)
):
    """Lấy danh sách các chủ đề nóng đang hoạt động (yêu cầu API Key thông thường)."""
    return get_active_topics(db)

# ─── ADMIN ENDPOINTS ────────────────────────────────────

@router.get("/admin/all", response_model=list[TrendingTopicResponse])
@limiter.limit("20/minute")
def get_all_hot_topics_admin(
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_secret)
):
    """Lấy tất cả các chủ đề nóng (chỉ dành cho Admin)."""
    return get_all_topics(db)

@router.post("/admin/topics", response_model=TrendingTopicResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def create_new_topic(
    topic_in: TrendingTopicCreate,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_secret)
):
    """Tạo mới một chủ đề nóng (chỉ dành cho Admin)."""
    return create_topic(
        db=db,
        name=topic_in.name,
        description=topic_in.description,
        icon=topic_in.icon,
        display_order=topic_in.display_order
    )

@router.put("/admin/topics/reorder")
@limiter.limit("20/minute")
def reorder_topics_display_index(
    request: Request,
    ids: list[int] = Body(...),
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_secret)
):
    """Cập nhật lại thứ tự hiển thị display_order của các chủ đề nóng (chỉ dành cho Admin)."""
    success = reorder_topics(db, ids)
    return {"success": success}

@router.put("/admin/topics/{topic_id}", response_model=TrendingTopicResponse)
@limiter.limit("20/minute")
def update_existing_topic(
    topic_id: int,
    topic_in: TrendingTopicUpdate,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_secret)
):
    """Cập nhật thông tin chủ đề nóng (chỉ dành cho Admin)."""
    db_topic = update_topic(
        db=db,
        topic_id=topic_id,
        name=topic_in.name,
        description=topic_in.description,
        icon=topic_in.icon,
        display_order=topic_in.display_order,
        is_active=topic_in.is_active
    )
    if not db_topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy chủ đề nóng tương ứng"
        )
    return db_topic

@router.delete("/admin/topics/{topic_id}")
@limiter.limit("10/minute")
def delete_existing_topic(
    topic_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_secret)
):
    """Xóa hoàn toàn một chủ đề nóng (chỉ dành cho Admin)."""
    success = delete_topic(db, topic_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy chủ đề nóng để xóa"
        )
    return {"success": True, "message": "Xóa chủ đề thành công"}

@router.patch("/admin/topics/{topic_id}/toggle", response_model=TrendingTopicResponse)
@limiter.limit("20/minute")
def toggle_topic_active_status(
    topic_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_secret)
):
    """Bật/tắt trạng thái hiển thị của chủ đề nóng (chỉ dành cho Admin)."""
    db_topic = toggle_topic(db, topic_id)
    if not db_topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy chủ đề nóng để toggle"
        )
    return db_topic
