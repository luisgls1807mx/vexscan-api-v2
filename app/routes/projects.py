"""
VexScan API - Projects Routes
Project management endpoints
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional

from app.core.auth import get_current_user, get_org_admin, CurrentUser
from app.services.projects_service import projects_service
from app.schemas import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    PaginatedResponse
)

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("", response_model=PaginatedResponse)
async def list_projects(
    organization_id: str,
    workspace_id: Optional[str] = Query(None, description="Filter by workspace"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, regex="^(active|archived|completed)$"),
    search: Optional[str] = None,
    user: CurrentUser = Depends(get_current_user)
):
    """
    List projects for an organization.
    
    Optionally filter by workspace_id to get only projects in that workspace.
    Returns projects with vulnerability stats.
    """
    result = await projects_service.list_projects(
        user.access_token,
        organization_id=organization_id,
        workspace_id=workspace_id,
        page=page,
        per_page=per_page,
        status=status,
        search=search
    )
    return result


@router.post("", response_model=ProjectResponse)
async def create_project(
    request: ProjectCreate,
    user: CurrentUser = Depends(get_org_admin)
):
    """
    Create a new project.
    
    Requires org_admin role.
    If workspace_id is provided, the project will be associated with that workspace.
    """
    result = await projects_service.create_project(
        user.access_token,
        organization_id=request.organization_id,
        name=request.name,
        workspace_id=getattr(request, 'workspace_id', None),
        description=request.description,
        color=request.color,
        leader_id=request.leader_id,
        responsible_id=request.responsible_id
    )
    return result


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Get project details with stats.
    
    Includes:
    - Vulnerability counts by severity
    - Asset count
    - Recent scans
    """
    result = await projects_service.get_project(
        user.access_token,
        project_id
    )
    return result


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    request: ProjectUpdate,
    user: CurrentUser = Depends(get_current_user)
):
    """Update project details."""
    result = await projects_service.update_project(
        user.access_token,
        project_id=project_id,
        name=request.name,
        description=request.description,
        color=request.color,
        status=request.status,
        responsible_id=request.responsible_id
    )
    return result
