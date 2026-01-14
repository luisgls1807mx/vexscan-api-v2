"""
VexScan API - Teams Service
Business logic for team management
"""

import anyio
from typing import Optional, List, Dict, Any
from app.core.supabase import supabase


class TeamsService:
    """Service for managing teams."""
    
    @staticmethod
    async def list_teams(
        access_token: str,
        organization_id: str,
        is_active: Optional[bool] = True,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List teams in an organization."""
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_get_organization_teams',
                access_token,
                {
                    'p_organization_id': organization_id,
                    'p_is_active': is_active,
                    'p_search': search
                }
            )
        )
        return result or []
    
    @staticmethod
    async def create_team(
        access_token: str,
        organization_id: str,
        name: str,
        description: Optional[str] = None,
        icon: Optional[str] = None,
        color: Optional[str] = "#3b82f6",
        leader_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new team."""
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_create_team',
                access_token,
                {
                    'p_org_id': organization_id,
                    'p_name': name,
                    'p_description': description,
                    'p_icon': icon,
                    'p_color': color,
                    'p_leader_id': leader_id
                }
            )
        )
        return result
    
    @staticmethod
    async def get_team(access_token: str, team_id: str) -> Optional[Dict[str, Any]]:
        """Get team details."""
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_get_team',
                access_token,
                {'p_team_id': team_id}
            )
        )
        return result
    
    @staticmethod
    async def update_team(
        access_token: str,
        team_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        icon: Optional[str] = None,
        color: Optional[str] = None,
        leader_id: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Update team details."""
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_update_team',
                access_token,
                {
                    'p_team_id': team_id,
                    'p_name': name,
                    'p_description': description,
                    'p_icon': icon,
                    'p_color': color,
                    'p_leader_id': leader_id,
                    'p_is_active': is_active
                }
            )
        )
        return result
    
    @staticmethod
    async def delete_team(access_token: str, team_id: str) -> bool:
        """Deactivate a team."""
        await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_deactivate_team',
                access_token,
                {'p_team_id': team_id}
            )
        )
        return True
    
    @staticmethod
    async def list_team_members(
        access_token: str,
        team_id: str
    ) -> List[Dict[str, Any]]:
        """List team members."""
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_list_team_members',
                access_token,
                {'p_team_id': team_id}
            )
        )
        return result or []
    
    @staticmethod
    async def add_team_members(
        access_token: str,
        team_id: str,
        user_ids: List[str],
        role: str = "member"
    ) -> List[Dict[str, Any]]:
        """Add members to team."""
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_add_team_members',
                access_token,
                {
                    'p_team_id': team_id,
                    'p_user_ids': user_ids,
                    'p_role': role
                }
            )
        )
        return result or []
    
    @staticmethod
    async def remove_team_member(
        access_token: str,
        team_id: str,
        member_id: str
    ) -> Dict[str, Any]:
        """Remove member from team (soft delete)."""
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_remove_team_member',
                access_token,
                {
                    'p_team_id': team_id,
                    'p_member_id': member_id
                }
            )
        )
        return result
    
    @staticmethod
    async def update_member_role(
        access_token: str,
        team_id: str,
        member_id: str,
        role: str
    ) -> Dict[str, Any]:
        """Update member's role."""
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_update_team_member_role',
                access_token,
                {
                    'p_team_id': team_id,
                    'p_member_id': member_id,
                    'p_role': role
                }
            )
        )
        return result
    
    @staticmethod
    async def get_team_assignments(
        access_token: str,
        team_id: str,
        page: int = 1,
        per_page: int = 20,
        status: Optional[str] = None,
        severity: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get findings assigned to team."""
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_get_team_assignments',
                access_token,
                {
                    'p_team_id': team_id,
                    'p_page': page,
                    'p_per_page': per_page,
                    'p_status': status,
                    'p_severity': severity
                }
            )
        )
        return result
    
    @staticmethod
    async def get_team_stats(
        access_token: str,
        team_id: str
    ) -> Dict[str, Any]:
        """Get team performance statistics."""
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_get_team_stats',
                access_token,
                {'p_team_id': team_id}
            )
        )
        return result
