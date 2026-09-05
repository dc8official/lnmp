from __future__ import annotations

import asyncio
import ipaddress
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
from jose import JWTError, jwt

from app.config import settings

logger = logging.getLogger(__name__)

_ph = PasswordHasher()

# Default trusted reverse proxy CIDR networks (strictly loopback)
DEFAULT_TRUSTED_PROXIES = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
]

# IP-Scoped Failed Login Tracker:
# Key format: "<client_ip>:<username>" -> {"count": int, "last_attempt": datetime, "locked_until": datetime}
_failed_attempts: dict[str, dict] = {}

# In-Memory Concurrent Session Tracker:
# Key format: "<user_id>" -> [jti_1, jti_2] (ordered list of active session JWT IDs, FIFO rotated)
_active_user_sessions: dict[str, list[str]] = {}

READABLE_WORDS = [
    "Atlas", "Beacon", "Cedar", "Drift", "Ember", "Falcon", "Gravel", "Haven",
    "Iris", "Jasper", "Kestrel", "Lunar", "Matrix", "Nexus", "Opal", "Pulse",
    "Quartz", "Ridge", "Solar", "Titan", "Vortex", "Zenith", "Anchor", "Breeze",
]


def generate_readable_password() -> str:
    word = secrets.choice(READABLE_WORDS)
    number = secrets.randbelow(900) + 100  # 100 to 999
    return f"{word}-{number}"


def hash_password(password: str) -> str:
    """Synchronous Argon2id hashing."""
    return _ph.hash(password)


async def hash_password_async(password: str) -> str:
    """Non-blocking Argon2id hashing delegated to asyncio worker thread."""
    return await asyncio.to_thread(_ph.hash, password)


def verify_password(plain: str, hashed: str) -> bool:
    """Synchronous Argon2id password verification."""
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception:
        return False


async def verify_password_async(plain: str, hashed: str) -> bool:
    """Non-blocking Argon2id password verification delegated to asyncio worker thread."""
    return await asyncio.to_thread(verify_password, plain, hashed)


ALGORITHM = "HS256"


# ---------------------------------------------------------------------------
# Trusted Reverse Proxy Header Security
# ---------------------------------------------------------------------------
def is_ip_in_networks(
    ip_str: str,
    networks: Optional[Sequence[ipaddress.IPv4Network | ipaddress.IPv6Network]] = None,
) -> bool:
    """Checks if an IP string belongs to any of the specified trusted networks."""
    try:
        ip_obj = ipaddress.ip_address(ip_str.strip())
        target_nets = networks or DEFAULT_TRUSTED_PROXIES
        return any(ip_obj in net for net in target_nets)
    except ValueError:
        return False


def get_trusted_client_ip(
    request: Any,
    trusted_cidrs: Optional[Sequence[str]] = None,
) -> str:
    """
    Extracts the validated client IP address:
    - If the direct peer connection (request.client.host) is from a trusted proxy CIDR,
      inspects X-Forwarded-For to find the true source IP.
    - If the direct connection is NOT from a trusted proxy, ignores X-Forwarded-For
      to prevent header spoofing attacks.
    """
    peer_ip = "127.0.0.1"
    if getattr(request, "client", None) and getattr(request.client, "host", None):
        peer_ip = str(request.client.host).strip()

    trusted_nets = (
        [ipaddress.ip_network(c.strip()) for c in trusted_cidrs if c.strip()]
        if trusted_cidrs
        else DEFAULT_TRUSTED_PROXIES
    )

    if not is_ip_in_networks(peer_ip, trusted_nets):
        return peer_ip

    if hasattr(request, "headers") and hasattr(request.headers, "get"):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded and isinstance(forwarded, str):
            # Parse right-to-left through the forwarded chain
            parts = [p.strip() for p in forwarded.split(",") if p.strip()]
            for candidate in reversed(parts):
                if not is_ip_in_networks(candidate, trusted_nets):
                    return candidate
            if parts:
                return parts[0]

        real_ip = request.headers.get("X-Real-IP")
        if real_ip and isinstance(real_ip, str) and real_ip.strip():
            return real_ip.strip()

    return peer_ip


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

    try:
        from app.services.driver_manager import driver_manager

        loop = asyncio.get_running_loop()
        store = driver_manager.get_session_store()
        loop.create_task(store.register_session(u_id, jti, max_sessions=max_sessions))
    except Exception:
        pass


