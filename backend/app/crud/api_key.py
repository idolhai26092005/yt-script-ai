import hashlib
import secrets
from sqlalchemy.orm import Session
from app.models.api_key import APIKey
from app.schemas.api_key import APIKeyCreate

def hash_key(plain_key: str) -> str:
    return hashlib.sha256(plain_key.encode()).hexdigest()

def generate_plain_key() -> str:
    # 6 chars prefix + 26 hex chars = 32 chars total
    return f"yt_sk_{secrets.token_hex(13)}"

def create_api_key(db: Session, key_in: APIKeyCreate) -> tuple[str, APIKey]:
    plain_key = generate_plain_key()
    key_hash = hash_key(plain_key)
    
    db_api_key = APIKey(
        key_hash=key_hash,
        owner=key_in.owner,
        quota_limit=key_in.quota_limit,
        expiry=key_in.expiry,
        is_active=True,
        quota_used=0
    )
    
    db.add(db_api_key)
    db.commit()
    db.refresh(db_api_key)
    
    return plain_key, db_api_key

def get_api_key_by_hash(db: Session, key_hash: str) -> APIKey | None:
    return db.query(APIKey).filter(APIKey.key_hash == key_hash).first()

def list_api_keys(db: Session) -> list[APIKey]:
    return db.query(APIKey).order_by(APIKey.created_at.desc()).all()

def revoke_api_key(db: Session, key_id: int) -> APIKey | None:
    db_api_key = db.query(APIKey).filter(APIKey.id == key_id).first()
    if db_api_key:
        db_api_key.is_active = False
        db.commit()
        db.refresh(db_api_key)
    return db_api_key

def increment_quota(db: Session, api_key: APIKey) -> APIKey:
    if not isinstance(api_key, APIKey):
        try:
            api_key.quota_used += 1
        except Exception:
            pass
        return api_key
    api_key.quota_used += 1
    db.commit()
    db.refresh(api_key)
    return api_key
