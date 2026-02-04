"""
VexScan API - Translations Router
Endpoints para gestión de traducciones de vulnerabilidades
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from typing import Optional
from pydantic import BaseModel, Field
import logging

from app.core.auth import get_current_user, CurrentUser
from app.services.translation_service import translation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/translations", tags=["Translations"])


# ============================================================================
# SCHEMAS
# ============================================================================

class TranslateBatchRequest(BaseModel):
    """Request para traducción en batch."""
    batch_size: int = Field(default=5, ge=1, le=20)
    priority_severity: Optional[str] = Field(
        default=None,
        description="Priorizar severidad: Critical, High, Medium, Low, Info"
    )


class TranslateSingleRequest(BaseModel):
    """Request para traducir una vulnerabilidad específica."""
    vulnerability_id: int


class TranslationResponse(BaseModel):
    """Respuesta de traducción."""
    translated: int = 0
    failed: int = 0
    message: Optional[str] = None
    error: Optional[str] = None


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/stats")
async def get_translation_stats(
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    📊 Obtiene estadísticas de traducciones.
    
    Returns:
        - total: Total de vulnerabilidades en catálogo
        - translated: Cantidad traducidas
        - pending: Pendientes de traducir
        - failed: Traducciones fallidas permanentemente
        - by_severity: Desglose por severidad
        - by_family: Top 10 familias de plugins
    """
    try:
        stats = await translation_service.get_translation_stats(
            current_user.access_token
        )
        return {"success": True, "data": stats}
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch")
async def translate_batch(
    request: TranslateBatchRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    🔄 Traduce un lote de vulnerabilidades pendientes.
    
    Procesa hasta `batch_size` vulnerabilidades que no han sido traducidas.
    Prioriza por severidad (Critical > High > Medium > Low > Info).
    
    **Costo estimado**: ~$0.001-0.005 por vulnerabilidad con Haiku
    
    Args:
        batch_size: Cantidad de vulnerabilidades a traducir (1-20)
        priority_severity: Opcional, priorizar una severidad específica
    
    Returns:
        - translated: Cantidad traducidas exitosamente
        - failed: Cantidad que fallaron
    """
    if not translation_service.is_enabled:
        raise HTTPException(
            status_code=503,
            detail="Translation service not configured. Set ANTHROPIC_API_KEY."
        )
    
    try:
        result = await translation_service.process_pending_translations(
            access_token=current_user.access_token,
            batch_size=request.batch_size,
            priority_severity=request.priority_severity
        )
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Error in batch translation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch/background")
async def translate_batch_background(
    request: TranslateBatchRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    🔄 Inicia traducción en background (no bloquea).
    
    Útil para traducir grandes cantidades sin esperar respuesta.
    El proceso continúa en segundo plano.
    
    Returns:
        Confirmación de que el proceso fue iniciado.
    """
    if not translation_service.is_enabled:
        raise HTTPException(
            status_code=503,
            detail="Translation service not configured. Set ANTHROPIC_API_KEY."
        )
    
    async def background_translate():
        try:
            await translation_service.process_pending_translations(
                access_token=current_user.access_token,
                batch_size=request.batch_size,
                priority_severity=request.priority_severity
            )
        except Exception as e:
            logger.error(f"Background translation error: {e}")
    
    background_tasks.add_task(background_translate)
    
    return {
        "success": True,
        "status": "started",
        "message": f"Translation of up to {request.batch_size} vulnerabilities started in background"
    }


@router.post("/single")
async def translate_single(
    request: TranslateSingleRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    🔄 Traduce una vulnerabilidad específica bajo demanda.
    
    Útil para traducir cuando el usuario consulta un finding.
    Si ya está traducida, retorna la traducción existente.
    
    Args:
        vulnerability_id: ID de la vulnerabilidad en el catálogo
    
    Returns:
        - title_es, synopsis_es, description_es, solution_es
        - already_translated: true si ya existía la traducción
    """
    if not translation_service.is_enabled:
        raise HTTPException(
            status_code=503,
            detail="Translation service not configured. Set ANTHROPIC_API_KEY."
        )
    
    try:
        result = await translation_service.translate_on_demand(
            access_token=current_user.access_token,
            vulnerability_id=request.vulnerability_id
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error translating single: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pending")
async def get_pending_translations(
    limit: int = Query(default=50, le=100),
    severity: Optional[str] = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    📋 Lista vulnerabilidades pendientes de traducción.
    
    Args:
        limit: Cantidad máxima a retornar (max 100)
        severity: Filtrar por severidad
    
    Returns:
        Lista de vulnerabilidades sin traducir, ordenadas por severidad.
    """
    from app.core.supabase import supabase
    
    try:
        pending = await supabase.rpc_with_token(
            'fn_get_pending_translations',
            current_user.access_token,
            {
                'p_limit': limit,
                'p_priority_severity': severity
            }
        )
        return {
            "success": True,
            "count": len(pending) if pending else 0,
            "data": pending or []
        }
    except Exception as e:
        logger.error(f"Error getting pending: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalog")
async def list_vulnerability_catalog(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, le=100),
    severity: Optional[str] = None,
    translated_only: bool = False,
    search: Optional[str] = None,
    plugin_family: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    📚 Lista el catálogo de vulnerabilidades.
    
    Args:
        page: Número de página
        per_page: Resultados por página (max 100)
        severity: Filtrar por severidad
        translated_only: Solo mostrar traducidas
        search: Buscar en título
        plugin_family: Filtrar por familia de plugin
    
    Returns:
        Lista paginada del catálogo de vulnerabilidades.
    """
    from app.core.supabase import supabase
    
    try:
        client = supabase.get_client_with_token(current_user.access_token)
        
        query = client.table('vulnerabilities').select(
            'id, scanner, plugin_id, title, title_es, '
            'severity, plugin_family, is_translated, '
            'cvss_score, cvss3_score, created_at',
            count='exact'
        )
        
        if severity:
            query = query.eq('severity', severity)
        
        if translated_only:
            query = query.eq('is_translated', True)
        
        if search:
            query = query.ilike('title', f'%{search}%')
        
        if plugin_family:
            query = query.eq('plugin_family', plugin_family)
        
        # Paginación
        offset = (page - 1) * per_page
        query = query.order('created_at', desc=True).range(offset, offset + per_page - 1)
        
        result = query.execute()
        
        return {
            "success": True,
            "data": result.data,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": result.count
            }
        }
    except Exception as e:
        logger.error(f"Error listing catalog: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalog/{vulnerability_id}")
async def get_vulnerability_detail(
    vulnerability_id: int,
    auto_translate: bool = Query(default=False),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    🔍 Obtiene detalle de una vulnerabilidad del catálogo.
    
    Args:
        vulnerability_id: ID de la vulnerabilidad
        auto_translate: Si es true y no está traducida, la traduce automáticamente
    
    Returns:
        Detalle completo de la vulnerabilidad incluyendo traducciones.
    """
    from app.core.supabase import supabase
    
    try:
        client = supabase.get_client_with_token(current_user.access_token)
        
        result = client.table('vulnerabilities').select('*').eq(
            'id', vulnerability_id
        ).single().execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Vulnerability not found")
        
        vuln = result.data
        
        # Auto-traducir si se solicita y no está traducida
        if auto_translate and not vuln.get('is_translated') and translation_service.is_enabled:
            translation = await translation_service.translate_on_demand(
                access_token=current_user.access_token,
                vulnerability_id=vulnerability_id
            )
            if "error" not in translation:
                vuln.update(translation)
                vuln['is_translated'] = True
        
        return {"success": True, "data": vuln}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting vulnerability detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_translation_service_status(
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    ℹ️ Verifica el estado del servicio de traducciones.
    
    Returns:
        - enabled: Si el servicio está configurado
        - model: Modelo de Claude en uso
        - estimated_cost: Costo estimado por vulnerabilidad
    """
    return {
        "success": True,
        "data": {
            "enabled": translation_service.is_enabled,
            "model": translation_service.MODEL if translation_service.is_enabled else None,
            "batch_size": translation_service.DEFAULT_BATCH_SIZE,
            "estimated_cost_per_vuln": "$0.001-0.005 USD" if translation_service.is_enabled else None,
            "note": "Set ANTHROPIC_API_KEY environment variable to enable translations" if not translation_service.is_enabled else None
        }
    }
