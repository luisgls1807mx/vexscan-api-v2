"""
VexScan API - Common Schemas
Base models and enums shared across the application
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from enum import Enum


# ==================== Enums ====================

class SeverityLevel(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Info"


class FindingStatus(str, Enum):
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    WAITING = "Waiting"
    MITIGATED = "Mitigated"
    ACCEPTED_RISK = "Accepted Risk"
    FALSE_POSITIVE = "False Positive"
    NOT_OBSERVED = "Not Observed"


class ImportStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class NetworkZone(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class OrgRole(str, Enum):
    ORG_ADMIN = "org_admin"
    ORG_MEMBER = "org_member"


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ==================== Base Response Models ====================

class BaseResponse(BaseModel):
    """Base response model."""
    success: bool = True
    message: Optional[str] = None


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""
    data: List[Any]
    pagination: Dict[str, int]


class ErrorResponse(BaseModel):
    """Error response model."""
    success: bool = False
    error: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
