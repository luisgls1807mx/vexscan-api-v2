"""
VexScan API - Notification Schemas
User notification models
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


class NotificationResponse(BaseModel):
    """Single notification."""
    id: str
    type: str
    category: str
    priority: str
    title: str
    body: Optional[str] = None
    is_read: bool
    finding_id: Optional[str] = None
    project_id: Optional[str] = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Notification list with unread count."""
    data: List[NotificationResponse]
    unread_count: int
