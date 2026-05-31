from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional
from argon2 import PasswordHasher
from argon2.exceptions import (
    VerifyMismatchError,
    VerificationError,
    InvalidHashError,
)
from jose import JWTError, jwt
from app.config import settings

_ph = PasswordHasher()

_failed_attempts: dict[str, dict] = {}


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


ALGORITHM = "HS256"


def create_access_token(
    user_id: str,
    username: str,
    role_name: str,
) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role_name,
        "exp": datetime.now(timezone.utc) + timedelta(
            minutes=settings.security.session_timeout_minutes
        ),
    }
    return jwt.encode(
        payload,
        settings.security.secret_key,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(
            token,
            settings.security.secret_key,
            algorithms=[ALGORITHM],
        )
    except JWTError:
        return None


def is_account_locked(username: str) -> bool:
    entry = _failed_attempts.get(username)
    if not entry:
        return False
    locked_until = entry.get("locked_until")
    if locked_until and locked_until > datetime.now(timezone.utc):
        return True
    if locked_until:
        _failed_attempts.pop(username, None)
    return False


def record_failed_attempt(username: str) -> None:
    entry = _failed_attempts.get(username, {"count": 0})
    entry["count"] = entry.get("count", 0) + 1
    if entry["count"] >= 5:
        entry["locked_until"] = (
            datetime.now(timezone.utc) + timedelta(minutes=15)
        )
    _failed_attempts[username] = entry


def clear_failed_attempts(username: str) -> None:
    _failed_attempts.pop(username, None)
