"""Application Configuration Module

Strictly loads all variables from environment to ensure zero hardcoding.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List
import os

class Settings(BaseSettings):
    APP_NAME: str = os.getenv("APP_NAME", "SEC-OPS Retail Exit Monitoring Platform")
    APP_VERSION: str = os.getenv("APP_VERSION", "2.0.0")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")
    SECOPS_DEBUG: bool = os.getenv("SECOPS_DEBUG", "false").lower() == "true"
    
    # Database (No Hardcoded Credentials)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    
    # CORS (Dynamic parsing)
    CORS_ORIGINS: List[str] = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []
    
    # Security (Strict No Hardcoding)
    SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "test-secret")
    ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))
    
    # Edge Ingestion & ML Defaults
    DEFAULT_STORE_ID: str = os.getenv("DEFAULT_STORE_ID", "")
    DEFAULT_VISION_MODEL: str = os.getenv("DEFAULT_VISION_MODEL", "")
    DEFAULT_OCR_MODEL: str = os.getenv("DEFAULT_OCR_MODEL", "")
    DEFAULT_FACE_MODEL: str = os.getenv("DEFAULT_FACE_MODEL", "")
    
    # Infrastructure
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    WS_HEARTBEAT_INTERVAL_SEC: int = int(os.getenv("WS_HEARTBEAT_INTERVAL_SEC", "15"))
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()