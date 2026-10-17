"""Live Telemetry KPI Schemas"""

from typing import Dict, Any, Optional
from pydantic import BaseModel


class LiveKPIResponse(BaseModel):
    todayThroughputUnits: int
    openAlertsCount: int
    openAlertsBySeverity: Dict[str, int]
    consensusAccuracyRate: float
    activeLanesCount: int
    totalLanesCount: int
    camerasOnlineCount: int
    camerasTotalCount: int
    startOfDay: Optional[str] = None
