"""
VexScan API - Dashboard Schemas
Dashboard summary and statistics models
"""

from typing import Optional, Dict, List, Any
from pydantic import BaseModel


class DashboardSummary(BaseModel):
    """Dashboard summary statistics."""
    total_findings: int = 0
    open_findings: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    mitigated_this_month: int = 0
    avg_mttr_days: Optional[float] = None


class DashboardResponse(BaseModel):
    """Complete dashboard response."""
    summary: DashboardSummary
    by_severity: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    recent_activity: List[Dict[str, Any]] = []
    trends: Dict[str, Any] = {}
