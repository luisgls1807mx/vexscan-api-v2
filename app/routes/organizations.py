"""
VexScan API - Organizations Routes
Organization management endpoints (Super Admin only)
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional

from app.core.auth import get_current_user, get_super_admin, CurrentUser
from app.services.organizations_service import organizations_service
from app.schemas import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    PaginatedResponse,
    BaseResponse
)

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("", response_model=PaginatedResponse)
async def list_organizations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    user: CurrentUser = Depends(get_super_admin)
):
    """
    List all organizations (Super Admin only).
    
    Returns organizations with stats (projects, users, findings counts).
    """
    result = await organizations_service.list_organizations(
        user.access_token,
        page=page,
        per_page=per_page,
        search=search,
        is_active=is_active
    )
    return result


@router.post("", response_model=OrganizationResponse)
async def create_organization(
    request: OrganizationCreate,
    user: CurrentUser = Depends(get_super_admin)
):
    """
    Create a new organization (Super Admin only).
    
    This creates:
    - Organization
    - Default workspace
    - Admin user with org_admin role
    - Default roles (Admin, Analyst, Viewer)
    """
    result = await organizations_service.create_organization(
        user.access_token,
        name=request.name,
        slug=request.slug,
        admin_email=request.admin_email,
        admin_name=request.admin_name,
        admin_password=request.admin_password,
        settings=request.settings
    )
    return result


@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """Get organization details with stats."""
    result = await organizations_service.get_organization(
        user.access_token,
        organization_id
    )
    return result


@router.put("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    organization_id: str,
    request: OrganizationUpdate,
    user: CurrentUser = Depends(get_super_admin)
):
    """Update organization (Super Admin only)."""
    result = await organizations_service.update_organization(
        user.access_token,
        organization_id,
        name=request.name,
        is_active=request.is_active,
        settings=request.settings
    )
    return result
