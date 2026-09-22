"""Employee Pydantic Schemas"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List


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

