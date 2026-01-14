"""
VexScan API - Evidence Routes
Evidence management for findings (screenshots, logs, etc.)
"""

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional, List
from pydantic import BaseModel
import io
import uuid
import hashlib
import json
import re

from app.core.auth import get_current_user, require_permission, CurrentUser
from app.core.supabase import supabase
from app.core.config import settings
from app.core.exceptions import NotFoundError, RPCError, ValidationError
from app.schemas import EvidenceResponse
import anyio

router = APIRouter(prefix="/evidence", tags=["Evidence"])


# ==================== Request Models ====================

class EvidenceCreateRequest(BaseModel):
    finding_id: str
    evidence_type: str = "other"  # initial, reproduction, mitigation, closure, retest, other
    title: Optional[str] = None
    description: Optional[str] = None
    comment: Optional[str] = None
    status_change_type: Optional[str] = None  # For mitigation/closure evidence


# ==================== Allowed Formats ====================

@router.get("/formats")
async def list_allowed_formats(
    user: CurrentUser = Depends(get_current_user)
):
    """
    List allowed evidence file formats.
    
    Returns formats with:
    - extension
    - mime_type
    - is_allowed
    - max_size
    """
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_list_evidence_formats',
            user.access_token,
            {}
        ))
        return {
            "success": True,
            "data": result or [],
            "allowed": [f for f in (result or []) if f.get('is_allowed')],
            "blocked": [f for f in (result or []) if not f.get('is_allowed')]
        }
    except Exception as e:
        raise RPCError('fn_list_evidence_formats', str(e))


# ==================== Evidence CRUD ====================

@router.get("")
async def list_evidence(
    finding_id: Optional[str] = None,
    project_id: Optional[str] = None,
    evidence_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user)
):
    """
    List evidence.
    
    Must provide either finding_id or project_id.
    """
    if not finding_id and not project_id:
        raise ValidationError("Either finding_id or project_id is required")
    
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_list_evidence',
            user.access_token,
            {
                'p_finding_id': finding_id,
                'p_project_id': project_id,
                'p_evidence_type': evidence_type,
                'p_page': page,
                'p_per_page': per_page
            }
        ))
        return result
    except Exception as e:
        raise RPCError('fn_list_evidence', str(e))


@router.post("")
async def create_evidence(
    request: EvidenceCreateRequest,
    user: CurrentUser = Depends(require_permission("evidence.create"))
):
    """
    Create evidence record (without file).
    
    Use POST /evidence/{id}/attachments to upload files.
    """
    if not user.workspace_id:
        raise ValidationError("Workspace context required")
    
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_create_evidence',
            user.access_token,
            {
                'p_workspace_id': user.workspace_id,
                'p_finding_id': request.finding_id,
                'p_evidence_type': request.evidence_type,
                'p_title': request.title,
                'p_description': request.description,
                'p_comment': request.comment,
                'p_status_change_type': request.status_change_type
            }
        ))
        return {"success": True, "message": "Evidence created", "data": result}
    except Exception as e:
        raise RPCError('fn_create_evidence', str(e))


