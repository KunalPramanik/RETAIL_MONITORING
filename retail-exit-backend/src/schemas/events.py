"""Exit Event and Telemetry Schemas"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any


class EventLineItemSchema(BaseModel):
    productId: str
    casesQty: int
    unitsQty: int


class ExitEventBase(BaseModel):
    timestamp: str
    laneId: str
    employeeId: Optional[str] = None
    casesDetected: int
    unitsDetected: int
    visionCount: int
    rfidCount: Optional[int] = None
    weightKg: float
    consensusUnits: int
    invoiceId: Optional[str] = None
    declaredUnits: Optional[int] = None
    deltaUnits: int = 0
    verdict: str  # PASS | MISMATCH
    severity: str # NONE | LOW | MEDIUM | HIGH
    lineItems: List[EventLineItemSchema] = []
    notes: Optional[str] = None


class ExitEventResponse(ExitEventBase):
    eventId: str
    consensusMethod: Optional[str] = "weighted_vote_v2"
    snapshotUrl: Optional[str] = None
    clipUrl: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ExitEventDetailResponse(ExitEventResponse):
    employeeName: Optional[str] = None
    employeeRole: Optional[str] = None
    employeeMatchConfidence: Optional[float] = None
    invoiceNumber: Optional[str] = None
    carrierName: Optional[str] = None
    rawVisionDetections: List[Dict[str, Any]] = []
    rawRfidReads: List[Dict[str, Any]] = []
    rawWeightReadings: List[Dict[str, Any]] = []
    faceMatchDecision: Optional[str] = None


class IngestEventRequest(BaseModel):
    laneId: str
    employeeBadgeId: Optional[str] = None
    probeFaceEmbedding: Optional[List[float]] = None
    lineItems: List[Dict[str, Any]] = []  # items with productId, casesQty, singlesQty
    invoiceId: Optional[str] = None
    declaredUnits: Optional[int] = None
    simulateRfidAttenuation: bool = False
    rawScaleWeightKg: Optional[float] = None


