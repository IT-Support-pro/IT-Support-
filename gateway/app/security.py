import hashlib
import hmac
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def hash_secret(secret_token: str) -> str:
    """Hash device token or enrollment key using HMAC-SHA256 with JWT_SECRET as salt"""
    return hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        secret_token.strip().encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

def generate_enrollment_key(length: int = 16) -> str:
    """Generate human-readable enrollment key, e.g. ISL-XXXX-YYYY"""
    alphabet = string.ascii_uppercase + string.digits
    raw = "".join(secrets.choice(alphabet) for _ in range(length))
    return f"HBK-{raw[:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:]}" if length >= 12 else f"HBK-{raw}"

def generate_device_token() -> str:
    """Generate 48-byte URL-safe cryptographic token"""
    return secrets.token_urlsafe(36)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire, "iat": now, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")

def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=7))
    to_encode.update({"exp": expire, "iat": now, "type": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")

def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
