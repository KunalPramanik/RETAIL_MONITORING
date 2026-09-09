"""Product Pydantic Schemas"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class ProductBase(BaseModel):
    skuCode: str
    name: str
    category: str
    packSize: int = Field(gt=0, description="Units per sealed case")
    unitPrice: float = Field(ge=0)
    casePrice: float = Field(ge=0)
    reorderThreshold: int = Field(default=0, ge=0)


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


class ProductResponse(ProductBase):
    productId: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

