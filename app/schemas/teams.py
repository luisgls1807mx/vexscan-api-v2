"""
VexScan API - Team Schemas
Team management models
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class TeamBase(BaseModel):
    """Base team fields."""
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = "#3b82f6"


class TeamCreate(TeamBase):
    """Create team."""
    organization_id: str
    leader_id: Optional[str] = None


class TeamUpdate(BaseModel):
    """Update team fields."""
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    leader_id: Optional[str] = None
    is_active: Optional[bool] = None


class TeamMemberAdd(BaseModel):
    """Add members to team."""
    user_ids: List[str]
    role: str = "member"  # "leader" or "member"


class TeamResponse(TeamBase):
    """Team response with members and stats."""
    id: str
    organization_id: str
    leader_id: Optional[str] = None
    leader_name: Optional[str] = None
    is_active: bool
    member_count: int = 0
    assigned_findings_count: int = 0
    members: List[Dict[str, Any]] = []
    created_at: datetime
