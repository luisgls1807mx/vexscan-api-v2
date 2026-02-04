"""
VexScan API - Users Routes
User management within workspaces/organizations
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional
from pydantic import BaseModel, EmailStr

from app.core.auth import get_current_user, get_org_admin, CurrentUser
from app.core.exceptions import NotFoundError, RPCError
from app.schemas import UserCreate, UserUpdate, UserResponse, PaginatedResponse
from app.services.users_service import UsersService

router = APIRouter(prefix="/users", tags=["Users"])


# ==================== Additional Request Models ====================
# (UserCreate and UserUpdate are in schemas, but we need UserInvite)

class UserInviteRequest(BaseModel):
    """Invite user to organization."""
    email: EmailStr
    full_name: str
    role_id: str
    send_email: bool = True


# ==================== Organization Members ====================

@router.get("/organization/{organization_id}")
async def list_organization_members(
    organization_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    role: Optional[str] = Query(None, pattern="^(org_admin|org_member)$"),
    is_active: Optional[bool] = None,
    user: CurrentUser = Depends(get_current_user)
):
    """
    List all members of an organization.
    
    Returns users with their roles and stats.
    """
    try:
        result = await UsersService.list_organization_members(
            user.access_token,
            organization_id,
            page,
            per_page,
            search,
            role,
            is_active
        )
        return result
    except Exception as e:
        raise RPCError('fn_list_organization_members', str(e))


@router.post("/organization/{organization_id}")
async def add_organization_member(
    organization_id: str,
    request: UserCreate,
    user: CurrentUser = Depends(get_org_admin)
):
    """
    Create and add a new user to the organization (Org Admin only).
    
    Creates:
    - Supabase Auth user
    - Profile record
    - Organization membership
    - Workspace membership (default workspace)
    - Role assignment
    """
    try:
        result = await UsersService.add_organization_member(
            user.access_token,
            organization_id,
            request.email,
            request.full_name,
            request.password,
            request.role_id
        )
        return {"success": True, "message": "User created successfully", "data": result}
    except Exception as e:
        raise RPCError('fn_create_organization_member', str(e))


@router.post("/organization/{organization_id}/invite")
async def invite_organization_member(
    organization_id: str,
    request: UserInviteRequest,
    user: CurrentUser = Depends(get_org_admin)
):
    """
    Invite a user to the organization via email (Org Admin only).
    
    Sends an invitation email with a signup link.
    """
    try:
        result = await UsersService.invite_organization_member(
            user.access_token,
            organization_id,
            request.email,
            request.full_name,
            request.role_id,
            request.send_email
        )
        return {"success": True, "message": "Invitation sent", "data": result}
    except Exception as e:
        raise RPCError('fn_invite_organization_member', str(e))


# ==================== Workspace Users ====================

@router.get("/workspace/{workspace_id}", response_model=PaginatedResponse)
async def list_workspace_users(
    workspace_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    role_id: Optional[str] = None,
    is_active: Optional[bool] = None,
    user: CurrentUser = Depends(get_current_user)
):
    """
    List users in a workspace.
    
    Returns users with roles, permissions, and assignment stats.
    """
    try:
        result = await UsersService.list_workspace_users(
            user.access_token,
            workspace_id,
            page,
            per_page,
            search,
            role_id,
            is_active
        )
        return result
    except Exception as e:
        raise RPCError('fn_list_workspace_users', str(e))


# ==================== Individual User ====================

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Get user details.
    
    Includes:
    - Profile info
    - Role and permissions
    - Assignment stats
    - Team memberships
    """
    try:
        result = await UsersService.get_user(user.access_token, user_id)
        if not result:
            raise NotFoundError("User", user_id)
        return result
    except NotFoundError:
        raise
    except Exception as e:
        raise RPCError('fn_get_user', str(e))


@router.put("/{user_id}")
async def update_user(
    user_id: str,
    request: UserUpdate,
    user: CurrentUser = Depends(get_org_admin)
):
    """
    Update user details (Org Admin only).
    
    Can update:
    - full_name
    - role_id
    - is_active (deactivate/reactivate)
    - label (if present in UserUpdate schema)
    """
    try:
        result = await UsersService.update_user(
            user.access_token,
            user_id,
            request.full_name,
            request.role_id,
            request.is_active
        )
        return {"success": True, "message": "User updated", "data": result}
    except Exception as e:
        raise RPCError('fn_update_user', str(e))


@router.delete("/{user_id}")
async def deactivate_user(
    user_id: str,
    user: CurrentUser = Depends(get_org_admin)
):
    """
    Deactivate a user (Org Admin only).
    
    Does not delete the user, just sets is_active = false.
    """
    try:
        await UsersService.deactivate_user(user.access_token, user_id)
        return {"success": True, "message": "User deactivated"}
    except Exception as e:
        raise RPCError('fn_deactivate_user', str(e))


# ==================== User Role ====================

@router.put("/{user_id}/role")
async def change_user_role(
    user_id: str,
    role_id: str,
    workspace_id: str,
    user: CurrentUser = Depends(get_org_admin)
):
    """
    Change user's role in a workspace (Org Admin only).
    """
    try:
        result = await UsersService.change_user_role(
            user.access_token,
            user_id,
            role_id,
            workspace_id
        )
        return {"success": True, "message": "Role updated", "data": result}
    except Exception as e:
        raise RPCError('fn_change_user_role', str(e))


# ==================== User Stats ====================

@router.get("/{user_id}/stats")
async def get_user_stats(
    user_id: str,
    organization_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Get user activity statistics.
    
    Returns:
    - Findings assigned
    - Findings mitigated
    - Average time to mitigate
    - Activity by month
    """
    try:
        stats = await UsersService.get_user_stats(
            user.access_token,
            user_id,
            organization_id
        )
        return {"success": True, "data": stats}
    except Exception as e:
        raise RPCError('fn_get_user_stats', str(e))


@router.get("/{user_id}/assignments")
async def get_user_assignments(
    user_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Get findings assigned to a user.
    """
    try:
        result = await UsersService.get_user_assignments(
            user.access_token,
            user_id,
            page,
            per_page,
            status
        )
        return result
    except Exception as e:
        raise RPCError('fn_get_user_assignments', str(e))
