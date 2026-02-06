"""
VexScan API - Service Schemas
Models for network services (ports) found on assets
"""

from typing import Optional
from pydantic import BaseModel

class ServiceResponse(BaseModel):
    """Service/Port details aggregating findings."""
    asset_id: str
    asset_identifier: str
    asset_hostname: Optional[str] = None
    port: int
    protocol: Optional[str] = "tcp"
    service_name: Optional[str] = None
    vuln_count: int = 0
    status: str = "open"
