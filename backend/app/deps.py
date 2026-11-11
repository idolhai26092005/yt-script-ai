from typing import Generator
import hashlib
import datetime
from fastapi import Header, HTTPException, Depends, status
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.crud.api_key import get_api_key_by_hash, increment_quota

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_api_key(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db)
):
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Thiếu App API Key. Vui lòng cấu hình ở bảng điều khiển bên trái."
        )
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    api_key = get_api_key_by_hash(db, key_hash)
    
    if not api_key or not api_key.is_active:
        import logging
        logger = logging.getLogger("uvicorn.error")
        logger.warning("Unauthorized API key request rejected.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key không hợp lệ hoặc đã bị vô hiệu hóa"
        )
    
    if api_key.expiry and api_key.expiry < datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key đã hết hạn sử dụng"
        )
        
    if api_key.quota_used >= api_key.quota_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="API Key đã vượt quá giới hạn quota sử dụng"
        )
        
    return api_key

def increment_quota_after_success(db: Session, api_key):
    increment_quota(db, api_key)


def verify_api_key_no_quota(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db)
):
    """Xác thực API key mà KHÔNG tăng quota — dùng cho endpoint read-only."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Thiếu App API Key. Vui lòng cấu hình ở bảng điều khiển bên trái."
        )
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    api_key = get_api_key_by_hash(db, key_hash)

    if not api_key or not api_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key không hợp lệ hoặc đã bị vô hiệu hóa"
        )

    if api_key.expiry and api_key.expiry < datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key đã hết hạn sử dụng"
        )

    return api_key


def get_gemini_api_key(
    x_gemini_api_key: str | None = Header(None, alias="X-Gemini-API-Key")
) -> str:
    from app.core.config import settings
    api_key = x_gemini_api_key or settings.GEMINI_API_KEY
    if not api_key or api_key == "your_gemini_api_key_here":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gemini API Key is missing. Please provide it in 'X-Gemini-API-Key' header or set it in backend .env."
        )
    return api_key
