import json
from typing import Any

from fastapi import HTTPException, status

from app.crud.project import create_project, delete_project, update_project_suggestions
from app.crud.topic import get_topic_by_id
from app.schemas.script_production import SuggestionsResponse
from app.services.youtube import YouTubeService, compress_transcript, extract_video_id


# Application-service guard: suggestion selection moves out of FastAPI endpoint
# code without changing JSON parsing, index matching, or raised error messages.
def select_project_suggestion(db_project: Any, suggestion_index: int) -> dict:
    suggestions_list = json.loads(db_project.suggestions)
    selected_sug = None
    for sug in suggestions_list:
        if sug.get("index") == suggestion_index:
            selected_sug = sug
            break

    if not selected_sug:
        raise ValueError(f"Không tìm thấy gợi ý có index {suggestion_index}")
    return selected_sug


# Application-service guard: episode suggestion selection mirrors the existing
# series endpoint branch, including string JSON support and error detail.
def select_episode_suggestion(episode: Any, suggestion_index: int) -> dict:
    suggestions = episode.next_suggestions
    if isinstance(suggestions, str):
        suggestions = json.loads(suggestions)

    selected_sug = None
    for sug in suggestions:
        if sug.get("index") == suggestion_index:
            selected_sug = sug
            break

    if not selected_sug:
        raise HTTPException(status_code=400, detail="Không tìm thấy index gợi ý phù hợp")
    return selected_sug


# Application-service guard: rolling context injection remains a pure move from
# series endpoint code and intentionally mutates selected_sug like the old path.
def apply_rolling_context_to_suggestion(selected_sug: dict, rolling_context: dict | None) -> None:
    if not rolling_context:
        return

    master_summary_data = rolling_context.get("master_summary")
    master_text = ""
    if isinstance(master_summary_data, dict):
        master_text = master_summary_data.get("narrative_summary", "")
        char_persistent = master_summary_data.get("persistent_character_states", {})
        unresolved = master_summary_data.get("unresolved_threads", [])
        if char_persistent:
            master_text += f"\n- Trạng thái nhân vật tổng hợp: {json.dumps(char_persistent, ensure_ascii=False)}"
        if unresolved:
            master_text += f"\n- Plot threads bỏ ngỏ: {', '.join(unresolved)}"
    elif isinstance(master_summary_data, str):
        master_text = master_summary_data

    synopsis_with_context = f"""
        [NGỮ CẢNH CÁC TẬP TRƯỚC]
        - Tóm tắt tổng hợp các tập cũ: {master_text or 'Không có.'}
        - Các tập gần đây:
        """
    for e in rolling_context.get("recent_episodes", []):
        ep_sum = e["summary"]
        synopsis_with_context += (
            f"  * Tập {e['episode_number']} ({e.get('title', '')}): "
            f"Diễn biến: {ep_sum.get('plot_summary')} | "
            f"Trạng thái nhân vật: {ep_sum.get('character_states', 'Không có')} | "
            f"Sự kiện chính: {ep_sum.get('key_events', [])} | "
            f"Tông cảm xúc: {ep_sum.get('emotion_summary', 'Không có')} | "
            f"Hạ màn: {ep_sum.get('cliffhanger')}\n"
        )

    synopsis_with_context += f"""
        - Khóa liên tục hình ảnh (Visual locks): {json.dumps(rolling_context.get('visual_locks'), ensure_ascii=False)}

        [CỐT TRUYỆN TẬP HIỆN TẠI]
        {selected_sug.get('synopsis')}
        """
    selected_sug["synopsis"] = synopsis_with_context


# Application-service guard: suggestion orchestration is lifted from the endpoint
# as a pure move; it preserves title/raw-content resolution, project writes, quota
# increment timing, cleanup-on-error, and response shape.
# Duration persistence guard: single-flow config is chosen before suggestions,
# so project creation must save it for later history restore and SSE generation.
async def generate_script_suggestions_response(
    *,
    req: Any,
    service: Any,
    db: Any,
    api_key_check: Any,
) -> SuggestionsResponse:
    raw_content = req.input_content
    title = f"Dự án kịch bản phong cách {req.style.preset or req.style.custom or 'Anime'}"

    if req.input_type == "topic":
        if not req.topic_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Thiếu topic_id cho loại đầu vào chủ đề nóng"
            )
        db_topic = get_topic_by_id(db, req.topic_id)
        if not db_topic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy chủ đề nóng tương ứng"
            )
        title = f"Chủ đề: {db_topic.name}"
        raw_content = await service.suggest_from_topic(
            topic_name=db_topic.name,
            topic_description=db_topic.description or "",
            style=req.style.custom or req.style.preset.value,
            model_name=req.model_name
        )

    elif req.input_type == "youtube_url":
        video_id = extract_video_id(req.input_content)
        if not video_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="URL YouTube không đúng định dạng"
            )
        title = f"Từ YouTube ID: {video_id}"
        try:
            full_text, _ = YouTubeService.get_transcript(video_id)
            raw_content = compress_transcript(full_text)
        except Exception as yt_err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Không thể lấy phụ đề tự động từ video: {str(yt_err)}"
            )

    style_str = req.style.custom or (req.style.preset.value if req.style.preset else "anime")
    db_project = create_project(
        db=db,
        api_key_id=api_key_check.id,
        title=title,
        input_type=req.input_type.value,
        input_content=raw_content,
        topic_id=req.topic_id,
        style=style_str,
        num_scenes=req.num_scenes,
        generation_mode=req.generation_mode,
        scene_duration_sec=req.scene_duration_sec,
    )

    try:
        suggestions = await service.generate_suggestions(
            input_content=raw_content,
            style=style_str,
            num_scenes=req.num_scenes,
            num_suggestions=req.num_suggestions,
            model_name=req.model_name
        )

        db_project = update_project_suggestions(
            db=db,
            project_id=db_project.id,
            suggestions=json.dumps(suggestions, ensure_ascii=False)
        )

        if db_project and suggestions:
            first_sugg = suggestions[0] if isinstance(suggestions, list) else {}
            topic_type = first_sugg.get("topic_type", "fictional_original")
            db_project.topic_type = topic_type
            db.commit()
            db.refresh(db_project)

        from app.deps import increment_quota_after_success
        increment_quota_after_success(db, api_key_check)
        return SuggestionsResponse(
            success=True,
            project_id=db_project.id,
            suggestions=suggestions
        )
    except Exception as e:
        delete_project(db, db_project.id, api_key_check.id)
        return SuggestionsResponse(
            success=False,
            project_id=0,
            suggestions=[],
            error=str(e)
        )


__all__ = [
    "apply_rolling_context_to_suggestion",
    "generate_script_suggestions_response",
    "select_episode_suggestion",
    "select_project_suggestion",
]
