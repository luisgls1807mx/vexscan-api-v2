from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional

from app.core.auth import get_current_user, get_org_admin, CurrentUser
from app.core.exceptions import NotFoundError, RPCError, ValidationError
from app.schemas import RoleCreate, RoleUpdate, RoleResponse, BaseResponse
from app.services.roles_service import RolesService

router = APIRouter(prefix="/roles", tags=["Roles & Permissions"])


# ==================== Permissions ====================

@router.get("/permissions")
async def list_permissions(
    user: CurrentUser = Depends(get_current_user)
):
    """
    List all available permissions.
    
    Returns permissions grouped by category:
    - findings.*
    - assets.*
    - imports.*
    - evidence.*
    - reports.*
    - teams.*
    - workspace.*
    """
    try:
        permissions = await RolesService.list_permissions(user.access_token)
        grouped = await RolesService.group_permissions(permissions)
        
        return {
            "success": True,
            "data": permissions,
            "grouped": grouped
        }
    except Exception as e:
        raise RPCError('fn_list_permissions', str(e))


# ==================== Roles ====================

@router.get("")
async def list_roles(
    workspace_id: Optional[str] = Query(None, description="Workspace ID (mutually exclusive with organization_id)"),
    organization_id: Optional[str] = Query(None, description="Organization ID (mutually exclusive with workspace_id)"),
    include_system: bool = Query(True, description="Include system roles"),
    user: CurrentUser = Depends(get_current_user)
):
    """
    List roles for a workspace or organization.
    
    Must provide exactly ONE of:
    - workspace_id: List roles for specific workspace
    - organization_id: List roles for organization's default workspace
    
    Returns:
    - System roles (Admin, Analyst, Viewer)
    - Custom roles created for the workspace
    """
    # Validate exactly one parameter is provided
    if workspace_id and organization_id:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": "Debe pasar solo workspace_id O organization_id, no ambos",
                "error_code": "INVALID_PARAMS"
            }
        )
    
    if not workspace_id and not organization_id:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": "Debe pasar workspace_id o organization_id",
                "error_code": "MISSING_PARAMS"
            }
        )
    
    try:
        roles = await RolesService.list_roles(
            user.access_token,
            workspace_id=workspace_id,
            organization_id=organization_id,
            include_system=include_system
        )
        return {"success": True, "data": roles}
    except Exception as e:
        raise RPCError('fn_list_roles', str(e))


@router.post("", response_model=RoleResponse)
async def create_role(
    request: RoleCreate,
    workspace_id: Optional[str] = Query(None, description="Workspace ID (mutually exclusive with organization_id)"),
    organization_id: Optional[str] = Query(None, description="Organization ID (mutually exclusive with workspace_id)"),
    user: CurrentUser = Depends(get_org_admin)
):
    """
    Create a custom role (Org Admin only).
    
    Must provide exactly ONE of:
    - workspace_id: SuperAdmin puede especificar workspace exacto
    - organization_id: OrgAdmin crea roles en su organización
    
    Permissions must be valid permission codes from fn_list_permissions.
    """
    # Validate exactly one parameter is provided
    if workspace_id and organization_id:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": "Debe pasar solo workspace_id O organization_id, no ambos",
                "error_code": "INVALID_PARAMS"
            }
        )
    
    if not workspace_id and not organization_id:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": "Debe pasar workspace_id o organization_id",
                "error_code": "MISSING_PARAMS"
            }
        )
    
    if not request.permissions:
        raise ValidationError("At least one permission is required")
    
    try:
        role = await RolesService.create_role(
            user.access_token,
            name=request.name,
            permissions=request.permissions,
            workspace_id=workspace_id,
            organization_id=organization_id,
            description=request.description
        )
        return role
    except Exception as e:
        raise RPCError('fn_create_role', str(e))


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Get role details with permissions.
    """
    try:
        role = await RolesService.get_role(user.access_token, role_id)
        if not role:
            raise NotFoundError("Role", role_id)
        return role
    except NotFoundError:
        raise
    except Exception as e:
        raise RPCError('fn_get_role', str(e))


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: str,
    request: RoleUpdate,
    user: CurrentUser = Depends(get_org_admin)
):
    """
    Update a custom role (Org Admin only).
    
    System roles cannot be modified.
    """
    try:
        role = await RolesService.update_role(
            user.access_token,
            role_id,
            request.name,
            request.description,
            request.permissions
        )
        return role
    except Exception as e:
        error_msg = str(e)
        if 'system role' in error_msg.lower():
            raise ValidationError("System roles cannot be modified")
        raise RPCError('fn_update_role', str(e))


@router.delete("/{role_id}")
async def delete_role(
    role_id: str,
    user: CurrentUser = Depends(get_org_admin)
):
    """
    Delete a custom role (Org Admin only).
    
    - System roles cannot be deleted
    - Role must not have any users assigned
    """
    try:
        await RolesService.delete_role(user.access_token, role_id)
        return {"success": True, "message": "Role deleted"}
    except Exception as e:
        error_msg = str(e)
        if 'system role' in error_msg.lower():
            raise ValidationError("System roles cannot be deleted")
        if 'users assigned' in error_msg.lower():
            raise ValidationError("Cannot delete role with assigned users")
        raise RPCError('fn_delete_role', str(e))


# ==================== Role Users ====================

@router.get("/{role_id}/users")
async def list_role_users(
    role_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user)
):
    """
    List users assigned to a role.
    """
    try:
        result = await RolesService.list_role_users(
            user.access_token,
            role_id,
            page,
            per_page
        )
        return result
    except Exception as e:
        raise RPCError('fn_list_role_users', str(e))


# ==================== Default Roles ====================

@router.post("/workspace/{workspace_id}/initialize")
async def initialize_workspace_roles(
    workspace_id: str,
    user: CurrentUser = Depends(get_org_admin)
):
    """
    Initialize default roles for a workspace (Org Admin only).
    
    Creates:
    - Admin (full permissions)
    - Analyst (findings + evidence + reports)
    - Viewer (read-only)
    
    Usually called automatically when workspace is created.
    """
    try:
        result = await RolesService.initialize_workspace_roles(
            user.access_token,
            workspace_id
        )
        return {"success": True, "message": "Default roles created", "data": result}
    except Exception as e:
        raise RPCError('fn_create_default_workspace_roles', str(e))