@router.get("/{evidence_id}", response_model=EvidenceResponse)
async def get_evidence(
    evidence_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Get evidence details with attachments.
    """
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_get_evidence',
            user.access_token,
            {'p_evidence_id': evidence_id}
        ))
        if not result:
            raise NotFoundError("Evidence", evidence_id)
        return result
    except NotFoundError:
        raise
    except Exception as e:
        raise RPCError('fn_get_evidence', str(e))


@router.put("/{evidence_id}")
async def update_evidence(
    evidence_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    comment: Optional[str] = None,
    user: CurrentUser = Depends(require_permission("evidence.update"))
):
    """Update evidence details."""
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_update_evidence',
            user.access_token,
            {
                'p_evidence_id': evidence_id,
                'p_title': title,
                'p_description': description,
                'p_comment': comment
            }
        ))
        return {"success": True, "message": "Evidence updated", "data": result}
    except Exception as e:
        raise RPCError('fn_update_evidence', str(e))


@router.delete("/{evidence_id}")
async def delete_evidence(
    evidence_id: str,
    user: CurrentUser = Depends(require_permission("evidence.delete"))
):
    """
    Delete evidence and all attachments.
    """
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_delete_evidence',
            user.access_token,
            {'p_evidence_id': evidence_id}
        ))
        return {"success": True, "message": "Evidence deleted"}
    except Exception as e:
        raise RPCError('fn_delete_evidence', str(e))


# ==================== Attachments ====================

@router.post("/{evidence_id}/attachments")
async def upload_attachment(
    evidence_id: str,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(require_permission("evidence.create"))
):
    """
    Upload a file attachment to evidence.
    
    Validates:
    - File extension against allowed formats
    - File size against limits
    """
    if not user.workspace_id:
        raise ValidationError("Workspace context required")
    
    # Read file content
    content = await file.read()
    file_size = len(content)
    filename = file.filename or "attachment"
    
    # Get file extension
    ext = ""
    if "." in filename:
        ext = "." + filename.split(".")[-1].lower()
    
    # Validate extension (call RPC to check)
    try:
        format_check = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_check_evidence_format',
            user.access_token,
            {'p_extension': ext}
        ))
        
        if not format_check or not format_check.get('is_allowed'):
            raise ValidationError(f"File format '{ext}' is not allowed")
        
        max_size = format_check.get('max_size', 10 * 1024 * 1024)  # Default 10MB
        if file_size > max_size:
            raise ValidationError(f"File too large. Maximum: {max_size // (1024*1024)}MB")
            
    except ValidationError:
        raise
    except Exception:
        pass  # If check fails, proceed with upload
    
    # Upload to storage
    import uuid
    from datetime import datetime
    
    storage_path = f"{user.workspace_id}/evidence/{evidence_id}/{uuid.uuid4()}{ext}"
    
    try:
        supabase.service.storage.from_('evidence').upload(
            storage_path,
            content,
            {"content-type": file.content_type or "application/octet-stream"}
        )
    except Exception as e:
        raise RPCError('storage_upload', str(e))
    
    # Create attachment record
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_create_evidence_attachment',
            user.access_token,
            {
                'p_evidence_id': evidence_id,
                'p_file_name': filename,
                'p_file_size': file_size,
                'p_mime_type': file.content_type,
                'p_storage_path': storage_path
            }
        ))
        return {"success": True, "message": "Attachment uploaded", "data": result}
    except Exception as e:
        raise RPCError('fn_create_evidence_attachment', str(e))


@router.get("/{evidence_id}/attachments/{attachment_id}/download")
async def download_attachment(
    evidence_id: str,
    attachment_id: str,  # file_hash del archivo
    user: CurrentUser = Depends(get_current_user)
):
    """
    Descarga un archivo de evidencia.
    
    Args:
        evidence_id: ID del registro de evidencia
        attachment_id: file_hash del archivo a descargar (dentro del array files)
    """
    try:
        # Obtener información del archivo usando la nueva función
        file_info = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_get_evidence_file',
            user.access_token,
            {
                'p_evidence_id': evidence_id,
                'p_file_hash': attachment_id  # El attachment_id es el file_hash
            }
        ))
        
        if not file_info:
            raise NotFoundError("File", attachment_id)
        
        # Descargar desde storage
        storage_path = file_info.get('file_path')
        if not storage_path:
            raise NotFoundError("File", attachment_id)
        
        file_content = supabase.service.storage.from_('evidence').download(storage_path)
        
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type=file_info.get('file_type', 'application/octet-stream'),
            headers={
                "Content-Disposition": f"attachment; filename={file_info.get('file_name', 'download')}"
            }
        )
    except NotFoundError:
        raise
    except Exception as e:
        raise RPCError('download_attachment', str(e))


@router.delete("/{evidence_id}/attachments/{attachment_id}")
async def delete_attachment(
    evidence_id: str,
    attachment_id: str,  # file_hash del archivo
    user: CurrentUser = Depends(require_permission("evidence.delete"))
):
    """
    Elimina un archivo específico de una evidencia.
    
    Nota: Con la estructura optimizada, esto elimina el archivo del array JSONB files
    y del storage, pero mantiene el registro de evidencia si hay otros archivos.
    """
    try:
        # Obtener información del archivo usando la nueva función
        file_info = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_get_evidence_file',
            user.access_token,
            {
                'p_evidence_id': evidence_id,
                'p_file_hash': attachment_id  # El attachment_id es el file_hash
            }
        ))
        
        if not file_info:
            raise NotFoundError("File", attachment_id)
        
        storage_path = file_info.get('file_path')
        if storage_path:
            # Eliminar del storage
            try:
                supabase.service.storage.from_('evidence').remove([storage_path])
            except:
                pass  # Continue even if storage delete fails
        
        # Eliminar archivo del array JSONB usando función SQL
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_remove_evidence_file',
            user.access_token,
            {
                'p_evidence_id': evidence_id,
                'p_file_hash': attachment_id
            }
        ))
        
        return {
            "success": True,
            "message": "Archivo eliminado exitosamente",
            "data": result
        }
    except Exception as e:
        raise RPCError('fn_delete_evidence_attachment', str(e))


# ==================== Finding Evidence ====================

@router.get("/finding/{finding_id}")
async def get_finding_evidence(
    finding_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Get all evidence for a finding.
    
    Groups evidence by type (initial, mitigation, etc.)
    """
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_get_finding_evidence',
            user.access_token,
            {'p_finding_id': finding_id}
        ))
        
        # Group by tags (opcional, para compatibilidad)
        grouped = {}
        for ev in (result or []):
            ev_tags = ev.get('tags', [])
            if not ev_tags:
                if 'untagged' not in grouped:
                    grouped['untagged'] = []
                grouped['untagged'].append(ev)
            else:
                # Agrupar por el primer tag (extraer el valor del tag)
                if isinstance(ev_tags, list) and len(ev_tags) > 0:
                    first_tag_obj = ev_tags[0]
                    if isinstance(first_tag_obj, dict) and 'tag' in first_tag_obj:
                        first_tag = first_tag_obj['tag']
                    else:
                        first_tag = 'untagged'
                else:
                    first_tag = 'untagged'
                
                if first_tag not in grouped:
                    grouped[first_tag] = []
                grouped[first_tag].append(ev)
        
        return {
            "success": True,
            "data": result or [],
            "grouped": grouped
        }
    except Exception as e:
        raise RPCError('fn_get_finding_evidence', str(e))


