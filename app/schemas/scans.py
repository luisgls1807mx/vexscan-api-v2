"""
VexScan API - Scan Import Schemas
Scanner file import and comparison models
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel

from .common import ImportStatus, NetworkZone


class ScanImportCreate(BaseModel):
    """Create scan import."""
    project_id: Optional[str] = None
    network_zone: NetworkZone = NetworkZone.INTERNAL


class ScanImportResponse(BaseModel):
    """Scan import response with stats."""
    id: str
    workspace_id: str
    project_id: Optional[str] = None
    file_name: str
    scanner: str
    status: ImportStatus
    network_zone: NetworkZone
    
    findings_total: int = 0
    findings_new: int = 0
    findings_updated: int = 0
    findings_closed: int = 0
    hosts_total: int = 0
    
    uploaded_by: str
    imported_at: datetime
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class ScanDiffResponse(BaseModel):
    """Scan comparison/diff response."""
    scan_id: str
    previous_scan_id: Optional[str] = None
    new_findings: Optional[List[Dict[str, Any]]] = []
    resolved_findings: Optional[List[Dict[str, Any]]] = []
    persistent_findings: Optional[List[Dict[str, Any]]] = []
    reopened_findings: Optional[List[Dict[str, Any]]] = []
    
    summary: Optional[Dict[str, int]] = {}


class ScanDiffSummary(BaseModel):
    """Scan diff summary only (lazy loading)."""
    scan_id: str
    previous_scan_id: Optional[str] = None
    summary: Dict[str, int] = {
        "new": 0,
        "resolved": 0,
        "persistent": 0,
        "reopened": 0
    }


class ScanDiffFindings(BaseModel):
    """Paginated findings for a specific diff type."""
    data: List[Dict[str, Any]]
    pagination: Dict[str, Any]
