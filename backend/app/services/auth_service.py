from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"

_failed_attempts: dict[str, dict] = {}

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(
    user_id: str,
    username: str,
    role_name: str,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.security.session_timeout_minutes)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role_name,
        "exp": expire,
    }
    return jwt.encode(payload, settings.security.secret_key, algorithm=ALGORITHM)

def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.security.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None

def is_account_locked(username: str) -> bool:
    entry = _failed_attempts.get(username)
    if not entry:
        return False
        
    locked_until = entry.get("locked_until")
    if locked_until and locked_until > datetime.now(timezone.utc):
        return True
        
    if locked_until and locked_until <= datetime.now(timezone.utc):
        _failed_attempts.pop(username, None)
        return False
        
    return False

def record_failed_attempt(username: str) -> None:
    entry = _failed_attempts.setdefault(username, {"count": 0, "locked_until": None})
    entry["count"] += 1
    if entry["count"] >= 5:
        entry["locked_until"] = datetime.now(timezone.utc) + timedelta(minutes=15)

def clear_failed_attempts(username: str) -> None:
    _failed_attempts.pop(username, None)
