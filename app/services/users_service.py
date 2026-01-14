"""
VexScan API - Users Service
Business logic for user management
"""

from typing import Optional, Dict, Any
from app.core.supabase import supabase
import anyio


class UsersService:
    """Service for managing users."""
    
    @staticmethod
    async def list_organization_members(
        access_token: str,
        organization_id: str,
        page: int = 1,
        per_page: int = 50,
        search: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        List organization members.
        
        Args:
            access_token: User's access token
            organization_id: Organization ID
            page: Page number
            per_page: Items per page
            search: Search term
            role: Filter by role
            is_active: Filter by active status
            
        Returns:
            Paginated members list
        """
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_list_organization_members',
            access_token,
            {
                'p_organization_id': organization_id,
                'p_page': page,
                'p_per_page': per_page,
                'p_search': search,
                'p_role': role,
                'p_is_active': is_active
            }
        ))
        return result
    
    @staticmethod
    async def add_organization_member(
        access_token: str,
        organization_id: str,
        email: str,
        full_name: str,
        password: str,
        role_id: str
    ) -> Dict[str, Any]:
        """
        Create and add user to organization.
        
        Args:
            access_token: User's access token
            organization_id: Organization ID
            email: User email
            full_name: User full name
            password: User password
            role_id: Role ID
            
        Returns:
            Created user
        """
        from app.core.exceptions import RPCError
        
        # 1. Crear usuario en Supabase Auth usando service role
        try:
            auth_response = await anyio.to_thread.run_sync(
                lambda: supabase.service.auth.admin.create_user({
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {
                        "full_name": full_name
                    }
                })
            )
            
            if not auth_response or not hasattr(auth_response, 'user') or not auth_response.user:
                raise RPCError('fn_create_organization_member', 'Failed to create user in Auth')
            
            user_id = str(auth_response.user.id)
        except Exception as e:
            raise RPCError('fn_create_organization_member', f'Error creating auth user: {str(e)}')
        
        # 2. Llamar al RPC para crear profile y memberships
        try:
            result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
                'fn_create_organization_member',
                access_token,
                {
                    'p_organization_id': organization_id,
                    'p_user_id': user_id,
                    'p_email': email,
                    'p_full_name': full_name,
                    'p_role_id': role_id
                }
            ))
            return result
        except Exception as e:
            # Si falla el RPC, intentar eliminar el usuario de Auth para mantener consistencia
            try:
                await anyio.to_thread.run_sync(
                    lambda: supabase.service.auth.admin.delete_user(user_id)
                )
            except:
                pass  # Ignorar error de cleanup
            raise RPCError('fn_create_organization_member', str(e))
    
    @staticmethod
    async def invite_organization_member(
        access_token: str,
        organization_id: str,
        email: str,
        full_name: str,
        role_id: str,
        send_email: bool = True
    ) -> Dict[str, Any]:
        """
        Invite user to organization.
        
        Args:
            access_token: User's access token
            organization_id: Organization ID
            email: User email
            full_name: User full name
            role_id: Role ID
            send_email: Send invitation email
            
        Returns:
            Invitation details
        """
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_invite_organization_member',
            access_token,
            {
                'p_organization_id': organization_id,
                'p_email': email,
                'p_full_name': full_name,
                'p_role_id': role_id,
                'p_send_email': send_email
            }
        ))
        return result
    
    @staticmethod
    async def list_workspace_users(
        access_token: str,
        workspace_id: str,
        page: int = 1,
        per_page: int = 50,
        search: Optional[str] = None,
        role_id: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        List workspace users.
        
        Args:
            access_token: User's access token
            workspace_id: Workspace ID
            page: Page number
            per_page: Items per page
            search: Search term
            role_id: Filter by role ID
            is_active: Filter by active status
            
        Returns:
            Paginated users list
        """
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_list_workspace_users',
            access_token,
            {
                'p_workspace_id': workspace_id,
                'p_page': page,
                'p_per_page': per_page,
                'p_search': search,
                'p_role_id': role_id,
                'p_is_active': is_active
            }
        ))
        return result
    
    @staticmethod
    async def get_user(access_token: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user details.
        
        Args:
            access_token: User's access token
            user_id: User ID
            
        Returns:
            User details or None
        """
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_get_user',
            access_token,
            {'p_user_id': user_id}
        ))
        return result
    
    @staticmethod
    async def update_user(
        access_token: str,
        user_id: str,
        full_name: Optional[str] = None,
        role_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        label: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update user details.
        
        Args:
            access_token: User's access token
            user_id: User ID
            full_name: New full name
            role_id: New role ID
            is_active: Active status
            label: User label
            
        Returns:
            Updated user
        """
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_update_user',
            access_token,
            {
                'p_user_id': user_id,
                'p_full_name': full_name,
                'p_role_id': role_id,
                'p_is_active': is_active,
                'p_label': label
            }
        ))
        return result
    
    @staticmethod
    async def deactivate_user(access_token: str, user_id: str) -> bool:
        """
        Deactivate user.
        
        Args:
            access_token: User's access token
            user_id: User ID
            
        Returns:
            True if deactivated
        """
        await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_deactivate_user',
            access_token,
            {'p_user_id': user_id}
        ))
        return True
    
    @staticmethod
    async def change_user_role(
        access_token: str,
        user_id: str,
        role_id: str,
        workspace_id: str
    ) -> Dict[str, Any]:
        """
        Change user's role in workspace.
        
        Args:
            access_token: User's access token
            user_id: User ID
            role_id: New role ID
            workspace_id: Workspace ID
            
        Returns:
            Updated assignment
        """
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_change_user_role',
            access_token,
            {
                'p_user_id': user_id,
                'p_role_id': role_id,
                'p_workspace_id': workspace_id
            }
        ))
        return result
    
    @staticmethod
    async def get_user_stats(
        access_token: str,
        user_id: str,
        organization_id: str
    ) -> Dict[str, Any]:
        """
        Get user activity statistics.
        
        Args:
            access_token: User's access token
            user_id: User ID
            organization_id: Organization ID
            
        Returns:
            User statistics
        """
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_get_user_stats',
            access_token,
            {
                'p_user_id': user_id,
                'p_organization_id': organization_id
            }
        ))
        return result
    
    @staticmethod
    async def get_user_assignments(
        access_token: str,
        user_id: str,
        page: int = 1,
        per_page: int = 20,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get findings assigned to user.
        
        Args:
            access_token: User's access token
            user_id: User ID
            page: Page number
            per_page: Items per page
            status: Filter by status
            
        Returns:
            Paginated findings list
        """
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_get_user_assignments',
            access_token,
            {
                'p_user_id': user_id,
                'p_page': page,
                'p_per_page': per_page,
                'p_status': status
            }
        ))
        return result
