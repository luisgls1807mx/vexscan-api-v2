"""
VexScan API - Findings Routes
Vulnerability management endpoints
"""

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException
from typing import Optional, List
import logging
import json
from datetime import datetime
from uuid import uuid4
import hashlib

from app.core.auth import get_current_user, require_permission, CurrentUser
from app.core.supabase import supabase
from app.core.exceptions import RPCError, ValidationError
from app.core.config import settings
from app.services.findings_service import findings_service
import anyio

logger = logging.getLogger(__name__)
from app.schemas import (
    FindingResponse,
    FindingListResponse,
    FindingStatusUpdate,
    FindingAssignment,
    FindingComment,
    BaseResponse
)

router = APIRouter(prefix="/findings", tags=["Findings"])


@router.get("", response_model=FindingListResponse)
async def list_findings(
    project_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    severity: Optional[str] = Query(None, regex="^(Critical|High|Medium|Low|Info)$"),
    status: Optional[str] = None,
    search: Optional[str] = None,
    hostname: Optional[str] = None,
    ip_address: Optional[str] = None,
    port: Optional[int] = None,
    assigned_to_me: Optional[bool] = None,
    assigned_to_team: Optional[str] = None,
    diff_type: Optional[str] = Query(None, regex="^(new|resolved|persistent|reopened)$"),
    scan_id: Optional[str] = None,
    sort_by: str = Query("severity", regex="^(severity|first_seen|last_activity_at|folio)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    user: CurrentUser = Depends(require_permission("findings.read"))
):
    """
    List findings for a project.
    
    Supports extensive filtering:
    - severity: Critical, High, Medium, Low, Info
    - status: Open, In Progress, Waiting, Mitigated, Accepted Risk, False Positive
    - search: Text search in title
    - hostname/ip_address/port: Location filters
    - assigned_to_me: Only my assignments
    - assigned_to_team: Filter by team
    - diff_type: new, resolved, persistent, reopened (requires scan_id)
    - scan_id: Diff against specific scan
    
    Returns findings with summary by severity.
    """
    result = await findings_service.list_findings(
        user.access_token,
        project_id=project_id,
        page=page,
        per_page=per_page,
        severity=severity,
        status=status,
        search=search,
        hostname=hostname,
        ip_address=ip_address,
        port=port,
        assigned_to_me=assigned_to_me,
        assigned_to_team=assigned_to_team,
        diff_type=diff_type,
        scan_id=scan_id,
        sort_by=sort_by,
        sort_order=sort_order
    )
    return result


@router.get("/{finding_id}", response_model=FindingResponse)
async def get_finding(
    finding_id: str,
    user: CurrentUser = Depends(require_permission("findings.read"))
):
    """
    Get finding details.
    
    Includes:
    - Full vulnerability information
    - Assigned users and teams
    - External ticket info
    - Scanner data
    """
    result = await findings_service.get_finding(
        user.access_token,
        finding_id
    )
    return result


@router.put("/{finding_id}/status")
async def update_finding_status(
    finding_id: str,
    request: FindingStatusUpdate,
    user: CurrentUser = Depends(require_permission("findings.change_status"))
):
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
    result = await findings_service.update_finding_status(
        user.access_token,
        finding_id=finding_id,
        status=request.status.value,
        comment=request.comment,
        evidence_ids=request.evidence_ids
    )
    return {
        "success": True,
        "message": f"Status updated to '{request.status.value}'",
        "data": result
    }


@router.post("/{finding_id}/assign")
async def assign_finding(
    finding_id: str,
    request: FindingAssignment,
    user: CurrentUser = Depends(require_permission("findings.assign"))
):
    """
    Assign finding to users and/or teams.
    
    Triggers:
    - Creates assignment records
    - Notifies all assignees
    - Records in assignment history
    """
    result = await findings_service.assign_finding(
        user.access_token,
        finding_id=finding_id,
        user_ids=request.user_ids,
        team_ids=request.team_ids,
        due_date=request.due_date,
        priority=request.priority.value if request.priority else None,
        notes=request.notes
    )
    return {
        "success": True,
        "message": "Finding assigned successfully",
        "data": result
    }


@router.post("/{finding_id}/comments")
async def add_comment(
    finding_id: str,
    request: FindingComment,
    user: CurrentUser = Depends(require_permission("findings.comment"))
):
    """Add a comment to a finding."""
    result = await findings_service.add_comment(
        user.access_token,
        finding_id=finding_id,
        content=request.content,
        is_internal=request.is_internal
    )
    return {
        "success": True,
        "message": "Comment added",
        "data": result
    }


@router.get("/{finding_id}/history")
async def get_finding_history(
    finding_id: str,
    user: CurrentUser = Depends(require_permission("findings.read"))
):
    """
    Get complete finding history.
    
    Includes:
    - Status changes
    - Assignments
    - Comments
    - Evidence uploads
    """
    result = await findings_service.get_finding_history(
        user.access_token,
        finding_id
    )
    return {
        "success": True,
        "data": result
    }


@router.get("/{finding_id}/status-history")
async def get_status_history(
    finding_id: str,
    page: int = Query(1, ge=1, description="Número de página"),
    per_page: int = Query(20, ge=1, le=100, description="Elementos por página (máximo 100)"),
    user: CurrentUser = Depends(require_permission("findings.read"))
):
    """
    Obtiene el historial paginado de cambios de estatus con evidencias relacionadas.
    
    Retorna:
    - Lista de cambios de estatus ordenados por fecha (más reciente primero)
    - Cada cambio incluye:
      - Estatus anterior y nuevo
      - Usuario que hizo el cambio
      - Fecha y hora
      - Comentario
      - Evidencias relacionadas (si las hay)
    - Información de paginación (total, página actual, total de páginas)
    
    Parámetros:
    - page: Número de página (default: 1)
    - per_page: Elementos por página (default: 20, máximo: 100)
    """
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_get_finding_status_history_with_evidence',
            user.access_token,
            {
                'p_finding_id': finding_id,
                'p_page': page,
                'p_per_page': per_page
            }
        ))
        return {
            "success": True,
            "data": result.get('data', []) if result else [],
            "pagination": result.get('pagination', {}) if result else {
                "page": page,
                "per_page": per_page,
                "total": 0,
                "total_pages": 0
            }
        }
    except Exception as e:
        logger.error(f"Error getting status history: {e}")
        raise RPCError('fn_get_finding_status_history_with_evidence', str(e))


