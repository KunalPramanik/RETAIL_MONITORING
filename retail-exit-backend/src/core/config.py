"""Application Configuration Module

Strictly loads all variables from environment with zero insecure fallbacks.
Refuses to start if mandatory secrets or database URLs are missing.
"""

import os
from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel, Field
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


class DetectionConfig(BaseModel):
    confidence_floor: float = Field(default_factory=lambda: float(os.getenv("SECOPS_CONFIDENCE_FLOOR", "0.50")))
    confirmed_entity_standard: float = Field(default_factory=lambda: float(os.getenv("SECOPS_CONFIRMED_ENTITY_STANDARD", "0.90")))
    fire_confirmed_threshold: float = Field(default_factory=lambda: float(os.getenv("SECOPS_FIRE_CONFIRMED_THRESHOLD", "0.90")))
    fire_hazard_floor: float = Field(default_factory=lambda: float(os.getenv("SECOPS_FIRE_HAZARD_FLOOR", "0.45")))
    suspicious_confirmed_threshold: float = Field(default_factory=lambda: float(os.getenv("SECOPS_SUSPICIOUS_CONFIRMED_THRESHOLD", "0.90")))
    ppe_confirmed_threshold: float = Field(default_factory=lambda: float(os.getenv("SECOPS_PPE_CONFIRMED_THRESHOLD", "0.85")))
    person_conf_threshold: float = Field(default_factory=lambda: float(os.getenv("SECOPS_PERSON_CONF_THRESHOLD", "0.50")))
    item_conf_threshold: float = Field(default_factory=lambda: float(os.getenv("SECOPS_ITEM_CONF_THRESHOLD", "0.45")))
    case_conf_threshold: float = Field(default_factory=lambda: float(os.getenv("SECOPS_CASE_CONF_THRESHOLD", "0.50")))
    vehicle_conf_threshold: float = Field(default_factory=lambda: float(os.getenv("SECOPS_VEHICLE_CONF_THRESHOLD", "0.25")))
    nms_iou_threshold: float = Field(default_factory=lambda: float(os.getenv("SECOPS_NMS_IOU_THRESHOLD", "0.35")))
    dense_shelf_nms_iou_threshold: float = Field(default_factory=lambda: float(os.getenv("SECOPS_DENSE_SHELF_NMS_IOU_THRESHOLD", "0.45")))


class TrackingConfig(BaseModel):
    tracker_max_lost_frames: int = Field(default_factory=lambda: int(os.getenv("SECOPS_TRACKER_MAX_LOST_FRAMES", "15")))
    tracker_iou_threshold: float = Field(default_factory=lambda: float(os.getenv("SECOPS_TRACKER_IOU_THRESHOLD", "0.30")))


class TripwireConfig(BaseModel):
    lock_cooldown_sec: float = Field(default_factory=lambda: float(os.getenv("SECOPS_TRIPWIRE_LOCK_COOLDOWN_SEC", "3.5")))
    tailgating_window_sec: float = Field(default_factory=lambda: float(os.getenv("SECOPS_TAILGATING_WINDOW_SEC", "1.2")))


class FusionConfig(BaseModel):
    baseline_vision_weight: float = Field(default_factory=lambda: float(os.getenv("SECOPS_FUSION_VISION_WEIGHT", "0.50")))
    baseline_rfid_weight: float = Field(default_factory=lambda: float(os.getenv("SECOPS_FUSION_RFID_WEIGHT", "0.30")))
    baseline_scale_weight: float = Field(default_factory=lambda: float(os.getenv("SECOPS_FUSION_SCALE_WEIGHT", "0.20")))
    scale_weight_tolerance_pct: float = Field(default_factory=lambda: float(os.getenv("SECOPS_SCALE_TOLERANCE_PCT", "0.05")))
    occlusion_confidence_cap: float = Field(default_factory=lambda: float(os.getenv("SECOPS_OCCLUSION_CONFIDENCE_CAP", "0.75")))


class RateLimitConfig(BaseModel):
    auth_per_minute: int = Field(default_factory=lambda: int(os.getenv("RATE_LIMIT_AUTH_PER_MINUTE", "20")))
    camera_test_per_minute: int = Field(default_factory=lambda: int(os.getenv("RATE_LIMIT_CAMERA_TEST_PER_MINUTE", "15")))
    ocr_per_minute: int = Field(default_factory=lambda: int(os.getenv("RATE_LIMIT_OCR_PER_MINUTE", "30")))
    general_per_minute: int = Field(default_factory=lambda: int(os.getenv("RATE_LIMIT_GENERAL_PER_MINUTE", "120")))


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
    
    # Subsystem Configurations
    detection: DetectionConfig = Field(default_factory=DetectionConfig)
    tracking: TrackingConfig = Field(default_factory=TrackingConfig)
    tripwire: TripwireConfig = Field(default_factory=TripwireConfig)
    fusion: FusionConfig = Field(default_factory=FusionConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()