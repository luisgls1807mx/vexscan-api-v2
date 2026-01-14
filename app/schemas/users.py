"""
VexScan API - User Schemas
User management models
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    """Create user."""
    email: EmailStr
    full_name: str
    password: str
    role_id: str


class UserUpdate(BaseModel):
    """Update user fields."""
    full_name: Optional[str] = None
    role_id: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    """User response with assignment stats."""
    id: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    label: Optional[str] = None
    is_active: bool
    role_id: Optional[str] = None
    role_name: Optional[str] = None
    assigned_findings: int = 0
    mitigated_findings: int = 0
    created_at: datetime
