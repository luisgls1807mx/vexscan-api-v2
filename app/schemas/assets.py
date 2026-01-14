"""
VexScan API - Asset Schemas
Asset/host management models
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


class AssetBase(BaseModel):
    """Base asset fields."""
    identifier: str
    name: Optional[str] = None
    hostname: Optional[str] = None
    ip_address: Optional[str] = None


class AssetCreate(AssetBase):
    """Create asset."""
    project_id: Optional[str] = None
    asset_type: str = "host"
    operating_system: Optional[str] = None
    environment: Optional[str] = None
    criticality: Optional[str] = None
    owner: Optional[str] = None
    tags: Optional[List[str]] = None


class AssetUpdate(BaseModel):
    """Update asset fields."""
    name: Optional[str] = None
    hostname: Optional[str] = None
    operating_system: Optional[str] = None
    environment: Optional[str] = None
    criticality: Optional[str] = None
    owner: Optional[str] = None
    tags: Optional[List[str]] = None


class AssetResponse(AssetBase):
    """Asset response with stats."""
    id: str
    workspace_id: str
    project_id: Optional[str] = None
    asset_type: str
    operating_system: Optional[str] = None
    environment: Optional[str] = None
    criticality: Optional[str] = None
    owner: Optional[str] = None
    tags: Optional[List[str]] = None
    is_manual: bool
    
    first_seen: datetime
    last_seen: datetime
    
    # Stats
    findings_count: int = 0
    critical_count: int = 0
    high_count: int = 0
