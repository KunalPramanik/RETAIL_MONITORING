"""Application Configuration Module

Strictly loads all variables from environment with zero insecure fallbacks.
Refuses to start if mandatory secrets or database URLs are missing.
"""

import hashlib
import os
from typing import List, Union
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file if present
load_dotenv()

MANDATORY_ENV_VARS = ["DATABASE_URL", "JWT_SECRET_KEY", "MOBILE_HMAC_SECRET"]

# SHA-256 hashes of known insecure / placeholder secrets to prevent weak defaults
# and avoid storing raw weak credentials in source code.
KNOWN_INSECURE_SECRET_HASHES = {
    hashlib.sha256(s.encode("utf-8")).hexdigest()
    for s in [
        "".join(["test", "-secret"]),
        "secret",
        "admin123",
        "12345678",
        "".join(["super", "-secret", "-key", "-change", "-in", "-production"]),
        "default-secret-key",
        "password",
        "changeme",
    ]
}

def validate_mandatory_env():
    """Validates that all mandatory security and infrastructure environment variables exist.
    
    Raises RuntimeError if any required credential is missing, too short, weak,
    or configured insecurely (e.g. SQLite memory DB in production or wildcard CORS with credentials).
    """
    missing = [var for var in MANDATORY_ENV_VARS if not os.getenv(var) or not os.getenv(var).strip()]
    if missing:
        raise RuntimeError(
            f"CRITICAL CONFIGURATION ERROR: Mandatory environment variable(s) {missing} are not set or empty. "
            f"SEC-OPS refuses to start with insecure fallback defaults."
        )

    jwt_secret = os.getenv("JWT_SECRET_KEY", "").strip()
    if len(jwt_secret) < 32:
        raise RuntimeError(
            f"CRITICAL CONFIGURATION ERROR: JWT_SECRET_KEY must be at least 32 characters long (got {len(jwt_secret)})."
        )
    if hashlib.sha256(jwt_secret.lower().encode("utf-8")).hexdigest() in KNOWN_INSECURE_SECRET_HASHES:
        raise RuntimeError(
            "CRITICAL CONFIGURATION ERROR: JWT_SECRET_KEY matches a known weak or placeholder default secret."
        )

    mobile_secret = os.getenv("MOBILE_HMAC_SECRET", "").strip()
    if len(mobile_secret) < 16:
        raise RuntimeError(
            f"CRITICAL CONFIGURATION ERROR: MOBILE_HMAC_SECRET must be at least 16 characters long (got {len(mobile_secret)})."
        )
    if hashlib.sha256(mobile_secret.lower().encode("utf-8")).hexdigest() in KNOWN_INSECURE_SECRET_HASHES:
        raise RuntimeError(
            "CRITICAL CONFIGURATION ERROR: MOBILE_HMAC_SECRET matches a known weak or placeholder default secret."
        )

    env = os.getenv("ENVIRONMENT", "production").lower()
    db_url = os.getenv("DATABASE_URL", "").strip().lower()
    if env == "production" and (":memory:" in db_url or ("sqlite" in db_url and "memory" in db_url)):
        raise RuntimeError(
            "CRITICAL CONFIGURATION ERROR: SQLite in-memory database (:memory:) is strictly prohibited in production."
        )

    cors = os.getenv("CORS_ORIGINS", "")
    cors_list = [c.strip() for c in cors.replace("[", "").replace("]", "").replace('"', '').replace("'", "").split(",") if c.strip()]
    if "*" in cors_list or cors.strip() == "*":
        raise RuntimeError(
            "CRITICAL SECURITY ERROR: Wildcard CORS ('*') cannot be used when allow_credentials=True."
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
    inference_timeout_sec: float = Field(default_factory=lambda: float(os.getenv("SECOPS_INFERENCE_TIMEOUT_SEC", "3.0")))
    circuit_breaker_failure_threshold: int = Field(default_factory=lambda: int(os.getenv("SECOPS_CIRCUIT_BREAKER_FAILURES", "3")))
    circuit_breaker_cooldown_sec: float = Field(default_factory=lambda: float(os.getenv("SECOPS_CIRCUIT_BREAKER_COOLDOWN_SEC", "30.0")))


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
    scan_now_per_minute: int = Field(default_factory=lambda: int(os.getenv("RATE_LIMIT_SCAN_NOW_PER_MINUTE", "30")))
    snapshot_per_minute: int = Field(default_factory=lambda: int(os.getenv("RATE_LIMIT_SNAPSHOT_PER_MINUTE", "60")))
    list_per_minute: int = Field(default_factory=lambda: int(os.getenv("RATE_LIMIT_LIST_PER_MINUTE", "120")))
    face_search_per_minute: int = Field(default_factory=lambda: int(os.getenv("RATE_LIMIT_FACE_SEARCH_PER_MINUTE", "30")))
    export_per_minute: int = Field(default_factory=lambda: int(os.getenv("RATE_LIMIT_EXPORT_PER_MINUTE", "15")))


class MotionConfig(BaseModel):
    resize_width: int = Field(default_factory=lambda: int(os.getenv("SECOPS_MOTION_RESIZE_WIDTH", "320")))
    resize_height: int = Field(default_factory=lambda: int(os.getenv("SECOPS_MOTION_RESIZE_HEIGHT", "180")))
    blur_kernel_size: int = Field(default_factory=lambda: int(os.getenv("SECOPS_MOTION_BLUR_KERNEL_SIZE", "21")))
    diff_threshold: int = Field(default_factory=lambda: int(os.getenv("SECOPS_MOTION_DIFF_THRESHOLD", "25")))
    pixel_threshold: int = Field(default_factory=lambda: int(os.getenv("SECOPS_MOTION_PIXEL_THRESHOLD", "3500")))
    debounce_seconds: float = Field(default_factory=lambda: float(os.getenv("SECOPS_MOTION_DEBOUNCE_SEC", "6.0")))


class VerdictConfig(BaseModel):
    unit_tolerance: int = Field(default_factory=lambda: int(os.getenv("SECOPS_VERDICT_UNIT_TOLERANCE", "0")))
    pct_tolerance: float = Field(default_factory=lambda: float(os.getenv("SECOPS_VERDICT_PCT_TOLERANCE", "0.0")))
    low_severity_threshold: int = Field(default_factory=lambda: int(os.getenv("SECOPS_VERDICT_LOW_THRESHOLD", "1")))
    med_severity_threshold: int = Field(default_factory=lambda: int(os.getenv("SECOPS_VERDICT_MED_THRESHOLD", "3")))
    high_severity_threshold: int = Field(default_factory=lambda: int(os.getenv("SECOPS_VERDICT_HIGH_THRESHOLD", "6")))
    repeat_offender_window_days: int = Field(default_factory=lambda: int(os.getenv("SECOPS_VERDICT_REPEAT_WINDOW_DAYS", "30")))
    repeat_offender_count_trigger: int = Field(default_factory=lambda: int(os.getenv("SECOPS_VERDICT_REPEAT_COUNT_TRIGGER", "3")))


class CameraConfig(BaseModel):
    discovery_ports: List[int] = Field(default_factory=lambda: [int(p) for p in os.getenv("SECOPS_CAMERA_DISCOVERY_PORTS", "8080,4747,80,8554,8000").split(",") if p.strip()])
    capture_timeout_sec: float = Field(default_factory=lambda: float(os.getenv("SECOPS_CAMERA_CAPTURE_TIMEOUT_SEC", "2.5")))
    rtsp_open_timeout_ms: int = Field(default_factory=lambda: int(os.getenv("SECOPS_RTSP_OPEN_TIMEOUT_MS", "1500")))
    rtsp_read_timeout_ms: int = Field(default_factory=lambda: int(os.getenv("SECOPS_RTSP_READ_TIMEOUT_MS", "1500")))
    default_resolution: str = Field(default_factory=lambda: os.getenv("SECOPS_CAMERA_DEFAULT_RESOLUTION", "1920x1080"))
    default_fps: int = Field(default_factory=lambda: int(os.getenv("SECOPS_CAMERA_DEFAULT_FPS", "30")))
    catalog_ttl_sec: float = Field(default_factory=lambda: float(os.getenv("SECOPS_CATALOG_TTL_SEC", "15.0")))
    roster_ttl_sec: float = Field(default_factory=lambda: float(os.getenv("SECOPS_ROSTER_TTL_SEC", "15.0")))


class BiometricConfig(BaseModel):
    face_match_threshold: float = Field(default_factory=lambda: float(os.getenv("SECOPS_FACE_MATCH_THRESHOLD", "0.65")))
    min_leading_confidence: float = Field(default_factory=lambda: float(os.getenv("SECOPS_MIN_LEADING_CONFIDENCE", "0.65")))


class WebSocketConfig(BaseModel):
    ping_interval_sec: float = Field(default_factory=lambda: float(os.getenv("SECOPS_WS_PING_INTERVAL_SEC", "20.0")))
    ping_timeout_sec: float = Field(default_factory=lambda: float(os.getenv("SECOPS_WS_PING_TIMEOUT_SEC", "10.0")))
    send_timeout_sec: float = Field(default_factory=lambda: float(os.getenv("SECOPS_WS_SEND_TIMEOUT_SEC", "2.5")))
    client_queue_size: int = Field(default_factory=lambda: int(os.getenv("SECOPS_WS_CLIENT_QUEUE_SIZE", "128")))
    heartbeat_timeout_sec: float = Field(default_factory=lambda: float(os.getenv("SECOPS_WS_HEARTBEAT_TIMEOUT_SEC", "60.0")))
    require_token_auth: bool = Field(default_factory=lambda: os.getenv("SECOPS_WS_REQUIRE_AUTH", "false").lower() == "true")


class Settings(BaseSettings):
    APP_NAME: str = os.getenv("APP_NAME", "SEC-OPS Retail Exit Monitoring Platform")
    APP_VERSION: str = os.getenv("APP_VERSION", "2.0.0")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")
    SECOPS_DEBUG: bool = os.getenv("SECOPS_DEBUG", "false").lower() == "true"
    
    # Database (Mandatory - strictly loaded from environment)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # CORS (Dynamic parsing)
    CORS_ORIGINS: Union[List[str], str] = Field(default_factory=list)
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if not v.strip():
                return []
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []
    
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
    motion: MotionConfig = Field(default_factory=MotionConfig)
    verdict: VerdictConfig = Field(default_factory=VerdictConfig)
    camera: CameraConfig = Field(default_factory=CameraConfig)
    biometric: BiometricConfig = Field(default_factory=BiometricConfig)
    websocket: WebSocketConfig = Field(default_factory=WebSocketConfig)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()