"""
VexScan API - Projects Service
Project management using Supabase RPC functions
"""

from typing import Optional, Dict, Any
import logging

from app.core.supabase import supabase
from app.core.exceptions import NotFoundError, RPCError
import anyio

logger = logging.getLogger(__name__)


class ProjectsService:
    """Service for project operations."""
    
    async def list_projects(
        self,
        access_token: str,
        organization_id: str,
        workspace_id: Optional[str] = None,  # Nuevo parámetro
        page: int = 1,
        per_page: int = 20,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """List projects with stats. Optionally filter by workspace."""
        try:
            result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
                'fn_list_projects',
                access_token,
                {
                    'p_org_id': organization_id,
                    'p_workspace_id': workspace_id,  # Nuevo parámetro
                    'p_page': page,
                    'p_per_page': per_page,
                    'p_status': status,
                    'p_search': search
                }
            ))
            return result
        except Exception as e:
            logger.error(f"Error listing projects: {e}")
            raise RPCError('fn_list_projects', str(e))
    
    async def create_project(
        self,
        access_token: str,
        organization_id: str,
        name: str,
        leader_id: str,
        workspace_id: Optional[str] = None,  # Nuevo parámetro
        description: Optional[str] = None,
        color: Optional[str] = None,
        responsible_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new project."""
        try:
            result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
                'fn_create_project',
                access_token,
                {
                    'p_org_id': organization_id,
                    'p_workspace_id': workspace_id,  # Nuevo parámetro
                    'p_name': name,
                    'p_description': description,
                    'p_color': color or '#3b82f6',
                    'p_leader_id': leader_id,
                    'p_responsible_id': responsible_id
                }
            ))
            return result
        except Exception as e:
            logger.error(f"Error creating project: {e}")
            raise RPCError('fn_create_project', str(e))
    
    async def get_project(
        self,
        access_token: str,
        project_id: str
    ) -> Dict[str, Any]:
        """Get project details with stats."""
        try:
            result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
                'fn_get_project',
                access_token,
                {'p_project_id': project_id}
            ))
            
            if not result:
                raise NotFoundError("Project", project_id)
            
            return result
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error getting project: {e}")
            raise RPCError('fn_get_project', str(e))
    
    async def update_project(
        self,
        access_token: str,
        project_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None,
        status: Optional[str] = None,
        responsible_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update project details."""
        try:
            result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
                'fn_update_project',
                access_token,
                {
                    'p_project_id': project_id,
                    'p_name': name,
                    'p_description': description,
                    'p_color': color,
                    'p_status': status,
                    'p_responsible_id': responsible_id
                }
            ))
            return result
        except Exception as e:
            logger.error(f"Error updating project: {e}")
            raise RPCError('fn_update_project', str(e))


projects_service = ProjectsService()
