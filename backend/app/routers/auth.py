from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.repositories.auth_repo import AuthRepository
from app.schemas import APIResponse
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
)
from app.services.auth_service import (
    clear_failed_attempts,
    create_access_token,
    decode_access_token,
    hash_password,
    invalidate_session,
    is_account_locked,
    is_session_active,
    record_failed_attempt,
    verify_password,
)

logger = logging.getLogger(__name__)

cookie_name = "lnmp_access_token"


def get_client_ip(request: Request) -> str:
    """Extracts client source IP address, respecting X-Forwarded-For if behind a reverse proxy."""
    try:
        if hasattr(request, "headers") and hasattr(request.headers, "get"):
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded and isinstance(forwarded, str):
                return str(forwarded.split(",")[0].strip())
        if getattr(request, "client", None) and getattr(request.client, "host", None):
            host = request.client.host
            if isinstance(host, str):
                return str(host.strip())
    except Exception:
        pass
    return "127.0.0.1"


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(
    payload: LoginRequest,
    response: Response,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
):
    client_ip = get_client_ip(http_request)
    if is_account_locked(client_ip, payload.username):
        raise HTTPException(
            status_code=403,
            detail="Account temporarily locked for 15 minutes due to multiple failed login attempts from this location.",
        )

    auth_repo = AuthRepository(db)
    user = await auth_repo.get_user_by_username(payload.username)

    is_active = getattr(user, "is_active", False) if user else False
    password_hash = getattr(user, "password_hash", "") if user else ""

    if not user or not is_active:
        record_failed_attempt(client_ip, payload.username)
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    if not verify_password(payload.password, password_hash):
        record_failed_attempt(client_ip, payload.username)
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    clear_failed_attempts(client_ip, payload.username)

    user_id = getattr(user, "id", None)
    username = getattr(user, "username", payload.username)
    role_name = "VIEWER"
    if hasattr(user, "role_name") and isinstance(user.role_name, str):
        role_name = user.role_name
    elif hasattr(user, "role"):
        if isinstance(user.role, str):
            role_name = user.role
        elif hasattr(user.role, "role_name") and isinstance(user.role.role_name, str):
            role_name = user.role.role_name
    must_change_password = bool(getattr(user, "must_change_password", False))

    now = datetime.now(timezone.utc)
    if user_id:
        await auth_repo.update_last_login(user_id, now)
        await auth_repo.create_audit_log(
            user_id=user_id,
            action="USER:LOGIN",
            target_type="users",
            target_id=user_id,
            details={"username": payload.username, "ip": client_ip},
        )
        await db.commit()

    token = create_access_token(
        user_id=str(user_id),
        username=username,
        role_name=str(role_name),
    )

    response_body = LoginResponse(
        username=username,
        role=str(role_name),
        must_change_password=must_change_password,
        message="Login successful.",
    )

    is_secure = http_request.url.scheme == "https" or getattr(
        settings.security, "hsts_enabled", False
    )

    response.set_cookie(
        key=cookie_name,
        value=token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        path="/",
        max_age=settings.security.session_timeout_minutes * 60,
    )

    return APIResponse.success(data=response_body)


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get(cookie_name)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
    if token:
        payload = decode_access_token(token)
        if payload and payload.get("sub") and payload.get("jti"):
            invalidate_session(payload.get("sub"), payload.get("jti"))

    is_secure = request.url.scheme == "https" or getattr(
        settings.security, "hsts_enabled", False
    )
    response.delete_cookie(
        key=cookie_name,
        path="/",
        secure=is_secure,
        httponly=True,
        samesite="lax",
    )
    return APIResponse.success(data={"message": "Logged out."})


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    client_ip = get_client_ip(request)
    token = request.cookies.get(cookie_name)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
    if not token:
        logger.warning(
            "Auth failure on %s %s from IP %s: Missing authentication token",
            request.method,
            request.url.path,
            client_ip,
        )
        raise HTTPException(status_code=401, detail="Not authenticated.")

    payload = decode_access_token(token)
    if payload is None:
        logger.warning(
            "Auth failure on %s %s from IP %s: JWT token is expired, tampered, or invalid",
            request.method,
            request.url.path,
            client_ip,
        )
        raise HTTPException(status_code=401, detail="Session expired or invalid.")

    user_id_str = payload.get("sub")
    jti = payload.get("jti")
    if not user_id_str:
        logger.warning(
            "Auth failure on %s %s from IP %s: Token missing subject claims",
            request.method,
            request.url.path,
            client_ip,
        )
        raise HTTPException(status_code=401, detail="Invalid token claims.")

    if not is_session_active(str(user_id_str), jti):
        logger.warning(
            "Auth eviction on %s %s from IP %s: User %s session (JTI: %s) evicted",
            request.method,
            request.url.path,
            client_ip,
            user_id_str,
            jti,
        )
        raise HTTPException(
            status_code=401,
            detail="Session terminated: maximum active sessions reached or session expired.",
        )

    try:
        user_uuid = UUID(str(user_id_str))
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token claims.")

    auth_repo = AuthRepository(db)
    user = await auth_repo.get_user_by_id(user_uuid)

    is_active = getattr(user, "is_active", False) if user else False
    if not user or not is_active:
        logger.warning(
            "Auth rejection on %s %s from IP %s: User %s is disabled or inactive in database",
            request.method,
            request.url.path,
            client_ip,
            user_id_str,
        )
        raise HTTPException(
            status_code=401, detail="User account is inactive or disabled."
        )

    payload["must_change_password"] = getattr(
        user, "must_change_password", False
    )
    return payload


async def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return current_user


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        user_uuid = UUID(str(current_user.get("sub")))
    except (ValueError, TypeError):
        raise HTTPException(status_code=404, detail="User not found.")

    auth_repo = AuthRepository(db)
    user = await auth_repo.get_user_by_id(user_uuid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    password_hash = getattr(user, "password_hash", "")
    must_change_password = getattr(user, "must_change_password", False)

    if request.old_password and request.old_password.strip():
        if not verify_password(request.old_password.strip(), password_hash):
            raise HTTPException(status_code=400, detail="Invalid current password.")
    elif not must_change_password:
        raise HTTPException(status_code=400, detail="Current password is required.")

    if not request.new_password or len(request.new_password.strip()) < 8:
        raise HTTPException(
            status_code=400,
            detail="New password must be at least 8 characters long.",
        )

    clean_new_pass = request.new_password.strip()
    hashed = hash_password(clean_new_pass)

    await auth_repo.update_password(user_uuid, hashed, must_change_password=False)
    await auth_repo.create_audit_log(
        user_id=user_uuid,
        action="USER:CHANGE_PASSWORD",
        target_type="users",
        target_id=user_uuid,
        details={"username": current_user.get("username")},
    )
    await db.commit()

    return APIResponse.success(data={"message": "Password changed successfully."})
