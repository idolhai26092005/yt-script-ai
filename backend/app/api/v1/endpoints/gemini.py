import asyncio
import logging

from fastapi import APIRouter, Header, Depends, Request
from sqlalchemy.orm import Session
from app.deps import get_db, verify_api_key, verify_api_key_no_quota, get_gemini_api_key
from app.models.api_key import APIKey
from app.core.limiter import limiter
from app.schemas.gemini import (
    GeminiTestRequest, 
    GeminiTestResponse
)
from app.services.gemini import GeminiService


router = APIRouter()
logger = logging.getLogger("uvicorn.error")

async def _cleanup_locks_and_tasks_loop():
    while True:
        try:
            await asyncio.sleep(300)  # runs every 5 minutes
            
            from app.models.processing_lock import ProcessingLock
            from app.models.background_task import BackgroundTask
            from app.models.script_cache import ScriptCache
            from app.core.database import SessionLocal
            from datetime import datetime, timezone, timedelta
            
            db = SessionLocal()
            try:
                now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
                
                # Delete expired processing locks
                db.query(ProcessingLock).filter(ProcessingLock.expires_at < now_utc).delete()
                
                # Delete background tasks older than 30 minutes
                cutoff_tasks = now_utc - timedelta(minutes=30)
                db.query(BackgroundTask).filter(BackgroundTask.created_at < cutoff_tasks).delete()
                
                # Delete script caches older than 30 days
                cutoff_caches = now_utc - timedelta(days=30)
                db.query(ScriptCache).filter(ScriptCache.updated_at < cutoff_caches).delete()
                
                db.commit()
            except Exception as cleanup_err:
                db.rollback()
                logger.warning(f"Cleanup task failed: {type(cleanup_err).__name__}")
            finally:
                db.close()

            # Cleanup old model usage records (> 7 days)
            try:
                from app.crud.model_usage import cleanup_old_usage
                cleanup_db = SessionLocal()
                try:
                    cleanup_old_usage(cleanup_db, days_to_keep=7)
                finally:
                    cleanup_db.close()
            except Exception as usage_cleanup_err:
                logger.warning(f"Model usage cleanup failed: {type(usage_cleanup_err).__name__}")
        except Exception as loop_err:
            logger.warning(f"Cleanup loop iteration failed: {type(loop_err).__name__}")

def start_cleanup_tasks():
    return asyncio.create_task(_cleanup_locks_and_tasks_loop())


@router.get("/models")
@limiter.limit("60/minute")
async def get_available_models(
    request: Request,
    api_key: APIKey = Depends(verify_api_key_no_quota),
    db: Session = Depends(get_db)
):
    """Trả về danh sách model khả dụng kèm trạng thái và lượt gọi còn lại."""
    from app.services.gemini import get_models_status
    models = get_models_status(api_key_id=api_key.id, db=db)
    return {"success": True, "models": models}


@router.post("/validate-app-key")
async def validate_app_key(
    api_key_check: APIKey = Depends(verify_api_key)
):
    return {"success": True, "message": "App API Key hợp lệ"}


@router.post("/test", response_model=GeminiTestResponse)
async def test_gemini_connection(
    request: GeminiTestRequest,
    x_groq_api_key: str | None = Header(None, alias="X-Groq-API-Key"),
    db: Session = Depends(get_db),
    api_key_check: APIKey = Depends(verify_api_key),
    gemini_api_key: str = Depends(get_gemini_api_key)
):
    try:
        service = GeminiService(api_key=gemini_api_key, groq_api_key=x_groq_api_key, db=db, api_key_id=api_key_check.id)
        model_to_test = request.model_name or "gemini-2.5-flash"
        response_text = await service.generate_text(request.prompt, model_name=model_to_test)
        from app.deps import increment_quota_after_success
        increment_quota_after_success(db, api_key_check)
        return GeminiTestResponse(
            success=True,
            response=response_text
        )
    except Exception as e:
        return GeminiTestResponse(
            success=False,
            response="",
            error=str(e)
        )
