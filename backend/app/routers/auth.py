from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Optional
from app.services.timezone_utils import get_local_timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import text

logger = logging.getLogger(__name__)
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas import APIResponse
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    is_account_locked,
    record_failed_attempt,
    clear_failed_attempts,
    is_session_active,
    invalidate_session,
    invalidate_all_user_sessions,
)
from app.config import settings

cookie_name = "lnmp_access_token"

def get_client_ip(request: Request) -> str:
    """Extracts the client's source IP address, respecting X-Forwarded-For if behind a reverse proxy."""
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

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    username: str
    role: str
    must_change_password: bool
    message: str

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
            detail="Account temporarily locked for 15 minutes due to multiple failed login attempts from this location."
        )

    query = text("""
        SELECT u.id, u.username, u.password_hash,
               u.is_active, u.must_change_password, r.role_name
        FROM users u
        JOIN roles r ON u.role_id = r.id
        WHERE u.username = :username
        LIMIT 1
    """)
    result = await db.execute(query, {"username": payload.username})
    row = result.fetchone()

    if not row or not row.is_active:
        record_failed_attempt(client_ip, payload.username)
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    if not verify_password(payload.password, row.password_hash):
        record_failed_attempt(client_ip, payload.username)
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    clear_failed_attempts(client_ip, payload.username)

    now = datetime.now(get_local_timezone())
    update_query = text("""
        UPDATE users
        SET last_login = :now
        WHERE id = CAST(:user_id AS uuid)
    """)
    await db.execute(update_query, {"now": now, "user_id": str(row.id)})

    audit_query = text("""
        INSERT INTO audit_logs (
            user_id, action, target_type,
            target_id, details
        ) VALUES (
            CAST(:user_id AS uuid), 'USER:LOGIN',
            'users', CAST(:user_id AS uuid),
            :details
        )
    """)
    await db.execute(audit_query, {
        "user_id": str(row.id),
        "details": json.dumps({"username": payload.username, "ip": client_ip})
    })
    await db.commit()

    token = create_access_token(
        user_id=str(row.id),
        username=row.username,
        role_name=row.role_name,
    )

    response_body = LoginResponse(
        username=row.username,
        role=row.role_name,
        must_change_password=row.must_change_password,
        message="Login successful."
    )

    is_secure = http_request.url.scheme == "https" or getattr(settings.security, "hsts_enabled", False)

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

    is_secure = request.url.scheme == "https" or getattr(settings.security, "hsts_enabled", False)
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
        logger.warning("Auth failure on %s %s from IP %s: Missing authentication token (cookie or header)", request.method, request.url.path, client_ip)
        raise HTTPException(status_code=401, detail="Not authenticated.")
        
    payload = decode_access_token(token)
    if payload is None:
        logger.warning("Auth failure on %s %s from IP %s: JWT token is expired, tampered, or invalid", request.method, request.url.path, client_ip)
        raise HTTPException(status_code=401, detail="Session expired or invalid.")

    user_id = payload.get("sub")
    jti = payload.get("jti")
    if not user_id:
        logger.warning("Auth failure on %s %s from IP %s: Token missing subject claims", request.method, request.url.path, client_ip)
        raise HTTPException(status_code=401, detail="Invalid token claims.")

    if not is_session_active(str(user_id), jti):
        logger.warning("Auth eviction on %s %s from IP %s: User %s session (JTI: %s) evicted by newer login or session limit", request.method, request.url.path, client_ip, user_id, jti)
        raise HTTPException(
            status_code=401,
            detail="Session terminated: maximum active sessions reached or session expired."
        )

    user_query = text("""
        SELECT is_active, must_change_password
        FROM users
        WHERE id = CAST(:user_id AS uuid)
    """)
    res = await db.execute(user_query, {"user_id": str(user_id)})
    row = res.fetchone()
    if not row or not row.is_active:
        logger.warning("Auth rejection on %s %s from IP %s: User %s is disabled or inactive in database", request.method, request.url.path, client_ip, user_id)
        raise HTTPException(status_code=401, detail="User account is inactive or disabled.")

    payload["must_change_password"] = row.must_change_password
    return payload

async def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return current_user

class ChangePasswordRequest(BaseModel):
    old_password: Optional[str] = None
    new_password: str

@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = text("""
        SELECT id, password_hash, must_change_password FROM users
        WHERE id = CAST(:user_id AS uuid) AND is_active = TRUE
        LIMIT 1
    """)
    result = await db.execute(query, {"user_id": current_user.get("sub")})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found.")
        
    if request.old_password and request.old_password.strip():
        if not verify_password(request.old_password.strip(), row.password_hash):
            raise HTTPException(status_code=400, detail="Invalid current password.")
    elif not row.must_change_password:
        raise HTTPException(status_code=400, detail="Current password is required.")
        
    if not request.new_password or len(request.new_password.strip()) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters long.")

    clean_new_pass = request.new_password.strip()
    hashed = hash_password(clean_new_pass)
    update_query = text("""
        UPDATE users
        SET password_hash = :p,
            must_change_password = FALSE,
            updated_at = NOW()
        WHERE id = CAST(:user_id AS uuid)
    """)
    await db.execute(update_query, {
        "p": hashed,
        "user_id": str(current_user.get("sub"))
    })
    
    audit_query = text("""
        INSERT INTO audit_logs (
            user_id, action, target_type, target_id, details
        ) VALUES (
            CAST(:user_id AS uuid), 'USER:CHANGE_PASSWORD', 'users', CAST(:user_id AS uuid), :details
        )
    """)
    await db.execute(audit_query, {
        "user_id": str(current_user.get("sub")),
        "details": json.dumps({"username": current_user.get("username")})
    })
    
    await db.commit()
    
    return APIResponse.success(data={"message": "Password changed successfully."})
