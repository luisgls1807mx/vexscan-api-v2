"""
VexScan API - Notifications Routes
User notifications and preferences
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from pydantic import BaseModel

from app.core.auth import get_current_user, CurrentUser
from app.core.supabase import supabase
from app.core.exceptions import NotFoundError, RPCError
from app.schemas import NotificationResponse, NotificationListResponse
import anyio

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ==================== Request Models ====================

class NotificationPreferencesUpdate(BaseModel):
    # In-App notifications
    in_app_finding_assigned: Optional[bool] = None
    in_app_finding_status_changed: Optional[bool] = None
    in_app_finding_commented: Optional[bool] = None
    in_app_team_assigned: Optional[bool] = None
    in_app_evidence_added: Optional[bool] = None
    in_app_scan_completed: Optional[bool] = None
    
    # Email notifications
    email_finding_assigned: Optional[bool] = None
    email_finding_status_changed: Optional[bool] = None
    email_daily_digest: Optional[bool] = None
    email_weekly_report: Optional[bool] = None
    
    # Webhook (for integrations)
    webhook_url: Optional[str] = None
    webhook_enabled: Optional[bool] = None


# ==================== Notifications ====================

@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    is_read: Optional[bool] = None,
    category: Optional[str] = Query(None, regex="^(finding|team|scan|system)$"),
    priority: Optional[str] = Query(None, regex="^(critical|high|medium|low)$"),
    user: CurrentUser = Depends(get_current_user)
):
    """
    List user's notifications.
    
    Filters:
    - is_read: true/false
    - category: finding, team, scan, system
    - priority: critical, high, medium, low
    
    Returns notifications and unread count.
    """
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_list_notifications',
            user.access_token,
            {
                'p_page': page,
                'p_per_page': per_page,
                'p_is_read': is_read,
                'p_category': category,
                'p_priority': priority
            }
        ))
        return result
    except Exception as e:
        raise RPCError('fn_list_notifications', str(e))


@router.get("/unread-count")
async def get_unread_count(
    user: CurrentUser = Depends(get_current_user)
):
    """Get count of unread notifications."""
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_get_unread_notifications_count',
            user.access_token,
            {}
        ))
        return {"success": True, "unread_count": result or 0}
    except Exception as e:
        raise RPCError('fn_get_unread_notifications_count', str(e))


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """Get a specific notification."""
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_get_notification',
            user.access_token,
            {'p_notification_id': notification_id}
        ))
        if not result:
            raise NotFoundError("Notification", notification_id)
        return result
    except NotFoundError:
        raise
    except Exception as e:
        raise RPCError('fn_get_notification', str(e))


@router.put("/{notification_id}/read")
async def mark_as_read(
    notification_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """Mark a notification as read."""
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_mark_notification_read',
            user.access_token,
            {'p_notification_id': notification_id}
        ))
        return {"success": True, "message": "Marked as read"}
    except Exception as e:
        raise RPCError('fn_mark_notification_read', str(e))


@router.put("/read-all")
async def mark_all_as_read(
    user: CurrentUser = Depends(get_current_user)
):
    """Mark all notifications as read."""
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_mark_all_notifications_read',
            user.access_token,
            {}
        ))
        return {"success": True, "message": f"Marked {result or 0} notifications as read"}
    except Exception as e:
        raise RPCError('fn_mark_all_notifications_read', str(e))


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """Delete a notification."""
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_delete_notification',
            user.access_token,
            {'p_notification_id': notification_id}
        ))
        return {"success": True, "message": "Notification deleted"}
    except Exception as e:
        raise RPCError('fn_delete_notification', str(e))


@router.delete("")
async def delete_all_notifications(
    only_read: bool = Query(True, description="Only delete read notifications"),
    user: CurrentUser = Depends(get_current_user)
):
    """Delete notifications (all or only read)."""
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_delete_notifications',
            user.access_token,
            {'p_only_read': only_read}
        ))
        return {"success": True, "message": f"Deleted {result or 0} notifications"}
    except Exception as e:
        raise RPCError('fn_delete_notifications', str(e))


# ==================== Notification Preferences ====================

@router.get("/preferences")
async def get_notification_preferences(
    user: CurrentUser = Depends(get_current_user)
):
    """Get user's notification preferences."""
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_get_notification_preferences',
            user.access_token,
            {}
        ))
        return {"success": True, "data": result or {}}
    except Exception as e:
        raise RPCError('fn_get_notification_preferences', str(e))


@router.put("/preferences")
async def update_notification_preferences(
    request: NotificationPreferencesUpdate,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Update notification preferences.
    
    Preferences control which notifications are sent via:
    - In-app (always stored, but can be filtered)
    - Email
    - Webhook
    """
    try:
        # Build preferences dict, excluding None values
        prefs = {k: v for k, v in request.model_dump().items() if v is not None}
        
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_update_notification_preferences',
            user.access_token,
            {'p_preferences': prefs}
        ))
        return {"success": True, "message": "Preferences updated", "data": result}
    except Exception as e:
        raise RPCError('fn_update_notification_preferences', str(e))


# ==================== Test Notifications ====================

@router.post("/test")
async def send_test_notification(
    channel: str = Query("in_app", regex="^(in_app|email|webhook)$"),
    user: CurrentUser = Depends(get_current_user)
):
    """
    Send a test notification.
    
    Useful for verifying notification settings.
    """
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_send_test_notification',
            user.access_token,
            {'p_channel': channel}
        ))
        return {"success": True, "message": f"Test notification sent via {channel}"}
    except Exception as e:
        raise RPCError('fn_send_test_notification', str(e))
