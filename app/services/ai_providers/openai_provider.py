"""
VexScan API - OpenAI Provider
ChatGPT/GPT-4 implementation
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


class OpenAIProvider(BaseAIProvider):
    """
    OpenAI (ChatGPT) provider implementation.
    
    Models disponibles:
    - gpt-4o-mini: Económico, rápido, bueno para tareas estructuradas ($0.15/1M input)
    - gpt-4o: Más potente, más costoso ($2.50/1M input)
    - gpt-4-turbo: Balance entre costo y capacidad
    
    Recomendado: gpt-4o-mini para este caso de uso
    """
    
    API_URL = "https://api.openai.com/v1/chat/completions"
    
    def __init__(self, api_key: str, model: str = None):
        config = PROVIDER_CONFIGS[AIProviderType.OPENAI]
        super().__init__(api_key, model or config["model"])
        self.max_tokens = config["max_tokens"]
        self.temperature = config["temperature"]
        
    async def analyze_vulnerability(
        self,
        query: str,
        context: Optional[str] = None
    ) -> VulnerabilityResponse:
        """Analyze vulnerability using OpenAI API."""
        
        user_prompt = self._build_user_prompt(query, context)
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"}  # Forzar JSON
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.API_URL,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                
                data = response.json()
                raw_content = data["choices"][0]["message"]["content"]
                
                logger.info(
                    "OpenAI response received",
                    model=self.model,
                    tokens_used=data.get("usage", {}).get("total_tokens", 0)
                )
                
                return self._parse_response(raw_content)
                
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI API error: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"OpenAI request failed: {e}")
            raise
            
    async def health_check(self) -> bool:
        """Check if OpenAI API is available."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                return response.status_code == 200
        except:
            return False
