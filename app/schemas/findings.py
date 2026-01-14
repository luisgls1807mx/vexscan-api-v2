"""
VexScan API - Finding Schemas
Vulnerability finding models
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, date
from pydantic import BaseModel, field_validator

from .common import SeverityLevel, FindingStatus, Priority


class FindingBase(BaseModel):
    """Base finding fields."""
    title: str
    description: Optional[str] = None
    solution: Optional[str] = None
    severity: SeverityLevel
    location: Optional[str] = None


class FindingCreate(FindingBase):
    """For manual finding creation."""
    project_id: str
    asset_id: Optional[str] = None
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    port: Optional[int] = None
    cves: Optional[List[str]] = None
    cvss_score: Optional[float] = None


class FindingUpdate(BaseModel):
    """Update finding fields."""
    severity: Optional[SeverityLevel] = None
    severity_justification: Optional[str] = None
    owasp_category: Optional[str] = None
    external_ticket_id: Optional[str] = None
    external_ticket_url: Optional[str] = None


class FindingStatusUpdate(BaseModel):
    """Update finding status with validation."""
    status: FindingStatus
    comment: str
    evidence_ids: Optional[List[str]] = None
    
    @field_validator('comment')
    @classmethod
    def comment_required_for_closure(cls, v, info):
        status = info.data.get('status')
        if status in [FindingStatus.MITIGATED, FindingStatus.ACCEPTED_RISK, FindingStatus.FALSE_POSITIVE]:
            if not v or len(v.strip()) < 10:
                raise ValueError(f"Comment required (min 10 chars) for status '{status}'")
        return v


class FindingAssignment(BaseModel):
    """Assign finding to users/teams."""
    user_ids: Optional[List[str]] = None
    team_ids: Optional[List[str]] = None
    due_date: Optional[date] = None
    priority: Optional[Priority] = None
    notes: Optional[str] = None


class FindingComment(BaseModel):
    """Add comment to finding."""
    content: str
    is_internal: bool = False


class FindingResponse(BaseModel):
    """Complete finding response."""
    id: str
    workspace_id: str
    project_id: Optional[str] = None
    asset_id: Optional[str] = None
    
    folio: str
    title: str
    description: Optional[str] = None
    solution: Optional[str] = None
    location: Optional[str] = None
    
    severity: SeverityLevel
    original_severity: Optional[str] = None
    status: FindingStatus
    
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = None
    service: Optional[str] = None
    
    cves: Optional[List[str]] = None
    cvss_score: Optional[float] = None
    cvss_vector: Optional[str] = None
    cwe: Optional[str] = None
    
    scanner: str
    scanner_finding_id: Optional[str] = None
    fingerprint: str
    
    first_seen: datetime
    last_seen: datetime
    last_activity_at: datetime
    
    is_reopened: bool = False
    reopen_count: int = 0
    time_to_mitigate: Optional[str] = None
    
    # Related
    assigned_users: List[Dict[str, Any]] = []
    assigned_teams: List[Dict[str, Any]] = []
    comment_count: int = 0
    evidence_count: int = 0
    
    created_at: datetime
    updated_at: datetime


class FindingListResponse(BaseModel):
    """Paginated finding list with summary."""
    data: List[FindingResponse]
    pagination: Dict[str, int]
    summary: Dict[str, int] = {}
