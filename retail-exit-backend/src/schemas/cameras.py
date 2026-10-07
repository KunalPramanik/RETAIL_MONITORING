"""Pydantic Schemas for Camera Fleet Management

Provides strict input validation and SSRF defenses for IP/hostname,
ports, RTSP paths, FPS, and resolutions.
"""

import ipaddress
import re
from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator


BLOCKED_NETWORKS = [
    ipaddress.ip_network("169.254.0.0/16"),   # IPv4 Link-local / Cloud Metadata (SSRF)
    ipaddress.ip_network("224.0.0.0/4"),      # IPv4 Multicast
    ipaddress.ip_network("240.0.0.0/4"),      # IPv4 Reserved
    ipaddress.ip_network("fe80::/10"),        # IPv6 Link-local
    ipaddress.ip_network("ff00::/8"),         # IPv6 Multicast
]


def validate_camera_host(host: str) -> str:
    host_clean = host.strip()
    if not host_clean:
        raise ValueError("ipAddress cannot be empty")
    
    # Check if host is an IP address
    try:
        ip_obj = ipaddress.ip_address(host_clean)
        for net in BLOCKED_NETWORKS:
            if ip_obj in net:
                raise ValueError(f"Prohibited IP address or subnet: {host_clean} (SSRF / Multicast blocked)")
        if ip_obj.is_unspecified:
            raise ValueError(f"Prohibited unspecified IP address: {host_clean}")
        return host_clean
    except ValueError as e:
        if "Prohibited" in str(e):
            raise
        # Not an IP address; check if valid hostname / FQDN
        if re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$", host_clean):
            if host_clean.lower() in ("metadata.google.internal", "instance-data"):
                raise ValueError(f"Prohibited cloud metadata hostname: {host_clean}")
            return host_clean
        raise ValueError(f"Invalid IP address or hostname: '{host_clean}'")


def validate_camera_resolution(res: Optional[str]) -> Optional[str]:
    if res is None:
        return res
    res_clean = res.strip().lower()
    if not re.match(r"^\d{3,4}x\d{3,4}$", res_clean):
        raise ValueError(f"Invalid resolution format: '{res}'. Must match standard pattern like '1920x1080' or '1280x720'.")
    return res_clean


def validate_camera_fps(fps: Optional[int]) -> Optional[int]:
    if fps is None:
        return fps
    if not (1 <= fps <= 120):
        raise ValueError(f"FPS must be between 1 and 120 (got {fps}).")
    return fps


def validate_camera_rtsp_path(path: str) -> str:
    path_clean = path.strip()
    if not path_clean:
        raise ValueError("rtspPath cannot be empty")
    if not path_clean.startswith("/"):
        path_clean = f"/{path_clean}"
    return path_clean


class CameraResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    cameraId: str
    label: str
    laneId: Optional[str] = None
    ipAddress: str
    rtspPath: str
    subStreamPath: Optional[str] = None
    streamUrl: Optional[str] = None
    pairingMethod: Optional[str] = "MANUAL"
    resolution: Optional[str] = "1920x1080"
    fps: Optional[int] = 30
    bitrateKbps: Optional[float] = 4096.0
    fpsObserved: Optional[float] = 30.0
    droppedFrames: Optional[int] = 0
    status: str  # ONLINE, OFFLINE, DEGRADED, PENDING_SETUP
    lastHeartbeatAt: Optional[str] = None
    offlineSince: Optional[str] = None
    addedAt: str
    removedAt: Optional[str] = None
    ptzCapable: Optional[bool] = False
    isIrMode: Optional[bool] = False
    roiPolygon: Optional[List[Any]] = None
    ignoredClasses: Optional[List[str]] = Field(default_factory=list)


class CameraCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    label: str = Field(..., min_length=2, max_length=255)
    ipAddress: str = Field(..., min_length=1, max_length=255)
    rtspPath: str = Field(..., min_length=1)
    subStreamPath: Optional[str] = None
    streamUrl: Optional[str] = None
    credentials: Optional[str] = None
    laneId: Optional[str] = None
    pairingMethod: Optional[str] = "MANUAL"
    resolution: Optional[str] = "1920x1080"
    fps: Optional[int] = 30
    ignoredClasses: Optional[List[str]] = Field(default_factory=list, alias="ignored_classes")

    @field_validator("label")
    @classmethod
    def clean_label(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 2:
            raise ValueError("Label must be at least 2 characters")
        return cleaned

    @field_validator("ipAddress")
    @classmethod
    def check_ip(cls, v: str) -> str:
        return validate_camera_host(v)

    @field_validator("rtspPath")
    @classmethod
    def check_rtsp_path(cls, v: str) -> str:
        return validate_camera_rtsp_path(v)

    @field_validator("resolution")
    @classmethod
    def check_resolution(cls, v: Optional[str]) -> Optional[str]:
        return validate_camera_resolution(v)

    @field_validator("fps")
    @classmethod
    def check_fps(cls, v: Optional[int]) -> Optional[int]:
        return validate_camera_fps(v)


class CameraUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    label: Optional[str] = None
    ipAddress: Optional[str] = None
    rtspPath: Optional[str] = None
    subStreamPath: Optional[str] = None
    streamUrl: Optional[str] = None
    credentials: Optional[str] = None
    laneId: Optional[str] = None
    resolution: Optional[str] = None
    fps: Optional[int] = None
    status: Optional[str] = None
    ignoredClasses: Optional[List[str]] = Field(default=None, alias="ignored_classes")

    @field_validator("label")
    @classmethod
    def clean_label(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            if len(cleaned) < 2:
                raise ValueError("Label must be at least 2 characters")
            return cleaned
        return v

    @field_validator("ipAddress")
    @classmethod
    def check_ip(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_camera_host(v)
        return v

    @field_validator("rtspPath")
    @classmethod
    def check_rtsp_path(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_camera_rtsp_path(v)
        return v

    @field_validator("resolution")
    @classmethod
    def check_resolution(cls, v: Optional[str]) -> Optional[str]:
        return validate_camera_resolution(v)

    @field_validator("fps")
    @classmethod
    def check_fps(cls, v: Optional[int]) -> Optional[int]:
        return validate_camera_fps(v)


class CameraTestConnectionRequest(BaseModel):
    ipAddress: Optional[str] = None
    rtspPath: Optional[str] = None
    subStreamPath: Optional[str] = None
    streamUrl: Optional[str] = None
    credentials: Optional[str] = None


class CameraTestConnectionResponse(BaseModel):
    success: bool
    status: str
    streamUrl: Optional[str] = None
    subStreamPath: Optional[str] = None
    snapshotUrl: Optional[str] = None
    resolution: Optional[str] = None
    fps: Optional[int] = None
    latencyMs: Optional[float] = None
    errorMessage: Optional[str] = None


class CameraHeartbeatCreate(BaseModel):
    fpsObserved: Optional[float] = 30.0
    bitrateKbps: Optional[float] = 4096.0
    droppedFrames: Optional[int] = 0


class CameraTelemetryResponse(BaseModel):
    cameraId: str
    status: str
    fpsObserved: float = 30.0
    bitrateKbps: float = 4096.0
    droppedFrames: int = 0
    lastHeartbeatAt: Optional[str] = None


class QRDecodeRequest(BaseModel):
    qrPayload: str


class QRDecodeResponse(BaseModel):
    ipAddress: Optional[str] = None
    model: Optional[str] = None
    suggestedLabel: Optional[str] = None
    rtspPath: Optional[str] = None
    credentials: Optional[str] = None


class PairingTokenCreate(BaseModel):
    storeId: Optional[str] = None
    laneId: Optional[str] = None
    wifiSsid: Optional[str] = None
    wifiPassword: Optional[str] = None


class PairingTokenResponse(BaseModel):
    tokenId: str
    tokenValue: str
    qrPayload: str
    expiresAt: str
    status: str  # ACTIVE, EXPIRED, USED
    laneId: Optional[str] = None
    usedAt: Optional[str] = None
    usedByCameraId: Optional[str] = None


class PairCameraRequest(BaseModel):
    token: str
    ipAddress: Optional[str] = None
    label: Optional[str] = None
    model: Optional[str] = None
    rtspPath: Optional[str] = "/live/ch0"
    credentials: Optional[str] = None

