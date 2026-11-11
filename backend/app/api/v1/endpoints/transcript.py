from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import get_db, verify_api_key
from app.models.api_key import APIKey
from app.schemas.transcript import TranscriptRequest, TranscriptResponse
from app.services.youtube import extract_video_id, YouTubeService
from app.crud.transcript import get_transcript_by_video_id, create_transcript

router = APIRouter()

@router.post("/", response_model=TranscriptResponse, deprecated=True)
async def get_video_transcript(
    request: TranscriptRequest,
    db: Session = Depends(get_db),
    api_key_check: APIKey = Depends(verify_api_key)
):
    video_id = extract_video_id(request.url)
    if not video_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="YouTube URL hoặc Video ID không hợp lệ."
        )
        
    # 1. Check if transcript already exists in database
    db_transcript = get_transcript_by_video_id(db, video_id)
    if db_transcript:
        return TranscriptResponse(
            success=True,
            video_id=video_id,
            transcript=db_transcript.transcript,
            segments=[], # Segments not saved in DB for simplicity, or we could parse them
            error=None
        )
        
    # 2. Fetch transcript from YouTube
    try:
        full_text, segments = YouTubeService.get_transcript(video_id)
        
        # 3. Save transcript to database for future reference
        try:
            create_transcript(db, video_id, request.url, full_text)
        except Exception as db_err:
            # If DB save fails (e.g. unique constraint race), log and continue
            import logging
            logging.getLogger("uvicorn.error").warning(f"Database save transcript failed: {db_err}")
            
        return TranscriptResponse(
            success=True,
            video_id=video_id,
            transcript=full_text,
            segments=[{"text": s.text, "start": s.start, "duration": s.duration} for s in segments],
            error=None
        )
        
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if "Không tìm thấy" in str(e) or "bị tắt" in str(e) else status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi không xác định: {str(e)}"
        )
