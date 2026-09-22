"""Employee Pydantic Schemas"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict


class EmployeeBase(BaseModel):
    name: str
    role: str
    rfidBadgeId: str
    shiftId: Optional[str] = None
    activeFlag: bool = True


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    rfidBadgeId: Optional[str] = None
    shiftId: Optional[str] = None
    activeFlag: Optional[bool] = None


class EmployeeResponse(EmployeeBase):
    employeeId: str
    mismatchCount30d: int = 0
    hasFaceEnrolled: bool = False
    embeddingUpdatedAt: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class EmployeePhotoResponse(BaseModel):
    employeeId: str
    name: str
    hasFaceEnrolled: bool
    embeddingDimension: int = 512
    message: str


class EmployeeHistoryItem(BaseModel):
    eventId: str
    timestamp: str
    laneId: str
    casesDetected: int
    consensusUnits: int
    declaredUnits: Optional[int]
    deltaUnits: Optional[int]
    verdict: str
    severity: str
    notes: Optional[str]


class EmployeeHistoryResponse(BaseModel):
    employee: EmployeeResponse
    totalTraversals: int
    mismatches30d: int
    repeatOffenderRisk: bool
    events: List[EmployeeHistoryItem]


class MaterialMovementItem(BaseModel):
    materialName: str
    skuCode: Optional[str] = None
    quantity: int
    direction: str  # "ENTRY" | "EXIT"


class EmployeeMovementRecord(BaseModel):
    eventId: str
    timestamp: str
    laneId: str
    cameraName: str
    direction: str  # "ENTRY" | "EXIT" | "TRAVERSAL"
    personIdentity: str
    isKnown: bool
    materialsCarried: List[MaterialMovementItem] = []
    casesDetected: int = 0
    unitsDetected: int = 0
    snapshotUrl: Optional[str] = None


class EmployeeMovementSummaryResponse(BaseModel):
    employeeId: str
    name: str
    totalEntries: int
    totalExits: int
    totalTraversals: int
    lastSeenCamera: Optional[str] = None
    lastSeenTimestamp: Optional[str] = None
    materialsHandledSummary: Dict[str, Dict[str, int]] = {}  # materialName -> {"in": int, "out": int, "net": int}
    movements: List[EmployeeMovementRecord] = []


