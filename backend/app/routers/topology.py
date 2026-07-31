from __future__ import annotations

from fastapi import APIRouter, Depends

from app.routers.auth import get_current_user
from app.schemas import APIResponse
from app.services.topology import topology_manager

router = APIRouter(prefix="/topology", tags=["topology"])


@router.get("", response_model=APIResponse)
@router.get("/", response_model=APIResponse)
async def get_topology(
    current_user: dict = Depends(get_current_user),
):
    """
    Returns the network topology graph directly from in-memory RAM cache in O(1) time
    with zero database queries on read requests.
    """
    graph_data = topology_manager.get_cached_graph()
    return APIResponse.success(data=graph_data)
