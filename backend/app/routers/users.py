from __future__ import annotations
import json
from datetime import datetime
from app.services.timezone_utils import get_local_timezone
from typing import Literal, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.routers.auth import require_admin, get_current_user
from app.services.auth_service import hash_password
from app.schemas import APIResponse

router = APIRouter(prefix="/users", tags=["users"])

class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: Optional[str] = None
    role: Literal["ADMIN", "VIEWER"]

class UpdateUserRequest(BaseModel):
    role: Optional[Literal["ADMIN", "VIEWER"]] = None
    is_active: Optional[bool] = None

class ResetPasswordRequest(BaseModel):
    password: Optional[str] = None

@router.get("/")
async def list_users(
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = text("""
        SELECT u.id, u.username, u.is_active, u.must_change_password, 
               u.last_login, u.created_at, r.role_name
        FROM users u
        JOIN roles r ON u.role_id = r.id
        ORDER BY u.created_at DESC
    """)
    result = await db.execute(query)
    rows = result.fetchall()
    
    users_data = []
    for row in rows:
        users_data.append({
            "id": str(row.id),
            "username": row.username,
            "is_active": row.is_active,
            "must_change_password": row.must_change_password,
            "last_login": row.last_login,
            "created_at": row.created_at,
            "role": row.role_name
        })
        
    return APIResponse.success(data=users_data)

@router.post("/", status_code=201)
async def create_user(
    request: CreateUserRequest,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # Check if username already exists
    dup_query = text("SELECT id FROM users WHERE username = :username LIMIT 1")
    dup_result = await db.execute(dup_query, {"username": request.username})
    if dup_result.fetchone():
        raise HTTPException(status_code=409, detail="Username is already taken.")
        
    # Get role_id
    role_query = text("SELECT id FROM roles WHERE role_name = :role LIMIT 1")
    role_result = await db.execute(role_query, {"role": request.role})
    role_row = role_result.fetchone()
    if not role_row:
        raise HTTPException(status_code=400, detail="Invalid role specified.")
        
    # Set default password if not provided
    plain_password = request.password if request.password else "password123"
    hashed = hash_password(plain_password)
    
    insert_query = text("""
        INSERT INTO users (
            username, password_hash, role_id, is_active, must_change_password
        ) VALUES (
            :u, :p, :r, TRUE, TRUE
        ) RETURNING id, created_at
    """)
    insert_result = await db.execute(insert_query, {
        "u": request.username,
        "p": hashed,
        "r": str(role_row.id)
    })
    new_user = insert_result.fetchone()
    
    audit_query = text("""
        INSERT INTO audit_logs (
            user_id, action, target_type, target_id, details
        ) VALUES (
            :user_id, 'USER:CREATE', 'users', :target_id, :details
        )
    """)
    await db.execute(audit_query, {
        "user_id": current_user.get("sub"),
        "target_id": str(new_user.id),
        "details": json.dumps({
            "username": request.username,
            "role": request.role
        })
    })
    
    await db.commit()
    
    return APIResponse.success(data={
        "id": str(new_user.id),
        "username": request.username,
        "role": request.role,
        "message": f"User account '{request.username}' created successfully."
    })

@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: UUID,
    request: ResetPasswordRequest,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = text("SELECT id, username FROM users WHERE id = :user_id LIMIT 1")
    result = await db.execute(query, {"user_id": str(user_id)})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found.")
        
    plain_password = request.password if request.password else "password123"
    hashed = hash_password(plain_password)
    
    update_query = text("""
        UPDATE users
        SET password_hash = :p,
            must_change_password = TRUE,
            updated_at = NOW()
        WHERE id = :user_id
    """)
    await db.execute(update_query, {
        "p": hashed,
        "user_id": str(user_id)
    })
    
    audit_query = text("""
        INSERT INTO audit_logs (
            user_id, action, target_type, target_id, details
        ) VALUES (
            :user_id, 'USER:RESET_PASSWORD', 'users', :target_id, :details
        )
    """)
    await db.execute(audit_query, {
        "user_id": current_user.get("sub"),
        "target_id": str(user_id),
        "details": json.dumps({"username": row.username})
    })
    
    await db.commit()
    
    return APIResponse.success(data={
        "message": f"Password for user '{row.username}' reset successfully."
    })

@router.patch("/{user_id}")
async def update_user(
    user_id: UUID,
    request: UpdateUserRequest,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # Safety Check: Prevent modifying self
    if str(user_id) == str(current_user.get("sub")):
        raise HTTPException(status_code=400, detail="Administrative roles cannot modify their own privileges or status.")
        
    query = text("SELECT id, username FROM users WHERE id = :user_id LIMIT 1")
    result = await db.execute(query, {"user_id": str(user_id)})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found.")
        
    updates = {}
    if request.role is not None:
        role_query = text("SELECT id FROM roles WHERE role_name = :role LIMIT 1")
        role_result = await db.execute(role_query, {"role": request.role})
        role_row = role_result.fetchone()
        if not role_row:
            raise HTTPException(status_code=400, detail="Invalid role specified.")
        updates["role_id"] = str(role_row.id)
        
    if request.is_active is not None:
        updates["is_active"] = request.is_active
        
    if not updates:
        return APIResponse.success(data={"message": "No updates provided."})
        
    updates["updated_at"] = datetime.now(get_local_timezone())
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    update_query = text(f"UPDATE users SET {set_clause} WHERE id = :user_id")
    
    params = updates.copy()
    params["user_id"] = str(user_id)
    await db.execute(update_query, params)
    
    audit_details = {k: v for k, v in updates.items() if k != "updated_at"}
    if "role_id" in audit_details:
        audit_details["role"] = request.role
        del audit_details["role_id"]
        
    audit_query = text("""
        INSERT INTO audit_logs (
            user_id, action, target_type, target_id, details
        ) VALUES (
            :user_id, 'USER:UPDATE', 'users', :target_id, :details
        )
    """)
    await db.execute(audit_query, {
        "user_id": current_user.get("sub"),
        "target_id": str(user_id),
        "details": json.dumps(audit_details)
    })
    
    await db.commit()
    
    return APIResponse.success(data={"message": f"User '{row.username}' updated successfully."})

@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # Safety Check: Prevent deleting self
    if str(user_id) == str(current_user.get("sub")):
        raise HTTPException(status_code=400, detail="Administrators cannot delete or deactivate their own active accounts.")
        
    query = text("SELECT id, username FROM users WHERE id = :user_id LIMIT 1")
    result = await db.execute(query, {"user_id": str(user_id)})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found.")
        
    # Soft delete / deactivate user
    update_query = text("""
        UPDATE users
        SET is_active = FALSE,
            updated_at = NOW()
        WHERE id = :user_id
    """)
    await db.execute(update_query, {"user_id": str(user_id)})
    
    audit_query = text("""
        INSERT INTO audit_logs (
            user_id, action, target_type, target_id, details
        ) VALUES (
            :user_id, 'USER:DEACTIVATE', 'users', :target_id, :details
        )
    """)
    await db.execute(audit_query, {
        "user_id": current_user.get("sub"),
        "target_id": str(user_id),
        "details": json.dumps({"username": row.username})
    })
    
    await db.commit()
    
    return APIResponse.success(data={"message": f"User '{row.username}' deactivated successfully."})
