"""
VexScan API - Findings Service
Vulnerability management using Supabase RPC functions
"""

from typing import Optional, Dict, Any, List
from datetime import date
import logging

from app.core.supabase import supabase
from app.core.exceptions import NotFoundError, RPCError, ValidationError
import anyio

logger = logging.getLogger(__name__)


class FindingsService:
    """Service for finding/vulnerability operations."""
    
    async def list_findings(
        self,
        access_token: str,
        project_id: str,
        page: int = 1,
        per_page: int = 50,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        hostname: Optional[str] = None,
        ip_address: Optional[str] = None,
        port: Optional[int] = None,
        assigned_to_me: Optional[bool] = None,
        assigned_to_team: Optional[str] = None,
        diff_type: Optional[str] = None,
        scan_id: Optional[str] = None,
        sort_by: str = "severity",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """
        List findings with filters.
        
        Returns:
            Dict with data, pagination, and summary by severity
        """
        try:
            # Construir parámetros (coincide con la firma de la función SQL)
            params = {
                'p_project_id': project_id,
                'p_page': page,
                'p_per_page': per_page,
                'p_severity': severity,
                'p_status': status,
                'p_search': search,
                'p_hostname': hostname,
                'p_ip_address': ip_address,
                'p_assigned_to_me': assigned_to_me if assigned_to_me is not None else False,
                'p_assigned_to_team': assigned_to_team,  # UUID del team
                'p_diff_type': diff_type,
                'p_scan_id': scan_id,
                'p_sort_by': sort_by if sort_by else 'last_seen',
                'p_sort_order': sort_order if sort_order else 'desc'
            }
            # Eliminar solo parámetros NULL (p_assigned_to_me siempre se envía con su valor o False)
            params = {k: v for k, v in params.items() if v is not None}
            
            result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
                'fn_list_findings',
                access_token,
                params
            ))
            return result
        except Exception as e:
            logger.error(f"Error listing findings: {e}")
            raise RPCError('fn_list_findings', str(e))
    
    async def get_finding(
        self,
        access_token: str,
        finding_id: str
    ) -> Dict[str, Any]:
        """Get finding details with assignments, comments, evidence."""
        try:
            result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
                'fn_get_finding',
                access_token,
                {'p_finding_id': finding_id}
            ))
            
            if not result:
                raise NotFoundError("Finding", finding_id)
            
            return result
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error getting finding: {e}")
            raise RPCError('fn_get_finding', str(e))
    
    async def update_finding_status(
        self,
        access_token: str,
        finding_id: str,
        status: str,
        comment: str,
        evidence_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Update finding status.
        
        Validations:
        - Mitigated: requires comment + evidence
        - Accepted Risk / False Positive: requires comment
        
        Triggers:
        - Calculates time_to_mitigate
        - Creates status history
        - Notifies assignees
        """
        try:
            result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
                'fn_update_finding_status',
                access_token,
                {
                    'p_finding_id': finding_id,
                    'p_status': status,
                    'p_comment': comment,
                    'p_evidence_ids': evidence_ids or []
                }
            ))
            return result
        except Exception as e:
            error_msg = str(e)
            # Check for validation errors from the function
            if 'evidencia obligatoria' in error_msg.lower():
                raise ValidationError("Evidence required for Mitigated status")
            if 'comentario obligatorio' in error_msg.lower():
                raise ValidationError("Comment required for this status change")
            
            logger.error(f"Error updating finding status: {e}")
            raise RPCError('fn_update_finding_status', str(e))
    
    async def assign_finding(
        self,
        access_token: str,
        finding_id: str,
        user_ids: Optional[List[str]] = None,
        team_ids: Optional[List[str]] = None,
        due_date: Optional[date] = None,
        priority: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Assign finding to users and/or teams.
        
        Triggers:
        - Creates assignment records
        - Notifies all assignees
        - Records in assignment history
        """
        try:
            result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
                'fn_assign_finding',
                access_token,
                {
                    'p_finding_id': finding_id,
                    'p_user_ids': user_ids or [],
                    'p_team_ids': team_ids or [],
                    'p_due_date': due_date.isoformat() if due_date else None,
                    'p_priority': priority,
                    'p_notes': notes
                }
            ))
            return result
        except Exception as e:
            logger.error(f"Error assigning finding: {e}")
            raise RPCError('fn_assign_finding', str(e))
    
    async def add_comment(
        self,
        access_token: str,
        finding_id: str,
        content: str,
        is_internal: bool = False
    ) -> Dict[str, Any]:
        """Add a comment to a finding."""
        try:
            result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
                'fn_add_finding_comment',
                access_token,
                {
                    'p_finding_id': finding_id,
                    'p_content': content,
                    'p_is_internal': is_internal
                }
            ))
            return result
        except Exception as e:
            logger.error(f"Error adding comment: {e}")
            raise RPCError('fn_add_finding_comment', str(e))
    
    async def get_finding_history(
        self,
        access_token: str,
        finding_id: str
    ) -> List[Dict[str, Any]]:
        """Get complete history (status changes, assignments, comments, evidence)."""
        try:
            result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
                'fn_get_finding_history',
                access_token,
                {'p_finding_id': finding_id}
            ))
            return result or []
        except Exception as e:
            logger.error(f"Error getting finding history: {e}")
            raise RPCError('fn_get_finding_history', str(e))


findings_service = FindingsService()
