"""
VexScan API - Organization Schemas
Organization management models
"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr


class OrganizationBase(BaseModel):
    """Base organization fields."""
    name: str
    slug: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class OrganizationCreate(OrganizationBase):
    """Create organization with admin user."""
    admin_email: EmailStr
    admin_name: str
    admin_password: str


class OrganizationUpdate(BaseModel):
    """Update organization fields."""
    name: Optional[str] = None
    is_active: Optional[bool] = None
    settings: Optional[Dict[str, Any]] = None


class OrganizationResponse(OrganizationBase):
    """Organization response with stats."""
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    # Stats
    projects_count: int = 0
    users_count: int = 0
    findings_count: int = 0
