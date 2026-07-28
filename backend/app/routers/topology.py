from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.auth import get_current_user
from app.schemas import APIResponse
from app.services.topology import get_topology_graph

router = APIRouter(prefix="/topology", tags=["topology"])


@router.get("", response_model=APIResponse)
@router.get("/", response_model=APIResponse)
async def get_topology(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the network topology graph containing nodes (monitored & transit)
    and directed edges, along with Root Cause Analysis (RCA) status flags.
    """
    graph_data = await get_topology_graph(db)
    return APIResponse.success(data=graph_data)
