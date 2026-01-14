"""
VexScan API - Assets Routes
Asset/Host inventory management
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from pydantic import BaseModel

from app.core.auth import get_current_user, require_permission, require_workspace, CurrentUser
from app.core.supabase import supabase
from app.core.exceptions import NotFoundError, RPCError
from app.schemas import AssetResponse, PaginatedResponse
import anyio

router = APIRouter(prefix="/assets", tags=["Assets"])


# ==================== Request Models ====================

class AssetCreateRequest(BaseModel):
    identifier: str  # IP or hostname
    name: Optional[str] = None
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    project_id: Optional[str] = None
    asset_type: str = "host"
    operating_system: Optional[str] = None
    environment: Optional[str] = None  # prod, dev, staging, qa
    criticality: Optional[str] = None  # critical, high, medium, low
    owner: Optional[str] = None
    department: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class AssetUpdateRequest(BaseModel):
    name: Optional[str] = None
    hostname: Optional[str] = None
    operating_system: Optional[str] = None
    environment: Optional[str] = None
    criticality: Optional[str] = None
    owner: Optional[str] = None
    department: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class AssetBulkTagRequest(BaseModel):
    asset_ids: List[str]
    tags: List[str]
    operation: str = "add"  # "add", "remove", "replace"


# ==================== Assets ====================

@router.get("", response_model=PaginatedResponse)
async def list_assets(
    workspace_id: Optional[str] = None,
    project_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    asset_type: Optional[str] = None,
    operating_system: Optional[str] = None,
    environment: Optional[str] = None,
    criticality: Optional[str] = None,
    has_findings: Optional[bool] = None,
    is_manual: Optional[bool] = None,
    sort_by: str = Query("last_seen", regex="^(identifier|last_seen|findings_count)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    user: CurrentUser = Depends(get_current_user)
):
    """
    List assets/hosts.
    
    Filters:
    - workspace_id/project_id: Scope
    - search: Search in identifier, hostname, IP
    - asset_type: host, ip, url, app, network
    - operating_system: Filter by OS
    - environment: prod, dev, staging, qa
    - criticality: critical, high, medium, low
    - has_findings: Only assets with open findings
    - is_manual: Only manually created assets
    
    Returns assets with finding counts by severity.
    """
    ws_id = workspace_id or user.workspace_id
    
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_list_assets',
            user.access_token,
            {
                'p_workspace_id': ws_id,
                'p_project_id': project_id,
                'p_page': page,
                'p_per_page': per_page,
                'p_search': search,
                'p_asset_type': asset_type,
                'p_operating_system': operating_system,
                'p_environment': environment,
                'p_criticality': criticality,
                'p_has_findings': has_findings,
                'p_is_manual': is_manual,
                'p_sort_by': sort_by,
                'p_sort_order': sort_order
            }
        ))
        return result
    except Exception as e:
        raise RPCError('fn_list_assets', str(e))


@router.post("", response_model=AssetResponse)
async def create_asset(
    request: AssetCreateRequest,
    user: CurrentUser = Depends(require_permission("assets.create"))
):
    """
    Create a manual asset.
    
    Manual assets are flagged with is_manual = true.
    Scanner-discovered assets have is_manual = false.
    """
    if not user.workspace_id:
        raise RPCError('create_asset', 'Workspace context required')
    
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_create_asset',
            user.access_token,
            {
                'p_workspace_id': user.workspace_id,
                'p_project_id': request.project_id,
                'p_identifier': request.identifier,
                'p_name': request.name,
                'p_hostname': request.hostname,
                'p_ip_address': request.ip_address,
                'p_asset_type': request.asset_type,
                'p_operating_system': request.operating_system,
                'p_environment': request.environment,
                'p_criticality': request.criticality,
                'p_owner': request.owner,
                'p_department': request.department,
                'p_tags': request.tags or [],
                'p_notes': request.notes,
                'p_is_manual': True
            }
        ))
        return result
    except Exception as e:
        raise RPCError('fn_create_asset', str(e))


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Get asset details.
    
    Includes:
    - Asset information
    - Finding counts by severity
    - Recent findings
    - Scan history
    """
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_get_asset',
            user.access_token,
            {'p_asset_id': asset_id}
        ))
        if not result:
            raise NotFoundError("Asset", asset_id)
        return result
    except NotFoundError:
        raise
    except Exception as e:
        raise RPCError('fn_get_asset', str(e))