# ==================== Finding Evidence (Nueva tabla finding_evidence) ====================

@router.post("/findings/{finding_id}/upload")
async def upload_finding_evidence(
    finding_id: str,
    files: List[UploadFile] = File(...),
    description: Optional[str] = Form(None),
    comments: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # JSON string array: [{"tag": "mitigation", "color": "#FF5733"}, ...]
    related_status_change_id: Optional[str] = Form(None),  # ID del cambio de estatus relacionado (opcional)
    user: CurrentUser = Depends(require_permission("evidence.create"))
):
    """
    Sube múltiples archivos como evidencia directamente a un finding.
    
    Permite subir múltiples archivos (imágenes, documentos, etc.) en una sola llamada.
    Cada archivo se almacena en storage y se crea un registro en finding_evidence.
    
    **Múltiples usuarios pueden subir evidencias para el mismo finding.**
    Cada usuario crea su propio registro de evidencia con sus archivos y comentarios.
    
    Args:
        finding_id: ID del finding al que se asociarán las evidencias
        files: Lista de archivos a subir (múltiples archivos permitidos)
        description: Descripción opcional para todas las evidencias
        comments: Comentarios opcionales para todas las evidencias
        tags: JSON string array de tags (ej: '["mitigation", "verification", "testing"]')
    
    Returns:
        Resultado con la lista de evidencias creadas
    
    Example:
        - Admin sube evidencia de mitigación: tags='[{"tag": "mitigation", "color": "#FF5733"}, {"tag": "patch", "color": "#33FF57"}]'
        - Ingeniero de Redes sube evidencia de verificación: tags='[{"tag": "verification", "color": "#3357FF"}, {"tag": "testing", "color": "#FF33F5"}]'
        - Todos pueden ver las evidencias de todos
    """
    if not user.workspace_id:
        raise ValidationError("Workspace context required")
    
    if not files:
        raise ValidationError("Al menos un archivo es requerido")
    
    # Validar límite de archivos
    if len(files) > 20:
        raise ValidationError("Máximo 20 archivos por solicitud")
    
    files_data = []
    uploaded_paths = []
    
    try:
        # Procesar cada archivo
        for file in files:
            # Leer contenido
            content = await file.read()
            file_size = len(content)
            filename = file.filename or "evidence"
            
            # Validar tamaño (50MB por archivo)
            max_size = 50 * 1024 * 1024  # 50MB
            if file_size > max_size:
                raise ValidationError(f"Archivo '{filename}' excede el tamaño máximo de 50MB")
            
            # Obtener extensión
            ext = ""
            if "." in filename:
                ext = "." + filename.split(".")[-1].lower()
            
            # Generar hash del archivo
            file_hash = hashlib.sha256(content).hexdigest()
            
            # Generar path único en storage
            # Formato: {workspace_id}/{finding_id}/{filename}
            # El bucket 'evidence' ya está especificado en el upload
            timestamp = uuid.uuid4().hex[:8]
            storage_path = f"{user.workspace_id}/{finding_id}/{timestamp}_{filename}"
            
            # Subir a storage
            try:
                supabase.service.storage.from_('evidence').upload(
                    storage_path,
                    content,
                    {"content-type": file.content_type or "application/octet-stream"}
                )
                uploaded_paths.append(storage_path)
            except Exception as e:
                # Si falla, eliminar archivos ya subidos
                for path in uploaded_paths:
                    try:
                        supabase.service.storage.from_('evidence').remove([path])
                    except:
                        pass
                raise RPCError('storage_upload', f"Error al subir '{filename}': {str(e)}")
            
            # Agregar datos del archivo (sin description/comments aquí, van a nivel del grupo)
            files_data.append({
                "file_name": filename,
                "file_path": storage_path,
                "file_size": file_size,
                "file_type": file.content_type or "application/octet-stream",
                "file_hash": file_hash
            })
        
        # Parsear tags si se proporcionan
        # Estructura esperada: [{"tag": "mitigation", "color": "#FF5733"}, ...]
        tags_jsonb = None
        if tags:
            try:
                # Si viene como string JSON, parsearlo
                if isinstance(tags, str):
                    tags_list = json.loads(tags)
                else:
                    tags_list = tags
                
                # Validar que sea una lista
                if not isinstance(tags_list, list):
                    raise ValidationError("tags debe ser un array JSON")
                
                # Validar estructura de cada tag
                for tag_item in tags_list:
                    if not isinstance(tag_item, dict):
                        raise ValidationError("Cada tag debe ser un objeto con 'tag' y 'color'")
                    if 'tag' not in tag_item or 'color' not in tag_item:
                        raise ValidationError("Cada tag debe tener 'tag' y 'color' (ej: {'tag': 'mitigation', 'color': '#FF5733'})")
                    if not isinstance(tag_item['tag'], str) or not tag_item['tag'].strip():
                        raise ValidationError("El campo 'tag' debe ser un string no vacío")
                    if not isinstance(tag_item['color'], str):
                        raise ValidationError("El campo 'color' debe ser un string")
                    # Validar formato de color (hexadecimal)
                    if not re.match(r'^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$', tag_item['color']):
                        raise ValidationError("El campo 'color' debe ser un color hexadecimal (ej: '#FF5733' o '#FF5733FF')")
                
                tags_jsonb = tags_list
            except json.JSONDecodeError:
                raise ValidationError("tags debe ser un array JSON válido")
        
        # Crear UN SOLO registro con todos los archivos en el campo files (JSONB)
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_create_finding_evidence',
            user.access_token,
            {
                'p_finding_id': finding_id,
                'p_files': files_data,  # Array de archivos
                'p_description': description,
                'p_comments': comments,
                'p_tags': tags_jsonb,  # Array de tags (JSONB)
                'p_related_status_change_id': related_status_change_id  # Opcional: relacionar con cambio de estatus
            }
        ))
        
        return {
            "success": True,
            "message": f"{len(files_data)} archivo(s) subido(s) exitosamente en un solo registro",
            "data": result
        }
        
    except ValidationError:
        # Limpiar archivos subidos si hay error de validación
        for path in uploaded_paths:
            try:
                supabase.service.storage.from_('evidence').remove([path])
            except:
                pass
        raise
    except Exception as e:
        # Limpiar archivos subidos si hay error
        for path in uploaded_paths:
            try:
                supabase.service.storage.from_('evidence').remove([path])
            except:
                pass
        raise RPCError('fn_create_finding_evidence', str(e))


