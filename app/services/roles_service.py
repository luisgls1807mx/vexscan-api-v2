"""
VexScan API - Roles Service
Business logic for role and permission management
"""

import anyio
from typing import Optional, List, Dict, Any
from app.core.supabase import supabase


class RolesService:
    """Service for managing roles and permissions."""
    
    @staticmethod
    async def list_permissions(access_token: str) -> List[Dict[str, Any]]:
        """List all available permissions."""
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token('fn_list_permissions', access_token, {})
        )
        return result or []
    
    @staticmethod
    async def group_permissions(permissions: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group permissions by category."""
        grouped = {}
        for perm in permissions:
            category = perm.get('code', '').split('.')[0]
            if category not in grouped:
                grouped[category] = []
            grouped[category].append(perm)
        return grouped
    
    @staticmethod
    async def list_roles(
        access_token: str,
        workspace_id: str,
        include_system: bool = True
    ) -> List[Dict[str, Any]]:
        """List roles for a workspace."""
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_list_roles',
                access_token,
                {'p_workspace_id': workspace_id, 'p_include_system': include_system}
            )
        )
        return result or []
    
    @staticmethod
    async def create_role(
        access_token: str,
        workspace_id: str,
        name: str,
        permissions: List[str],
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a custom role."""
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_create_role',
                access_token,
                {
                    'p_workspace_id': workspace_id,
                    'p_name': name,
                    'p_description': description,
                    'p_permissions': permissions
                }
            )
        )
        return result
    
    @staticmethod
    async def get_role(access_token: str, role_id: str) -> Optional[Dict[str, Any]]:
        """Get role details with permissions."""
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_get_role',
                access_token,
                {'p_role_id': role_id}
            )
        )
        return result
    
    @staticmethod
    async def update_role(
        access_token: str,
        role_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        permissions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Update a custom role."""
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_update_role',
                access_token,
                {
                    'p_role_id': role_id,
                    'p_name': name,
                    'p_description': description,
                    'p_permissions': permissions
                }
            )
        )
        return result
    
    @staticmethod
    async def delete_role(access_token: str, role_id: str) -> bool:
        """Delete a custom role."""
        await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_delete_role',
                access_token,
                {'p_role_id': role_id}
            )
        )
        return True
    
    @staticmethod
    async def list_role_users(
        access_token: str,
        role_id: str,
        page: int = 1,
        per_page: int = 50
    ) -> Dict[str, Any]:
        """List users assigned to a role."""
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_list_role_users',
                access_token,
                {'p_role_id': role_id, 'p_page': page, 'p_per_page': per_page}
            )
        )
        return result
    
    @staticmethod
    async def initialize_workspace_roles(
        access_token: str,
        workspace_id: str
    ) -> Dict[str, Any]:
        """Initialize default roles for a workspace."""
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_create_default_workspace_roles',
                access_token,
                {'p_workspace_id': workspace_id}
            )
        )
        return result
