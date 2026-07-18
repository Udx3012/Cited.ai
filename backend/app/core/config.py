import os
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "Cited.AI Backend"
    APP_ENV: str = "development"
    DEBUG: bool = True
    
    # API security key
    BACKEND_API_KEY: str = "ca_live_default_dev_key"
    
    # CORS setup (converts comma separated string to list of origins)
    ALLOWED_ORIGINS: Union[str, List[str]] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    # Third party keys (stubs for later implementation stages)
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    HF_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    VOYAGE_API_KEY: str = ""

    # Query Rewriter settings
    QUERY_REWRITER_ENABLED: bool = True
    QUERY_REWRITER_MODEL: str = "llama-3.1-8b-instant"

    # Semantic Cache Settings
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 3600
    CACHE_SIMILARITY_THRESHOLD: float = 0.90

    # Supabase storage credentials
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_BUCKET_NAME: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