@router.get("/findings/{finding_id}")
async def list_finding_evidence(
    finding_id: str,
    user: CurrentUser = Depends(require_permission("evidence.read"))
):
    """
    Lista todas las evidencias (archivos) de un finding.
    
    Retorna la lista de archivos subidos como evidencia para el finding especificado.
    """
    try:
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_list_finding_evidence',
            user.access_token,
            {'p_finding_id': finding_id}
        ))
        return {
            "success": True,
            "data": result or []
        }
    except Exception as e:
        raise RPCError('fn_list_finding_evidence', str(e))


@router.delete("/findings/{finding_id}/{evidence_id}")
async def delete_finding_evidence(
    finding_id: str,
    evidence_id: str,
    user: CurrentUser = Depends(require_permission("evidence.delete"))
):
    """
    Elimina una evidencia de un finding.
    
    Realiza soft delete del registro y elimina el archivo del storage.
    """
    try:
        # Obtener información de la evidencia antes de eliminar
        evidence_list = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_list_finding_evidence',
            user.access_token,
            {'p_finding_id': finding_id}
        ))
        
        evidence_to_delete = None
        if evidence_list:
            for ev in evidence_list:
                if ev.get('id') == evidence_id:
                    evidence_to_delete = ev
                    break
        
        if not evidence_to_delete:
            raise NotFoundError("Evidence", evidence_id)
        
        # Eliminar registro (soft delete) - esto retorna los archivos que se eliminaron
        result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_delete_finding_evidence',
            user.access_token,
            {'p_evidence_id': evidence_id}
        ))
        
        # Eliminar todos los archivos del storage (puede haber múltiples archivos en el registro)
        files_to_delete = evidence_to_delete.get('files', [])
        if files_to_delete:
            file_paths = [f.get('file_path') for f in files_to_delete if f.get('file_path')]
            if file_paths:
                try:
                    supabase.service.storage.from_('evidence').remove(file_paths)
                except Exception as e:
                    # Log pero no fallar si los archivos ya no existen
                    pass
        
        return {
            "success": True,
            "message": "Evidencia eliminada exitosamente",
            "data": result
        }
    except NotFoundError:
        raise
    except Exception as e:
        raise RPCError('fn_delete_finding_evidence', str(e))
