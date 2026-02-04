"""
VexScan API - Gemini Provider
Google Gemini implementation
"""

import httpx
from typing import Optional
import structlog

from app.services.ai_providers.base import (
    BaseAIProvider,
    VulnerabilityResponse,
    PROVIDER_CONFIGS,
    AIProviderType
)

logger = structlog.get_logger()


class GeminiProvider(BaseAIProvider):
    """
    Google Gemini provider implementation.
    
    Models disponibles:
    - gemini-2.0-flash-exp: Muy rápido y económico (gratis en tier básico)
    - gemini-1.5-flash: Rápido, buen balance
    - gemini-1.5-pro: Más potente
    
    Recomendado: gemini-2.0-flash-exp para este caso de uso
    """
    
    API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
    
    def __init__(self, api_key: str, model: str = None):
        config = PROVIDER_CONFIGS[AIProviderType.GEMINI]
        super().__init__(api_key, model or config["model"])
        self.max_tokens = config["max_tokens"]
        self.temperature = config["temperature"]
        
    @property
    def api_url(self) -> str:
        return f"{self.API_BASE}/{self.model}:generateContent?key={self.api_key}"
        
    async def analyze_vulnerability(
        self,
        query: str,
        context: Optional[str] = None
    ) -> VulnerabilityResponse:
        """Analyze vulnerability using Gemini API."""
        
        user_prompt = self._build_user_prompt(query, context)
        
        # Gemini combina system + user en un solo prompt
        full_prompt = f"""{self.SYSTEM_PROMPT}

---

{user_prompt}

IMPORTANTE: Responde ÚNICAMENTE con un objeto JSON válido."""
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": full_prompt}
                    ]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": self.max_tokens,
                "temperature": self.temperature,
                "responseMimeType": "application/json"  # Forzar JSON
            },
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE"
                }
            ]
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Extraer texto de la respuesta de Gemini
                candidates = data.get("candidates", [])
                if not candidates:
                    raise ValueError("No response from Gemini")
                    
                raw_content = candidates[0]["content"]["parts"][0]["text"]
                
                logger.info(
                    "Gemini response received",
                    model=self.model,
                    token_count=data.get("usageMetadata", {}).get("totalTokenCount", 0)
                )
                
                return self._parse_response(raw_content)
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Gemini API error: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Gemini request failed: {e}")
            raise
            
    async def health_check(self) -> bool:
        """Check if Gemini API is available."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"{self.API_BASE}?key={self.api_key}"
                response = await client.get(url)
                return response.status_code == 200
        except:
            return False
