import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.deps import get_db, verify_api_key, verify_api_key_no_quota, get_gemini_api_key
from app.models.api_key import APIKey
from app.schemas.script_production import (
    GenerateSuggestionsRequest,
    SuggestionsResponse,
    GenerateFullScriptRequest
)
from app.crud.project import (
    count_projects,
    get_project,
    list_projects,
    delete_project,
    update_project_selection,
    update_project_status,
)
from app.core.limiter import limiter
from app.core.utils import to_legacy_v2
from app.services.production import ProductionService
from app.services.production.support.sse import (
    SSE_HEARTBEAT_INTERVAL_SEC,
    safe_sse_stream,
    sse_event,
)
from app.services.production.application import (
    generate_script_suggestions_response,
    select_project_suggestion,
)

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


# Compatibility shim: keep endpoint-local helper imports stable while shared SSE
# support moves under production/support during the backend architecture refactor.
# Remove in Phase F after endpoint/tests import production.support.sse directly.
def _sse_event(payload: dict) -> str:
    return sse_event(payload)


@router.post("/suggestions", response_model=SuggestionsResponse)
@limiter.limit("10/minute")
async def generate_script_suggestions(
    req: GenerateSuggestionsRequest,
    request: Request,
    x_groq_api_key: str | None = Header(None, alias="X-Groq-API-Key"),
    db: Session = Depends(get_db),
    api_key_check: APIKey = Depends(verify_api_key),
    gemini_api_key: str = Depends(get_gemini_api_key)
):
    """
    Bước 1: Sinh 5 gợi ý kịch bản từ ý tưởng/chủ đề/URL YouTube.
    Tạo mới một dự án Project và lưu 5 gợi ý kịch bản vào database.
    """
    service = ProductionService(api_key=gemini_api_key, groq_api_key=x_groq_api_key, db=db, api_key_id=api_key_check.id)
    return await generate_script_suggestions_response(
        req=req,
        service=service,
        db=db,
        api_key_check=api_key_check,
    )


