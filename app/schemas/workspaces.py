"""
VexScan API - Workspace Schemas
Workspace management models
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class WorkspaceBase(BaseModel):
    """Base workspace fields."""
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None


class WorkspaceCreate(WorkspaceBase):
    """Create workspace."""
    organization_id: str


class WorkspaceResponse(WorkspaceBase):
    """Workspace response."""
    id: str
    organization_id: str
    is_active: bool
    created_at: datetime
