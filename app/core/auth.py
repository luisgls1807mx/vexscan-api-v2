"""
VexScan API - Authentication & Dependencies
Handles JWT validation and user context
"""

import anyio
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import jwt, JWTError
import logging

from app.core.config import settings
from app.core.supabase import supabase, SupabaseClient

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    """Current authenticated user context."""
    id: str
    email: str
    full_name: Optional[str] = None
    is_super_admin: bool = False
    organization_id: Optional[str] = None
    workspace_id: Optional[str] = None
    role: Optional[str] = None
    permissions: list[str] = []
    
    # Raw token for passing to RPC calls
    access_token: str


class AuthService:
    """Authentication service using Supabase Auth."""
    
    def __init__(self, supabase_client: SupabaseClient):
        self.supabase = supabase_client
    
    async def get_current_user(
        self,
        credentials: Optional[HTTPAuthorizationCredentials],
        workspace_id: Optional[str] = None
    ) -> CurrentUser:
        """
        Validate JWT token and return user context.
        
        Args:
            credentials: Bearer token from request
            workspace_id: Optional workspace context
            
        Returns:
            CurrentUser with full context
        """
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        token = credentials.credentials
        
        try:
            # Verify token with Supabase (sync call wrapped in thread)
            user_response = await anyio.to_thread.run_sync(
                lambda: self.supabase.anon.auth.get_user(token)
            )
            
            if not user_response or not user_response.user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token"
                )
            
            supabase_user = user_response.user
            
            # Get user profile from our profiles table using RPC
            profile = await anyio.to_thread.run_sync(
                lambda: self.supabase.rpc_with_token(
                    'fn_get_current_user_profile',
                    token
                )
            )
            
            if not profile:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User profile not found"
                )
            
            # Build CurrentUser
            return CurrentUser(
                id=supabase_user.id,
                email=supabase_user.email,
                full_name=profile.get('full_name'),
                is_super_admin=profile.get('is_super_admin', False),
                organization_id=profile.get('organization_id'),
                workspace_id=workspace_id or profile.get('default_workspace_id'),
                role=profile.get('role'),
                permissions=profile.get('permissions', []),
                access_token=token
            )
            
        except HTTPException:
            raise
        except JWTError as e:
            logger.error(f"JWT validation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format"
            )
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed"
            )
    
    async def verify_permission(
        self,
        user: CurrentUser,
        permission: str
    ) -> bool:
        """Check if user has a specific permission."""
        if user.is_super_admin:
            return True
        return permission in user.permissions
    
    async def verify_workspace_access(
        self,
        user: CurrentUser,
        workspace_id: str
    ) -> bool:
        """Verify user has access to workspace."""
        if user.is_super_admin:
            return True
        
        # Call RPC to verify access
        result = await anyio.to_thread.run_sync(
            lambda: self.supabase.rpc_with_token(
                'fn_verify_workspace_access',
                user.access_token,
                {'p_workspace_id': workspace_id}
            )
        )
        
        return result is True


# Dependency instances
auth_service = AuthService(supabase)


# ==================== FastAPI Dependencies ====================

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-ID")
) -> CurrentUser:
    """
    Dependency to get current authenticated user.
    
    Usage:
        @router.get("/items")
        async def list_items(user: CurrentUser = Depends(get_current_user)):
            ...
    """
    return await auth_service.get_current_user(credentials, x_workspace_id)


async def get_current_active_user(
    user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """Dependency that ensures user is active."""
    # Could add additional checks here
    return user


async def get_super_admin(
    user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """Dependency that requires super_admin role."""
    if not user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    return user


async def get_org_admin(
    user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """Dependency that requires org_admin role."""
    if not user.is_super_admin and user.role != 'org_admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization admin access required"
        )
    return user


def require_permission(permission: str):
    """
    Factory for permission-checking dependency.
    
    Usage:
        @router.post("/items")
        async def create_item(
            user: CurrentUser = Depends(require_permission("items.create"))
        ):
            ...
    """
    async def check_permission(
        user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        if not user.is_super_admin and permission not in user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission} required"
            )
        return user
    
    return check_permission


def require_workspace():
    """
    Dependency that requires a workspace context.
    
    Usage:
        @router.get("/findings")
        async def list_findings(
            user: CurrentUser = Depends(require_workspace())
        ):
            # user.workspace_id is guaranteed to be set
            ...
    """
    async def check_workspace(
        user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        if not user.workspace_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workspace context required. Set X-Workspace-ID header."
            )
        return user
    
    return check_workspace
