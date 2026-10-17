from datetime import datetime, timezone
import secrets
import time
from typing import List, Optional, Dict
from fastapi import Depends, HTTPException, Security, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.orm import Session
import jwt

from app.database import get_db
from app.config import settings
from app.models import User, Device, UserStore
from app.security import decode_token, hash_secret

bearer_scheme = HTTPBearer(auto_error=False)
hermes_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# In-memory sliding window rate limiter: {key: [timestamp, ...]}
_hermes_request_log: Dict[str, List[float]] = {}
HERMES_RATE_LIMIT_PER_MINUTE = 60

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    db: Session = Depends(get_db)
) -> User:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type (access token required)",
            )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims",
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user account")
    
    return user

def require_role(roles: List[str]):
    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required roles: {roles}, your role: {user.role}"
            )
        return user
    return role_checker

def get_user_store_ids(user: User, db: Session) -> List[int]:
    if user.role == "admin":
        return []
    assigned = db.query(UserStore.store_id).filter(UserStore.user_id == user.id).all()
    return [row[0] for row in assigned]

def check_store_access(user: User, store_id: int, db: Session):
    if user.role == "admin":
        return
    accessible = get_user_store_ids(user, db)
    if store_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to store #{store_id}"
        )

def get_authenticated_device(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    db: Session = Depends(get_db)
) -> Device:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing device token header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    token_hash = hash_secret(token)
    device = db.query(Device).filter(Device.token_hash == token_hash).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked device token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return device

def get_hermes_auth(
    api_key: Optional[str] = Security(hermes_key_header)
) -> str:
    """
    Constant-time comparison for Hermes API key.
    Enforces 401 if missing or invalid, plus 60 req/min rate limit.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )
    
    # Constant-time comparison
    if not secrets.compare_digest(api_key.strip(), settings.HERMES_API_KEY.strip()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Hermes API key",
        )

    # Rate limiting: 60 requests per minute per key
    now = time.time()
    timestamps = _hermes_request_log.setdefault(api_key, [])
    # Filter out requests older than 60 seconds
    valid_timestamps = [t for t in timestamps if now - t < 60.0]
    
    if len(valid_timestamps) >= HERMES_RATE_LIMIT_PER_MINUTE:
        _hermes_request_log[api_key] = valid_timestamps
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Hermes rate limit exceeded: maximum {HERMES_RATE_LIMIT_PER_MINUTE} requests per minute."
        )

    valid_timestamps.append(now)
    _hermes_request_log[api_key] = valid_timestamps
    return api_key

async def verify_payload_size(request: Request):
    MAX_SIZE = 256 * 1024 # 256 KB
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Payload exceeds maximum allowed size of 256 KB ({content_length} bytes received)"
        )
