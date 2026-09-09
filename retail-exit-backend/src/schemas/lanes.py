"""Sensor Lane Schemas"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List


class SensorLaneSchema(BaseModel):
    laneId: str
    name: str
    location: str
    status: str  # ONLINE | OFFLINE | DEGRADED
    cameraIp: str
    cameraFps: float
    rfidGatePowerDbm: float
    scaleTareKg: float
    lastPing: str

    model_config = ConfigDict(from_attributes=True)


class LaneCreate(BaseModel):
    laneId: Optional[str] = None
    label: str = Field(..., min_length=2, max_length=128)
    storeId: Optional[str] = "store_0402"
    rfidAntennaId: Optional[str] = None
    weightSensorId: Optional[str] = None
    turnstileCtrlId: Optional[str] = None