@router.post("/script/generate")
@limiter.limit("5/minute")
async def generate_full_production_script(
    req: GenerateFullScriptRequest,
    request: Request,
    x_groq_api_key: str | None = Header(None, alias="X-Groq-API-Key"),
    db: Session = Depends(get_db),
    api_key_check: APIKey = Depends(verify_api_key),
    gemini_api_key: str = Depends(get_gemini_api_key)
):
    """
    Bước 2: Sinh kịch bản đầy đủ chuẩn Veo 3 (SSE stream).
    Cập nhật kịch bản đã sinh theo từng phần vào database dự án (Project).
    """

    # Kiểm tra quyền sở hữu của project
    db_project = get_project(db, req.project_id, api_key_check.id)
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy dự án tương ứng hoặc không có quyền truy cập"
        )

    if not db_project.suggestions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dự án chưa được sinh gợi ý kịch bản ở Bước 1"
        )

    # Trích xuất gợi ý đã chọn
    try:
        selected_sug = select_project_suggestion(db_project, req.suggestion_index)
    except Exception as parse_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lỗi đọc danh sách gợi ý kịch bản: {str(parse_err)}"
        )

    # Determine aspect ratio and scene duration, defaulting to project defaults if not provided in request override
    aspect_ratio_val = req.aspect_ratio or "9:16"
    scene_duration_val = req.scene_duration_sec or db_project.scene_duration or 8
    generation_mode_val = db_project.generation_mode or req.generation_mode or "single"

    # Series isolation guard: direct production calls must never route series
    # modes into the single/longform pipeline; series must use the v2 route.
    if generation_mode_val in {"series_short", "series_long"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Luồng sinh chuỗi phải dùng /api/v1/series; /api/v1/production chỉ dành cho single và longform."
        )

    # Selection-title guard: once a user starts detailed generation, history
    # should name the project after the chosen suggestion instead of draft style.
    updated_project = update_project_selection(
        db,
        db_project.id,
        req.suggestion_index,
        title=selected_sug.get("title"),
        topic_type=selected_sug.get("topic_type"),
    )
    if updated_project:
        db_project = updated_project

    service = ProductionService(api_key=gemini_api_key, groq_api_key=x_groq_api_key, db=db, api_key_id=api_key_check.id)

    # Trả về Response SSE stream
    stream = service.generate_full_script_stream(
        suggestion=selected_sug,
        style=db_project.style,
        num_scenes=db_project.num_scenes,
        project_id=db_project.id,
        db=db,
        model_name=req.model_name,
        topic_type_override=req.topic_type_override,
        aspect_ratio=aspect_ratio_val,
        scene_duration_sec=scene_duration_val,
        batch_mode=req.batch_mode,
        generation_mode=generation_mode_val,
        restart=req.restart,
    )

    # Recovery-status guard: safe_sse_stream turns producer crashes into SSE
    # errors, while this wrapper also marks the persisted project recoverable.
    async def stream_with_failed_status():
        try:
            async for chunk in stream:
                yield chunk
        except Exception:
            update_project_status(db, db_project.id, "script_failed")
            raise

    return StreamingResponse(
        safe_sse_stream(stream_with_failed_status()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# Durable API guard: project detail exposes v3 beside a legacy v2 adapter so frontend
# migration can happen last without hiding the new canonical JSON from backend callers.
@router.get("/project/{project_id}")
def get_project_details(
    project_id: int,
    db: Session = Depends(get_db),
    api_key_check: APIKey = Depends(verify_api_key_no_quota)
):
    """Lấy thông tin chi tiết một dự án (bao gồm kịch bản đã sinh)."""
    db_project = get_project(db, project_id, api_key_check.id)
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy dự án tương ứng hoặc bạn không có quyền sở hữu"
        )
    
    # Parse json fields
    sug_list = []
    if db_project.suggestions:
        try:
            sug_list = json.loads(db_project.suggestions)
        except Exception:
            sug_list = []
            
    script_out = None
    script_out_v3 = None
    if db_project.script_output:
        try:
            raw_script_out = json.loads(db_project.script_output)
            script_out_v3 = raw_script_out if isinstance(raw_script_out, dict) and raw_script_out.get("schema_version") == "3.0" else None
            # Durable API guard: UI still consumes legacy flat fields while backend stores
            # canonical v3; expose both so migration can be gradual and observable.
            script_out = to_legacy_v2(raw_script_out)
        except Exception:
            script_out = None

    return {
        "id": db_project.id,
        "title": db_project.title,
        "input_type": db_project.input_type,
        "input_content": db_project.input_content,
        "topic_id": db_project.topic_id,
        "style": db_project.style,
        "num_scenes": db_project.num_scenes,
        "scene_duration": db_project.scene_duration,
        "generation_mode": db_project.generation_mode,
        "status": db_project.status,
        "topic_type": db_project.topic_type or "fictional_original",
        "suggestions": sug_list,
        "selected_suggestion_idx": db_project.selected_suggestion_idx,
        "script_output": script_out,
        "script_output_v3": script_out_v3,
        "created_at": db_project.created_at,
        "updated_at": db_project.updated_at
    }


# Pagination response guard: rebuilt history UI expects items plus total metadata
# instead of inferring page state from a capped list.
@router.get("/projects")
def list_user_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    api_key_check: APIKey = Depends(verify_api_key_no_quota)
):
    """Lấy danh sách lịch sử dự án kịch bản của người dùng."""
    projects_list = list_projects(db, api_key_check.id, limit, skip)
    total = count_projects(db, api_key_check.id)
    res = []
    for proj in projects_list:
        res.append({
            "id": proj.id,
            "title": proj.title,
            "input_type": proj.input_type,
            "input_content": proj.input_content,
            "topic_id": proj.topic_id,
            "style": proj.style,
            "num_scenes": proj.num_scenes,
            "scene_duration": proj.scene_duration,
            "status": proj.status,
            "topic_type": proj.topic_type or "fictional_original",
            "selected_suggestion_idx": proj.selected_suggestion_idx,
            "generation_mode": proj.generation_mode,
            "created_at": proj.created_at,
            "updated_at": proj.updated_at,
        })
    return {
        "items": res,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.delete("/project/{project_id}")
def delete_user_project(
    project_id: int,
    db: Session = Depends(get_db),
    api_key_check: APIKey = Depends(verify_api_key)
):
    """Xóa bỏ một dự án khỏi hệ thống."""
    success = delete_project(db, project_id, api_key_check.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy dự án để xóa hoặc không có quyền sở hữu"
        )
    return {"success": True, "message": "Xóa dự án thành công"}
