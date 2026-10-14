"""System Calibration and Threshold Config Schemas"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class ThresholdConfigSchema(BaseModel):
    unitTolerance: int = Field(default=0, ge=0)
    pctTolerance: float = Field(default=0.0, ge=0.0)
    lowSeverityThreshold: int = Field(default=1, ge=1)
    medSeverityThreshold: int = Field(default=3, ge=1)
    highSeverityThreshold: int = Field(default=6, ge=1)
    repeatOffenderThreshold: int = Field(default=3, ge=1)
    repeatOffenderCountTrigger: int = Field(default=3, ge=1)
    repeatOffenderWindowDays: int = Field(default=30, ge=1)
    cameraOfflineAlertAfterSec: int = Field(default=60, ge=10)
    audioAlarmEnabled: bool = True
    alarmVolume: float = Field(default=0.75, ge=0.0, le=1.0)
    streamFrequencySeconds: int = Field(default=8, ge=2)
    autoSimulationEnabled: bool = True
    turnstileAutoLockOnHigh: bool = True

    model_config = ConfigDict(from_attributes=True)

