"""
VexScan API - Routes Module
All API endpoints organized by resource
"""

from fastapi import APIRouter

# Import all routers
from app.routes.auth import router as auth_router
from app.routes.organizations import router as organizations_router
from app.routes.workspaces import router as workspaces_router
from app.routes.users import router as users_router
from app.routes.roles import router as roles_router
from app.routes.projects import router as projects_router
from app.routes.teams import router as teams_router
from app.routes.assets import router as assets_router
from app.routes.findings import router as findings_router
from app.routes.scans import router as scans_router
from app.routes.scans_experimental import router as scans_experimental_router
from app.routes.evidence import router as evidence_router
from app.routes.notifications import router as notifications_router
from app.routes.dashboard import router as dashboard_router

# Main router
api_router = APIRouter()

# Include all routers
api_router.include_router(auth_router)
api_router.include_router(organizations_router)
api_router.include_router(workspaces_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(projects_router)
api_router.include_router(teams_router)
api_router.include_router(assets_router)
api_router.include_router(findings_router)
api_router.include_router(scans_router)
api_router.include_router(scans_experimental_router)
api_router.include_router(evidence_router)
api_router.include_router(notifications_router)
api_router.include_router(dashboard_router)

__all__ = ["api_router"]
