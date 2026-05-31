from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.routers.auth import get_current_user, require_admin
from app.schemas import APIResponse, PaginationMeta

class CreateEndpointRequest(BaseModel):
    ip_address: str
    hostname: str
    device_type: str
    location: Optional[str] = None
    description: Optional[str] = None
    monitoring_enabled: bool = True

class UpdateEndpointRequest(BaseModel):
    hostname: Optional[str] = None
    device_type: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    monitoring_enabled: Optional[bool] = None
    endpoint_status: Optional[Literal["ACTIVE", "DISABLED"]] = None

router = APIRouter(prefix="/endpoints", tags=["endpoints"])

@router.get("/", response_model=APIResponse)
async def list_endpoints(
    status: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now_utc = datetime.now(timezone.utc)
    since_utc = now_utc - timedelta(hours=24)
    
    query_str = """
        SELECT
            e.id,
            e.hostname,
            host(e.ip_address) AS ip_address,
            e.device_type,
            e.location,
            e.endpoint_status,
            e.monitoring_enabled,
            e.created_at,
            e.updated_at,
            ev.operational_state  AS current_operational_state,
            ev.detailed_state     AS current_detailed_state,
            ev.health_score       AS current_health_score,
            ev.start_time         AS last_seen,
            COALESCE(
                (
                    SELECT
                        ROUND(
                            (
                                COUNT(CASE WHEN sub_ev.operational_state = 'UP' THEN 1 END)::numeric /
                                NULLIF(COUNT(sub_ev.id), 0)::numeric
                            ) * 100,
                            2
                        )
                    FROM endpoint_events sub_ev
                    WHERE sub_ev.endpoint_id = e.id
                      AND sub_ev.start_time >= :since_utc
                      AND sub_ev.start_time <= :now_utc
                ),
                100.0
            ) AS uptime_percentage_24h
        FROM endpoints e
        LEFT JOIN LATERAL (
            SELECT operational_state, detailed_state, health_score, start_time
            FROM endpoint_events
            WHERE endpoint_id = e.id
            ORDER BY start_time DESC
            LIMIT 1
        ) ev ON TRUE
        WHERE e.endpoint_status != 'DELETED'
    """
    
    params = {
        "now_utc": now_utc,
        "since_utc": since_utc,
    }
    if status is not None:
        query_str += " AND e.endpoint_status = :status"
        params["status"] = status
        
    query_str += " ORDER BY e.hostname ASC"
    
    query = text(query_str)
    result = await db.execute(query, params)
    rows = result.fetchall()
    
    data = []
    for row in rows:
        data.append({
            "id": str(row.id),
            "hostname": row.hostname,
            "ip_address": row.ip_address,
            "device_type": row.device_type,
            "location": row.location,
            "endpoint_status": row.endpoint_status,
            "monitoring_enabled": row.monitoring_enabled,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "current_operational_state": row.current_operational_state if row.current_operational_state else "DOWN",
            "current_detailed_state": row.current_detailed_state if row.current_detailed_state else "DOWN",
            "current_health_score": row.current_health_score if row.current_health_score is not None else 0.0,
            "last_seen": row.last_seen,
            "uptime_percentage_24h": float(row.uptime_percentage_24h) if row.uptime_percentage_24h is not None else 100.0,
        })
        
    meta = PaginationMeta(
        total=len(rows),
        page=1,
        page_size=len(rows),
        total_pages=1
    )
    
    return APIResponse.success(data=data, meta=meta)

@router.get("/{endpoint_id}", response_model=APIResponse)
async def get_endpoint(
    endpoint_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now_utc = datetime.now(timezone.utc)
    since_utc = now_utc - timedelta(hours=24)
    query = text("""
        SELECT
            e.id,
            e.hostname,
            host(e.ip_address) AS ip_address,
            e.device_type,
            e.location,
            e.description,
            e.monitoring_enabled,
            e.endpoint_status,
            e.created_by,
            e.created_at,
            e.updated_at,
            ev.operational_state  AS current_operational_state,
            ev.detailed_state     AS current_detailed_state,
            ev.health_score       AS current_health_score,
            ev.start_time         AS last_seen,
            COALESCE(
                (
                    SELECT
                        ROUND(
                            (
                                COUNT(CASE WHEN sub_ev.operational_state = 'UP' THEN 1 END)::numeric /
                                NULLIF(COUNT(sub_ev.id), 0)::numeric
                            ) * 100,
                            2
                        )
                    FROM endpoint_events sub_ev
                    WHERE sub_ev.endpoint_id = e.id
                      AND sub_ev.start_time >= :since_utc
                      AND sub_ev.start_time <= :now_utc
                ),
                100.0
            ) AS uptime_percentage_24h
        FROM endpoints e
        LEFT JOIN LATERAL (
            SELECT operational_state, detailed_state, health_score, start_time
            FROM endpoint_events
            WHERE endpoint_id = e.id
            ORDER BY start_time DESC
            LIMIT 1
        ) ev ON TRUE
        WHERE e.id = :endpoint_id
          AND e.endpoint_status != 'DELETED'
    """)
    result = await db.execute(query, {
        "endpoint_id": str(endpoint_id),
        "now_utc": now_utc,
        "since_utc": since_utc,
    })
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Endpoint not found.")
        
    data = {
        "id": str(row.id),
        "hostname": row.hostname,
        "ip_address": row.ip_address,
        "device_type": row.device_type,
        "location": row.location,
        "description": row.description,
        "monitoring_enabled": row.monitoring_enabled,
        "endpoint_status": row.endpoint_status,
        "created_by": str(row.created_by) if row.created_by else None,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "current_operational_state": row.current_operational_state if row.current_operational_state else "DOWN",
        "current_detailed_state": row.current_detailed_state if row.current_detailed_state else "DOWN",
        "current_health_score": row.current_health_score if row.current_health_score is not None else 0.0,
        "last_seen": row.last_seen,
        "uptime_percentage_24h": float(row.uptime_percentage_24h) if row.uptime_percentage_24h is not None else 100.0,
    }
    
    return APIResponse.success(data=data)

@router.post("/", response_model=APIResponse, status_code=201)
async def create_endpoint(
    request: CreateEndpointRequest,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    check_query = text("""
        SELECT id FROM endpoints
        WHERE ip_address = :ip_address
          AND endpoint_status != 'DELETED'
    """)
    check_result = await db.execute(check_query, {"ip_address": request.ip_address})
    if check_result.fetchone():
        raise HTTPException(status_code=409, detail="An endpoint with this IP address already exists.")
        
    # Check if a soft-deleted endpoint with the same IP already exists to restore it
    deleted_query = text("""
        SELECT id FROM endpoints
        WHERE ip_address = :ip_address
          AND endpoint_status = 'DELETED'
    """)
    deleted_result = await db.execute(deleted_query, {"ip_address": request.ip_address})
    deleted_row = deleted_result.fetchone()
    
    if deleted_row:
        restore_query = text("""
            UPDATE endpoints
            SET hostname = :hostname,
                device_type = :device_type,
                location = :location,
                description = :description,
                monitoring_enabled = :monitoring_enabled,
                endpoint_status = 'ACTIVE',
                deleted_at = NULL,
                updated_at = NOW()
            WHERE id = :endpoint_id
        """)
        await db.execute(restore_query, {
            "hostname": request.hostname,
            "device_type": request.device_type,
            "location": request.location,
            "description": request.description,
            "monitoring_enabled": request.monitoring_enabled,
            "endpoint_id": str(deleted_row.id)
        })
        
        audit_query = text("""
            INSERT INTO audit_logs (
                user_id, action, target_type, target_id, details
            ) VALUES (
                :user_id, 'ENDPOINT:RESTORE', 'endpoints',
                :target_id, :details
            )
        """)
        await db.execute(audit_query, {
            "user_id": current_user.get("sub"),
            "target_id": str(deleted_row.id),
            "details": json.dumps({
                "ip_address": request.ip_address,
                "hostname": request.hostname,
                "note": "Restored soft-deleted endpoint"
            })
        })
        
        await db.commit()
        return APIResponse.success(
            data={"id": str(deleted_row.id), "message": "Endpoint restored successfully."},
        )
        
    insert_query = text("""
        INSERT INTO endpoints (
            ip_address, hostname, device_type,
            location, description, monitoring_enabled,
            endpoint_status, created_by
        ) VALUES (
            :ip_address, :hostname, :device_type,
            :location, :description, :monitoring_enabled,
            'ACTIVE', :created_by
        ) RETURNING id, created_at, updated_at
    """)
    insert_result = await db.execute(insert_query, {
        "ip_address": request.ip_address,
        "hostname": request.hostname,
        "device_type": request.device_type,
        "location": request.location,
        "description": request.description,
        "monitoring_enabled": request.monitoring_enabled,
        "created_by": current_user.get("sub"),
    })
    new_endpoint = insert_result.fetchone()
    
    audit_query = text("""
        INSERT INTO audit_logs (
            user_id, action, target_type, target_id, details
        ) VALUES (
            :user_id, 'ENDPOINT:CREATE', 'endpoints',
            :target_id, :details
        )
    """)
    await db.execute(audit_query, {
        "user_id": current_user.get("sub"),
        "target_id": str(new_endpoint.id),
        "details": json.dumps({
            "ip_address": request.ip_address,
            "hostname": request.hostname,
        })
    })
    
    await db.commit()
    
    return APIResponse.success(
        data={"id": str(new_endpoint.id), "message": "Endpoint created."},
    )

@router.patch("/{endpoint_id}", response_model=APIResponse)
async def update_endpoint(
    endpoint_id: UUID,
    request: UpdateEndpointRequest,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    check_query = text("""
        SELECT id FROM endpoints
        WHERE id = :endpoint_id
          AND endpoint_status != 'DELETED'
    """)
    check_result = await db.execute(check_query, {"endpoint_id": str(endpoint_id)})
    if not check_result.fetchone():
        raise HTTPException(status_code=404, detail="Endpoint not found.")
        
    updates = {}
    if request.hostname is not None:
        updates["hostname"] = request.hostname
    if request.device_type is not None:
        updates["device_type"] = request.device_type
    if request.location is not None:
        updates["location"] = request.location
    if request.description is not None:
        updates["description"] = request.description
    if request.monitoring_enabled is not None:
        updates["monitoring_enabled"] = request.monitoring_enabled
    if request.endpoint_status is not None:
        updates["endpoint_status"] = request.endpoint_status
        
    updates["updated_at"] = datetime.now(timezone.utc)
    
    if len(updates) == 1:
        return APIResponse.success(data={"message": "No changes provided."})
        
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    update_query = text(f"""
        UPDATE endpoints SET {set_clause}
        WHERE id = :endpoint_id
    """)
    
    params = updates.copy()
    params["endpoint_id"] = str(endpoint_id)
    
    await db.execute(update_query, params)
    
    audit_details = {k: v for k, v in updates.items() if k != "updated_at"}
    audit_query = text("""
        INSERT INTO audit_logs (
            user_id, action, target_type, target_id, details
        ) VALUES (
            :user_id, 'ENDPOINT:UPDATE', 'endpoints',
            :target_id, :details
        )
    """)
    await db.execute(audit_query, {
        "user_id": current_user.get("sub"),
        "target_id": str(endpoint_id),
        "details": json.dumps(audit_details, default=str),
    })
    
    await db.commit()
    
    return APIResponse.success(data={"message": "Endpoint updated."})

@router.delete("/{endpoint_id}", response_model=APIResponse)
async def delete_endpoint(
    endpoint_id: UUID,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    check_query = text("""
        SELECT id FROM endpoints
        WHERE id = :endpoint_id
          AND endpoint_status != 'DELETED'
    """)
    check_result = await db.execute(check_query, {"endpoint_id": str(endpoint_id)})
    if not check_result.fetchone():
        raise HTTPException(status_code=404, detail="Endpoint not found.")
        
    now = datetime.now(timezone.utc)
    delete_query = text("""
        UPDATE endpoints
        SET endpoint_status = 'DELETED',
            deleted_at = :now,
            updated_at = :now
        WHERE id = :endpoint_id
    """)
    await db.execute(delete_query, {
        "endpoint_id": str(endpoint_id),
        "now": now,
    })
    
    audit_query = text("""
        INSERT INTO audit_logs (
            user_id, action, target_type, target_id, details
        ) VALUES (
            :user_id, 'ENDPOINT:DELETE', 'endpoints',
            :target_id, :details
        )
    """)
    await db.execute(audit_query, {
        "user_id": current_user.get("sub"),
        "target_id": str(endpoint_id),
        "details": json.dumps({}),
    })
    
    await db.commit()
    
    return APIResponse.success(data={"message": "Endpoint deleted."})