# ==================== Complete with Evidence ====================

@router.post("/{finding_id}/complete-with-evidence")
async def complete_finding_with_evidence(
    finding_id: str,
    status: str = Form(..., description="Nuevo estado: Mitigated, Accepted Risk, False Positive"),
    comment: str = Form(..., description="Comentario/justificación del cambio"),
    files: List[UploadFile] = File(default=[], description="Archivos de evidencia"),
    description: Optional[str] = Form(None, description="Descripción de la evidencia"),
    tags: Optional[str] = Form(None, description='Tags como JSON array: ["remediación", "parche"]'),
    evidence_comments: Optional[str] = Form(None, description="Comentarios adicionales sobre la evidencia"),
    user: CurrentUser = Depends(require_permission("findings.change_status"))
):
    """
    Completar trabajo en un finding con evidencia.
    
    Este endpoint combina:
    1. Subida de archivos de evidencia al storage
    2. Creación de registros de evidencia
    3. Actualización del status del finding
    
    Validaciones:
    - Mitigated: requiere al menos un archivo de evidencia
    - Accepted Risk / False Positive: requiere comentario
    
    Content-Type: multipart/form-data
    """
    # Validar status permitidos
    valid_statuses = ["Mitigated", "Accepted Risk", "False Positive", "Not Observed"]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": f"Estado inválido. Debe ser uno de: {', '.join(valid_statuses)}",
                "error_code": "INVALID_STATUS"
            }
        )
    
    # Validar que Mitigated requiere evidencia
    if status == "Mitigated" and len(files) == 0:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": "El estado 'Mitigated' requiere al menos un archivo de evidencia",
                "error_code": "EVIDENCE_REQUIRED"
            }
        )
    
    # Validar comentario
    if not comment or len(comment.strip()) == 0:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": "Se requiere un comentario para este cambio de estado",
                "error_code": "COMMENT_REQUIRED"
            }
        )
    
    # Parsear tags si vienen
    parsed_tags = []
    if tags:
        try:
            parsed_tags = json.loads(tags)
        except json.JSONDecodeError:
            parsed_tags = [t.strip() for t in tags.split(",") if t.strip()]
    
    # Obtener información del finding para workspace_id
    try:
        finding_info = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_get_finding',
            user.access_token,
            {'p_finding_id': finding_id}
        ))
        if not finding_info:
            raise HTTPException(status_code=404, detail={"success": False, "error": "Finding no encontrado"})
        
        workspace_id = finding_info.get('workspace_id')
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting finding: {e}")
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)})
    
    # Subir archivos al storage y preparar array para RPC
    files_data = []  # Array para fn_create_finding_evidence
    evidence_files = []  # Para la respuesta
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    
    for file in files:
        try:
            # Leer contenido del archivo
            content = await file.read()
            file_size = len(content)
            
            # Validar tamaño
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "success": False,
                        "error": f"El archivo '{file.filename}' excede el tamaño máximo permitido (50MB)",
                        "error_code": "FILE_TOO_LARGE"
                    }
                )
            
            # Generar path único en storage
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid4())[:8]
            file_hash = hashlib.sha256(content).hexdigest()[:12]
            storage_path = f"{workspace_id}/evidence/{finding_id}/{timestamp}_{unique_id}_{file.filename}"
            
            # Subir al storage usando closure para capturar valores correctamente
            def upload_file(path, data, ctype):
                return supabase.service.storage.from_("evidence").upload(
                    path, data, {"content-type": ctype}
                )
            
            await anyio.to_thread.run_sync(
                lambda p=storage_path, c=content, t=file.content_type: upload_file(p, c, t or "application/octet-stream")
            )
            
            # Agregar al array de archivos para el RPC
            files_data.append({
                "file_name": file.filename,
                "file_path": storage_path,
                "file_size": file_size,
                "file_type": file.content_type or "application/octet-stream",
                "file_hash": file_hash
            })
            
            evidence_files.append({
                "file_name": file.filename,
                "file_size": file_size,
                "file_type": file.content_type
            })
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error uploading evidence file {file.filename}: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "error": f"Error subiendo archivo '{file.filename}': {str(e)}",
                    "error_code": "UPLOAD_ERROR"
                }
            )
    
    # PASO 1: Crear registro de evidencia PRIMERO (sin status_change_id por ahora)
    # Esto es necesario porque el RPC fn_update_finding_status verifica que exista evidencia para Mitigated
    evidence_id = None
    formatted_tags = []
    
    if len(files_data) > 0:
        try:
            # Parsear tags al formato esperado por el RPC: [{tag: string, color: string}, ...]
            if parsed_tags:
                colors = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"]
                for i, tag in enumerate(parsed_tags):
                    if isinstance(tag, str):
                        formatted_tags.append({
                            "tag": tag,
                            "color": colors[i % len(colors)]
                        })
                    elif isinstance(tag, dict) and 'tag' in tag:
                        formatted_tags.append(tag)
            
            evidence_result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
                'fn_create_finding_evidence',
                user.access_token,
                {
                    'p_finding_id': finding_id,
                    'p_files': files_data,
                    'p_description': description,
                    'p_comments': evidence_comments,
                    'p_tags': formatted_tags if formatted_tags else None,
                    'p_related_status_change_id': None  # Sin status_change_id por ahora
                }
            ))
            
            evidence_id = evidence_result.get('id') if evidence_result else None
            
            # Actualizar evidence_files con el ID
            for ef in evidence_files:
                ef["evidence_id"] = evidence_id
                
        except Exception as e:
            logger.error(f"Error creating evidence record: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "error": f"Error creando registro de evidencia: {str(e)}",
                    "error_code": "EVIDENCE_CREATE_ERROR"
                }
            )
    
    # PASO 2: Actualizar status del finding (ahora encontrará la evidencia que acabamos de crear)
    status_change_id = None
    previous_status = None
    try:
        status_result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_update_finding_status',
            user.access_token,
            {
                'p_finding_id': finding_id,
                'p_status': status,
                'p_comment': comment,
                'p_evidence_ids': [evidence_id] if evidence_id else []
            }
        ))
        
        status_change_id = status_result.get('status_change_id') if status_result else None
        previous_status = status_result.get('from_status') if status_result else None
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error updating finding status: {e}")
        
        if 'evidencia obligatoria' in error_msg.lower():
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "El estado 'Mitigated' requiere al menos un archivo de evidencia",
                    "error_code": "EVIDENCE_REQUIRED"
                }
            )
        
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "error_code": "RPC_ERROR"
            }
        )
    
    # PASO 3: Actualizar la evidencia para vincularla al status_change_id
    if evidence_id and status_change_id:
        try:
            await anyio.to_thread.run_sync(lambda: supabase.service.table('finding_evidence').update({
                'related_status_change_id': status_change_id
            }).eq('id', evidence_id).execute())
        except Exception as e:
            # Log pero no fallar, la evidencia ya fue creada
            logger.warning(f"Could not link evidence to status change: {e}")
    
    # Respuesta exitosa
    return {
        "success": True,
        "message": "Estado actualizado con evidencia",
        "data": {
            "finding_id": finding_id,
            "status_change_id": status_change_id,
            "new_status": status,
            "previous_status": previous_status,
            "evidence_count": len(evidence_files),
            "evidence_files": evidence_files,
            "evidence_id": evidence_id,
            "time_to_mitigate_hours": status_result.get('time_to_mitigate_hours') if status_result else None,
            "changed_at": datetime.utcnow().isoformat() + "Z",
            "changed_by": {
                "id": user.id,
                "full_name": user.full_name or user.email
            }
        }
    }



