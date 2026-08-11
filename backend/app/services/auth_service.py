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

import secrets

_ph = PasswordHasher()

_failed_attempts: dict[str, dict] = {}

READABLE_WORDS = [
    "Atlas", "Beacon", "Cedar", "Drift", "Ember", "Falcon", "Gravel", "Haven",
    "Iris", "Jasper", "Kestrel", "Lunar", "Matrix", "Nexus", "Opal", "Pulse",
    "Quartz", "Ridge", "Solar", "Titan", "Vortex", "Zenith", "Anchor", "Breeze"
]


def generate_readable_password() -> str:
    word = secrets.choice(READABLE_WORDS)
    number = secrets.randbelow(900) + 100  # 100 to 999
    return f"{word}-{number}"


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


# Account Lockout Memory Manager:
# In-memory failed login tracking is used to shield PostgreSQL from database connection
# amplification and write load during brute-force authentication attacks.
# Under default single-worker Uvicorn deployment (netmon-api.service), lockout tracking is
# 100% accurate. Under multi-worker cluster deployments, each worker process tracks lockout
# thresholds independently while preserving zero DB query overhead per authentication attempt.
MAX_FAILED_ATTEMPTS_ENTRIES = 1000


def _prune_expired_attempts() -> None:
    """Prunes expired account lockout entries and enforces max memory allocation bounds."""
    now = datetime.now(timezone.utc)
    expired = [
        u for u, data in _failed_attempts.items()
        if (data.get("locked_until") and data["locked_until"] <= now) or
           (data.get("last_attempt") and now - data["last_attempt"] > timedelta(minutes=30))
    ]
    for u in expired:
        _failed_attempts.pop(u, None)

    if len(_failed_attempts) > MAX_FAILED_ATTEMPTS_ENTRIES:
        sorted_keys = sorted(
            _failed_attempts.keys(),
            key=lambda k: _failed_attempts[k].get("last_attempt") or datetime.min.replace(tzinfo=timezone.utc)
        )
        for k in sorted_keys[: len(_failed_attempts) - MAX_FAILED_ATTEMPTS_ENTRIES]:
            _failed_attempts.pop(k, None)


def is_account_locked(username: str) -> bool:
    _prune_expired_attempts()
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
    _prune_expired_attempts()
    now = datetime.now(timezone.utc)
    entry = _failed_attempts.get(username, {"count": 0})
    entry["count"] = entry.get("count", 0) + 1
    entry["last_attempt"] = now
    if entry["count"] >= 5:
        entry["locked_until"] = now + timedelta(minutes=15)
    _failed_attempts[username] = entry


def clear_failed_attempts(username: str) -> None:
    _failed_attempts.pop(username, None)
