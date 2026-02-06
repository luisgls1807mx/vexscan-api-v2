"""
VexScan API - Services Routes
Network services/ports management
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional
import anyio

from app.core.auth import get_current_user, CurrentUser
from app.core.supabase import supabase
from app.core.exceptions import RPCError
from app.schemas import PaginatedResponse

router = APIRouter(prefix="/services", tags=["Services"])

@router.get("", response_model=PaginatedResponse)
async def list_services(
    workspace_id: Optional[str] = None,
    project_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    user: CurrentUser = Depends(get_current_user)
):
    """
    List services (ports) detected across assets.
    Aggregates findings by asset, port, and protocol.
    """
    ws_id = workspace_id or user.workspace_id
    
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_list_services',
            user.access_token,
            {
                'p_workspace_id': ws_id,
                'p_project_id': project_id,
                'p_page': page,
                'p_per_page': per_page,
                'p_search': search
            }
        ))
        return result
    except Exception as e:
        raise RPCError('fn_list_services', str(e))
