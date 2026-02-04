"""
VexScan API - AI Provider Base
Abstract base class for AI chat providers
"""

from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel
from enum import Enum


class VulnerabilityResponse(BaseModel):
    """Structured response for vulnerability analysis."""
    descripcion: str  # Descripción simple para no técnicos
    recomendaciones: list[str]  # Lista de recomendaciones
    proceso_mitigacion: list[str]  # Pasos del proceso
    riesgos_mitigacion: list[str]  # Riesgos al mitigar
    referencias: list[str]  # URLs de referencia
    vulnerabilidad_consultada: str  # Nombre de la vulnerabilidad
    

class AIProviderType(str, Enum):
    OPENAI = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"


class BaseAIProvider(ABC):
    """
    Abstract base class for AI providers.
    
    To switch providers, change the import in ai_chat_service.py:
    
    # For OpenAI:
    from app.services.ai_providers.openai_provider import OpenAIProvider as AIProvider
    
    # For Claude:
    from app.services.ai_providers.claude_provider import ClaudeProvider as AIProvider
    
    # For Gemini:
    from app.services.ai_providers.gemini_provider import GeminiProvider as AIProvider
    """
    
    # System prompt optimizado para respuestas concisas y estructuradas
    SYSTEM_PROMPT = """Eres un experto en ciberseguridad especializado en análisis y mitigación de vulnerabilidades. 
Tu objetivo es explicar vulnerabilidades de manera clara y concisa.

REGLAS IMPORTANTES:
1. Responde ÚNICAMENTE en formato JSON válido
2. Usa español claro y simple que cualquier persona pueda entender
3. Sé conciso: máximo 2-3 oraciones por punto en descripción
4. Las listas deben tener máximo 5 elementos cada una
5. Solo incluye información verificable y práctica
6. Si no conoces la vulnerabilidad exacta, indica que necesitas más contexto

FORMATO DE RESPUESTA (JSON estricto):
{
    "descripcion": "Explicación simple de qué es y qué hace esta vulnerabilidad (2-3 oraciones)",
    "recomendaciones": ["recomendación 1", "recomendación 2", "..."],
    "proceso_mitigacion": ["paso 1", "paso 2", "..."],
    "riesgos_mitigacion": ["riesgo 1", "riesgo 2", "..."],
    "referencias": ["https://url1.com", "https://url2.com"],
    "vulnerabilidad_consultada": "nombre de la vulnerabilidad"
}

NOTAS:
- En "descripcion": explica como si hablaras con alguien sin conocimientos técnicos
- En "recomendaciones": acciones específicas y priorizadas
- En "proceso_mitigacion": pasos ordenados y claros
- En "riesgos_mitigacion": qué podría salir mal al implementar las mitigaciones
- En "referencias": solo URLs oficiales (NIST, MITRE, vendors, OWASP)"""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        
    @abstractmethod
    async def analyze_vulnerability(
        self,
        query: str,
        context: Optional[str] = None
    ) -> VulnerabilityResponse:
        """
        Analyze a vulnerability and return structured response.
        
        Args:
            query: User's question about the vulnerability
            context: Optional additional context (CVE, description, etc.)
            
        Returns:
            VulnerabilityResponse with all 5 required fields
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available."""
        pass
    
    def _build_user_prompt(self, query: str, context: Optional[str] = None) -> str:
        """Build the user prompt with optional context."""
        prompt = f"Analiza la siguiente vulnerabilidad y responde en JSON:\n\n{query}"
        
        if context:
            prompt += f"\n\nContexto adicional:\n{context}"
            
        return prompt
    
    def _parse_response(self, raw_response: str) -> VulnerabilityResponse:
        """Parse the raw AI response into structured format."""
        import json
        import re
        
        # Intentar extraer JSON del response
        try:
            # Buscar JSON en la respuesta
            json_match = re.search(r'\{[\s\S]*\}', raw_response)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(raw_response)
                
            return VulnerabilityResponse(
                descripcion=data.get('descripcion', 'No disponible'),
                recomendaciones=data.get('recomendaciones', [])[:5],
                proceso_mitigacion=data.get('proceso_mitigacion', [])[:5],
                riesgos_mitigacion=data.get('riesgos_mitigacion', [])[:5],
                referencias=data.get('referencias', [])[:5],
                vulnerabilidad_consultada=data.get('vulnerabilidad_consultada', 'No especificada')
            )
        except json.JSONDecodeError:
            # Si falla el parsing, retornar respuesta de error estructurada
            return VulnerabilityResponse(
                descripcion="No se pudo procesar la respuesta. Por favor, intenta reformular tu pregunta.",
                recomendaciones=["Intenta ser más específico con el nombre de la vulnerabilidad"],
                proceso_mitigacion=["Consulta la documentación oficial"],
                riesgos_mitigacion=["Sin información disponible"],
                referencias=["https://nvd.nist.gov", "https://cve.mitre.org"],
                vulnerabilidad_consultada=query[:100] if 'query' in dir() else 'No especificada'
            )


# Configuration for each provider
PROVIDER_CONFIGS = {
    AIProviderType.OPENAI: {
        "model": "gpt-4o-mini",  # Económico y bueno
        "max_tokens": 1200,
        "temperature": 0.2,
    },
    AIProviderType.CLAUDE: {
        "model": "claude-sonnet-4-20250514",  # Más económico
        "max_tokens": 1200,
        "temperature": 0.2,
    },
    AIProviderType.GEMINI: {
        "model": "gemini-3-flash-preview",  # Rápido y económico
        "max_tokens": 1200,
        "temperature": 0.2,
    },
}
