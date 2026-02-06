"""
VexScan API - Schemas Package
Centralized exports for all Pydantic schemas
"""

# Common (Enums and Base Models)
from .common import (
    # Enums
    SeverityLevel,
    FindingStatus,
    ImportStatus,
    NetworkZone,
    OrgRole,
    Priority,
    # Base Responses
    BaseResponse,
    PaginatedResponse,
    ErrorResponse,
)

# Auth
from .auth import (
    LoginRequest,
    LoginResponse,
    UserProfile,
    UpdateProfileRequest,
)

# Organizations
from .organizations import (
    OrganizationBase,
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
)

# Workspaces
from .workspaces import (
    WorkspaceBase,
    WorkspaceCreate,
    WorkspaceResponse,
)

# Projects
from .projects import (
    ProjectBase,
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
)

# Teams
from .teams import (
    TeamBase,
    TeamCreate,
    TeamUpdate,
    TeamMemberAdd,
    TeamResponse,
)

# Users
from .users import (
    UserCreate,
    UserUpdate,
    UserResponse,
)

# Roles
from .roles import (
    RoleCreate,
    RoleUpdate,
    RoleResponse,
)

# Findings
from .findings import (
    FindingBase,
    FindingCreate,
    FindingUpdate,
    FindingStatusUpdate,
    FindingAssignment,
    FindingComment,
    FindingResponse,
    FindingListResponse,
)

# Services
from .services import ServiceResponse

# Assets
from .assets import (
    AssetBase,
    AssetCreate,
    AssetUpdate,
    AssetResponse,
)

# Scans
from .scans import (
    ScanImportCreate,
    ScanImportResponse,
    ScanDiffResponse,
    ScanDiffSummary,
    ScanDiffFindings,
)

# Evidence
from .evidence import (
    EvidenceCreate,
    EvidenceResponse,
)

# Notifications
from .notifications import (
    NotificationResponse,
    NotificationListResponse,
)

# Dashboard
from .dashboard import (
    DashboardSummary,
    DashboardResponse,
)

__all__ = [
    # Enums
    "SeverityLevel",
    "FindingStatus",
    "ImportStatus",
    "NetworkZone",
    "OrgRole",
    "Priority",
    # Base
    "BaseResponse",
    "PaginatedResponse",
    "ErrorResponse",
    # Auth
    "LoginRequest",
    "LoginResponse",
    "UserProfile",
    "UpdateProfileRequest",
    # Organizations
    "OrganizationBase",
    "OrganizationCreate",
    "OrganizationUpdate",
    "OrganizationResponse",
    # Workspaces
    "WorkspaceBase",
    "WorkspaceCreate",
    "WorkspaceResponse",
    # Projects
    "ProjectBase",
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectResponse",
    # Teams
    "TeamBase",
    "TeamCreate",
    "TeamUpdate",
    "TeamMemberAdd",
    "TeamResponse",
    # Users
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    # Roles
    "RoleCreate",
    "RoleUpdate",
    "RoleResponse",
    # Findings
    "FindingBase",
    "FindingCreate",
    "FindingUpdate",
    "FindingStatusUpdate",
    "FindingAssignment",
    "FindingComment",
    "FindingResponse",
    "FindingListResponse",
    # Assets
    "AssetBase",
    "AssetCreate",
    "AssetUpdate",
    "AssetResponse",
    # Services
    "ServiceResponse",
    # Scans
    "ScanImportCreate",
    "ScanImportResponse",
    "ScanDiffResponse",
    "ScanDiffSummary",
    "ScanDiffFindings",
    # Evidence
    "EvidenceCreate",
    "EvidenceResponse",
    # Notifications
    "NotificationResponse",
    "NotificationListResponse",
    # Dashboard
    "DashboardSummary",
    "DashboardResponse",
]
