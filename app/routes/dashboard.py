"""
VexScan API - Dashboard Routes
Analytics and reporting endpoints
"""

import anyio
from fastapi import APIRouter, Depends, Query
from typing import Optional
from datetime import date, datetime, timedelta

from app.core.auth import get_current_user, get_super_admin, CurrentUser
from app.core.supabase import supabase
from app.core.exceptions import RPCError
from app.schemas import DashboardResponse, DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ==================== Super Admin Dashboard ====================

@router.get("/super-admin")
async def get_super_admin_dashboard(
    user: CurrentUser = Depends(get_super_admin)
):
    """Super Admin dashboard (platform-wide)."""
    try:
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_get_dashboard_super_admin',
                user.access_token,
                {}
            )
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise RPCError('fn_get_dashboard_super_admin', str(e))


# ==================== Organization Dashboard ====================

@router.get("/organization/{organization_id}")
async def get_organization_dashboard(
    organization_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """Organization dashboard."""
    try:
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_get_dashboard_organization',
                user.access_token,
                {'p_organization_id': organization_id}
            )
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise RPCError('fn_get_dashboard_organization', str(e))


@router.get("/project/{project_id}")
async def get_project_dashboard(
    project_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """Project dashboard."""
    try:
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_get_dashboard_project',
                user.access_token,
                {'p_project_id': project_id}
            )
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise RPCError('fn_get_dashboard_project', str(e))


# ==================== User Dashboard ====================

@router.get("/my")
async def get_my_dashboard(
    user: CurrentUser = Depends(get_current_user)
):
    """Personal dashboard for current user."""
    try:
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_get_dashboard_user',
                user.access_token,
                {}
            )
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise RPCError('fn_get_dashboard_user', str(e))


# ==================== Trends & Analytics ====================

@router.get("/trends/{organization_id}")
async def get_trends(
    organization_id: str,
    period: str = Query("3m", regex="^(1m|3m|6m|1y|all)$"),
    user: CurrentUser = Depends(get_current_user)
):
    """Get finding trends over time."""
    try:
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_get_trends',
                user.access_token,
                {
                    'p_organization_id': organization_id,
                    'p_period': period
                }
            )
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise RPCError('fn_get_trends', str(e))


@router.get("/severity-breakdown/{organization_id}")
async def get_severity_breakdown(
    organization_id: str,
    project_id: Optional[str] = None,
    user: CurrentUser = Depends(get_current_user)
):
    """Get findings breakdown by severity."""
    try:
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_get_severity_breakdown',
                user.access_token,
                {
                    'p_organization_id': organization_id,
                    'p_project_id': project_id
                }
            )
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise RPCError('fn_get_severity_breakdown', str(e))


@router.get("/status-breakdown/{organization_id}")
async def get_status_breakdown(
    organization_id: str,
    project_id: Optional[str] = None,
    user: CurrentUser = Depends(get_current_user)
):
    """Get findings breakdown by status."""
    try:
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_get_status_breakdown',
                user.access_token,
                {
                    'p_organization_id': organization_id,
                    'p_project_id': project_id
                }
            )
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise RPCError('fn_get_status_breakdown', str(e))


# ==================== MTTR (Mean Time to Remediate) ====================

@router.get("/mttr/{organization_id}")
async def get_mttr(
    organization_id: str,
    period: str = Query("3m", regex="^(1m|3m|6m|1y|all)$"),
    group_by: str = Query("severity", regex="^(severity|project|team|month)$"),
    user: CurrentUser = Depends(get_current_user)
):
    """Get Mean Time to Remediate (MTTR) statistics."""
    try:
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_get_mttr',
                user.access_token,
                {
                    'p_organization_id': organization_id,
                    'p_period': period,
                    'p_group_by': group_by
                }
            )
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise RPCError('fn_get_mttr', str(e))


# ==================== Top Lists ====================

@router.get("/top-vulnerabilities/{organization_id}")
async def get_top_vulnerabilities(
    organization_id: str,
    limit: int = Query(10, ge=1, le=50),
    user: CurrentUser = Depends(get_current_user)
):
    """Get top recurring vulnerabilities."""
    try:
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_get_top_vulnerabilities',
                user.access_token,
                {
                    'p_organization_id': organization_id,
                    'p_limit': limit
                }
            )
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise RPCError('fn_get_top_vulnerabilities', str(e))


@router.get("/top-assets/{organization_id}")
async def get_top_assets(
    organization_id: str,
    limit: int = Query(10, ge=1, le=50),
    user: CurrentUser = Depends(get_current_user)
):
    """Get assets with most critical/high findings."""
    try:
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_get_top_assets',
                user.access_token,
                {
                    'p_organization_id': organization_id,
                    'p_limit': limit
                }
            )
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise RPCError('fn_get_top_assets', str(e))


@router.get("/top-performers/{organization_id}")
async def get_top_performers(
    organization_id: str,
    period: str = Query("1m", regex="^(1m|3m|6m|1y)$"),
    limit: int = Query(10, ge=1, le=50),
    user: CurrentUser = Depends(get_current_user)
):
    """Get top performing users/teams by findings mitigated."""
    try:
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_get_top_performers',
                user.access_token,
                {
                    'p_organization_id': organization_id,
                    'p_period': period,
                    'p_limit': limit
                }
            )
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise RPCError('fn_get_top_performers', str(e))


# ==================== Recent Activity ====================

@router.get("/activity/{organization_id}")
async def get_recent_activity(
    organization_id: str,
    limit: int = Query(20, ge=1, le=100),
    activity_type: Optional[str] = None,
    user: CurrentUser = Depends(get_current_user)
):
    """Get recent activity feed."""
    try:
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_get_recent_activity',
                user.access_token,
                {
                    'p_organization_id': organization_id,
                    'p_limit': limit,
                    'p_activity_type': activity_type
                }
            )
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise RPCError('fn_get_recent_activity', str(e))


# ==================== SLA Compliance ====================

@router.get("/sla/{organization_id}")
async def get_sla_compliance(
    organization_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """Get SLA compliance metrics."""
    try:
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                'fn_get_sla_compliance',
                user.access_token,
                {'p_organization_id': organization_id}
            )
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise RPCError('fn_get_sla_compliance', str(e))
