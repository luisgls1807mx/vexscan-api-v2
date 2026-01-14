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
    workspace_id: str
    name: str
    description: Optional[str] = None
    is_system: bool
    permissions: List[Dict[str, Any]] = []
    users_count: int = 0
    created_at: datetime
