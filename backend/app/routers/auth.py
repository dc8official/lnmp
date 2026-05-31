from __future__ import annotations
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import text
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
)
from app.config import settings

cookie_name = "lnmp_access_token"

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
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    if is_account_locked(request.username):
        raise HTTPException(
            status_code=403,
            detail="Account temporarily locked due to failed login attempts."
        )

    query = text("""
        SELECT u.id, u.username, u.password_hash,
               u.is_active, u.must_change_password, r.role_name
        FROM users u
        JOIN roles r ON u.role_id = r.id
        WHERE u.username = :username
        LIMIT 1
    """)
    result = await db.execute(query, {"username": request.username})
    row = result.fetchone()

    if not row or not row.is_active:
        record_failed_attempt(request.username)
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    if not verify_password(request.password, row.password_hash):
        record_failed_attempt(request.username)
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    clear_failed_attempts(request.username)

    now = datetime.now(timezone.utc)
    update_query = text("""
        UPDATE users
        SET last_login = :now
        WHERE id = :user_id
    """)
    await db.execute(update_query, {"now": now, "user_id": str(row.id)})

    audit_query = text("""
        INSERT INTO audit_logs (
            user_id, action, target_type,
            target_id, details
        ) VALUES (
            :user_id, 'USER:LOGIN',
            'users', :user_id,
            :details
        )
    """)
    await db.execute(audit_query, {
        "user_id": str(row.id),
        "details": json.dumps({"username": request.username})
    })

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

    response.set_cookie(
        key=cookie_name,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=settings.security.session_timeout_minutes * 60,
    )

    return response_body

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(
        key=cookie_name,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    return APIResponse.success(data={"message": "Logged out."})

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    token = request.cookies.get(cookie_name)
    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
        
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Session expired or invalid.")
        
    return payload

async def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return current_user

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = text("""
        SELECT id, password_hash FROM users
        WHERE id = :user_id AND is_active = TRUE
        LIMIT 1
    """)
    result = await db.execute(query, {"user_id": current_user.get("sub")})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found.")
        
    if not verify_password(request.old_password, row.password_hash):
        raise HTTPException(status_code=400, detail="Invalid current password.")
        
    hashed = hash_password(request.new_password)
    update_query = text("""
        UPDATE users
        SET password_hash = :p,
            must_change_password = FALSE,
            updated_at = NOW()
        WHERE id = :user_id
    """)
    await db.execute(update_query, {
        "p": hashed,
        "user_id": str(current_user.get("sub"))
    })
    
    audit_query = text("""
        INSERT INTO audit_logs (
            user_id, action, target_type, target_id, details
        ) VALUES (
            :user_id, 'USER:CHANGE_PASSWORD', 'users', :user_id, :details
        )
    """)
    await db.execute(audit_query, {
        "user_id": str(current_user.get("sub")),
        "details": json.dumps({"username": current_user.get("username")})
    })
    
    await db.commit()
    
    return APIResponse.success(data={"message": "Password changed successfully."})
