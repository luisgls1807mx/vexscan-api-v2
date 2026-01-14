"""
VexScan API - Auth Schemas
Authentication and user profile models
"""

from typing import Optional, List
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class UserProfile(BaseModel):
    """User profile information."""
    id: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    label: Optional[str] = None
    is_super_admin: bool = False
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    role: Optional[str] = None
    permissions: List[str] = []


class LoginResponse(BaseModel):
    """Successful login response."""
    access_token: str
    refresh_token: str  # Añadido para poder refrescar el token
    token_type: str = "bearer"
    expires_in: int
    user: UserProfile


class UpdateProfileRequest(BaseModel):
    """Update user profile request."""
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    label: Optional[str] = None


# Rebuild for forward references
LoginResponse.model_rebuild()
