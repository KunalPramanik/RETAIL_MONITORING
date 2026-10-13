"""Product Pydantic Schemas

Supports dynamic catalog configuration, visual class ID binding,
and PendingProductIdentification review workflows per Section 5.1.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List


class ProductBase(BaseModel):
    skuCode: str
    name: str
    category: str
    packSize: int = Field(gt=0, description="Units per sealed case")
    unitPrice: float = Field(ge=0)
    casePrice: float = Field(ge=0)
    reorderThreshold: int = Field(default=0, ge=0)
    visionClassId: Optional[int] = Field(default=None, description="Links runtime YOLOX/detector class to product")


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    skuCode: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    packSize: Optional[int] = Field(default=None, gt=0)
    unitPrice: Optional[float] = Field(default=None, ge=0)
    casePrice: Optional[float] = Field(default=None, ge=0)
    reorderThreshold: Optional[int] = Field(default=None, ge=0)
    visionClassId: Optional[int] = None


class ProductResponse(ProductBase):
    productId: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PendingProductIdentificationResponse(BaseModel):
    id: str
    cameraId: Optional[str] = None
    visionClassId: int
    detectedLabel: str
    confidence: float
    snapshotUrl: Optional[str] = None
    status: str
    mappedSku: Optional[str] = None
    mappedProductId: Optional[str] = None
    reviewedBy: Optional[str] = None
    reviewedAt: Optional[str] = None
    createdAt: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PendingProductMapRequest(BaseModel):
    action: str = Field(..., description="MAP_TO_SKU, CREATE_NEW_PRODUCT, or IGNORE")
    skuCode: Optional[str] = None
    newProductName: Optional[str] = None
    category: Optional[str] = "GENERAL"
    packSize: Optional[int] = 1
    unitPrice: Optional[float] = 0.0
    casePrice: Optional[float] = 0.0
    operatorId: str = "OPERATOR_ADMIN"
