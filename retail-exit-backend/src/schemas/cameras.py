"""Pydantic Schemas for Camera Fleet Management"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CameraResponse(BaseModel):
    cameraId: str
    label: str
    laneId: Optional[str] = None
    ipAddress: str
    rtspPath: str
    streamUrl: Optional[str] = None
    pairingMethod: Optional[str] = "MANUAL"
    resolution: Optional[str] = "1920x1080"
    fps: Optional[int] = 30
    status: str  # ONLINE, OFFLINE, DEGRADED, PENDING_SETUP
    lastHeartbeatAt: Optional[str] = None
    offlineSince: Optional[str] = None
    addedAt: str
    removedAt: Optional[str] = None


class CameraCreate(BaseModel):
    label: str = Field(..., min_length=2, max_length=255)
    ipAddress: str = Field(..., pattern=r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$|localhost")
    rtspPath: str = Field(..., min_length=1)
    credentials: Optional[str] = None
    laneId: Optional[str] = None
    pairingMethod: Optional[str] = "MANUAL"
    resolution: Optional[str] = "1920x1080"
    fps: Optional[int] = 30


class CameraUpdate(BaseModel):
    label: Optional[str] = None
    laneId: Optional[str] = None
    resolution: Optional[str] = None
    fps: Optional[int] = None
    status: Optional[str] = None


class CameraTestConnectionRequest(BaseModel):
    ipAddress: Optional[str] = None
    rtspPath: Optional[str] = None
    credentials: Optional[str] = None


class CameraTestConnectionResponse(BaseModel):
    success: bool
    status: str
    streamUrl: Optional[str] = None
    snapshotUrl: Optional[str] = None
    resolution: Optional[str] = None
    fps: Optional[int] = None
    latencyMs: Optional[float] = None
    errorMessage: Optional[str] = None


class CameraHeartbeatCreate(BaseModel):
    fpsObserved: Optional[float] = 30.0
    bitrateKbps: Optional[float] = 4096.0


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
    ipAddress: Optional[str] = "192.168.10.45"
    label: Optional[str] = None
    model: Optional[str] = None
    rtspPath: Optional[str] = "/live/ch0"
    credentials: Optional[str] = None


