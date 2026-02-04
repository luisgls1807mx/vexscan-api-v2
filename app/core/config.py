"""
VexScan API - Configuration
Loads settings from environment variables
"""

from typing import Optional, List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # App Info
    APP_NAME: str = "VexScan API"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # API
    API_PREFIX: str = "/api/v1"
    
    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    # PostgreSQL Direct Connection
    user: str
    password: str
    host: str
    port: int
    dbname: str
    
    # JWT (Supabase uses its own JWT)
    JWT_SECRET: Optional[str] = None  # Optional: for custom JWT validation
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 24 hours
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # Storage
    STORAGE_BUCKET: str = "scans"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS: List[str] = [".nessus", ".xml", ".json"]
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # seconds
    
    # AI Providers - Set ONE of these based on your chosen provider
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    
    @property
    def AI_API_KEY(self) -> Optional[str]:
        """
        Get the configured AI API key.
        Priority: OpenAI > Anthropic > Google
        """
        return self.OPENAI_API_KEY or self.ANTHROPIC_API_KEY or self.GOOGLE_API_KEY
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
