"""Application Configuration Module

Supports environment variable loading with sensible defaults for local development
and containerized deployment.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Union, Any
import os


class Settings(BaseSettings):
    APP_NAME: str = "SEC-OPS Retail Exit Monitoring Platform"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: str = "development"
    SECOPS_DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "sqlite+aiosqlite:///./retail_exit.db"
    )
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:4173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:4173",
        "*"
    ]
    
    # Security
    SECRET_KEY: str = "sec-ops-production-secret-key-32-chars-min"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    
    # Edge Ingestion & ML Defaults
    DEFAULT_STORE_ID: str = "store_0402"
    DEFAULT_VISION_MODEL: str = "yolov8-retail-pack-v2.1"
    DEFAULT_OCR_MODEL: str = "paddleocr-invoice-layout-v3.0"
    DEFAULT_FACE_MODEL: str = "arcface-r100-512d-v1.4"
    
    # WebSocket Broadcast
    WS_HEARTBEAT_INTERVAL_SEC: int = 15
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

