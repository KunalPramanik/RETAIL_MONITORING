"""Live Telemetry KPI Schemas"""

from pydantic import BaseModel
from typing import Dict, Any


class LiveKPIResponse(BaseModel):
    todayThroughputUnits: int
    openAlertsCount: int
    openAlertsBySeverity: Dict[str, int]
    consensusAccuracyRate: float
    activeLanesCount: int
    totalLanesCount: int
    camerasOnlineCount: int
    camerasTotalCount: int
