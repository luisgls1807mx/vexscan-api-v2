"""
VexScan API - Evidence Schemas
Evidence and attachment models for findings
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class TagWithColor(BaseModel):
    """Tag con color asociado."""
    tag: str = Field(..., description="Nombre del tag")
    color: str = Field(..., description="Color hexadecimal (ej: #FF5733 o #FF5733FF)", pattern=r'^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$')


class EvidenceCreate(BaseModel):
    """Create evidence."""
    finding_id: str
    tags: Optional[List[TagWithColor]] = []  # Array de tags con color
    title: Optional[str] = None
    description: Optional[str] = None
    comment: Optional[str] = None
    status_change_type: Optional[str] = None


class EvidenceResponse(BaseModel):
    """Evidence response with attachments."""
    id: str
    finding_id: str
    tags: Optional[List[TagWithColor]] = []  # Array de tags con color
    title: Optional[str] = None
    description: Optional[str] = None
    comment: Optional[str] = None
    uploaded_by: str
    uploader_name: Optional[str] = None
    attachments: List[Dict[str, Any]] = []
    created_at: datetime