@router.put("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: str,
    request: AssetUpdateRequest,
    user: CurrentUser = Depends(require_permission("assets.update"))
):
    """Update asset details."""
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_update_asset',
            user.access_token,
            {
                'p_asset_id': asset_id,
                'p_name': request.name,
                'p_hostname': request.hostname,
                'p_operating_system': request.operating_system,
                'p_environment': request.environment,
                'p_criticality': request.criticality,
                'p_owner': request.owner,
                'p_department': request.department,
                'p_tags': request.tags,
                'p_notes': request.notes
            }
        ))
        return result
    except Exception as e:
        raise RPCError('fn_update_asset', str(e))


@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: str,
    user: CurrentUser = Depends(require_permission("assets.delete"))
):
    """
    Delete an asset.
    
    Only manual assets can be deleted.
    Scanner-discovered assets are retained for history.
    """
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_delete_asset',
            user.access_token,
            {'p_asset_id': asset_id}
        ))
        return {"success": True, "message": "Asset deleted"}
    except Exception as e:
        raise RPCError('fn_delete_asset', str(e))


# ==================== Asset Findings ====================

@router.get("/{asset_id}/findings")
async def get_asset_findings(
    asset_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    severity: Optional[str] = None,
    user: CurrentUser = Depends(get_current_user)
):
    """Get findings for a specific asset."""
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_get_asset_findings',
            user.access_token,
            {
                'p_asset_id': asset_id,
                'p_page': page,
                'p_per_page': per_page,
                'p_status': status,
                'p_severity': severity
            }
        ))
        return result
    except Exception as e:
        raise RPCError('fn_get_asset_findings', str(e))


# ==================== Bulk Operations ====================

@router.post("/bulk/tags")
async def bulk_update_tags(
    request: AssetBulkTagRequest,
    user: CurrentUser = Depends(require_permission("assets.update"))
):
    """
    Bulk update tags for multiple assets.
    
    Operations:
    - add: Add tags to existing
    - remove: Remove specified tags
    - replace: Replace all tags
    """
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_bulk_update_asset_tags',
            user.access_token,
            {
                'p_asset_ids': request.asset_ids,
                'p_tags': request.tags,
                'p_operation': request.operation
            }
        ))
        return {"success": True, "message": f"Updated {len(request.asset_ids)} assets"}
    except Exception as e:
        raise RPCError('fn_bulk_update_asset_tags', str(e))


@router.post("/bulk/criticality")
async def bulk_update_criticality(
    asset_ids: List[str],
    criticality: str,
    user: CurrentUser = Depends(require_permission("assets.update"))
):
    """Bulk update criticality for multiple assets."""
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_bulk_update_asset_criticality',
            user.access_token,
            {
                'p_asset_ids': asset_ids,
                'p_criticality': criticality
            }
        ))
        return {"success": True, "message": f"Updated {len(asset_ids)} assets"}
    except Exception as e:
        raise RPCError('fn_bulk_update_asset_criticality', str(e))


# ==================== Asset Stats ====================

@router.get("/stats/summary")
async def get_assets_summary(
    workspace_id: Optional[str] = None,
    project_id: Optional[str] = None,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Get asset summary statistics.
    
    Returns:
    - Total assets
    - By operating system
    - By criticality
    - By environment
    - With critical/high findings
    """
    ws_id = workspace_id or user.workspace_id
    
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_get_assets_summary',
            user.access_token,
            {
                'p_workspace_id': ws_id,
                'p_project_id': project_id
            }
        ))
        return {"success": True, "data": result}
    except Exception as e:
        raise RPCError('fn_get_assets_summary', str(e))