class AwaitableBool:
    """
    A boolean wrapper that supports both synchronous truthiness evaluation
    and asynchronous await expressions. Ensures backwards compatibility across
    sync test suites (e.g. test_auth_security.py) and async callers.
    """
    __slots__ = ("_val",)

    def __init__(self, val: bool) -> None:
        self._val = bool(val)

    def __bool__(self) -> bool:
        return self._val

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AwaitableBool):
            return self._val == other._val
        return self._val == other

    def __repr__(self) -> str:
        return repr(self._val)

    def __await__(self):
        async def _coro():
            return self._val
        return _coro().__await__()


def is_session_active(user_id: str, jti: Optional[str]) -> AwaitableBool:
    """
    Validates if a given JTI session token is active for the user.
    Option B (Strict Security Wipe): Invalidate legacy tokens without jti immediately.
    """
    if not jti:
        return AwaitableBool(False)
    u_id = str(user_id)
    if u_id not in _active_user_sessions:
        return AwaitableBool(False)
    return AwaitableBool(jti in _active_user_sessions[u_id])


def invalidate_session(user_id: str, jti: Optional[str]) -> None:
    """Invalidates a single active session JTI on logout."""
    if not jti:
        return
    u_id = str(user_id)
    if u_id in _active_user_sessions:
        _active_user_sessions[u_id] = [
            s for s in _active_user_sessions[u_id] if s != jti
        ]
        if not _active_user_sessions[u_id]:
            _active_user_sessions.pop(u_id, None)

    try:
        from app.services.driver_manager import driver_manager

        loop = asyncio.get_running_loop()
        store = driver_manager.get_session_store()
        loop.create_task(store.invalidate_session(u_id, jti))
    except Exception:
        pass


def invalidate_all_user_sessions(user_id: str) -> None:
    """Invalidates all sessions for a user (e.g. on password reset or account deactivation)."""
    u_id = str(user_id)
    _active_user_sessions.pop(u_id, None)

    try:
        from app.services.driver_manager import driver_manager

        loop = asyncio.get_running_loop()
        store = driver_manager.get_session_store()
        loop.create_task(store.invalidate_all_user_sessions(u_id))
    except Exception:
        pass


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
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=settings.security.session_timeout_minutes),
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
        k
        for k, data in _failed_attempts.items()
        if (data.get("locked_until") and data["locked_until"] <= now)
        or (
            data.get("last_attempt")
            and now - data["last_attempt"] > timedelta(minutes=30)
        )
    ]
    for k in expired:
        _failed_attempts.pop(k, None)

    if len(_failed_attempts) > MAX_FAILED_ATTEMPTS_ENTRIES:
        sorted_keys = sorted(
            _failed_attempts.keys(),
            key=lambda k: _failed_attempts[k].get("last_attempt")
            or datetime.min.replace(tzinfo=timezone.utc),
        )
        for k in sorted_keys[: len(_failed_attempts) - MAX_FAILED_ATTEMPTS_ENTRIES]:
            _failed_attempts.pop(k, None)


def is_account_locked(
    client_ip_or_username: str, username: Optional[str] = None
) -> bool:
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


def record_failed_attempt(
    client_ip_or_username: str, username: Optional[str] = None
) -> None:
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


def clear_failed_attempts(
    client_ip_or_username: str, username: Optional[str] = None
) -> None:
    """Clears failed attempts for the specific (client_ip, username) upon successful authentication."""
    if username is None:
        client_ip = "127.0.0.1"
        user = client_ip_or_username
    else:
        client_ip = client_ip_or_username
        user = username
    key = _get_lockout_key(client_ip, user)
    _failed_attempts.pop(key, None)
