"""Application Configuration Module

Strictly loads all variables from environment with zero insecure fallbacks.
Refuses to start if mandatory secrets or database URLs are missing.
"""

import os
from typing import List
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file if present
load_dotenv()

MANDATORY_ENV_VARS = ["DATABASE_URL", "JWT_SECRET_KEY", "MOBILE_HMAC_SECRET"]

def validate_mandatory_env():
    """Validates that all mandatory security and infrastructure environment variables exist.
    
    Raises RuntimeError if any required credential is missing or empty, preventing
    the application from ever booting into a silently-weakened or insecure state.
    """
    missing = [var for var in MANDATORY_ENV_VARS if not os.getenv(var) or not os.getenv(var).strip()]
    if missing:
        raise RuntimeError(
            f"CRITICAL CONFIGURATION ERROR: Mandatory environment variable(s) {missing} are not set or empty. "
            f"SEC-OPS refuses to start with insecure fallback defaults."
        )

# Validate immediately upon module load
validate_mandatory_env()

class Settings(BaseSettings):
    APP_NAME: str = os.getenv("APP_NAME", "SEC-OPS Retail Exit Monitoring Platform")
    APP_VERSION: str = os.getenv("APP_VERSION", "2.0.0")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")
    SECOPS_DEBUG: bool = os.getenv("SECOPS_DEBUG", "false").lower() == "true"
    
    # Database (Mandatory - strictly loaded from environment)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # CORS (Dynamic parsing)
    CORS_ORIGINS: List[str] = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []
    
    # Security (Mandatory - strictly loaded from environment)
    SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
    ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))
    MOBILE_HMAC_SECRET: str = os.getenv("MOBILE_HMAC_SECRET", "")
    
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