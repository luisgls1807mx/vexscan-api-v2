"""
VexScan API - AI Chat Service
Servicio de chat con IA para análisis de vulnerabilidades
"""

from typing import Optional
import structlog

from app.core.config import settings
from app.services.ai_providers.base import VulnerabilityResponse, AIProviderType

# ============================================================================
# SELECCIÓN DE PROVEEDOR DE IA
# ============================================================================
# Para cambiar de proveedor, comenta/descomenta la línea correspondiente:

# Opción 1: OpenAI (ChatGPT) - gpt-4o-mini - $0.15/1M tokens
from app.services.ai_providers.openai_provider import OpenAIProvider as AIProvider

# Opción 2: Claude (Anthropic) - claude-3-haiku - $0.25/1M tokens
#from app.services.ai_providers.claude_provider import ClaudeProvider as AIProvider

# Opción 3: Gemini (Google) - gemini-3-pro-preview - Gratis/económico
#from app.services.ai_providers.gemini_provider import GeminiProvider as AIProvider

# ============================================================================

logger = structlog.get_logger()


class AIChatService:
    """
    Service for AI-powered vulnerability analysis.
    
    Provides structured analysis with:
    - Simple description for non-technical users
    - Recommendations
    - Mitigation steps
    - Risks of mitigation
    - Reference links
    
    Usage:
        service = AIChatService()
        response = await service.analyze("SQL Injection")
    """
    
    def __init__(self):
        self._provider: Optional[AIProvider] = None
        
    @property
    def provider(self) -> AIProvider:
        """Lazy initialization of AI provider."""
        if self._provider is None:
            # Determinar API Key basada en el proveedor seleccionado
            provider_name = AIProvider.__name__
            api_key = None
            
            if provider_name == "OpenAIProvider":
                api_key = settings.OPENAI_API_KEY
            elif provider_name == "ClaudeProvider":
                api_key = settings.ANTHROPIC_API_KEY
            elif provider_name == "GeminiProvider":
                api_key = settings.GOOGLE_API_KEY
            
            # Fallback a la config genérica si no coincide (por si acaso)
            if not api_key:
                api_key = settings.AI_API_KEY

            if not api_key:
                raise ValueError(
                    f"API Key no configurada para {provider_name}. "
                    "Configura la variable de entorno correspondiente en .env "
                    "(OPENAI_API_KEY, ANTHROPIC_API_KEY, o GOOGLE_API_KEY)"
                )
            self._provider = AIProvider(api_key=api_key)
        return self._provider
    
    async def analyze_vulnerability(
        self,
        query: str,
        context: Optional[str] = None
    ) -> VulnerabilityResponse:
        """
        Analyze a vulnerability and return structured response.
        
        Args:
            query: Name or description of the vulnerability
                   Examples: "SQL Injection", "CVE-2021-44228", "XSS en formularios"
            context: Optional additional context
                     Examples: CVE details, affected system, specific scenario
                     
        Returns:
            VulnerabilityResponse with:
            - descripcion: Simple explanation
            - recomendaciones: List of recommendations
            - proceso_mitigacion: Step-by-step mitigation
            - riesgos_mitigacion: Risks when mitigating
            - referencias: Reference URLs
        """
        logger.info(
            "Analyzing vulnerability",
            query=query[:100],
            has_context=bool(context),
            provider=type(self.provider).__name__
        )
        
        try:
            response = await self.provider.analyze_vulnerability(
                query=query,
                context=context
            )
            
            logger.info(
                "Vulnerability analysis completed",
                vulnerability=response.vulnerabilidad_consultada
            )
            
            return response
            
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            # Retornar respuesta de error estructurada
            return VulnerabilityResponse(
                descripcion="No se pudo completar el análisis. Por favor, intenta de nuevo.",
                recomendaciones=["Verifica tu conexión", "Intenta con otra vulnerabilidad"],
                proceso_mitigacion=["Consulta la documentación oficial"],
                riesgos_mitigacion=["Sin información disponible"],
                referencias=["https://nvd.nist.gov", "https://cve.mitre.org"],
                vulnerabilidad_consultada=query[:100]
            )
    
    async def analyze_finding(
        self,
        title: str,
        description: Optional[str] = None,
        cves: Optional[list[str]] = None,
        solution: Optional[str] = None
    ) -> VulnerabilityResponse:
        """
        Analyze a finding from the VexScan database.
        
        This method builds context from finding data for better analysis.
        
        Args:
            title: Finding title (e.g., "Apache Log4j RCE")
            description: Finding description from scanner
            cves: List of CVE IDs
            solution: Existing solution from scanner
            
        Returns:
            VulnerabilityResponse with enhanced analysis
        """
        # Construir contexto enriquecido
        context_parts = []
        
        if cves:
            context_parts.append(f"CVEs: {', '.join(cves)}")
        if description:
            # Limitar descripción para no exceder tokens
            context_parts.append(f"Descripción técnica: {description[:500]}")
        if solution:
            context_parts.append(f"Solución sugerida por scanner: {solution[:300]}")
            
        context = "\n".join(context_parts) if context_parts else None
        
        return await self.analyze_vulnerability(
            query=title,
            context=context
        )
    
    async def health_check(self) -> dict:
        """Check AI service status."""
        try:
            is_healthy = await self.provider.health_check()
            return {
                "status": "healthy" if is_healthy else "degraded",
                "provider": type(self.provider).__name__,
                "model": self.provider.model
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# Singleton instance
ai_chat_service = AIChatService()
