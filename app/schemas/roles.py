"""
VexScan API - Role Schemas
Role and permission management models
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class RoleCreate(BaseModel):
    """Create role."""
    name: str
    description: Optional[str] = None
    permissions: List[str]


class RoleUpdate(BaseModel):
    """Update role fields."""
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None


class RoleResponse(BaseModel):
    """Role response with permissions."""
    id: str
    workspace_id: Optional[str] = None
    organization_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    is_system: bool = False
    permissions: Optional[Any] = None  # Can be list (fn_list_roles) or dict (fn_get_role)
    permissions_count: Optional[int] = None
    users_count: Optional[int] = 0
    users: Optional[List[Dict[str, Any]]] = None
    created_at: Optional[datetime] = None

