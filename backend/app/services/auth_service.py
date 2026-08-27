from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict
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

# IP-Scoped Failed Login Tracker:
# Key format: "<client_ip>:<username>" -> {"count": int, "last_attempt": datetime, "locked_until": datetime}
_failed_attempts: dict[str, dict] = {}

# In-Memory Concurrent Session Tracker:
# Key format: "<user_id>" -> [jti_1, jti_2] (ordered list of active session JWT IDs, FIFO rotated)
_active_user_sessions: dict[str, list[str]] = {}

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


# ---------------------------------------------------------------------------
# Concurrent Session Management (Token-based FIFO rotation)
# ---------------------------------------------------------------------------
def register_session(user_id: str, jti: str, max_sessions: int = 2) -> None:
    """
    Registers a new session JTI for the user.
    If the user has reached max_sessions, the oldest session is evicted (FIFO).
    """
    u_id = str(user_id)
    active_list = _active_user_sessions.get(u_id, [])
    active_list.append(jti)
    if len(active_list) > max_sessions:
        # Evict oldest session(s)
        active_list = active_list[-max_sessions:]
    _active_user_sessions[u_id] = active_list


def is_session_active(user_id: str, jti: Optional[str]) -> bool:
    """
    Validates if a given JTI session token is active for the user.
    If no JTI is present or session registry has no record for this user, returns True for backward compatibility.
    """
    if not jti:
        return True
    u_id = str(user_id)
    if u_id not in _active_user_sessions:
        return True
    return jti in _active_user_sessions[u_id]


def invalidate_session(user_id: str, jti: Optional[str]) -> None:
    """Invalidates a single active session JTI on logout."""
    if not jti:
        return
    u_id = str(user_id)
    if u_id in _active_user_sessions:
        _active_user_sessions[u_id] = [s for s in _active_user_sessions[u_id] if s != jti]
        if not _active_user_sessions[u_id]:
            _active_user_sessions.pop(u_id, None)


def invalidate_all_user_sessions(user_id: str) -> None:
    """Invalidates all sessions for a user (e.g. on password reset or account deactivation)."""
    _active_user_sessions.pop(str(user_id), None)


def create_access_token(
    user_id: str,
    username: str,
    role_name: str,
    jti: Optional[str] = None,
) -> str:
    session_id = jti or str(secrets.token_hex(16))
    max_sess = getattr(settings.security, "max_active_sessions_per_user", 2)
    register_session(user_id, session_id, max_sessions=max_sess)

    payload = {
        "sub": user_id,
        "username": username,
        "role": role_name,
        "jti": session_id,
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


# ---------------------------------------------------------------------------
# IP-Scoped Account Lockout Memory Manager
# ---------------------------------------------------------------------------
MAX_FAILED_ATTEMPTS_ENTRIES = 2000


def _get_lockout_key(client_ip: str, username: str) -> str:
    ip = client_ip.strip() if client_ip else "127.0.0.1"
    user = username.strip().lower() if username else ""
    return f"{ip}:{user}"


def _prune_expired_attempts() -> None:
    """Prunes expired account lockout entries and enforces max memory allocation bounds."""
    now = datetime.now(timezone.utc)
    expired = [
        k for k, data in _failed_attempts.items()
        if (data.get("locked_until") and data["locked_until"] <= now) or
           (data.get("last_attempt") and now - data["last_attempt"] > timedelta(minutes=30))
    ]
    for k in expired:
        _failed_attempts.pop(k, None)

    if len(_failed_attempts) > MAX_FAILED_ATTEMPTS_ENTRIES:
        sorted_keys = sorted(
            _failed_attempts.keys(),
            key=lambda k: _failed_attempts[k].get("last_attempt") or datetime.min.replace(tzinfo=timezone.utc)
        )
        for k in sorted_keys[: len(_failed_attempts) - MAX_FAILED_ATTEMPTS_ENTRIES]:
            _failed_attempts.pop(k, None)


def is_account_locked(client_ip_or_username: str, username: Optional[str] = None) -> bool:
    """Checks if the (client_ip, username) combination is currently locked out."""
    _prune_expired_attempts()
    if username is None:
        client_ip = "127.0.0.1"
        user = client_ip_or_username
    else:
        client_ip = client_ip_or_username
        user = username
    key = _get_lockout_key(client_ip, user)
    entry = _failed_attempts.get(key)
    if not entry:
        return False
    locked_until = entry.get("locked_until")
    if locked_until and locked_until > datetime.now(timezone.utc):
        return True
    if locked_until:
        _failed_attempts.pop(key, None)
    return False


def record_failed_attempt(client_ip_or_username: str, username: Optional[str] = None) -> None:
    """Records a failed login attempt for the specific (client_ip, username) pair."""
    _prune_expired_attempts()
    if username is None:
        client_ip = "127.0.0.1"
        user = client_ip_or_username
    else:
        client_ip = client_ip_or_username
        user = username
    key = _get_lockout_key(client_ip, user)
    now = datetime.now(timezone.utc)
    entry = _failed_attempts.get(key, {"count": 0})
    entry["count"] = entry.get("count", 0) + 1
    entry["last_attempt"] = now
    if entry["count"] >= 5:
        entry["locked_until"] = now + timedelta(minutes=15)
    _failed_attempts[key] = entry


def clear_failed_attempts(client_ip_or_username: str, username: Optional[str] = None) -> None:
    """Clears failed attempts for the specific (client_ip, username) upon successful authentication."""
    if username is None:
        client_ip = "127.0.0.1"
        user = client_ip_or_username
    else:
        client_ip = client_ip_or_username
        user = username
    key = _get_lockout_key(client_ip, user)
    _failed_attempts.pop(key, None)
