"""
VexScan API - Claude Provider
Anthropic Claude implementation
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


class ClaudeProvider(BaseAIProvider):
    """
    Anthropic Claude provider implementation.
    
    Models disponibles:
    - claude-3-haiku-20240307: Más económico y rápido ($0.25/1M input)
    - claude-3-5-sonnet-20241022: Balance costo/capacidad ($3/1M input)
    - claude-3-opus-20240229: Más potente ($15/1M input)
    
    Recomendado: claude-3-haiku para este caso de uso (económico y suficiente)
    """
    
    API_URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"
    
    def __init__(self, api_key: str, model: str = None):
        config = PROVIDER_CONFIGS[AIProviderType.CLAUDE]
        super().__init__(api_key, model or config["model"])
        self.max_tokens = config["max_tokens"]
        self.temperature = config["temperature"]
        
    async def analyze_vulnerability(
        self,
        query: str,
        context: Optional[str] = None
    ) -> VulnerabilityResponse:
        """Analyze vulnerability using Claude API."""
        
        user_prompt = self._build_user_prompt(query, context)
        
        # Claude requiere que el JSON prompt esté en el mensaje del usuario
        enhanced_prompt = f"""{user_prompt}

IMPORTANTE: Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional antes o después."""
        
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": self.SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": enhanced_prompt}
            ]
        }
        
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": self.API_VERSION
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
                raw_content = data["content"][0]["text"]
                
                logger.info(
                    "Claude response received",
                    model=self.model,
                    input_tokens=data.get("usage", {}).get("input_tokens", 0),
                    output_tokens=data.get("usage", {}).get("output_tokens", 0)
                )
                
                return self._parse_response(raw_content)
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Claude API error: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Claude request failed: {e}")
            raise
            
    async def health_check(self) -> bool:
        """Check if Claude API is available."""
        try:
            # Claude no tiene endpoint de health, hacemos un request mínimo
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.API_URL,
                    json={
                        "model": self.model,
                        "max_tokens": 10,
                        "messages": [{"role": "user", "content": "ping"}]
                    },
                    headers={
                        "x-api-key": self.api_key,
                        "Content-Type": "application/json",
                        "anthropic-version": self.API_VERSION
                    }
                )
                return response.status_code == 200
        except:
            return False
