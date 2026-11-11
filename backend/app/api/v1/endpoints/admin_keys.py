from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy.orm import Session
from app.deps import get_db
from app.schemas.api_key import APIKeyCreate, APIKeyResponse, APIKeyGeneratedResponse
from app.crud.api_key import create_api_key, list_api_keys, revoke_api_key
from app.core.limiter import limiter

router = APIRouter()

import hmac
from app.core.config import settings

def verify_admin_secret(x_admin_secret: str = Header(..., alias="X-Admin-Secret")):
    admin_secret = settings.ADMIN_SECRET
    # Clean quotes and spaces
    admin_secret = admin_secret.strip('\'"').strip()
    x_admin_secret = x_admin_secret.strip('\'"').strip()

    if not hmac.compare_digest(x_admin_secret.encode(), admin_secret.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mã xác thực Admin không hợp lệ"
        )
    return x_admin_secret

@router.post("", response_model=APIKeyGeneratedResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def generate_new_key(
    key_in: APIKeyCreate,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_secret)
):
    plain_key, db_api_key = create_api_key(db, key_in)
    return {
        "plain_key": plain_key,
        "api_key": db_api_key
    }

@router.get("", response_model=list[APIKeyResponse])
@limiter.limit("20/minute")
def get_all_keys(
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_secret)
):
    return list_api_keys(db)

@router.delete("/{key_id}", response_model=APIKeyResponse)
@limiter.limit("10/minute")
def revoke_key(
    key_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_secret)
):
    db_api_key = revoke_api_key(db, key_id)
    if not db_api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy API Key"
        )
    return db_api_key
