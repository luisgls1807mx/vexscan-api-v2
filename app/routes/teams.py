"""
VexScan API - Teams Routes
Team management for collaborative vulnerability handling
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional

from app.core.auth import get_current_user, require_permission, CurrentUser
from app.core.exceptions import NotFoundError, RPCError
from app.schemas import TeamCreate, TeamUpdate, TeamMemberAdd, TeamResponse
from app.services.teams_service import TeamsService

router = APIRouter(prefix="/teams", tags=["Teams"])


# ==================== Teams ====================

@router.get("")
async def list_teams(
    organization_id: str,
    is_active: Optional[bool] = True,
    search: Optional[str] = None,
    user: CurrentUser = Depends(get_current_user)
):
    """
    List all teams in an organization.
    
    Returns teams with:
    - Member count
    - Leader info
    - Assigned findings count
    """
    try:
        teams = await TeamsService.list_teams(
            user.access_token,
            organization_id,
            is_active,
            search
        )
        return {"success": True, "data": teams}
    except Exception as e:
        raise RPCError('fn_get_organization_teams', str(e))


@router.post("", response_model=TeamResponse)
async def create_team(
    organization_id: str,
    request: TeamCreate,
    user: CurrentUser = Depends(require_permission("teams.create"))
):
    """
    Create a new team.
    
    Optionally assign a leader during creation.
    """
    try:
        team = await TeamsService.create_team(
            user.access_token,
            organization_id,
            request.name,
            request.description,
            request.icon,
            request.color,
            request.leader_id
        )
        return team
    except Exception as e:
        raise RPCError('fn_create_team', str(e))


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Get team details.
    
    Includes:
    - Team info
    - All members with roles
    - Assigned findings summary
    """
    try:
        team = await TeamsService.get_team(user.access_token, team_id)
        if not team:
            raise NotFoundError("Team", team_id)
        return team
    except NotFoundError:
        raise
    except Exception as e:
        raise RPCError('fn_get_team', str(e))


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: str,
    request: TeamUpdate,
    user: CurrentUser = Depends(require_permission("teams.update"))
):
    """Update team details."""
    try:
        team = await TeamsService.update_team(
            user.access_token,
            team_id,
            request.name,
            request.description,
            request.icon,
            request.color,
            request.leader_id,
            request.is_active
        )
        return team
    except Exception as e:
        raise RPCError('fn_update_team', str(e))


@router.delete("/{team_id}")
async def delete_team(
    team_id: str,
    user: CurrentUser = Depends(require_permission("teams.delete"))
):
    """
    Deactivate a team.
    
    Does not delete, sets is_active = false.
    """
    try:
        await TeamsService.delete_team(user.access_token, team_id)
        return {"success": True, "message": "Team deactivated"}
    except Exception as e:
        raise RPCError('fn_deactivate_team', str(e))


# ==================== Team Members ====================

@router.get("/{team_id}/members")
async def list_team_members(
    team_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """List all members of a team."""
    try:
        members = await TeamsService.list_team_members(user.access_token, team_id)
        return {"success": True, "data": members}
    except Exception as e:
        raise RPCError('fn_list_team_members', str(e))


@router.post("/{team_id}/members")
async def add_team_members(
    team_id: str,
    request: TeamMemberAdd,
    user: CurrentUser = Depends(require_permission("teams.manage_members"))
):
    """
    Add members to a team.
    
    Role can be:
    - "leader": Team leader (only one per team)
    - "member": Regular member
    """
    try:
        await TeamsService.add_team_members(
            user.access_token,
            team_id,
            request.user_ids,
            request.role
        )
        return {"success": True, "message": f"Added {len(request.user_ids)} members"}
    except Exception as e:
        raise RPCError('fn_add_team_members', str(e))


@router.delete("/{team_id}/members/{member_id}")
async def remove_team_member(
    team_id: str,
    member_id: str,
    user: CurrentUser = Depends(require_permission("teams.manage_members"))
):
    """Remove a member from a team (soft delete)."""
    try:
        result = await TeamsService.remove_team_member(user.access_token, team_id, member_id)
        
        # El RPC retorna JSON con success: true/false
        if result and result.get('success'):
            return result
        else:
            # Retornar el mensaje de error del RPC
            raise NotFoundError("Team Member", member_id, result.get('message', 'Error removing member'))
    except NotFoundError:
        raise
    except Exception as e:
        raise RPCError('fn_remove_team_member', str(e))


@router.put("/{team_id}/members/{member_id}/role")
async def update_member_role(
    team_id: str,
    member_id: str,
    role: str,
    user: CurrentUser = Depends(require_permission("teams.manage_members"))
):
    """
    Update a member's role in the team.
    
    Setting role to "leader" will demote current leader to "member".
    """
    try:
        await TeamsService.update_member_role(
            user.access_token,
            team_id,
            member_id,
            role
        )
        return {"success": True, "message": "Role updated"}
    except Exception as e:
        raise RPCError('fn_update_team_member_role', str(e))


# ==================== Team Assignments ====================

@router.get("/{team_id}/assignments")
async def get_team_assignments(
    team_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    severity: Optional[str] = None,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Get findings assigned to a team.
    """
    try:
        result = await TeamsService.get_team_assignments(
            user.access_token,
            team_id,
            page,
            per_page,
            status,
            severity
        )
        return result
    except Exception as e:
        raise RPCError('fn_get_team_assignments', str(e))


@router.get("/{team_id}/stats")
async def get_team_stats(
    team_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Get team performance statistics.
    
    Returns:
    - Total findings assigned
    - Findings by status
    - Average time to mitigate
    - Member performance breakdown
    """
    try:
        stats = await TeamsService.get_team_stats(user.access_token, team_id)
        return {"success": True, "data": stats}
    except Exception as e:
        raise RPCError('fn_get_team_stats', str(e))
