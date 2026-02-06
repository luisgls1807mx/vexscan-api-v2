"""
VexScan API - Project Schemas
Project management models
"""

from typing import Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel


class ProjectBase(BaseModel):
    """Base project fields."""
    name: str
    description: Optional[str] = None
    color: Optional[str] = "#3b82f6"


class ProjectCreate(ProjectBase):
    """Create project."""
    organization_id: str
    workspace_id: Optional[str] = None  # Nuevo: asociar proyecto a workspace
    leader_id: str
    responsible_id: Optional[str] = None


class ProjectUpdate(BaseModel):
    """Update project fields."""
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    status: Optional[str] = None
    responsible_id: Optional[str] = None
    workspace_id: Optional[str] = None  # Nuevo: cambiar workspace del proyecto


class ProjectResponse(ProjectBase):
    """Project response with stats."""
    id: str
    organization_id: str
    workspace_id: Optional[str] = None  # Nuevo: workspace del proyecto
    slug: Optional[str] = None
    status: str
    # Leader puede venir como objeto {id, full_name} desde el RPC
    leader: Optional[Dict[str, Any]] = None
    leader_id: Optional[str] = None
    leader_name: Optional[str] = None
    # Responsible puede venir como objeto {id, full_name} desde el RPC
    responsible: Optional[Dict[str, Any]] = None
    responsible_id: Optional[str] = None
    responsible_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    # Stats (pueden venir del RPC o calcularse)
    stats: Optional[Dict[str, Any]] = None
    total_findings: int = 0
    open_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    total_assets: int = 0
    services_count: int = 0
    last_scan_at: Optional[datetime] = None

