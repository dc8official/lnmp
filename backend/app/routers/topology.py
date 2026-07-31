from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.auth import get_current_user
from app.schemas import APIResponse
from app.services.topology import generate_unified_topology

router = APIRouter(prefix="/topology", tags=["topology"])


@router.get("", response_model=APIResponse)
@router.get("/", response_model=APIResponse)
async def get_topology(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the network topology graph containing nodes (root, monitored, transit)
    and directed edges, along with Root Cause Analysis (RCA) status flags.
    """
    graph_data = await generate_unified_topology(db)
    return APIResponse.success(data=graph_data)
