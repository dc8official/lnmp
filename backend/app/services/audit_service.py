from __future__ import annotations
import json
import logging
from typing import Optional
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

async def log_action(
    db: AsyncSession,
    action: str,
    target_type: str,
    target_id: UUID,
    details: Optional[dict] = None,
    user_id: Optional[UUID] = None,
) -> None:
    query = text("""
        INSERT INTO audit_logs (
            user_id,
            action,
            target_type,
            target_id,
            details
        ) VALUES (
            :user_id,
            :action,
            :target_type,
            :target_id,
            :details
        )
    """)
    
    await db.execute(
        query,
        {
            "user_id": str(user_id) if user_id is not None else None,
            "action": action,
            "target_type": target_type,
            "target_id": str(target_id),
            "details": json.dumps(details) if details is not None else None,
        }
    )
    
    logger.debug(
        "Audit: action=%s target_type=%s target_id=%s user_id=%s",
        action,
        target_type,
        str(target_id),
        str(user_id) if user_id else "SYSTEM",
    )
