"""
VexScan API - AI Providers Package

═══════════════════════════════════════════════════════════════════════════════
CÓMO CAMBIAR DE PROVEEDOR DE IA
═══════════════════════════════════════════════════════════════════════════════

Edita el archivo: app/services/ai_chat_service.py

Busca la sección "SELECCIÓN DE PROVEEDOR DE IA" y cambia el import:

# ═══════════════════════════════════════════════════════════════════════════
# Para OpenAI (ChatGPT) - Modelo: gpt-4o-mini
from app.services.ai_providers.openai_provider import OpenAIProvider as AIProvider

# Para Claude (Anthropic) - Modelo: claude-3-haiku
# from app.services.ai_providers.claude_provider import ClaudeProvider as AIProvider

# Para Gemini (Google) - Modelo: gemini-2.0-flash
# from app.services.ai_providers.gemini_provider import GeminiProvider as AIProvider
# ═══════════════════════════════════════════════════════════════════════════

También asegúrate de configurar la API key correspondiente en .env:
- OpenAI: OPENAI_API_KEY=sk-...
- Claude: ANTHROPIC_API_KEY=sk-ant-...
- Gemini: GOOGLE_API_KEY=...
"""

from app.services.ai_providers.base import (
    BaseAIProvider,
    VulnerabilityResponse,
    AIProviderType,
    PROVIDER_CONFIGS
)
from app.services.ai_providers.openai_provider import OpenAIProvider
from app.services.ai_providers.claude_provider import ClaudeProvider
from app.services.ai_providers.gemini_provider import GeminiProvider

__all__ = [
    "BaseAIProvider",
    "VulnerabilityResponse",
    "AIProviderType",
    "PROVIDER_CONFIGS",
    "OpenAIProvider",
    "ClaudeProvider",
    "GeminiProvider",
]
