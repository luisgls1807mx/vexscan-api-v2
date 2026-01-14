"""
VexScan API - Organizations Service
Organization management using Supabase RPC functions
"""

from typing import Optional, Dict, Any, List
import logging

from app.core.supabase import supabase
from app.core.exceptions import NotFoundError, RPCError
import anyio

logger = logging.getLogger(__name__)


class OrganizationsService:
    """Service for organization operations."""
    
    async def list_organizations(
        self,
        access_token: str,
        page: int = 1,
        per_page: int = 20,
        search: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        List all organizations (super_admin only).
        
        Returns:
            Dict with data and pagination
        """
        try:
            result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
                'fn_list_organizations',
                access_token,
                {
                    'p_page': page,
                    'p_per_page': per_page,
                    'p_search': search,
                    'p_is_active': is_active
                }
            ))
            return result
        except Exception as e:
            logger.error(f"Error listing organizations: {e}")
            raise RPCError('fn_list_organizations', str(e))
    
    async def create_organization(
        self,
        access_token: str,
        name: str,
        admin_email: str,
        admin_name: str,
        admin_password: str,
        slug: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new organization with admin user.
        
        This creates:
        - Admin user in Supabase Auth
        - Organization
        - Default workspace
        - Admin user with org_admin role
        - Default roles (Admin, Analyst, Viewer)
        """
        try:
            # 1. Crear usuario en Supabase Auth usando service role
            auth_response = await anyio.to_thread.run_sync(
                lambda: supabase.service.auth.admin.create_user({
                    "email": admin_email,
                    "password": admin_password,
                    "email_confirm": True,
                    "user_metadata": {
                        "full_name": admin_name
                    }
                })
            )
            
            # Obtener el user_id de la respuesta
            if not auth_response or not hasattr(auth_response, 'user') or not auth_response.user:
                raise RPCError('fn_create_organization', 'Failed to create admin user in Auth')
            
            admin_user_id = auth_response.user.id
            
            # 2. Llamar a la función RPC con el user_id
            # IMPORTANTE: La función SQL debe tener p_admin_user_id UUID en su firma
            result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
                'fn_create_organization',
                access_token,
                {
                    'p_name': name,
                    'p_admin_email': admin_email,
                    'p_admin_full_name': admin_name,
                    'p_admin_user_id': admin_user_id
                }
            ))
            return result
        except Exception as e:
            logger.error(f"Error creating organization: {e}")
            raise RPCError('fn_create_organization', str(e))
    
    async def get_organization(
        self,
        access_token: str,
        organization_id: str
    ) -> Dict[str, Any]:
        """Get organization details with stats."""
        try:
            result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
                'fn_get_organization',
                access_token,
                {'p_org_id': organization_id}
            ))
            
            if not result:
                raise NotFoundError("Organization", organization_id)
            
            return result
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error getting organization: {e}")
            raise RPCError('fn_get_organization', str(e))
    
    async def update_organization(
        self,
        access_token: str,
        organization_id: str,
        name: Optional[str] = None,
        is_active: Optional[bool] = None,
        settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Update organization details."""
        try:
            result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
                'fn_update_organization',
                access_token,
                {
                    'p_organization_id': organization_id,
                    'p_name': name,
                    'p_is_active': is_active,
                    'p_settings': settings
                }
            ))
            return result
        except Exception as e:
            logger.error(f"Error updating organization: {e}")
            raise RPCError('fn_update_organization', str(e))


organizations_service = OrganizationsService()
