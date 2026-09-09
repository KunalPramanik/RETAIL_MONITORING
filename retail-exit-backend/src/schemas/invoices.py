"""Invoice and OCR Manifest Schemas"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


class InvoiceLineItemSchema(BaseModel):
    skuCode: str
    description: str
    casesDeclared: int
    unitsPerCase: int
    totalUnits: int
    status: str = "MATCHED"  # MATCHED | DISCREPANCY


class InvoiceBase(BaseModel):
    invoiceNumber: str
    carrierName: str
    storeDestination: str
    ocrConfidence: float
    scanTimestamp: str
    declaredTotalUnits: int
    linkedEventId: Optional[str] = None
    lineItems: List[InvoiceLineItemSchema]
    rawOcrText: Optional[str] = None
    rawFileUrl: Optional[str] = None


class InvoiceCreateSchema(BaseModel):
    invoiceNumber: Optional[str] = None
    carrierName: Optional[str] = None
    storeDestination: Optional[str] = "Store #402 - Metro Central"
    ocrConfidence: Optional[float] = 96.0
    declaredTotalUnits: Optional[int] = None
    linkedEventId: Optional[str] = None
    lineItems: List[InvoiceLineItemSchema] = Field(default_factory=list)
    rawOcrText: Optional[str] = None
    rawFileUrl: Optional[str] = None


class InvoiceResponse(InvoiceBase):
    invoiceId: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

