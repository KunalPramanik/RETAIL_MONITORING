"""Alert and Alarm Schemas"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List


class AlertBase(BaseModel):
    eventId: Optional[str] = None
    cameraId: Optional[str] = None
    alertType: str
    severity: str
    deltaUnits: int = 0
    createdAt: str
    status: str = "OPEN"  # OPEN | ACKNOWLEDGED | RESOLVED
    resolvedBy: Optional[str] = None
    resolutionNote: Optional[str] = None


class AlertResponse(AlertBase):
    alertId: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AcknowledgeAlertRequest(BaseModel):
    acknowledgedBy: str = Field(min_length=2, description="Supervisor name or ID")


class ResolveAlertRequest(BaseModel):
    resolutionNote: str = Field(min_length=5, description="Mandatory detailed loss-prevention resolution note")
    resolvedBy: str = Field(min_length=2, description="Supervisor / officer name")
