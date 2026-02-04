"""
VexScan API - AI Chat Routes
Endpoints for AI-powered vulnerability analysis
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from pydantic import BaseModel, Field

from app.core.auth import get_current_user, CurrentUser
from app.services.ai_chat_service import ai_chat_service
from app.services.ai_providers.base import VulnerabilityResponse

router = APIRouter(prefix="/ai", tags=["AI Chat"])


# ==================== Request Models ====================

class VulnerabilityQueryRequest(BaseModel):
    """Request for vulnerability analysis."""
    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Nombre o descripción de la vulnerabilidad",
        examples=["SQL Injection", "CVE-2021-44228", "Cross-Site Scripting (XSS)"]
    )
    context: Optional[str] = Field(
        None,
        max_length=1000,
        description="Contexto adicional (sistema afectado, escenario, etc.)",
        examples=["En formulario de login de aplicación PHP", "Servidor Apache 2.4"]
    )


class FindingAnalysisRequest(BaseModel):
    """Request for finding analysis from database."""
    title: str = Field(..., min_length=3, max_length=300)
    description: Optional[str] = Field(None, max_length=2000)
    cves: Optional[list[str]] = Field(None, max_length=10)
    solution: Optional[str] = Field(None, max_length=1000)


# ==================== Response Models ====================

class AIAnalysisResponse(BaseModel):
    """Structured response for vulnerability analysis."""
    success: bool
    data: VulnerabilityResponse
    provider: str
    model: str


class AIHealthResponse(BaseModel):
    """Health check response."""
    status: str
    provider: str
    model: Optional[str] = None
    error: Optional[str] = None


# ==================== Endpoints ====================

@router.post("/analyze", response_model=AIAnalysisResponse)
async def analyze_vulnerability(
    request: VulnerabilityQueryRequest,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Analizar una vulnerabilidad con IA.
    
    Envía el nombre o descripción de una vulnerabilidad y recibe:
    - **Descripción simple**: Explicación para personas no técnicas
    - **Recomendaciones**: Acciones prioritarias a tomar
    - **Proceso de mitigación**: Pasos ordenados para mitigar
    - **Riesgos de mitigación**: Qué podría salir mal al implementar
    - **Referencias**: URLs oficiales para más información
    
    **Ejemplos de queries:**
    - "SQL Injection"
    - "CVE-2021-44228" (Log4Shell)
    - "Cross-Site Scripting en formularios"
    - "Buffer Overflow en aplicaciones C"
    
    **Contexto opcional:**
    Proporciona información adicional para respuestas más precisas:
    - Sistema operativo afectado
    - Versión del software
    - Escenario específico
    """
    try:
        response = await ai_chat_service.analyze_vulnerability(
            query=request.query,
            context=request.context
        )
        
        return AIAnalysisResponse(
            success=True,
            data=response,
            provider=type(ai_chat_service.provider).__name__,
            model=ai_chat_service.provider.model
        )
        
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"AI service unavailable: {str(e)}"
        )


@router.post("/analyze-finding", response_model=AIAnalysisResponse)
async def analyze_finding(
    request: FindingAnalysisRequest,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Analizar un finding existente de VexScan.
    
    Usa los datos de un finding (título, descripción, CVEs) para
    obtener un análisis más preciso y contextualizado.
    
    Ideal para integrar el botón "Analizar con IA" en la UI.
    """
    try:
        response = await ai_chat_service.analyze_finding(
            title=request.title,
            description=request.description,
            cves=request.cves,
            solution=request.solution
        )
        
        return AIAnalysisResponse(
            success=True,
            data=response,
            provider=type(ai_chat_service.provider).__name__,
            model=ai_chat_service.provider.model
        )
        
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"AI service unavailable: {str(e)}"
        )


@router.get("/analyze", response_model=AIAnalysisResponse)
async def analyze_vulnerability_get(
    query: str = Query(
        ...,
        min_length=3,
        max_length=500,
        description="Nombre de la vulnerabilidad",
        examples=["SQL Injection", "XSS", "CVE-2021-44228"]
    ),
    context: Optional[str] = Query(
        None,
        max_length=500,
        description="Contexto adicional"
    ),
    user: CurrentUser = Depends(get_current_user)
):
    """
    Analizar vulnerabilidad (método GET).
    
    Versión GET del endpoint para facilitar pruebas y uso desde navegador.
    Para análisis con contexto extenso, usar POST.
    """
    try:
        response = await ai_chat_service.analyze_vulnerability(
            query=query,
            context=context
        )
        
        return AIAnalysisResponse(
            success=True,
            data=response,
            provider=type(ai_chat_service.provider).__name__,
            model=ai_chat_service.provider.model
        )
        
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"AI service unavailable: {str(e)}"
        )


@router.get("/health", response_model=AIHealthResponse)
async def ai_health_check():
    """
    Verificar estado del servicio de IA.
    
    Retorna el estado del proveedor configurado actualmente.
    No requiere autenticación.
    """
    result = await ai_chat_service.health_check()
    return AIHealthResponse(**result)


@router.get("/providers")
async def list_providers():
    """
    Listar proveedores de IA disponibles.
    
    Información sobre los modelos configurados para cada proveedor.
    """
    from app.services.ai_providers.base import PROVIDER_CONFIGS, AIProviderType
    
    return {
        "current_provider": type(ai_chat_service.provider).__name__,
        "current_model": ai_chat_service.provider.model,
        "available_providers": {
            provider.value: {
                "model": config["model"],
                "max_tokens": config["max_tokens"],
                "temperature": config["temperature"]
            }
            for provider, config in PROVIDER_CONFIGS.items()
        },
        "instructions": {
            "how_to_switch": "Edit app/services/ai_chat_service.py and change the AIProvider import",
            "openai": "from app.services.ai_providers.openai_provider import OpenAIProvider as AIProvider",
            "claude": "from app.services.ai_providers.claude_provider import ClaudeProvider as AIProvider",
            "gemini": "from app.services.ai_providers.gemini_provider import GeminiProvider as AIProvider"
        }
    }
