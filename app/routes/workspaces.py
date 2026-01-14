"""
VexScan API - Workspaces Routes
Workspace management within organizations
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional, List

from app.core.auth import get_current_user, get_org_admin, CurrentUser
from app.core.supabase import supabase
from app.core.exceptions import NotFoundError, RPCError
from app.schemas import WorkspaceCreate, WorkspaceResponse, PaginatedResponse, BaseResponse
import anyio

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.get("", response_model=PaginatedResponse)
async def list_workspaces(
    organization_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = None,
    user: CurrentUser = Depends(get_current_user)
):
    """
    List workspaces for an organization.
    
    Returns workspaces the user has access to.
    """
    try:
        # Intentar con p_org_id primero (patrón común en otras funciones)
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_list_workspaces',
            user.access_token,
            {
                'p_org_id': organization_id,
                'p_page': page,
                'p_per_page': per_page,
                'p_is_active': is_active
            }
        ))
        return result
    except Exception as e:
        # Si falla, puede ser que la función no exista o use otro nombre de parámetro
        raise RPCError('fn_list_workspaces', str(e))


@router.post("", response_model=WorkspaceResponse)
async def create_workspace(
    request: WorkspaceCreate,
    user: CurrentUser = Depends(get_org_admin)
):
    """
    Create a new workspace (Org Admin only).
    
    Workspaces are subdivisions within an organization
    for separating teams or departments.
    """
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_create_workspace',
            user.access_token,
            {
                'p_organization_id': request.organization_id,
                'p_name': request.name,
                'p_slug': request.slug,
                'p_description': request.description
            }
        ))
        return result
    except Exception as e:
        raise RPCError('fn_create_workspace', str(e))


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """Get workspace details."""
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_get_workspace',
            user.access_token,
            {'p_workspace_id': workspace_id}
        ))
        if not result:
            raise NotFoundError("Workspace", workspace_id)
        return result
    except NotFoundError:
        raise
    except Exception as e:
        raise RPCError('fn_get_workspace', str(e))


@router.put("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None,
    user: CurrentUser = Depends(get_org_admin)
):
    """Update workspace (Org Admin only)."""
    from fastapi import HTTPException
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_update_workspace',
            user.access_token,
            {
                'p_workspace_id': workspace_id,
                'p_name': name,
                'p_description': description,
                'p_is_active': is_active
            }
        ))
        
        # Handle RPC error response
        if isinstance(result, dict):
            if result.get('success') is False:
                raise HTTPException(status_code=403, detail=result.get('error', 'Error updating workspace'))
            # If success, return the data
            if 'data' in result:
                return result['data']
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise RPCError('fn_update_workspace', str(e))


# ==================== Workspace Members ====================

@router.get("/{workspace_id}/members")
async def list_workspace_members(
    workspace_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """List members of a workspace."""
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_list_workspace_members',
            user.access_token,
            {'p_workspace_id': workspace_id}
        ))
        return {"success": True, "data": result or []}
    except Exception as e:
        raise RPCError('fn_list_workspace_members', str(e))


@router.post("/{workspace_id}/members")
async def add_workspace_members(
    workspace_id: str,
    user_ids: List[str],
    user: CurrentUser = Depends(get_org_admin)
):
    """
    Add members to a workspace (Org Admin only).
    
    Users must already be organization members.
    """
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_add_workspace_members',
            user.access_token,
            {
                'p_workspace_id': workspace_id,
                'p_user_ids': user_ids
            }
        ))
        return {"success": True, "message": f"Added {len(user_ids)} members", "data": result}
    except Exception as e:
        raise RPCError('fn_add_workspace_members', str(e))


@router.delete("/{workspace_id}/members/{member_id}")
async def remove_workspace_member(
    workspace_id: str,
    member_id: str,
    user: CurrentUser = Depends(get_org_admin)
):
    """Remove a member from a workspace (Org Admin only)."""
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_remove_workspace_member',
            user.access_token,
            {
                'p_workspace_id': workspace_id,
                'p_user_id': member_id
            }
        ))
        return {"success": True, "message": "Member removed"}
    except Exception as e:
        raise RPCError('fn_remove_workspace_member', str(e))
